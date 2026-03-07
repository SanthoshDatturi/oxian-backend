import asyncio
import base64
import json
import logging
from collections.abc import Awaitable, Callable
from datetime import date
from typing import Any, TypeAlias, cast

from langchain_core.messages import (
    AIMessage,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.tools import BaseTool, tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel
from typing_extensions import NotRequired, TypedDict

from app.core.config import settings
from app.integrations.storage import files as storage_files
from app.integrations.weather import open_weather
from app.prompts.prompt_manager import PromptManager
from app.repositories import (
    chat_repository,
    farm_profile_repository,
    message_repository,
    process_repository,
    user_pref_repository,
)
from app.schemas.chat import (
    Chat,
    ChatErrorEvent,
    ChatErrorPayload,
    ChatMode,
    ChatOutboundEnvelope,
    ChatProcessPayload,
    ChatUpsertedEvent,
    ChatUpsertedPayload,
    FarmProfileSavedEvent,
    FarmProfileSavedPayload,
    MessageChunkEvent,
    MessageChunkPayload,
    MessageCompletedEvent,
    MessageCompletedPayload,
    MessageUpsertedEvent,
    MessageUpsertedPayload,
)
from app.schemas.farm_profile import FarmProfile
from app.schemas.message import (
    FarmProfileReferencePart,
    FileMediaKind,
    FilePart,
    LocationPart,
    Message,
    MessageError,
    MessagePart,
    MessageStatus,
    MessageUsage,
    Role,
    TextPart,
)
from app.schemas.process import Process, ProcessError, State
from app.schemas.user_pref import UserPreference

logger = logging.getLogger(__name__)

SendEvent = Callable[[ChatOutboundEnvelope], Awaitable[None]]
ToolCallSpec: TypeAlias = tuple[str, str, dict[str, Any]]
HumanMessageContent: TypeAlias = list[str | dict[str, Any]]


class AttachmentSummary(BaseModel):
    summary: str


class SaveFarmProfileInput(BaseModel):
    profile: FarmProfile


class WeatherCoordinatesInput(BaseModel):
    lat: float
    lon: float


class ChatGraphState(TypedDict):
    chat: Chat
    process: Process
    process_payload: ChatProcessPayload
    user_message: Message
    assistant_message: Message
    history: list[Message]
    user_preference: UserPreference | None
    agent_messages: list[BaseMessage]
    response_text: str
    usage: NotRequired[MessageUsage | None]
    latest_ai_message: NotRequired[AIMessage | None]
    tool_calls: NotRequired[list[ToolCallSpec]]
    farm_profile_reference: NotRequired[FarmProfileReferencePart | None]


class _RunContext(TypedDict):
    send_event: SendEvent
    response_text: str
    usage: MessageUsage | None
    downloaded_files: dict[str, bytes]


@tool("save_farm_profile", args_schema=SaveFarmProfileInput)
async def save_farm_profile_tool(profile: FarmProfile) -> dict[str, str]:
    """Save a validated farm profile once all required details are known."""
    saved = await farm_profile_repository.save(profile)
    return {"farm_id": saved.id, "name": saved.name}


@tool("get_current_weather", args_schema=WeatherCoordinatesInput)
async def get_current_weather_tool(lat: float, lon: float) -> dict[str, Any]:
    """Get current weather for farm advice at the given coordinates."""
    weather = await open_weather.get_current_weather(lat, lon)
    if weather is None:
        raise ValueError("Current weather is unavailable for these coordinates.")
    return weather.model_dump(mode="json", by_alias=True, exclude_none=True)


@tool("get_5_day_3_hour_forecast", args_schema=WeatherCoordinatesInput)
async def get_5_day_3_hour_forecast_tool(lat: float, lon: float) -> dict[str, Any]:
    """Get the 5-day weather forecast in 3-hour intervals for the farm."""
    forecast = await open_weather.get_5_day_3_hour_forecast(lat, lon)
    if forecast is None:
        raise ValueError("Forecast data is unavailable for these coordinates.")
    return forecast.model_dump(mode="json", by_alias=True, exclude_none=True)


@tool("get_air_pollution", args_schema=WeatherCoordinatesInput)
async def get_air_pollution_tool(lat: float, lon: float) -> dict[str, Any]:
    """Get local air quality data that may affect farm operations."""
    pollution = await open_weather.get_air_pollution(lat, lon)
    if pollution is None:
        raise ValueError("Air pollution data is unavailable for these coordinates.")
    return pollution.model_dump(mode="json", by_alias=True, exclude_none=True)


@tool("get_reverse_geocoding", args_schema=WeatherCoordinatesInput)
async def get_reverse_geocoding_tool(lat: float, lon: float) -> dict[str, Any]:
    """Resolve shared coordinates into a place description for weather context."""
    locations = await open_weather.get_reverse_geocoding(lat, lon)
    if not locations:
        raise ValueError("Location details are unavailable for these coordinates.")
    return {
        "results": [
            location.model_dump(mode="json", by_alias=True, exclude_none=True)
            for location in locations
        ]
    }


def _chat_model(*, temperature: float = 0.3, streaming: bool = False):
    return ChatGoogleGenerativeAI(
        model=settings.GEMINI_CHAT_MODEL,
        temperature=temperature,
        streaming=streaming,
    )


def _structured_model(schema: type[Any], *, temperature: float = 0):
    return _chat_model(temperature=temperature).with_structured_output(schema)


def _json_dump(value: Any) -> str:
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json", exclude_none=True)
    return json.dumps(value, ensure_ascii=False, indent=2)


def _today_iso() -> str:
    return date.today().isoformat()


def _message_error(code: str, message: str, details: dict[str, Any] | None = None):
    return MessageError(code=code, message=message, details=details)


def _process_error(code: str, message: str, details: dict[str, Any] | None = None):
    return ProcessError(code=code, message=message, details=details)


def _parse_usage(raw_usage: dict[str, Any] | None) -> MessageUsage | None:
    if not raw_usage:
        return None
    return MessageUsage.model_validate(raw_usage)


def _get_process_payload(process: Process) -> ChatProcessPayload:
    return ChatProcessPayload.model_validate(process.payload or {})


def _farm_profile_schema_json() -> str:
    return _json_dump(FarmProfile.model_json_schema())


def _prompt_context(
    chat: Chat, user_preference: UserPreference | None, continuation_text: str
) -> dict[str, str]:
    response_language_code = ""
    if user_preference and user_preference.language_code:
        response_language_code = user_preference.language_code

    return {
        "current_date": _today_iso(),
        "mode": chat.mode.value,
        "user_id": chat.user_id,
        "response_language_code": response_language_code,
        "chat_title": chat.title,
        "continuation_text": continuation_text,
        "farm_profile_schema_json": _farm_profile_schema_json(),
    }


def _tool_result_content(result: Any) -> str:
    if isinstance(result, str):
        return result
    if hasattr(result, "model_dump"):
        result = result.model_dump(mode="json", by_alias=True, exclude_none=True)
    return _json_dump(result)


def _normalize_tool_calls(ai_message: AIMessage) -> list[ToolCallSpec]:
    normalized_calls: list[ToolCallSpec] = []
    for tool_call in ai_message.tool_calls:
        tool_name = tool_call.get("name")
        tool_call_id = tool_call.get("id")
        tool_args = tool_call.get("args")

        if not isinstance(tool_name, str) or not isinstance(tool_call_id, str):
            logger.warning("Skipping tool call with invalid name or id: %s", tool_call)
            continue
        if not isinstance(tool_args, dict):
            logger.warning("Skipping tool call with invalid args: %s", tool_call)
            continue

        normalized_calls.append((tool_name, tool_call_id, tool_args))
    return normalized_calls


def _get_tools_for_mode(mode: ChatMode) -> list[BaseTool]:
    if mode == ChatMode.GENERAL:
        return [
            get_current_weather_tool,
            get_5_day_3_hour_forecast_tool,
            get_air_pollution_tool,
            get_reverse_geocoding_tool,
        ]
    return [save_farm_profile_tool]


def _tool_map_for_mode(mode: ChatMode) -> dict[str, BaseTool]:
    return {tool.name: tool for tool in _get_tools_for_mode(mode)}


async def _download_file(blob_reference: str, run_context: _RunContext) -> bytes:
    cached = run_context["downloaded_files"].get(blob_reference)
    if cached is not None:
        return cached

    data = await storage_files.download(blob_reference)
    if data is None:
        raise ValueError(f"Unable to download file {blob_reference}")

    run_context["downloaded_files"][blob_reference] = data
    return data


async def _parts_to_human_content(
    parts: list[MessagePart],
    *,
    raw_files: bool,
    run_context: _RunContext,
) -> HumanMessageContent:
    content: HumanMessageContent = []
    for part in parts:
        if isinstance(part, TextPart):
            content.append({"type": "text", "text": part.text})
        elif isinstance(part, LocationPart):
            content.append(
                {
                    "type": "text",
                    "text": (
                        "User shared location coordinates: "
                        f"{part.location.latitude}, {part.location.longitude}."
                    ),
                }
            )
        elif isinstance(part, FilePart):
            if raw_files:
                file_bytes = await _download_file(part.blob_reference, run_context)
                file_base64 = base64.b64encode(file_bytes).decode("utf-8")
                if part.media_kind == FileMediaKind.IMAGE:
                    content.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{part.mime_type};base64,{file_base64}"
                            },
                        }
                    )
                else:
                    content.append(
                        {
                            "type": "file",
                            "source_type": "base64",
                            "mime_type": part.mime_type,
                            "data": file_base64,
                        }
                    )
                if part.caption:
                    content.append(
                        {"type": "text", "text": f"File caption: {part.caption}"}
                    )
            else:
                summary = (
                    part.extracted_text
                    or f"{part.media_kind.value} file: {part.filename}"
                )
                content.append(
                    {"type": "text", "text": f"Attachment summary: {summary}"}
                )

    if not content:
        content.append({"type": "text", "text": ""})
    return content


