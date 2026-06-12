from datetime import datetime, timezone

from app.integrations.database.mogodb import get_cultivation_crops_collection
from app.schemas.cultivation_crop import (
    BaseCrop,
    CultivationCrop,
    CultivationCropDocument,
)
from app.schemas.generic_types import PersistenceLanguage


def _to_cultivation_crop(
    document: dict,
    language: PersistenceLanguage,
) -> CultivationCrop:
    fields = document.get(language.value) or {}
    data = {
        **fields,
        "id": document["_id"],
        "farm_id": document["farm_id"],
    }
    crop_state = document.get("crop_state", fields.get("crop_state"))
    selected_area = document.get("selected_area", fields.get("selected_area"))
    if document.get("recommendation_id") is not None:
        data["recommendation_id"] = document["recommendation_id"]
    if document.get("intercropping_id") is not None:
        data["intercropping_id"] = document["intercropping_id"]
    if crop_state is not None:
        data["crop_state"] = crop_state
    if selected_area is not None:
        data["selected_area"] = selected_area
    if document.get("created_at") is not None:
        data["created_at"] = document["created_at"]
    if document.get("updated_at") is not None:
        data["updated_at"] = document["updated_at"]
    return CultivationCrop.model_validate(data)


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
    fields = BaseCrop.model_validate(crop).model_dump(
        exclude_none=True, mode="json"
    )
    await get_cultivation_crops_collection().update_one(
        {"_id": crop.id, "farm_id": crop.farm_id},
        {
            "$set": {
                "farm_id": crop.farm_id,
                "recommendation_id": crop.recommendation_id,
                "intercropping_id": crop.intercropping_id,
                "crop_state": crop.crop_state,
                "selected_area": crop.selected_area.model_dump(mode="json"),
                "updated_at": crop.updated_at,
                language.value: fields,
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


async def delete(crop_id: str, farm_id: str | None = None) -> bool:
    query: dict[str, str] = {"_id": crop_id}
    if farm_id:
        query["farm_id"] = farm_id
    result = await get_cultivation_crops_collection().delete_one(query)
    return result.deleted_count > 0


async def delete_all_by_farm(farm_id: str) -> int:
    result = await get_cultivation_crops_collection().delete_many({"farm_id": farm_id})
    return result.deleted_count
