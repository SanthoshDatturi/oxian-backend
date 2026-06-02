from typing import Any

from pymongo import ASCENDING, DESCENDING

from app.integrations.database.mogodb import (
    get_device_registrations_collection,
    get_notification_records_collection,
)
from app.schemas.notification import DeviceRegistration, NotificationRecord


async def ensure_indexes() -> None:
    device_collection = get_device_registrations_collection()
    await device_collection.create_index(
        [("device_token", ASCENDING)],
        unique=True,
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
        {"device_token": registration.device_token},
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


async def delete_device_registration(
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
