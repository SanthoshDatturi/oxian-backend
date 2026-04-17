import json

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse

from app.core.dependencies import authenticate_rest
from app.repositories import chat_repository, message_repository
from app.schemas.chat import Chat
from app.schemas.message import ChatMessageInput, Message, NewChatMessageInput
from app.services.chat import (
    start_existing_chat_turn,
    start_new_chat_turn,
    stop_chat_turn,
)

router = APIRouter(prefix="/chats", tags=["Chats"])


def _get_user_id(user_payload: dict) -> str:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return user_id


def _format_sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=True)}\n\n"


@router.post("/messages")
async def create_chat_message(
    payload: NewChatMessageInput,
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    try:
        session = await start_new_chat_turn(user_id=user_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

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
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    try:
        session = await start_existing_chat_turn(
            user_id=user_id,
            chat_id=chat_id,
            payload=payload,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail)

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
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    try:
        stopped = await stop_chat_turn(user_id=user_id, chat_id=chat_id)
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if "not found" in detail.lower() else 400
        raise HTTPException(status_code=status_code, detail=detail)

    return {"stopped": stopped}


@router.get("/", response_model=list[Chat])
async def list_chats(user_payload: dict = Depends(authenticate_rest)) -> list[Chat]:
    user_id = _get_user_id(user_payload)
    return await chat_repository.list_by_user(user_id)


@router.get("/{chat_id}", response_model=Chat)
async def get_chat(
    chat_id: str, user_payload: dict = Depends(authenticate_rest)
) -> Chat:
    user_id = _get_user_id(user_payload)
    chat = await chat_repository.get_by_id(chat_id, user_id=user_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat


@router.delete("/{chat_id}", status_code=204)
async def delete_chat(chat_id: str, user_payload: dict = Depends(authenticate_rest)):
    user_id = _get_user_id(user_payload)
    deleted = await chat_repository.delete(chat_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Chat not found")
    await message_repository.delete_by_chat(chat_id)
    return


@router.get("/{chat_id}/messages", response_model=list[Message])
async def list_messages(
    chat_id: str,
    user_payload: dict = Depends(authenticate_rest),
    limit: int = Query(default=50, ge=1, le=200),
    since: float | None = Query(default=None, ge=0),
) -> list[Message]:
    user_id = _get_user_id(user_payload)
    chat = await chat_repository.get_by_id(chat_id, user_id=user_id)
    if chat is None:
        raise HTTPException(status_code=404, detail="Chat not found")
    if since is not None:
        return await message_repository.list_by_chat_since(
            chat_id=chat_id, since=since, limit=limit
        )
    return await message_repository.list_latest_by_chat(chat_id, limit=limit)