async def _build_agent_messages(
    history: list[Message],
    *,
    current_user_message: Message,
    assistant_message_id: str,
    system_prompt: str,
    run_context: _RunContext,
) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=system_prompt)]
    for message in history:
        if message.id == assistant_message_id:
            continue
        if message.role == Role.HUMAN:
            content = await _parts_to_human_content(
                message.parts,
                raw_files=message.id == current_user_message.id,
                run_context=run_context,
            )
            messages.append(HumanMessage(content=content))
        elif message.role == Role.AI:
            text = message.text_content()
            if text:
                messages.append(AIMessage(content=text))
    return messages


def _coerce_chunk_text(chunk: Any) -> str:
    text_method = getattr(chunk, "text", None)
    if callable(text_method):
        value = text_method()
        if value:
            return value

    content = getattr(chunk, "content", None)
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        fragments: list[str] = []
        for item in content:
            if isinstance(item, str):
                fragments.append(item)
            elif isinstance(item, dict) and isinstance(item.get("text"), str):
                fragments.append(item["text"])
        return "".join(fragments)
    return ""


async def _emit_chunk(
    *,
    chat_id: str,
    process_id: str,
    message_id: str,
    delta: str,
    run_context: _RunContext,
) -> None:
    if not delta:
        return

    run_context["response_text"] += delta
    await run_context["send_event"](
        MessageChunkEvent(
            payload=MessageChunkPayload(
                chat_id=chat_id,
                process_id=process_id,
                message_id=message_id,
                delta=delta,
            )
        )
    )


