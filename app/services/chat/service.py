import asyncio
import base64
import json
import logging
from dataclasses import dataclass
from datetime import date
from typing import Any, cast

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.process_manager import process_manager
from app.core.simple_queue import enqueue
from app.integrations.storage.base import StorageEntity
from app.integrations.weather import open_weather
from app.prompts.prompt_manager import PromptManager
from app.repositories import (
    chat_repository,
    farm_profile_repository,
    message_repository,
    process_repository,
    user_pref_repository,
)
from app.schemas.chat import Chat, ChatMode
from app.schemas.farm_profile import (
    Area,
    FarmProfile,
    IrrigationSystem,
    Location,
    PreviousCrops,
    SoilTestProperties,
    SoilType,
    WaterSource,
)
from app.schemas.message import (
    ChatMessageInput,
    FileMediaKind,
    FilePart,
    FarmProfileReferencePart,
    IncomingMessagePart,
    LocationPart,
    Message,
    NewChatMessageInput,
    PartType,
    Role,
    TextPart,
)
from app.schemas.process import Process, ProcessError, State
from app.services.storage import service as storage_service

logger = logging.getLogger(__name__)


@dataclass
class ChatStreamSession:
    meta: dict[str, Any]
    events: asyncio.Queue[dict[str, Any] | None]


class FarmProfileToolPayload(BaseModel):
    name: str
    location: Location
    soil_type: SoilType
    total_area: Area
    cultivated_area: Area
    water_source: WaterSource
    irrigation_system: IrrigationSystem | None = None
    crops: list[PreviousCrops] | None = None
    soil_test_properties: SoilTestProperties | None = None


class SaveFarmProfileInput(BaseModel):
    profile: FarmProfileToolPayload


def _sse_event(event: str, data: dict[str, Any]) -> dict[str, Any]:
    return {"event": event, "data": data}


def _infer_media_kind(mime_type: str) -> FileMediaKind:
    if mime_type.startswith("image/"):
        return FileMediaKind.IMAGE
    if mime_type.startswith("audio/"):
        return FileMediaKind.AUDIO
    return FileMediaKind.DOCUMENT


def _generate_backend_title(parts: list[IncomingMessagePart]) -> str:
    for part in parts:
        if isinstance(part, TextPart):
            text = " ".join(part.text.split())
            if text:
                return text[:70]
    has_file = any(isinstance(part, FilePart) for part in parts)
    has_location = any(isinstance(part, LocationPart) for part in parts)
    if has_file and has_location:
        return "Farm query with files and location"
    if has_file:
        return "Farm query with attachments"
    if has_location:
        return "Farm query for location"
    return "Farming chat"


def _serialize_message(message: Message) -> dict[str, Any]:
    return message.model_dump(by_alias=True, mode="json")


def _format_part_for_history(part: Any) -> str:
    if getattr(part, "type", None) == PartType.TEXT:
        return part.text
    if getattr(part, "type", None) == PartType.LOCATION:
        label = f" ({part.label})" if part.label else ""
        return (
            f"Location{label}: lat={part.location.latitude}, "
            f"lon={part.location.longitude}"
        )
    if getattr(part, "type", None) == PartType.FILE:
        text_bits: list[str] = [f"Attachment file_id: {part.file_id}"]
        if part.media_kind:
            text_bits.append(f"media_kind: {part.media_kind}")
        if part.caption:
            text_bits.append(f"caption: {part.caption}")
        return " | ".join(text_bits)
    if getattr(part, "type", None) == PartType.FARM_PROFILE_REFERENCE:
        return f"Farm reference: {part.name} ({part.farm_id})"
    return ""


def _to_history_message(message: Message) -> BaseMessage:
    text = "\n".join(
        part_text
        for part_text in (_format_part_for_history(part) for part in message.parts)
        if part_text
    )
    if message.role == Role.HUMAN:
        return HumanMessage(content=text or "(no text)")
    return AIMessage(content=text or "(no text)")


