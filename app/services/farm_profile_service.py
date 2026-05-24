import json

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.prompts.prompt_manager import PromptManager
from app.repositories import farm_profile_repository
from app.repositories import user_pref_repository
from app.schemas.farm_profile import (
    FarmProfile,
    FarmProfileFields,
    PersistenceFarmProfile,
    TranslatedFarmProfileFields,
)
from app.schemas.generic_types import PersistenceLanguage


async def _translate_farm_profile(
    *,
    user_id: str,
    fields: FarmProfileFields,
    source_language: PersistenceLanguage,
) -> TranslatedFarmProfileFields:
    preference = await user_pref_repository.get_by_user_id(user_id)
    user_language_code = preference.language_code if preference else None

    prompt = PromptManager.get_prompt(
        "farm_profile",
        source_language=source_language.value,
        user_language_code=user_language_code or "not set",
        farm_profile_json=json.dumps(fields.model_dump(mode="json"), indent=2),
        output_schema_json=json.dumps(
            TranslatedFarmProfileFields.model_json_schema(),
            indent=2,
        ),
    )
    model = ChatGoogleGenerativeAI(
        model=settings.GEMINI_CHAT_MODEL,
        temperature=0,
    ).with_structured_output(TranslatedFarmProfileFields)
    response = await model.ainvoke(prompt)
    if isinstance(response, TranslatedFarmProfileFields):
        return response
    return TranslatedFarmProfileFields.model_validate(response)


def _farm_profile(
    *,
    profile_id: str | None = None,
    user_id: str,
    fields: FarmProfileFields,
) -> FarmProfile:
    data = {**fields.model_dump(mode="json"), "user_id": user_id}
    if profile_id is not None:
        data["id"] = profile_id
    return FarmProfile.model_validate(data)


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
    translated = await _translate_farm_profile(
        user_id=user_id,
        fields=fields,
        source_language=PersistenceLanguage.USER_LANGUAGE,
    )
    persistence_profile = PersistenceFarmProfile(
        user_id=user_id,
        english=translated.english,
        user_language=translated.user_language,
    )
    await farm_profile_repository.create(persistence_profile)
    return _farm_profile(
        profile_id=persistence_profile.id,
        user_id=user_id,
        fields=translated.user_language,
    )


async def update_farm_profile(
    *,
    farm_id: str,
    user_id: str,
    fields: FarmProfileFields,
) -> FarmProfile:
    translated = await _translate_farm_profile(
        user_id=user_id,
        fields=fields,
        source_language=PersistenceLanguage.USER_LANGUAGE,
    )
    persistence_profile = PersistenceFarmProfile(
        id=farm_id,
        user_id=user_id,
        english=translated.english,
        user_language=translated.user_language,
    )
    await farm_profile_repository.save(persistence_profile)
    return _farm_profile(
        profile_id=farm_id,
        user_id=user_id,
        fields=translated.user_language,
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


async def _create_farm_profile(
    *,
    user_id: str,
    fields: FarmProfileFields,
) -> FarmProfile:
    translated = await _translate_farm_profile(
        user_id=user_id,
        fields=fields,
        source_language=PersistenceLanguage.ENGLISH,
    )
    persistence_profile = PersistenceFarmProfile(
        user_id=user_id,
        english=translated.english,
        user_language=translated.user_language,
    )
    await farm_profile_repository.create(persistence_profile)
    return _farm_profile(
        profile_id=persistence_profile.id,
        user_id=user_id,
        fields=translated.english,
    )


async def _create_translated_farm_profile(
    *,
    user_id: str,
    english: FarmProfileFields,
    user_language: FarmProfileFields,
) -> FarmProfile:
    persistence_profile = PersistenceFarmProfile(
        user_id=user_id,
        english=english,
        user_language=user_language,
    )
    await farm_profile_repository.create(persistence_profile)
    return _farm_profile(
        profile_id=persistence_profile.id,
        user_id=user_id,
        fields=user_language,
    )


async def _update_farm_profile(
    *,
    farm_id: str,
    user_id: str,
    fields: FarmProfileFields,
) -> FarmProfile:
    translated = await _translate_farm_profile(
        user_id=user_id,
        fields=fields,
        source_language=PersistenceLanguage.ENGLISH,
    )
    persistence_profile = PersistenceFarmProfile(
        id=farm_id,
        user_id=user_id,
        english=translated.english,
        user_language=translated.user_language,
    )
    await farm_profile_repository.save(persistence_profile)
    return _farm_profile(
        profile_id=farm_id,
        user_id=user_id,
        fields=translated.english,
    )


async def _update_translated_farm_profile(
    *,
    farm_id: str,
    user_id: str,
    english: FarmProfileFields,
    user_language: FarmProfileFields,
) -> FarmProfile:
    persistence_profile = PersistenceFarmProfile(
        id=farm_id,
        user_id=user_id,
        english=english,
        user_language=user_language,
    )
    await farm_profile_repository.save(persistence_profile)
    return _farm_profile(
        profile_id=farm_id,
        user_id=user_id,
        fields=user_language,
    )