async def _emit_text_as_chunks(
    *,
    chat_id: str,
    process_id: str,
    message_id: str,
    text: str,
    run_context: _RunContext,
) -> None:
    emitted = run_context["response_text"]
    if emitted and text.startswith(emitted):
        text = text[len(emitted) :]
    if not text:
        return

    buffer = ""
    for char in text:
        buffer += char
        if char in {" ", "\n", ".", ",", "?", "!"}:
            await _emit_chunk(
                chat_id=chat_id,
                process_id=process_id,
                message_id=message_id,
                delta=buffer,
                run_context=run_context,
            )
            buffer = ""

    if buffer:
        await _emit_chunk(
            chat_id=chat_id,
            process_id=process_id,
            message_id=message_id,
            delta=buffer,
            run_context=run_context,
        )


async def _set_process_state(
    process: Process,
    *,
    status: State | None = None,
    payload: ChatProcessPayload | None = None,
    error: ProcessError | None = None,
) -> Process:
    updates: dict[str, Any] = {}
    if status is not None:
        updates["status"] = status
    if payload is not None:
        updates["payload"] = payload.model_dump(mode="json", exclude_none=True)
    if error is not None or (status is not None and status == State.RUNNING):
        updates["error"] = error
    process = process.model_copy(update=updates)
    return await process_repository.save(process)


