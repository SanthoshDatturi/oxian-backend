from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import authenticate_rest
from app.repositories import chat_repository, message_repository
from app.schemas.chat import Chat
from app.schemas.message import Message

router = APIRouter(prefix="/chats", tags=["Chats"])


def _get_user_id(user_payload: dict) -> str:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return user_id


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
