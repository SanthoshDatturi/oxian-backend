from typing import Any

from pymongo import ASCENDING, DESCENDING

from app.infrastructure.database.mogodb import (
    get_device_registrations_collection,
    get_notification_records_collection,
)
from app.schemas.notification import DeviceRegistration, NotificationRecord


async def ensure_indexes() -> None:
    device_collection = get_device_registrations_collection()
    existing_indexes = await device_collection.index_information()
    for index_name, index_info in existing_indexes.items():
        if index_info.get("key") == [("device_token", ASCENDING)] and index_info.get("unique"):
            await device_collection.drop_index(index_name)
    await device_collection.create_index(
        [("device_token", ASCENDING)],
    )
    await device_collection.create_index([("user_id", ASCENDING), ("registered_at", DESCENDING)])

    notification_collection = get_notification_records_collection()
    await notification_collection.create_index([("user_id", ASCENDING), ("created_at", DESCENDING)])
    await notification_collection.create_index([("delivery_status", ASCENDING), ("created_at", DESCENDING)])


def _to_document(model: Any) -> dict[str, Any]:
    return model.model_dump(by_alias=True, exclude_none=True, mode="json")


async def upsert_device_registration(
    registration: DeviceRegistration,
) -> DeviceRegistration:
    await get_device_registrations_collection().replace_one(
        {"_id": registration.id},
        _to_document(registration),
        upsert=True,
    )
    return registration


async def list_device_registrations(user_id: str) -> list[DeviceRegistration]:
    cursor = (
        get_device_registrations_collection()
        .find({"user_id": user_id})
        .sort("registered_at", -1)
    )
    return [DeviceRegistration.model_validate(document) async for document in cursor]


async def get_device_registration_by_id(device_id: str) -> DeviceRegistration | None:
    document = await get_device_registrations_collection().find_one({"_id": device_id})
    if document is None:
        return None
    return DeviceRegistration.model_validate(document)


async def delete_device_registration_by_id(
    device_id: str,
    user_id: str | None = None,
) -> bool:
    query: dict[str, str] = {"_id": device_id}
    if user_id:
        query["user_id"] = user_id

    result = await get_device_registrations_collection().delete_one(query)
    return result.deleted_count > 0


async def delete_device_registrations_by_ids(
    device_ids: list[str],
    user_id: str | None = None,
) -> int:
    if not device_ids:
        return 0

    query: dict[str, Any] = {"_id": {"$in": device_ids}}
    if user_id:
        query["user_id"] = user_id

    result = await get_device_registrations_collection().delete_many(query)
    return result.deleted_count


async def delete_device_registration_by_token(
    device_token: str,
    user_id: str | None = None,
) -> bool:
    query: dict[str, str] = {"device_token": device_token}
    if user_id:
        query["user_id"] = user_id

    result = await get_device_registrations_collection().delete_one(query)
    return result.deleted_count > 0


async def create_notification_record(record: NotificationRecord) -> NotificationRecord:
    await get_notification_records_collection().insert_one(_to_document(record))
    return record


async def save_notification_record(record: NotificationRecord) -> NotificationRecord:
    await get_notification_records_collection().replace_one(
        {"_id": record.id},
        _to_document(record),
        upsert=True,
    )
    return record


async def list_notification_records(
    user_id: str,
    limit: int = 100,
) -> list[NotificationRecord]:
    cursor = (
        get_notification_records_collection()
        .find({"user_id": user_id})
        .sort("created_at", -1)
        .limit(limit)
    )
    return [NotificationRecord.model_validate(document) async for document in cursor]