async def _load_graph_context(
    user_id: str,
    payload: ChatProcessPayload,
) -> tuple[Chat, Message, Message, list[Message]]:
    chat = await chat_repository.get_by_id(payload.chat_id, user_id=user_id)
    if chat is None:
        raise ValueError("Chat not found for process.")

    user_message = await message_repository.get_by_id(
        payload.user_message_id, chat_id=chat.id
    )
    assistant_message = await message_repository.get_by_id(
        payload.assistant_message_id, chat_id=chat.id
    )
    if user_message is None or assistant_message is None:
        raise ValueError("Process message references are invalid.")

    history = await message_repository.list_latest_by_chat(
        chat.id, settings.CHAT_HISTORY_LIMIT
    )
    return chat, user_message, assistant_message, history


async def _summarize_attachments(
    state: ChatGraphState,
    run_context: _RunContext,
) -> ChatGraphState:
    updated_parts: list[MessagePart] = []
    changed = False

    for part in state["user_message"].parts:
        if isinstance(part, FilePart) and not part.extracted_text:
            summary_text = None
            try:
                model = _structured_model(AttachmentSummary)
                file_content = await _parts_to_human_content(
                    [part], raw_files=True, run_context=run_context
                )
                summary = await model.ainvoke(
                    [
                        SystemMessage(
                            content=(
                                "Summarize the attached farming file for future chat history. "
                                "Keep it short, factual, and useful for later turns."
                            )
                        ),
                        HumanMessage(
                            content=[
                                {
                                    "type": "text",
                                    "text": "Summarize the attached file.",
                                },
                                *file_content,
                            ]
                        ),
                    ]
                )
                summary_text = summary.summary.strip()
            except Exception:
                logger.exception(
                    "Attachment summarization failed for chat %s message %s",
                    state["chat"].id,
                    state["user_message"].id,
                )
                summary_text = (
                    part.caption or f"{part.media_kind.value} file: {part.filename}"
                )

            updated_parts.append(
                part.model_copy(update={"extracted_text": summary_text})
            )
            changed = True
        else:
            updated_parts.append(part)

    if changed:
        state["user_message"] = state["user_message"].model_copy(
            update={"parts": updated_parts}
        )
        state["user_message"] = await message_repository.save(state["user_message"])
        state["history"] = [
            state["user_message"] if message.id == state["user_message"].id else message
            for message in state["history"]
        ]

    return state


