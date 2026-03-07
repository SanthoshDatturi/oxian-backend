import asyncio
import logging

from pydantic import BaseModel, TypeAdapter

from app.api.websocket.connection_manager import manager as connection_manager
from app.core.process_manager import process_manager
from app.core.simple_queue import enqueue
from app.repositories import chat_repository, message_repository, process_repository
from app.schemas.chat import (
    Chat,
    ChatErrorEvent,
    ChatErrorPayload,
    ChatMode,
    ChatProcessPayload,
    CreateChatRequest,
    ChatResumeRequest,
    ChatRetryRequest,
    ChatStatus,
    ChatStopRequest,
    ChatUpsertedEvent,
    ChatUpsertedPayload,
    MessageUpsertedEvent,
    MessageUpsertedPayload,
    NewChatOrMessageRequest,
    NewMessageRequest,
)
from app.schemas.generic_types import Event, Service, WebSocketOutboundMessage
from app.schemas.message import Message, MessageStatus, Role
from app.schemas.process import Process, ProcessError, State
from app.services.chat import service

logger = logging.getLogger(__name__)


async def send_data(user_id: str, data: BaseModel):
    await connection_manager.send_to_user(
        user_id,
        WebSocketOutboundMessage(
            service=Service.CHAT,
            data=data.model_dump(mode="json", exclude_none=True),
        ),
    )


async def _send_error(
    user_id: str,
    *,
    code: str,
    message: str,
    chat_id: str | None = None,
    process_id: str | None = None,
    message_id: str | None = None,
) -> None:
    await send_data(
        user_id,
        ChatErrorEvent(
            payload=ChatErrorPayload(
                code=code,
                message=message,
                chat_id=chat_id,
                process_id=process_id,
                message_id=message_id,
            )
        ),
    )


def _default_title(mode: ChatMode, request: CreateChatRequest) -> str:
    for part in request.parts:
        text = getattr(part, "text", None)
        if text:
            return text[:80]
    return "Farm survey" if mode == ChatMode.FARM_SURVEY else "Farming chat"


async def _run_process(user_id: str, process_id: str):
    task = asyncio.current_task()
    if task is None:
        raise RuntimeError("Missing asyncio task while running process.")

    process_manager.register(process_id, task)
    try:
        await service.chat(
            user_id=user_id,
            process_id=process_id,
            send_event=lambda event: send_data(user_id, event),
        )
    finally:
        process_manager.remove(process_id)


async def _queue_process(user_id: str, process_id: str):
    await enqueue(lambda: _run_process(user_id, process_id))


async def _load_chat_for_start(
    user_id: str, request: NewChatOrMessageRequest
) -> tuple[Chat, bool]:
    if isinstance(request, NewMessageRequest):
        chat = await chat_repository.get_by_id(request.chat_id, user_id=user_id)
        if chat is None:
            raise ValueError("Chat not found.")
        return chat, False

    if request.mode is None:
        raise ValueError("mode is required when creating a new chat.")

    chat = Chat(
        user_id=user_id,
        mode=request.mode,
        title=_default_title(request.mode, request),
        status=ChatStatus.ACTIVE,
    )
    return await chat_repository.create(chat), True


async def _ensure_chat_can_start(chat: Chat):
    if not chat.last_process_id:
        return

    latest_process = await process_repository.get_by_id(chat.last_process_id)
    if latest_process is None:
        return

    if latest_process.status in {State.PENDING, State.RUNNING}:
        raise ValueError("A process is already active for this chat.")

    if latest_process.status == State.COMPLETED:
        await process_repository.delete(latest_process.id)


async def _create_turn_records(
    *,
    user_id: str,
    chat: Chat,
    parts,
    reuse_user_message: Message | None = None,
    retry_of_process_id: str | None = None,
) -> tuple[Chat, Process, Message, Message]:
    await _ensure_chat_can_start(chat)

    process = await process_repository.create(Process(status=State.PENDING, payload={}))

    user_message = reuse_user_message or Message(
        chat_id=chat.id,
        user_id=user_id,
        process_id=process.id,
        role=Role.HUMAN,
        status=MessageStatus.COMPLETE,
        parts=parts,
    )
    if reuse_user_message is None:
        user_message = await message_repository.create(user_message)

    assistant_message = await message_repository.create(
        Message(
            chat_id=chat.id,
            user_id=user_id,
            process_id=process.id,
            role=Role.AI,
            status=MessageStatus.PENDING,
            parts=[],
        )
    )

    payload = ChatProcessPayload(
        chat_id=chat.id,
        user_message_id=user_message.id,
        assistant_message_id=assistant_message.id,
        mode=chat.mode,
        retry_of_process_id=retry_of_process_id,
    )
    process = process.model_copy(
        update={"payload": payload.model_dump(mode="json", exclude_none=True)}
    )
    process = await process_repository.save(process)

    chat = chat.model_copy(
        update={
            "last_message_id": assistant_message.id,
            "last_process_id": process.id,
        }
    )
    chat = await chat_repository.save(chat)
    return chat, process, user_message, assistant_message


async def _emit_start_records(
    user_id: str,
    *,
    chat: Chat,
    user_message: Message | None,
    assistant_message: Message,
    request_id: str | None = None,
):
    await send_data(
        user_id,
        ChatUpsertedEvent(
            payload=ChatUpsertedPayload(chat=chat, request_id=request_id)
        ),
    )
    if user_message is not None:
        await send_data(
            user_id,
            MessageUpsertedEvent(
                payload=MessageUpsertedPayload(chat_id=chat.id, message=user_message)
            ),
        )
    await send_data(
        user_id,
        MessageUpsertedEvent(
            payload=MessageUpsertedPayload(chat_id=chat.id, message=assistant_message)
        ),
    )


