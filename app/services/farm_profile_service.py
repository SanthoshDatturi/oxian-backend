from app.repositories import farm_profile_repository
from app.schemas.farm_profile import (
    FarmProfile,
    FarmProfileDocument,
    FarmProfileFields,
)
from app.schemas.generic_types import PersistenceLanguage
from app.services import translation_service


async def list_all_farms(user_id: str, limit: int = 100) -> list[FarmProfile]:
    return await farm_profile_repository.list_by_user(
        user_id=user_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        limit=limit,
    )


async def get_farm_profile(farm_id: str, user_id: str) -> FarmProfile | None:
    return await farm_profile_repository.get_by_id(
        farm_id=farm_id,
        user_id=user_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )


async def create_farm_profile(
    *,
    user_id: str,
    fields: FarmProfileFields,
) -> FarmProfile:
    profile_document = FarmProfileDocument(
        user_id=user_id,
        english=await translation_service.to_english(user_id=user_id, fields=fields),
        user_language=fields,
    )
    profile_document = await farm_profile_repository.create(profile_document)
    return FarmProfile.model_validate(
        {
            **profile_document.user_language.model_dump(mode="json"),
            "id": profile_document.id,
            "user_id": user_id,
            "created_at": profile_document.created_at,
            "updated_at": profile_document.updated_at,
        }
    )


async def update_farm_profile(
    *,
    farm_id: str,
    user_id: str,
    fields: FarmProfileFields,
) -> FarmProfile:
    profile_document = FarmProfileDocument(
        id=farm_id,
        user_id=user_id,
        english=await translation_service.to_english(user_id=user_id, fields=fields),
        user_language=fields,
    )
    profile_document = await farm_profile_repository.save(profile_document)
    return FarmProfile.model_validate(
        {
            **profile_document.user_language.model_dump(mode="json"),
            "id": farm_id,
            "user_id": user_id,
            "created_at": profile_document.created_at,
            "updated_at": profile_document.updated_at,
        }
    )


async def delete_farm_profile(farm_id: str, user_id: str) -> bool:
    return await farm_profile_repository.delete(farm_id=farm_id, user_id=user_id)


async def _list_all_farms(user_id: str, limit: int = 100) -> list[FarmProfile]:
    return await farm_profile_repository.list_by_user(
        user_id=user_id,
        language=PersistenceLanguage.ENGLISH,
        limit=limit,
    )


async def _get_farm_profile(farm_id: str, user_id: str) -> FarmProfile | None:
    return await farm_profile_repository.get_by_id(
        farm_id=farm_id,
        user_id=user_id,
        language=PersistenceLanguage.ENGLISH,
    )


async def _create_translated_farm_profile(
    *,
    user_id: str,
    english: FarmProfileFields,
    user_language: FarmProfileFields,
) -> FarmProfileDocument:
    profile_document = FarmProfileDocument(
        user_id=user_id,
        english=english,
        user_language=user_language,
    )
    profile_document = await farm_profile_repository.create(profile_document)
    return profile_document


async def _update_farm_profile(
    *,
    farm_id: str,
    user_id: str,
    fields: FarmProfileFields,
) -> FarmProfile:
    profile_document = FarmProfileDocument(
        id=farm_id,
        user_id=user_id,
        english=fields,
        user_language=await translation_service.to_user_language(
            user_id=user_id, fields=fields
        ),
    )
    profile_document = await farm_profile_repository.save(profile_document)
    return FarmProfile.model_validate(
        {
            **profile_document.english.model_dump(mode="json"),
            "id": farm_id,
            "user_id": user_id,
            "created_at": profile_document.created_at,
            "updated_at": profile_document.updated_at,
        }
    )


async def _update_translated_farm_profile(
    *,
    farm_id: str,
    user_id: str,
    english: FarmProfileFields,
    user_language: FarmProfileFields,
) -> FarmProfileDocument:
    profile_document = FarmProfileDocument(
        id=farm_id,
        user_id=user_id,
        english=english,
        user_language=user_language,
    )
    profile_document = await farm_profile_repository.save(profile_document)
    return profile_document