async def _prepare_agent_messages(
    state: ChatGraphState,
    run_context: _RunContext,
) -> ChatGraphState:
    system_prompt = PromptManager.get_prompt(
        "chat",
        **_prompt_context(
            state["chat"],
            state["user_preference"],
            state["process_payload"].partial_response,
        ),
    )
    state["agent_messages"] = await _build_agent_messages(
        state["history"],
        current_user_message=state["user_message"],
        assistant_message_id=state["assistant_message"].id,
        system_prompt=system_prompt,
        run_context=run_context,
    )
    return state


async def _agent_turn(
    state: ChatGraphState,
    run_context: _RunContext,
) -> ChatGraphState:
    model = _chat_model().bind_tools(_get_tools_for_mode(state["chat"].mode))
    ai_message = await model.ainvoke(state["agent_messages"])
    tool_calls = _normalize_tool_calls(ai_message)

    state["latest_ai_message"] = ai_message
    state["tool_calls"] = tool_calls
    state["agent_messages"] = [*state["agent_messages"], ai_message]
    usage = _parse_usage(getattr(ai_message, "usage_metadata", None))
    if usage is not None:
        state["usage"] = usage

    if not tool_calls:
        text = _coerce_chunk_text(ai_message).strip()
        if text:
            await _emit_text_as_chunks(
                chat_id=state["chat"].id,
                process_id=state["process"].id,
                message_id=state["assistant_message"].id,
                text=text,
                run_context=run_context,
            )
        state["response_text"] = run_context["response_text"]

    return state


async def _handle_tool_calls(
    state: ChatGraphState,
    _: _RunContext,
) -> ChatGraphState:
    tool_calls = state.get("tool_calls") or []
    if not tool_calls:
        return state

    tool_map = _tool_map_for_mode(state["chat"].mode)
    payload = state["process_payload"]
    tool_messages: list[ToolMessage] = []

    for tool_name, tool_call_id, tool_args in tool_calls:
        tool_instance = tool_map.get(tool_name)

        if tool_instance is None:
            tool_messages.append(
                ToolMessage(
                    content=f"Unknown tool requested: {tool_name}",
                    tool_call_id=tool_call_id,
                    name=tool_name,
                    status="error",
                )
            )
            continue

        try:
            if (
                tool_name == save_farm_profile_tool.name
                and payload.saved_farm_id
                and payload.saved_farm_name
            ):
                result: Any = {
                    "farm_id": payload.saved_farm_id,
                    "name": payload.saved_farm_name,
                }
            else:
                result = await tool_instance.ainvoke(tool_args)

            if tool_name == save_farm_profile_tool.name:
                farm_id = result["farm_id"]
                farm_name = result["name"]
                payload = payload.model_copy(
                    update={"saved_farm_id": farm_id, "saved_farm_name": farm_name}
                )
                state["farm_profile_reference"] = FarmProfileReferencePart(
                    farm_id=farm_id,
                    name=farm_name,
                )

            tool_messages.append(
                ToolMessage(
                    content=_tool_result_content(result),
                    tool_call_id=tool_call_id,
                    name=tool_name,
                    status="success",
                )
            )
        except Exception as exc:
            logger.exception(
                "Tool %s failed for chat %s process %s",
                tool_name,
                state["chat"].id,
                state["process"].id,
            )
            tool_messages.append(
                ToolMessage(
                    content=str(exc),
                    tool_call_id=tool_call_id,
                    name=tool_name,
                    status="error",
                )
            )

    state["agent_messages"] = [*state["agent_messages"], *tool_messages]
    state["process_payload"] = payload
    state["process"] = await _set_process_state(state["process"], payload=payload)
    return state