async def start(user_id: str, data: dict):
    try:
        request = TypeAdapter(NewChatOrMessageRequest).validate_python(data)
        chat, _ = await _load_chat_for_start(user_id, request)
        chat, process, user_message, assistant_message = await _create_turn_records(
            user_id=user_id,
            chat=chat,
            parts=request.parts,
        )
        await _emit_start_records(
            user_id,
            chat=chat,
            user_message=user_message,
            assistant_message=assistant_message,
            request_id=request.request_id if isinstance(request, CreateChatRequest) else None,
        )
        await _queue_process(user_id, process.id)
    except Exception as exc:
        logger.exception("Failed to start chat process for user %s", user_id)
        await _send_error(user_id, code="chat_start_failed", message=str(exc))


async def retry(user_id: str, data: dict):
    try:
        request = ChatRetryRequest.model_validate(data)
        original_process = await process_repository.get_by_id(request.process_id)
        if original_process is None:
            raise ValueError("Process not found.")

        payload = ChatProcessPayload.model_validate(original_process.payload or {})
        if payload.chat_id != request.chat_id:
            raise ValueError("Process does not belong to this chat.")

        chat = await chat_repository.get_by_id(request.chat_id, user_id=user_id)
        if chat is None:
            raise ValueError("Chat not found.")

        user_message = await message_repository.get_by_id(
            payload.user_message_id, chat_id=chat.id
        )
        if user_message is None:
            raise ValueError("User message not found for retry.")

        chat, process, _, assistant_message = await _create_turn_records(
            user_id=user_id,
            chat=chat,
            parts=user_message.parts,
            reuse_user_message=user_message,
            retry_of_process_id=original_process.id,
        )
        await _emit_start_records(
            user_id,
            chat=chat,
            user_message=None,
            assistant_message=assistant_message,
        )
        await _queue_process(user_id, process.id)
    except Exception as exc:
        logger.exception("Failed to retry chat process for user %s", user_id)
        await _send_error(
            user_id,
            code="chat_retry_failed",
            message=str(exc),
            chat_id=data.get("chat_id"),
            process_id=data.get("process_id"),
        )


async def resume(user_id: str, data: dict):
    try:
        request = ChatResumeRequest.model_validate(data)
        chat = await chat_repository.get_by_id(request.chat_id, user_id=user_id)
        if chat is None:
            raise ValueError("Chat not found.")

        process = await process_repository.get_by_id(request.process_id)
        if process is None:
            raise ValueError("Process not found.")
        if process.status not in {State.STOPPED, State.FAILED}:
            raise ValueError("Only stopped or failed processes can be resumed.")
        if process_manager.is_active(process.id):
            raise ValueError("Process is already running.")

        payload = ChatProcessPayload.model_validate(process.payload or {})
        if payload.chat_id != request.chat_id:
            raise ValueError("Process does not belong to this chat.")

        process = process.model_copy(
            update={
                "status": State.PENDING,
                "error": None,
                "payload": payload.model_copy(
                    update={"resume_count": payload.resume_count + 1}
                ).model_dump(mode="json", exclude_none=True),
            }
        )
        process = await process_repository.save(process)
        await _queue_process(user_id, process.id)
    except Exception as exc:
        logger.exception("Failed to resume chat process for user %s", user_id)
        await _send_error(
            user_id,
            code="chat_resume_failed",
            message=str(exc),
            chat_id=data.get("chat_id"),
            process_id=data.get("process_id"),
        )


async def stop(user_id: str, data: dict):
    try:
        request = ChatStopRequest.model_validate(data)
        chat = await chat_repository.get_by_id(request.chat_id, user_id=user_id)
        if chat is None:
            raise ValueError("Chat not found.")

        process = await process_repository.get_by_id(request.process_id)
        if process is None:
            raise ValueError("Process not found.")

        payload = ChatProcessPayload.model_validate(process.payload or {})
        if payload.chat_id != request.chat_id:
            raise ValueError("Process does not belong to this chat.")

        cancelled = process_manager.cancel(process.id)
        if not cancelled and process.status == State.PENDING:
            assistant_message = await message_repository.get_by_id(
                payload.assistant_message_id, chat_id=request.chat_id
            )
            if assistant_message is not None:
                assistant_message = assistant_message.model_copy(
                    update={"status": MessageStatus.STOPPED}
                )
                assistant_message = await message_repository.save(assistant_message)
                await send_data(
                    user_id,
                    MessageUpsertedEvent(
                        payload=MessageUpsertedPayload(
                            chat_id=request.chat_id,
                            message=assistant_message,
                        )
                    ),
                )

            process = process.model_copy(
                update={
                    "status": State.STOPPED,
                    "error": ProcessError(
                        code="stopped",
                        message="Response generation was stopped by the user.",
                    ),
                }
            )
            await process_repository.save(process)
    except Exception as exc:
        logger.exception("Failed to stop chat process for user %s", user_id)
        await _send_error(
            user_id,
            code="chat_stop_failed",
            message=str(exc),
            chat_id=data.get("chat_id"),
            process_id=data.get("process_id"),
        )


chat_handlers = {
    Event.START: start,
    Event.RESUME: resume,
    Event.RETRY: retry,
    Event.STOP: stop,
}