def _extract_chunk_text(chunk: Any) -> str:
    content = getattr(chunk, "content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        texts: list[str] = []
        for item in content:
            if isinstance(item, str):
                texts.append(item)
            elif isinstance(item, dict) and item.get("type") == "text":
                texts.append(item.get("text", ""))
        return "".join(texts)
    return ""


def _deep_merge(base: dict[str, Any], patch: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in patch.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


async def _build_user_message(
    *,
    user_id: str,
    chat_id: str,
    parts: list[IncomingMessagePart],
) -> tuple[Message, list[dict[str, Any]]]:
    incoming_file_ids = [
        part.file_id for part in parts if isinstance(part, FilePart)
    ]
    file_lookup: dict[str, tuple[str, str]] = {}
    file_blocks: dict[str, dict[str, Any]] = {}

    if incoming_file_ids:
        activated_files = await storage_service.activate_files(
            file_ids=incoming_file_ids,
            entity=StorageEntity.CHAT,
            entity_id=chat_id,
            user_id=user_id,
        )
        for stored_file in activated_files:
            data_file, data_bytes = await storage_service.download_file(
                file_id=stored_file.id,
                user_id=user_id,
            )
            file_lookup[stored_file.id] = (data_file.filename, data_file.content_type)
            file_blocks[stored_file.id] = {
                "type": "file",
                "source_type": "base64",
                "mime_type": data_file.content_type,
                "data": base64.b64encode(data_bytes).decode("utf-8"),
            }

    message_parts: list[Any] = []
    model_content: list[dict[str, Any]] = []

    for part in parts:
        if isinstance(part, TextPart):
            message_parts.append(TextPart(text=part.text))
            model_content.append({"type": "text", "text": part.text})
            continue

        if isinstance(part, LocationPart):
            message_parts.append(LocationPart(location=part.location, label=part.label))
            location_line = (
                f"Farmer location: lat={part.location.latitude}, "
                f"lon={part.location.longitude}"
            )
            if part.label:
                location_line += f", label={part.label}"
            model_content.append({"type": "text", "text": location_line})
            continue

        if isinstance(part, FilePart):
            filename, mime_type = file_lookup.get(
                part.file_id, ("uploaded-file", "application/octet-stream")
            )
            media_kind = part.media_kind or _infer_media_kind(mime_type)
            message_parts.append(
                FilePart(
                    file_id=part.file_id,
                    media_kind=media_kind,
                    caption=part.caption,
                )
            )
            model_content.append(
                {"type": "text", "text": f"Attachment: {filename} ({mime_type})"}
            )
            if part.caption:
                model_content.append(
                    {"type": "text", "text": f"Caption: {part.caption}"}
                )
            media_block = file_blocks.get(part.file_id)
            if media_block:
                model_content.append(media_block)

    user_message = Message(
        chat_id=chat_id,
        user_id=user_id,
        role=Role.HUMAN,
        parts=message_parts,
    )
    user_message = await message_repository.create(user_message)
    return user_message, model_content


async def _build_prompt(
    *,
    mode: ChatMode,
    user_id: str,
    chat_title: str,
) -> str:
    preference = await user_pref_repository.get_by_user_id(user_id)
    response_language_code = preference.language_code if preference else None
    return PromptManager.get_prompt(
        "chat",
        current_date=str(date.today()),
        mode=mode.value,
        user_id=user_id,
        response_language_code=response_language_code,
        chat_title=chat_title,
        continuation_text=None,
        farm_profile_schema_json=json.dumps(FarmProfile.model_json_schema(), indent=2),
    )


async def _run_turn(
    *,
    process: Process,
    chat: Chat,
    user_message: Message,
    assistant_message: Message,
    model_content: list[dict[str, Any]],
    events: asyncio.Queue[dict[str, Any] | None],
) -> None:
    process_task = asyncio.current_task()
    if process_task is None:
        raise RuntimeError("No running task for process execution.")
    process_manager.register(process.id, process_task)

    process.status = State.RUNNING
    await process_repository.save(process)

    collected_text = ""
    saved_farm_profile_part: FarmProfileReferencePart | None = None
    active_chat = chat

    try:
        history = await message_repository.list_latest_by_chat(
            chat_id=chat.id,
            limit=settings.CHAT_HISTORY_LIMIT,
        )
        history_messages = [_to_history_message(msg) for msg in history[:-1]]
        system_prompt = await _build_prompt(
            mode=chat.mode,
            user_id=chat.user_id,
            chat_title=chat.title,
        )

        @tool(args_schema=SaveFarmProfileInput)
        async def save_farm_profile(profile: FarmProfileToolPayload) -> dict[str, str]:
            """Save a complete farm profile. Call only when all required FarmProfile fields are available."""

            nonlocal saved_farm_profile_part
            nonlocal active_chat

            incoming_profile = profile.model_dump(mode="json")

            if active_chat.farm_profile_id:
                existing = await farm_profile_repository.get_by_id(
                    active_chat.farm_profile_id,
                    user_id=active_chat.user_id,
                )
                if existing is None:
                    raise ValueError("Linked farm profile was not found.")
                merged = _deep_merge(
                    existing.model_dump(mode="json", by_alias=False),
                    incoming_profile,
                )
                merged["id"] = existing.id
                merged["user_id"] = active_chat.user_id
                farm_profile = FarmProfile.model_validate(merged)
                saved = await farm_profile_repository.save(farm_profile)
            else:
                merged = dict(incoming_profile)
                merged["user_id"] = active_chat.user_id
                farm_profile = FarmProfile.model_validate(merged)
                saved = await farm_profile_repository.create(farm_profile)
                active_chat = active_chat.model_copy(
                    update={"farm_profile_id": saved.id}
                )
                await chat_repository.save(active_chat)

            saved_farm_profile_part = FarmProfileReferencePart(
                farm_id=saved.id,
                name=saved.name,
            )
            return {"farm_id": saved.id, "name": saved.name}

        @tool
        async def get_current_weather(lat: float, lon: float) -> dict[str, Any]:
            """Get current weather for latitude and longitude."""
            data = await open_weather.get_current_weather(lat=lat, lon=lon)
            return (
                {"available": False} if data is None else data.model_dump(mode="json")
            )

        @tool
        async def get_5_day_3_hour_forecast(lat: float, lon: float) -> dict[str, Any]:
            """Get 5 day forecast in 3 hour steps for latitude and longitude."""
            data = await open_weather.get_5_day_3_hour_forecast(lat=lat, lon=lon)
            return (
                {"available": False} if data is None else data.model_dump(mode="json")
            )

        @tool
        async def get_air_pollution(lat: float, lon: float) -> dict[str, Any]:
            """Get air pollution metrics for latitude and longitude."""
            data = await open_weather.get_air_pollution(lat=lat, lon=lon)
            return (
                {"available": False} if data is None else data.model_dump(mode="json")
            )

        @tool
        async def get_reverse_geocoding(lat: float, lon: float) -> dict[str, Any]:
            """Get reverse geocoding details for latitude and longitude."""
            data = await open_weather.get_reverse_geocoding(lat=lat, lon=lon)
            if data is None:
                return {"available": False}
            return {
                "available": True,
                "results": [item.model_dump(mode="json") for item in data],
            }

        agent = create_agent(
            model=ChatGoogleGenerativeAI(
                model=settings.GEMINI_CHAT_MODEL,
                streaming=True,
                temperature=0.3,
            ),
            tools=[
                save_farm_profile,
                get_current_weather,
                get_5_day_3_hour_forecast,
                get_air_pollution,
                get_reverse_geocoding,
            ],
            system_prompt=system_prompt,
        )

        current_human_message = HumanMessage(
            content=cast(list[str | dict[str, Any]], model_content)
        )
        agent_input = {"messages": [*history_messages, current_human_message]}
        async for event in agent.astream_events(agent_input, version="v2"):
            if event.get("event") != "on_chat_model_stream":
                continue
            chunk = event.get("data", {}).get("chunk")
            if not chunk:
                continue
            delta = _extract_chunk_text(chunk)
            if not delta:
                continue
            collected_text += delta
            await events.put(_sse_event("delta", {"text": delta}))

        if not collected_text.strip():
            result = await agent.ainvoke(agent_input)
            messages = result.get("messages", []) if isinstance(result, dict) else []
            for message in reversed(messages):
                if isinstance(message, AIMessage):
                    collected_text = _extract_chunk_text(message) or str(
                        message.content
                    )
                    break
            if not collected_text.strip():
                raise RuntimeError("Assistant did not produce text output.")

        assistant_parts: list[Any] = [TextPart(text=collected_text)]
        if saved_farm_profile_part is not None:
            assistant_parts.append(saved_farm_profile_part)

        assistant_message = assistant_message.model_copy(
            update={
                "parts": assistant_parts,
                "error": None,
            }
        )
        assistant_message = await message_repository.save(assistant_message)

        try:
            await process_repository.delete(process.id)
        except Exception:
            logger.exception(
                "Failed to delete process after completion process_id=%s", process.id
            )

        message_event_data: dict[str, Any] = {
            "message": _serialize_message(assistant_message)
        }
        if saved_farm_profile_part is not None:
            message_event_data["farm_profile"] = saved_farm_profile_part.model_dump(
                mode="json"
            )
        await events.put(_sse_event("message", message_event_data))
        await events.put(_sse_event("done", {}))
    except ValidationError as exc:
        logger.exception(
            "Validation error while processing chat turn process_id=%s", process.id
        )
        assistant_message = assistant_message.model_copy(
            update={
                "error": {
                    "code": "validation_error",
                    "message": "Failed to validate generated response.",
                    "details": {"errors": exc.errors()},
                },
                "parts": [],
            }
        )
        await message_repository.save(assistant_message)
        process.status = State.FAILED
        process.error = ProcessError(
            code="validation_error",
            message="Validation failed during agent execution.",
        )
        await process_repository.save(process)
        await events.put(
            _sse_event(
                "error",
                {
                    "code": "validation_error",
                    "message": "Validation failed during processing.",
                },
            )
        )
    except asyncio.CancelledError:
        logger.info("Chat turn was cancelled process_id=%s", process.id)
        await events.put(_sse_event("done", {}))
        try:
            await process_repository.delete(process.id)
        except Exception:
            logger.exception(
                "Failed to delete process after cancellation process_id=%s", process.id
            )
    except Exception:
        logger.exception("Failed to process chat turn process_id=%s", process.id)
        assistant_message = assistant_message.model_copy(
            update={
                "error": {
                    "code": "agent_error",
                    "message": "Failed to process message.",
                },
                "parts": [],
            }
        )
        await message_repository.save(assistant_message)
        process.status = State.FAILED
        process.error = ProcessError(
            code="agent_error",
            message="Failed to process chat turn.",
        )
        await process_repository.save(process)
        await events.put(
            _sse_event(
                "error",
                {
                    "code": "agent_error",
                    "message": "Unable to complete the request right now.",
                },
            )
        )
    finally:
        process_manager.remove(process.id)
        await events.put(None)


async def _enqueue_turn(
    *,
    process: Process,
    chat: Chat,
    user_message: Message,
    assistant_message: Message,
    model_content: list[dict[str, Any]],
    events: asyncio.Queue[dict[str, Any] | None],
) -> None:
    async def _job() -> None:
        await _run_turn(
            process=process,
            chat=chat,
            user_message=user_message,
            assistant_message=assistant_message,
            model_content=model_content,
            events=events,
        )

    await enqueue(_job)


async def start_new_chat_turn(
    *,
    user_id: str,
    payload: NewChatMessageInput,
) -> ChatStreamSession:
    chat = Chat(
        user_id=user_id,
        mode=payload.mode,
        farm_profile_id=payload.farm_profile_id,
        title=_generate_backend_title(payload.parts),
    )
    chat = await chat_repository.create(chat)

    user_message, model_content = await _build_user_message(
        user_id=user_id,
        chat_id=chat.id,
        parts=payload.parts,
    )

    assistant_message = Message(
        chat_id=chat.id,
        user_id=user_id,
        role=Role.AI,
        parts=[],
    )
    assistant_message = await message_repository.create(assistant_message)

    process = Process(
        status=State.PENDING,
    )
    process = await process_repository.create(process)
    chat = chat.model_copy(update={"process_id": process.id})
    chat = await chat_repository.save(chat)

    events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    await _enqueue_turn(
        process=process,
        chat=chat,
        user_message=user_message,
        assistant_message=assistant_message,
        model_content=model_content,
        events=events,
    )
    return ChatStreamSession(
        meta={
            "chat_id": chat.id,
            "mode": chat.mode.value,
            "process_id": process.id,
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
            "farm_profile_id": chat.farm_profile_id,
        },
        events=events,
    )


async def start_existing_chat_turn(
    *,
    user_id: str,
    chat_id: str,
    payload: ChatMessageInput,
) -> ChatStreamSession:
    chat = await chat_repository.get_by_id(chat_id, user_id=user_id)
    if chat is None:
        raise ValueError("Chat not found.")

    user_message, model_content = await _build_user_message(
        user_id=user_id,
        chat_id=chat.id,
        parts=payload.parts,
    )

    assistant_message = Message(
        chat_id=chat.id,
        user_id=user_id,
        role=Role.AI,
        parts=[],
    )
    assistant_message = await message_repository.create(assistant_message)

    process = Process(
        status=State.PENDING,
    )
    process = await process_repository.create(process)
    chat = chat.model_copy(update={"process_id": process.id})
    chat = await chat_repository.save(chat)

    events: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()
    await _enqueue_turn(
        process=process,
        chat=chat,
        user_message=user_message,
        assistant_message=assistant_message,
        model_content=model_content,
        events=events,
    )
    return ChatStreamSession(
        meta={
            "chat_id": chat.id,
            "mode": chat.mode.value,
            "process_id": process.id,
            "user_message_id": user_message.id,
            "assistant_message_id": assistant_message.id,
            "farm_profile_id": chat.farm_profile_id,
        },
        events=events,
    )


async def stop_chat_turn(*, user_id: str, chat_id: str) -> bool:
    chat = await chat_repository.get_by_id(chat_id, user_id=user_id)
    if chat is None:
        raise ValueError("Chat not found.")
    if not chat.process_id:
        return False

    cancelled = process_manager.cancel(chat.process_id)
    if not cancelled:
        return False

    try:
        await process_repository.delete(chat.process_id)
    except Exception:
        logger.exception(
            "Failed to delete process after stop request process_id=%s chat_id=%s",
            chat.process_id,
            chat_id,
        )
    return True