def _build_graph(run_context: _RunContext):
    graph = StateGraph(cast(Any, ChatGraphState))

    async def summarize_attachments_node(state: ChatGraphState):
        return await _summarize_attachments(state, run_context)

    async def prepare_agent_messages_node(state: ChatGraphState):
        return await _prepare_agent_messages(state, run_context)

    async def agent_turn_node(state: ChatGraphState):
        return await _agent_turn(state, run_context)

    async def handle_tool_calls_node(state: ChatGraphState):
        return await _handle_tool_calls(state, run_context)

    def route_after_agent(state: ChatGraphState):
        if state.get("tool_calls"):
            return "handle_tool_calls"
        return END

    graph.add_node("summarize_attachments", summarize_attachments_node)
    graph.add_node("prepare_agent_messages", prepare_agent_messages_node)
    graph.add_node("agent_turn", agent_turn_node)
    graph.add_node("handle_tool_calls", handle_tool_calls_node)

    graph.add_edge(START, "summarize_attachments")
    graph.add_edge("summarize_attachments", "prepare_agent_messages")
    graph.add_edge("prepare_agent_messages", "agent_turn")
    graph.add_conditional_edges(
        "agent_turn",
        route_after_agent,
        {"handle_tool_calls": "handle_tool_calls", END: END},
    )
    graph.add_edge("handle_tool_calls", "agent_turn")
    return graph.compile()


async def _finalize_success(
    state: ChatGraphState,
    run_context: _RunContext,
) -> None:
    chat = state["chat"].model_copy(
        update={
            "last_message_id": state["assistant_message"].id,
            "last_process_id": state["process"].id,
        }
    )
    process_payload = state["process_payload"].model_copy(
        update={"partial_response": run_context["response_text"]}
    )
    process = await _set_process_state(
        state["process"],
        status=State.COMPLETED,
        payload=process_payload,
    )

    assistant_parts: list[TextPart | FarmProfileReferencePart] = []
    if run_context["response_text"]:
        assistant_parts.append(TextPart(text=run_context["response_text"]))
    farm_profile_reference = state.get("farm_profile_reference")
    if farm_profile_reference is not None:
        assistant_parts.append(farm_profile_reference)

    assistant_message = state["assistant_message"].model_copy(
        update={
            "status": MessageStatus.COMPLETE,
            "parts": assistant_parts,
            "usage": state.get("usage"),
            "error": None,
        }
    )
    assistant_message = await message_repository.save(assistant_message)
    await message_repository.save(state["user_message"])
    chat = await chat_repository.save(chat)

    await run_context["send_event"](
        ChatUpsertedEvent(payload=ChatUpsertedPayload(chat=chat))
    )
    await run_context["send_event"](
        MessageCompletedEvent(
            payload=MessageCompletedPayload(
                chat_id=chat.id,
                process_id=process.id,
                message=assistant_message,
            )
        )
    )
    if farm_profile_reference is not None:
        await run_context["send_event"](
            FarmProfileSavedEvent(
                payload=FarmProfileSavedPayload(
                    chat_id=chat.id,
                    process_id=process.id,
                    message_id=assistant_message.id,
                    farm_id=farm_profile_reference.farm_id,
                    name=farm_profile_reference.name,
                )
            )
        )


async def _finalize_interrupted(
    *,
    chat: Chat,
    process: Process,
    process_payload: ChatProcessPayload,
    user_message: Message,
    assistant_message: Message,
    send_event: SendEvent,
    status: State,
    code: str,
    message: str,
    partial_response: str,
) -> None:
    persisted_process = await process_repository.get_by_id(process.id)
    current_process = persisted_process or process
    current_payload = (
        _get_process_payload(current_process)
        if current_process.payload
        else process_payload
    )
    updated_payload = current_payload.model_copy(
        update={"partial_response": partial_response}
    )
    updated_message = assistant_message.model_copy(
        update={
            "status": MessageStatus.STOPPED
            if status == State.STOPPED
            else MessageStatus.ERROR,
            "parts": [TextPart(text=partial_response)] if partial_response else [],
            "error": _message_error(code, message),
        }
    )
    await message_repository.save(user_message)
    updated_message = await message_repository.save(updated_message)
    await _set_process_state(
        current_process,
        status=status,
        payload=updated_payload,
        error=_process_error(code, message),
    )
    await send_event(
        MessageUpsertedEvent(
            payload=MessageUpsertedPayload(
                chat_id=updated_message.chat_id, message=updated_message
            )
        )
    )
    if status == State.FAILED:
        await send_event(
            ChatErrorEvent(
                payload=ChatErrorPayload(
                    code=code,
                    message=message,
                    chat_id=chat.id,
                    process_id=process.id,
                    message_id=updated_message.id,
                )
            )
        )
    logger.warning("Chat process %s ended with status=%s", process.id, status)


