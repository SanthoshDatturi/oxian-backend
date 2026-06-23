from app.infrastructure.database.mogodb import (
    get_agricultural_input_recommendations_collection,
)
from app.schemas.agricultural_input_plan import AgriculturalInputInvariantFields
from app.schemas.agricultural_input_recommendation import (
    AgriculturalInputRecommendation,
    AgriculturalInputRecommendationDocument,
    AgriculturalInputRecommendationTranslatableFields,
)
from app.schemas.generic_types import PersistenceLanguage


def _to_agricultural_input_recommendation(
    document: dict,
    language: PersistenceLanguage,
) -> AgriculturalInputRecommendation:
    translatable_fields = document.get(language.value) or {}
    invariant_data = dict(document)
    for key in AgriculturalInputInvariantFields.model_fields:
        value = document.get(key, translatable_fields.get(key))
        if value is not None:
            invariant_data[key] = value
    invariant_fields = AgriculturalInputInvariantFields.model_validate(invariant_data)
    return AgriculturalInputRecommendation.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields,
        }
    )


async def create(
    recommendation: AgriculturalInputRecommendationDocument,
) -> AgriculturalInputRecommendationDocument:
    await get_agricultural_input_recommendations_collection().insert_one(
        recommendation.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return recommendation


async def save(
    recommendation: AgriculturalInputRecommendationDocument,
) -> AgriculturalInputRecommendationDocument:
    existing = await get_agricultural_input_recommendations_collection().find_one(
        {"_id": recommendation.id},
        {"created_at": 1},
    )
    if existing and existing.get("created_at") is not None:
        recommendation = recommendation.model_copy(
            update={"created_at": existing["created_at"]}
        )
    await get_agricultural_input_recommendations_collection().replace_one(
        {"_id": recommendation.id},
        recommendation.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return recommendation


async def save_language(
    recommendation: AgriculturalInputRecommendation,
    language: PersistenceLanguage,
) -> AgriculturalInputRecommendation:
    translatable_fields = (
        AgriculturalInputRecommendationTranslatableFields.model_validate(
            recommendation
        ).model_dump(exclude_none=True, mode="json")
    )
    invariant_fields = AgriculturalInputInvariantFields.model_validate(
        recommendation
    ).model_dump(exclude_none=True, mode="json")
    await get_agricultural_input_recommendations_collection().update_one(
        {
            "_id": recommendation.id,
            "cultivation_crop_id": recommendation.cultivation_crop_id,
        },
        {
            "$set": {
                **invariant_fields,
                language.value: translatable_fields,
            },
            "$setOnInsert": {"created_at": recommendation.created_at},
        },
        upsert=True,
    )
    return recommendation


async def get_by_id(
    recommendation_id: str,
    language: PersistenceLanguage,
    crop_id: str | None = None,
) -> AgriculturalInputRecommendation | None:
    query: dict[str, str] = {"_id": recommendation_id}
    if crop_id:
        query["cultivation_crop_id"] = crop_id
    projection = {
        "_id": 1,
        "cultivation_crop_id": 1,
        "created_at": 1,
        language.value: 1,
    }
    document = await get_agricultural_input_recommendations_collection().find_one(
        query, projection
    )
    if not document:
        return None
    return _to_agricultural_input_recommendation(document, language)


async def get_document_by_id(
    recommendation_id: str,
    crop_id: str | None = None,
) -> AgriculturalInputRecommendationDocument | None:
    query: dict[str, str] = {"_id": recommendation_id}
    if crop_id:
        query["cultivation_crop_id"] = crop_id
    document = await get_agricultural_input_recommendations_collection().find_one(query)
    if not document:
        return None
    return AgriculturalInputRecommendationDocument.model_validate(document)


async def get_crop_id_by_id(recommendation_id: str) -> str | None:
    document = await get_agricultural_input_recommendations_collection().find_one(
        {"_id": recommendation_id},
        {"cultivation_crop_id": 1},
    )
    if not document:
        return None
    return document.get("cultivation_crop_id")


async def list_by_crop(
    crop_id: str,
    language: PersistenceLanguage,
    limit: int = 100,
) -> list[AgriculturalInputRecommendation]:
    projection = {
        "_id": 1,
        "cultivation_crop_id": 1,
        "created_at": 1,
        language.value: 1,
    }
    cursor = (
        get_agricultural_input_recommendations_collection()
        .find({"cultivation_crop_id": crop_id}, projection)
        .sort("created_at", -1)
        .limit(limit)
    )
    return [
        _to_agricultural_input_recommendation(document, language)
        async for document in cursor
    ]


async def delete(recommendation_id: str, crop_id: str | None = None) -> bool:
    query: dict[str, str] = {"_id": recommendation_id}
    if crop_id:
        query["cultivation_crop_id"] = crop_id
    result = await get_agricultural_input_recommendations_collection().delete_one(query)
    return result.deleted_count > 0


async def delete_all_by_crop(crop_id: str) -> int:
    result = await get_agricultural_input_recommendations_collection().delete_many(
        {"cultivation_crop_id": crop_id}
    )
    return result.deleted_count
