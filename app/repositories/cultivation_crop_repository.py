from datetime import datetime, timezone

from app.infrastructure.database.collections import get_cultivation_crops_collection
from app.schemas.cultivation_crop import (
    BaseCrop,
    CultivationCrop,
    CultivationCropDocument,
    CultivationCropInputInvariantFields,
    CultivationCropInvariantFields,
)
from app.schemas.generic_types import PersistenceLanguage


def _to_cultivation_crop(
    document: dict,
    language: PersistenceLanguage,
) -> CultivationCrop:
    translatable_fields = document.get(language.value) or {}
    invariant_data = dict(document)
    for key in CultivationCropInvariantFields.model_fields:
        value = document.get(key, translatable_fields.get(key))
        if value is not None:
            invariant_data[key] = value
    invariant_fields = CultivationCropInvariantFields.model_validate(invariant_data)
    return CultivationCrop.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields,
        }
    )


def _touch(crop: CultivationCropDocument) -> CultivationCropDocument:
    return crop.model_copy(update={"updated_at": datetime.now(timezone.utc)})


async def create(crop: CultivationCropDocument) -> CultivationCropDocument:
    crop = _touch(crop)
    await get_cultivation_crops_collection().insert_one(
        crop.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return crop


async def save(crop: CultivationCropDocument) -> CultivationCropDocument:
    existing = await get_cultivation_crops_collection().find_one(
        {"_id": crop.id},
        {"created_at": 1},
    )
    if existing and existing.get("created_at") is not None:
        crop = crop.model_copy(update={"created_at": existing["created_at"]})
    crop = _touch(crop)
    await get_cultivation_crops_collection().replace_one(
        {"_id": crop.id},
        crop.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return crop


async def save_language(
    crop: CultivationCrop,
    language: PersistenceLanguage,
) -> CultivationCrop:
    crop = crop.model_copy(update={"updated_at": datetime.now(timezone.utc)})
    translatable_fields = BaseCrop.model_validate(crop).model_dump(
        exclude_none=True, mode="json"
    )
    invariant_fields = CultivationCropInputInvariantFields.model_validate(
        crop
    ).model_dump(exclude_none=True, mode="json")
    await get_cultivation_crops_collection().update_one(
        {"_id": crop.id, "farm_id": crop.farm_id},
        {
            "$set": {
                "farm_id": crop.farm_id,
                "recommendation_id": crop.recommendation_id,
                "intercropping_id": crop.intercropping_id,
                **invariant_fields,
                "updated_at": crop.updated_at,
                language.value: translatable_fields,
            },
            "$setOnInsert": {"created_at": crop.created_at},
        },
        upsert=True,
    )
    return crop


async def get_by_id(
    crop_id: str,
    language: PersistenceLanguage,
    farm_id: str | None = None,
) -> CultivationCrop | None:
    query: dict[str, str] = {"_id": crop_id}
    if farm_id:
        query["farm_id"] = farm_id
    projection = {
        "_id": 1,
        "farm_id": 1,
        "recommendation_id": 1,
        "intercropping_id": 1,
        "crop_state": 1,
        "selected_area": 1,
        "created_at": 1,
        "updated_at": 1,
        language.value: 1,
    }
    document = await get_cultivation_crops_collection().find_one(query, projection)
    if not document:
        return None
    return _to_cultivation_crop(document, language)


async def get_document_by_id(
    crop_id: str,
    farm_id: str | None = None,
) -> CultivationCropDocument | None:
    query: dict[str, str] = {"_id": crop_id}
    if farm_id:
        query["farm_id"] = farm_id
    document = await get_cultivation_crops_collection().find_one(query)
    if not document:
        return None
    return CultivationCropDocument.model_validate(document)


async def get_farm_id_by_id(crop_id: str) -> str | None:
    document = await get_cultivation_crops_collection().find_one(
        {"_id": crop_id},
        {"farm_id": 1},
    )
    if not document:
        return None
    return document.get("farm_id")


async def list_by_farm(
    farm_id: str,
    language: PersistenceLanguage,
    limit: int = 100,
) -> list[CultivationCrop]:
    projection = {
        "_id": 1,
        "farm_id": 1,
        "recommendation_id": 1,
        "intercropping_id": 1,
        "crop_state": 1,
        "selected_area": 1,
        "created_at": 1,
        "updated_at": 1,
        language.value: 1,
    }
    cursor = (
        get_cultivation_crops_collection()
        .find({"farm_id": farm_id}, projection)
        .sort("created_at", -1)
        .limit(limit)
    )
    return [_to_cultivation_crop(document, language) async for document in cursor]


async def list_by_intercropping(
    intercropping_id: str,
    language: PersistenceLanguage,
    limit: int = 100,
) -> list[CultivationCrop]:
    projection = {
        "_id": 1,
        "farm_id": 1,
        "recommendation_id": 1,
        "intercropping_id": 1,
        "crop_state": 1,
        "selected_area": 1,
        "created_at": 1,
        "updated_at": 1,
        language.value: 1,
    }
    cursor = (
        get_cultivation_crops_collection()
        .find({"intercropping_id": intercropping_id}, projection)
        .sort(f"{language.value}.name", 1)
        .limit(limit)
    )
    return [_to_cultivation_crop(document, language) async for document in cursor]


async def list_documents_by_intercropping(
    intercropping_id: str,
    farm_id: str | None = None,
    limit: int = 100,
) -> list[CultivationCropDocument]:
    query: dict[str, str] = {"intercropping_id": intercropping_id}
    if farm_id:
        query["farm_id"] = farm_id
    cursor = (
        get_cultivation_crops_collection()
        .find(query)
        .sort("created_at", -1)
        .limit(limit)
    )
    return [
        CultivationCropDocument.model_validate(document) async for document in cursor
    ]


async def delete(crop_id: str, farm_id: str | None = None) -> bool:
    query: dict[str, str] = {"_id": crop_id}
    if farm_id:
        query["farm_id"] = farm_id
    result = await get_cultivation_crops_collection().delete_one(query)
    return result.deleted_count > 0


async def delete_all_by_farm(farm_id: str) -> int:
    result = await get_cultivation_crops_collection().delete_many({"farm_id": farm_id})
    return result.deleted_count


async def delete_all_by_intercropping(
    intercropping_id: str,
    farm_id: str | None = None,
) -> int:
    query: dict[str, str] = {"intercropping_id": intercropping_id}
    if farm_id:
        query["farm_id"] = farm_id
    result = await get_cultivation_crops_collection().delete_many(query)
    return result.deleted_count
