import time

from app.integrations.database.mogodb import get_messages_collection
from app.schemas.message import Message


def _touch(message: Message) -> Message:
    return message.model_copy(update={"updated_at": time.time()})


async def create(message: Message) -> Message:
    message = _touch(message)
    await get_messages_collection().insert_one(
        message.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return message


async def save(message: Message) -> Message:
    message = _touch(message)
    await get_messages_collection().replace_one(
        {"_id": message.id},
        message.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return message


async def get_by_id(message_id: str, chat_id: str | None = None) -> Message | None:
    query: dict[str, str] = {"_id": message_id}
    if chat_id:
        query["chat_id"] = chat_id
    document = await get_messages_collection().find_one(query)
    if not document:
        return None
    return Message.model_validate(document)


async def list_by_chat(chat_id: str, limit: int = 50) -> list[Message]:
    cursor = (
        get_messages_collection()
        .find({"chat_id": chat_id})
        .sort("created_at", 1)
        .limit(limit)
    )
    return [Message.model_validate(document) async for document in cursor]


async def list_by_chat_since(
    chat_id: str, *, since: float, limit: int = 50
) -> list[Message]:
    cursor = (
        get_messages_collection()
        .find({"chat_id": chat_id, "created_at": {"$gt": since}})
        .sort("created_at", 1)
        .limit(limit)
    )
    return [Message.model_validate(document) async for document in cursor]


async def list_latest_by_chat(chat_id: str, limit: int = 20) -> list[Message]:
    cursor = (
        get_messages_collection()
        .find({"chat_id": chat_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    documents = [Message.model_validate(document) async for document in cursor]
    return list(reversed(documents))


async def delete_by_chat(chat_id: str) -> None:
    await get_messages_collection().delete_many({"chat_id": chat_id})