async def chat(user_id: str, process_id: str, send_event: SendEvent):
    process = await process_repository.get_by_id(process_id)
    if process is None:
        raise ValueError("Process not found.")

    process_payload = _get_process_payload(process)
    process = await _set_process_state(
        process,
        status=State.RUNNING,
        payload=process_payload,
        error=None,
    )

    try:
        (
            chat_record,
            user_message,
            assistant_message,
            history,
        ) = await _load_graph_context(user_id, process_payload)
    except Exception as exc:
        logger.exception("Failed to load chat context for process %s", process_id)
        await _set_process_state(
            process,
            status=State.FAILED,
            payload=process_payload,
            error=_process_error("chat_context_failed", str(exc)),
        )
        await send_event(
            ChatErrorEvent(
                payload=ChatErrorPayload(
                    code="chat_context_failed",
                    message=str(exc),
                    chat_id=process_payload.chat_id,
                    process_id=process.id,
                    message_id=process_payload.assistant_message_id,
                )
            )
        )
        raise

    run_context: _RunContext = {
        "send_event": send_event,
        "response_text": process_payload.partial_response,
        "usage": None,
        "downloaded_files": {},
    }

    assistant_message = assistant_message.model_copy(
        update={"status": MessageStatus.STREAMING, "error": None}
    )
    assistant_message = await message_repository.save(assistant_message)
    await send_event(
        MessageUpsertedEvent(
            payload=MessageUpsertedPayload(
                chat_id=chat_record.id, message=assistant_message
            )
        )
    )
    user_preference = await user_pref_repository.get_by_user_id(chat_record.user_id)

    initial_state: ChatGraphState = {
        "chat": chat_record,
        "process": process,
        "process_payload": process_payload,
        "user_message": user_message,
        "assistant_message": assistant_message,
        "history": history,
        "user_preference": user_preference,
        "agent_messages": [],
        "response_text": run_context["response_text"],
        "usage": None,
        "latest_ai_message": None,
        "tool_calls": [],
        "farm_profile_reference": (
            FarmProfileReferencePart(
                farm_id=process_payload.saved_farm_id,
                name=process_payload.saved_farm_name,
            )
            if process_payload.saved_farm_id and process_payload.saved_farm_name
            else None
        ),
    }

    graph = _build_graph(run_context)
    try:
        final_state = await graph.ainvoke(initial_state, config={"recursion_limit": 10})
        await _finalize_success(final_state, run_context)
    except asyncio.CancelledError:
        await _finalize_interrupted(
            chat=chat_record,
            process=process,
            process_payload=process_payload,
            user_message=user_message,
            assistant_message=assistant_message,
            send_event=send_event,
            status=State.STOPPED,
            code="stopped",
            message="Response generation was stopped by the user.",
            partial_response=run_context["response_text"],
        )
        raise
    except Exception as exc:
        logger.exception("Chat process %s failed", process_id)
        await _finalize_interrupted(
            chat=chat_record,
            process=process,
            process_payload=process_payload,
            user_message=user_message,
            assistant_message=assistant_message,
            send_event=send_event,
            status=State.FAILED,
            code="chat_failed",
            message=str(exc),
            partial_response=run_context["response_text"],
        )
        raise
