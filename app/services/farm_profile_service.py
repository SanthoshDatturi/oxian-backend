from app.repositories import farm_profile_repository
from app.schemas.farm_profile import (
    FarmProfile,
    FarmProfileDocument,
    FarmProfileInput,
    FarmProfileInputInvariantFields,
    FarmProfileInvariantFields,
    FarmProfileTranslatableFields,
)
from app.schemas.generic_types import PersistenceLanguage
from app.services import translation_service


def _to_farm_profile(
    document: FarmProfileDocument,
    translatable_fields: FarmProfileTranslatableFields,
) -> FarmProfile:
    invariant_fields = FarmProfileInvariantFields.model_validate(document)
    return FarmProfile.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields.model_dump(mode="json"),
        }
    )


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


async def has_farm_access(farm_id: str, user_id: str) -> bool:
    return await farm_profile_repository.exists_by_id(
        farm_id=farm_id,
        user_id=user_id,
    )


async def create_farm_profile(
    *,
    user_id: str,
    input: FarmProfileInput,
) -> FarmProfile:
    input_invariant_fields = FarmProfileInputInvariantFields.model_validate(input)
    invariant_fields = FarmProfileInvariantFields(
        user_id=user_id,
        **input_invariant_fields.model_dump(),
    )
    translatable_fields = FarmProfileTranslatableFields.model_validate(input)
    profile_document = FarmProfileDocument(
        **invariant_fields.model_dump(),
        english=await translation_service.to_english(
            user_id=user_id, fields=translatable_fields
        ),
        user_language=translatable_fields,
    )
    profile_document = await farm_profile_repository.create(profile_document)
    return _to_farm_profile(
        profile_document,
        profile_document.user_language,
    )


async def update_farm_profile(
    *,
    farm_id: str,
    user_id: str,
    input: FarmProfileInput,
) -> FarmProfile:
    input_invariant_fields = FarmProfileInputInvariantFields.model_validate(input)
    invariant_fields = FarmProfileInvariantFields(
        id=farm_id,
        user_id=user_id,
        **input_invariant_fields.model_dump(),
    )
    translatable_fields = FarmProfileTranslatableFields.model_validate(input)
    profile_document = FarmProfileDocument(
        **invariant_fields.model_dump(),
        english=await translation_service.to_english(
            user_id=user_id, fields=translatable_fields
        ),
        user_language=translatable_fields,
    )
    profile_document = await farm_profile_repository.save(profile_document)
    return _to_farm_profile(
        profile_document,
        profile_document.user_language,
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
    invariant_fields: FarmProfileInvariantFields,
    english: FarmProfileTranslatableFields,
    user_language: FarmProfileTranslatableFields,
) -> FarmProfileDocument:
    profile_document = FarmProfileDocument(
        **invariant_fields.model_dump(),
        english=english,
        user_language=user_language,
    )
    profile_document = await farm_profile_repository.create(profile_document)
    return profile_document


async def _update_farm_profile(
    *,
    farm_id: str,
    user_id: str,
    input: FarmProfileInput,
) -> FarmProfile:
    input_invariant_fields = FarmProfileInputInvariantFields.model_validate(input)
    invariant_fields = FarmProfileInvariantFields(
        id=farm_id,
        user_id=user_id,
        **input_invariant_fields.model_dump(),
    )
    translatable_fields = FarmProfileTranslatableFields.model_validate(input)
    profile_document = FarmProfileDocument(
        **invariant_fields.model_dump(),
        english=translatable_fields,
        user_language=await translation_service.to_user_language(
            user_id=user_id, fields=translatable_fields
        ),
    )
    profile_document = await farm_profile_repository.save(profile_document)
    return _to_farm_profile(
        profile_document,
        profile_document.english,
    )


async def _update_translated_farm_profile(
    *,
    invariant_fields: FarmProfileInvariantFields,
    english: FarmProfileTranslatableFields,
    user_language: FarmProfileTranslatableFields,
) -> FarmProfileDocument:
    profile_document = FarmProfileDocument(
        **invariant_fields.model_dump(),
        english=english,
        user_language=user_language,
    )
    profile_document = await farm_profile_repository.save(profile_document)
    return profile_document
