from app.infrastructure.database.collections import get_cultivation_tasks_collection
from app.schemas.cultivation_task import (
    CultivationTask,
    CultivationTaskDocument,
    CultivationTaskInvariantFields,
    CultivationTaskTranslatableFields,
)
from app.schemas.generic_types import PersistenceLanguage


def _to_cultivation_task(
    document: dict,
    language: PersistenceLanguage,
) -> CultivationTask:
    translatable_fields = document.get(language.value) or {}
    invariant_data = dict(document)
    for key in CultivationTaskInvariantFields.model_fields:
        value = document.get(key, translatable_fields.get(key))
        if value is not None:
            invariant_data[key] = value
    invariant_fields = CultivationTaskInvariantFields.model_validate(invariant_data)
    return CultivationTask.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields,
        }
    )


async def create(task: CultivationTaskDocument) -> CultivationTaskDocument:
    await get_cultivation_tasks_collection().insert_one(
        task.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return task


async def save(task: CultivationTaskDocument) -> CultivationTaskDocument:
    await get_cultivation_tasks_collection().replace_one(
        {"_id": task.id},
        task.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return task


async def save_language(
    task: CultivationTask,
    language: PersistenceLanguage,
) -> CultivationTask:
    translatable_fields = CultivationTaskTranslatableFields.model_validate(
        task
    ).model_dump(exclude_none=True, mode="json")
    invariant_fields = CultivationTaskInvariantFields.model_validate(
        task
    ).model_dump(exclude_none=True, mode="json")
    await get_cultivation_tasks_collection().update_one(
        {"_id": task.id, "crop_id": task.crop_id},
        {
            "$set": {
                **invariant_fields,
                language.value: translatable_fields,
            },
        },
        upsert=True,
    )
    return task


async def get_by_id(
    task_id: str,
    language: PersistenceLanguage,
    crop_id: str | None = None,
) -> CultivationTask | None:
    query: dict[str, str] = {"_id": task_id}
    if crop_id:
        query["crop_id"] = crop_id
    projection = {
        "_id": 1,
        "crop_id": 1,
        "sequence_number": 1,
        "planned_start_date": 1,
        "planned_end_date": 1,
        "status": 1,
        "priority": 1,
        "skippable": 1,
        "completed_at": 1,
        language.value: 1,
    }
    document = await get_cultivation_tasks_collection().find_one(query, projection)
    if not document:
        return None
    return _to_cultivation_task(document, language)


async def get_document_by_id(
    task_id: str,
    crop_id: str | None = None,
) -> CultivationTaskDocument | None:
    query: dict[str, str] = {"_id": task_id}
    if crop_id:
        query["crop_id"] = crop_id
    document = await get_cultivation_tasks_collection().find_one(query)
    if not document:
        return None
    return CultivationTaskDocument.model_validate(document)


async def get_crop_id_by_id(task_id: str) -> str | None:
    document = await get_cultivation_tasks_collection().find_one(
        {"_id": task_id},
        {"crop_id": 1},
    )
    if not document:
        return None
    return document.get("crop_id")


async def list_by_crop(
    crop_id: str,
    language: PersistenceLanguage,
    limit: int = 100,
) -> list[CultivationTask]:
    projection = {
        "_id": 1,
        "crop_id": 1,
        "sequence_number": 1,
        "planned_start_date": 1,
        "planned_end_date": 1,
        "status": 1,
        "priority": 1,
        "skippable": 1,
        "completed_at": 1,
        language.value: 1,
    }
    cursor = (
        get_cultivation_tasks_collection()
        .find({"crop_id": crop_id}, projection)
        .sort("sequence_number", 1)
        .limit(limit)
    )
    return [_to_cultivation_task(document, language) async for document in cursor]


async def delete(task_id: str, crop_id: str | None = None) -> bool:
    query: dict[str, str] = {"_id": task_id}
    if crop_id:
        query["crop_id"] = crop_id
    result = await get_cultivation_tasks_collection().delete_one(query)
    return result.deleted_count > 0


async def delete_all_by_crop(crop_id: str) -> int:
    result = await get_cultivation_tasks_collection().delete_many({"crop_id": crop_id})
    return result.deleted_count
