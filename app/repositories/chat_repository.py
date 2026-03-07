import time

from app.integrations.database.mogodb import get_chats_collection
from app.schemas.chat import Chat


def _touch(chat: Chat) -> Chat:
    now = time.time()
    updates = {"updated_at": now, "last_activity_at": now}
    return chat.model_copy(update=updates)


async def create(chat: Chat) -> Chat:
    chat = _touch(chat)
    await get_chats_collection().insert_one(
        chat.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return chat


async def save(chat: Chat) -> Chat:
    chat = _touch(chat)
    await get_chats_collection().replace_one(
        {"_id": chat.id},
        chat.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return chat


async def get_by_id(chat_id: str, user_id: str | None = None) -> Chat | None:
    query: dict[str, str] = {"_id": chat_id}
    if user_id:
        query["user_id"] = user_id
    document = await get_chats_collection().find_one(query)
    if not document:
        return None
    return Chat.model_validate(document)


async def list_by_user(user_id: str, limit: int = 50) -> list[Chat]:
    cursor = (
        get_chats_collection()
        .find({"user_id": user_id})
        .sort("last_activity_at", -1)
        .limit(limit)
    )
    return [Chat.model_validate(document) async for document in cursor]


async def delete(chat_id: str, user_id: str | None = None) -> None:
    query: dict[str, str] = {"_id": chat_id}
    if user_id:
        query["user_id"] = user_id
    await get_chats_collection().delete_one(query)
