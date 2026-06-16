from app.repositories import agricultural_input_recommendation_repository
from app.schemas.agricultural_input_recommendation import (
    AgriculturalInputRecommendation,
    AgriculturalInputRecommendationDocument,
)
from app.schemas.generic_types import PersistenceLanguage
from app.services import cultivation_crop_service


async def list_agricultural_input_recommendations(
    *, crop_id: str, user_id: str, limit: int = 100
) -> list[AgriculturalInputRecommendation]:
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return []
    return await agricultural_input_recommendation_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        limit=limit,
    )


async def get_agricultural_input_recommendation(
    *, recommendation_id: str, user_id: str
) -> AgriculturalInputRecommendation | None:
    crop_id = await agricultural_input_recommendation_repository.get_crop_id_by_id(
        recommendation_id
    )
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return None
    return await agricultural_input_recommendation_repository.get_by_id(
        recommendation_id=recommendation_id,
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )


async def delete_agricultural_input_recommendation(
    *, recommendation_id: str, user_id: str
) -> bool:
    crop_id = await agricultural_input_recommendation_repository.get_crop_id_by_id(
        recommendation_id
    )
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return False
    return await agricultural_input_recommendation_repository.delete(
        recommendation_id=recommendation_id, crop_id=crop_id
    )


async def _list_agricultural_input_recommendations(
    crop_id: str, limit: int = 100
) -> list[AgriculturalInputRecommendation]:
    return await agricultural_input_recommendation_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
        limit=limit,
    )


async def _get_agricultural_input_recommendation(
    recommendation_id: str, crop_id: str | None = None
) -> AgriculturalInputRecommendation | None:
    return await agricultural_input_recommendation_repository.get_by_id(
        recommendation_id=recommendation_id,
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
    )


async def _create_agricultural_input_recommendation(
    document: AgriculturalInputRecommendationDocument,
) -> AgriculturalInputRecommendationDocument:
    return await agricultural_input_recommendation_repository.create(document)
