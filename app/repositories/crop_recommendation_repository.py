from app.integrations.database.mogodb import get_crop_recommendations_collection
from app.schemas.crop_recommendation import (
    CropRecommendation,
    CropRecommendationDocument,
    CropRecommendationFields,
    CropRecommendationRequest,
)
from app.schemas.generic_types import PersistenceLanguage


def _to_crop_recommendation(
    document: dict,
    language: PersistenceLanguage,
) -> CropRecommendation:
    fields = document.get(language.value) or {}
    data = {
        **fields,
        "id": document["_id"],
        "farm_id": document["farm_id"],
        "request": document["request"],
    }
    if document.get("created_at") is not None:
        data["created_at"] = document["created_at"]
    return CropRecommendation.model_validate(data)


async def create(
    recommendation: CropRecommendationDocument,
) -> CropRecommendationDocument:
    await get_crop_recommendations_collection().insert_one(
        recommendation.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return recommendation


async def save(
    recommendation: CropRecommendationDocument,
) -> CropRecommendationDocument:
    existing = await get_crop_recommendations_collection().find_one(
        {"_id": recommendation.id},
        {"created_at": 1},
    )
    if existing and existing.get("created_at") is not None:
        recommendation = recommendation.model_copy(
            update={"created_at": existing["created_at"]}
        )
    await get_crop_recommendations_collection().replace_one(
        {"_id": recommendation.id},
        recommendation.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return recommendation


async def save_language(
    recommendation: CropRecommendation,
    language: PersistenceLanguage,
) -> CropRecommendation:
    fields = CropRecommendationFields.model_validate(recommendation).model_dump(
        exclude_none=True, mode="json"
    )
    request_data = CropRecommendationRequest.model_validate(
        recommendation.request
    ).model_dump(exclude_none=True, mode="json")
    await get_crop_recommendations_collection().update_one(
        {"_id": recommendation.id, "farm_id": recommendation.farm_id},
        {
            "$set": {
                "farm_id": recommendation.farm_id,
                "request": request_data,
                language.value: fields,
            },
            "$setOnInsert": {"created_at": recommendation.created_at},
        },
        upsert=True,
    )
    return recommendation


async def get_by_id(
    recommendation_id: str,
    language: PersistenceLanguage,
    farm_id: str | None = None,
) -> CropRecommendation | None:
    query: dict[str, str] = {"_id": recommendation_id}
    if farm_id:
        query["farm_id"] = farm_id
    projection = {
        "_id": 1,
        "farm_id": 1,
        "request": 1,
        "created_at": 1,
        language.value: 1,
    }
    document = await get_crop_recommendations_collection().find_one(query, projection)
    if not document:
        return None
    return _to_crop_recommendation(document, language)


async def get_document_by_id(
    recommendation_id: str,
    farm_id: str | None = None,
) -> CropRecommendationDocument | None:
    query: dict[str, str] = {"_id": recommendation_id}
    if farm_id:
        query["farm_id"] = farm_id
    document = await get_crop_recommendations_collection().find_one(query)
    if not document:
        return None
    return CropRecommendationDocument.model_validate(document)


async def get_farm_id_by_id(recommendation_id: str) -> str | None:
    document = await get_crop_recommendations_collection().find_one(
        {"_id": recommendation_id},
        {"farm_id": 1},
    )
    if not document:
        return None
    return document.get("farm_id")


async def list_by_farm(
    farm_id: str,
    language: PersistenceLanguage,
    limit: int = 100,
) -> list[CropRecommendation]:
    projection = {
        "_id": 1,
        "farm_id": 1,
        "request": 1,
        "created_at": 1,
        language.value: 1,
    }
    cursor = (
        get_crop_recommendations_collection()
        .find({"farm_id": farm_id}, projection)
        .sort("created_at", -1)
        .limit(limit)
    )
    return [_to_crop_recommendation(document, language) async for document in cursor]


async def delete(
    recommendation_id: str,
    farm_id: str | None = None,
) -> bool:
    query: dict[str, str] = {"_id": recommendation_id}
    if farm_id:
        query["farm_id"] = farm_id
    result = await get_crop_recommendations_collection().delete_one(query)
    return result.deleted_count > 0


async def delete_all_by_farm(farm_id: str) -> int:
    result = await get_crop_recommendations_collection().delete_many(
        {"farm_id": farm_id}
    )
    return result.deleted_count
