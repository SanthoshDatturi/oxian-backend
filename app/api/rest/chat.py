import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from app.api.dependencies import get_current_user_id
from app.core.errors import (
    AppError,
    ChatNotFound,
    ErrorCode,
    InternalOperationFailed,
    ValidationFailed,
)
from app.schemas.chat import Chat
from app.schemas.message import ChatMessageInput, Message, NewChatMessageInput
from app.services.chat_service import (
    delete_chat_by_id,
    get_chat_by_id,
    list_chat_messages,
    list_user_chats,
    start_existing_chat_turn,
    start_new_chat_turn,
    stop_chat_turn,
)

router = APIRouter(prefix="/chats", tags=["Chats"])
logger = logging.getLogger(__name__)


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=True)}\n\n"


@router.post("/messages")
async def create_chat_message(
    payload: NewChatMessageInput,
    user_id: str = Depends(get_current_user_id),
):
    try:
        session = await start_new_chat_turn(user_id=user_id, payload=payload)
    except AppError:
        raise
    except Exception as exc:
        logger.exception("Failed to start new chat turn")
        raise InternalOperationFailed(
            "Unable to start chat response right now."
        ) from exc

    async def event_stream():
        yield _format_sse("meta", session.meta)
        while True:
            event = await session.events.get()
            if event is None:
                break
            yield _format_sse(event["event"], event["data"])

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/{chat_id}/messages")
async def add_chat_message(
    chat_id: str,
    payload: ChatMessageInput,
    user_id: str = Depends(get_current_user_id),
):
    try:
        session = await start_existing_chat_turn(
            user_id=user_id,
            chat_id=chat_id,
            payload=payload,
        )
    except AppError:
        raise
    except Exception as exc:
        logger.exception("Failed to start chat turn chat_id=%s", chat_id)
        raise InternalOperationFailed(
            "Unable to start chat response right now.",
            context={"chat_id": chat_id},
        ) from exc

    async def event_stream():
        yield _format_sse("meta", session.meta)
        while True:
            event = await session.events.get()
            if event is None:
                break
            yield _format_sse(event["event"], event["data"])

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )


@router.post("/{chat_id}/stop")
async def stop_chat_message(
    chat_id: str,
    user_id: str = Depends(get_current_user_id),
):
    stopped = await stop_chat_turn(user_id=user_id, chat_id=chat_id)

    return {"stopped": stopped}


@router.get(
    "/",
    response_model=list[Chat],
    response_model_exclude={"__all__": {"user_id"}},
    response_model_exclude_none=True,
)
async def list_chats(user_id: str = Depends(get_current_user_id)) -> list[Chat]:
    return await list_user_chats(user_id=user_id)


@router.get(
    "/{chat_id}",
    response_model=Chat,
    response_model_exclude={"user_id"},
    response_model_exclude_none=True,
)
async def get_chat(chat_id: str, user_id: str = Depends(get_current_user_id)) -> Chat:
    chat = await get_chat_by_id(chat_id=chat_id, user_id=user_id)
    if chat is None:
        raise ChatNotFound(chat_id)
    return chat


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(chat_id: str, user_id: str = Depends(get_current_user_id)):
    deleted = await delete_chat_by_id(chat_id=chat_id, user_id=user_id)
    if not deleted:
        raise ChatNotFound(chat_id)


@router.get(
    "/{chat_id}/messages",
    response_model=list[Message],
    response_model_exclude={"__all__": {"user_id"}},
    response_model_exclude_none=True,
)
async def list_messages(
    chat_id: str,
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(default=50, ge=1, le=200),
    since: str | None = Query(default=None),
) -> list[Message]:
    parsed_since: datetime | None = None
    if since is not None:
        try:
            parsed_since = datetime.fromisoformat(since.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValidationFailed(
                "Invalid since timestamp.",
                code=ErrorCode.INVALID_TIMESTAMP,
                context={"since": since},
            ) from exc
    return await list_chat_messages(
        chat_id=chat_id,
        user_id=user_id,
        limit=limit,
        since=parsed_since,
    )
