from pymongo import ASCENDING

from app.integrations.database.mogodb import get_files_collection
from app.integrations.storage.base import StorageEntity
from app.schemas.file import File, FileStatus


async def ensure_indexes() -> None:
    collection = get_files_collection()
    await collection.create_index([("status", ASCENDING), ("created_at", ASCENDING)])
    await collection.create_index([("user_id", ASCENDING), ("entity_id", ASCENDING)])
    await collection.create_index([("user_id", ASCENDING), ("_id", ASCENDING)])


def _dedupe_file_ids(file_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(file_ids))


async def _validate_entity(entity: StorageEntity, entity_id: str, user_id: str) -> None:
    if not entity_id:
        raise ValueError("Entity id is required.")

    if entity == StorageEntity.CHAT:
        from app.repositories import chat_repository

        chat = await chat_repository.get_by_id(entity_id, user_id=user_id)
        if chat is None:
            raise ValueError("Chat not found.")
        return

    if entity == StorageEntity.CROP:
        raise ValueError("Crop file activation is not supported.")

    raise ValueError("Unsupported storage entity.")


async def create(file: File) -> File:
    await get_files_collection().insert_one(
        file.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return file


async def get_by_id(file_id: str, user_id: str) -> File | None:
    document = await get_files_collection().find_one({"_id": file_id, "user_id": user_id})
    if not document:
        return None
    return File.model_validate(document)


async def activate_for_entity(
    file_ids: list[str],
    entity: StorageEntity,
    entity_id: str,
    user_id: str,
) -> list[File]:
    normalized_ids = _dedupe_file_ids(file_ids)
    if not normalized_ids:
        return []

    await _validate_entity(entity=entity, entity_id=entity_id, user_id=user_id)

    cursor = get_files_collection().find(
        {"_id": {"$in": normalized_ids}, "user_id": user_id}
    )
    files = [File.model_validate(document) async for document in cursor]
    files_by_id = {file.id: file for file in files}

    missing_ids = [file_id for file_id in normalized_ids if file_id not in files_by_id]
    if missing_ids:
        raise ValueError("One or more files were not found.")

    for file in files:
        if file.entity_id and file.entity_id != entity_id:
            raise ValueError("File is already attached to another entity.")

    await get_files_collection().update_many(
        {"_id": {"$in": normalized_ids}, "user_id": user_id},
        {"$set": {"status": FileStatus.ACTIVE.value, "entity_id": entity_id}},
    )

    refreshed_cursor = get_files_collection().find(
        {"_id": {"$in": normalized_ids}, "user_id": user_id}
    )
    refreshed = [File.model_validate(document) async for document in refreshed_cursor]
    refreshed_by_id = {file.id: file for file in refreshed}
    return [refreshed_by_id[file_id] for file_id in normalized_ids]


async def list_by_entity(entity_id: str, user_id: str) -> list[File]:
    cursor = get_files_collection().find({"entity_id": entity_id, "user_id": user_id})
    return [File.model_validate(document) async for document in cursor]


async def delete_temp(file_id: str, user_id: str) -> File | None:
    document = await get_files_collection().find_one_and_delete(
        {"_id": file_id, "user_id": user_id, "status": FileStatus.TEMP.value}
    )
    if not document:
        return None
    return File.model_validate(document)


async def delete_by_entity_id(entity_id: str, user_id: str) -> list[File]:
    files = await list_by_entity(entity_id=entity_id, user_id=user_id)
    if not files:
        return []
    await delete_many_by_ids([file.id for file in files])
    return files


async def list_expired_temp(cutoff_ts: float) -> list[File]:
    cursor = get_files_collection().find(
        {"status": FileStatus.TEMP.value, "created_at": {"$lt": cutoff_ts}}
    )
    return [File.model_validate(document) async for document in cursor]


async def delete_many_by_ids(file_ids: list[str]) -> int:
    normalized_ids = _dedupe_file_ids(file_ids)
    if not normalized_ids:
        return 0

    result = await get_files_collection().delete_many({"_id": {"$in": normalized_ids}})
    return result.deleted_count
