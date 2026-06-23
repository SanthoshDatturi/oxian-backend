from datetime import datetime, timezone

from app.infrastructure.database.collections import get_farm_profiles_collection
from app.schemas.farm_profile import (
    FarmProfile,
    FarmProfileDocument,
    FarmProfileInputInvariantFields,
    FarmProfileInvariantFields,
    FarmProfileTranslatableFields,
)
from app.schemas.generic_types import PersistenceLanguage


def _to_farm_profile(
    document: dict,
    language: PersistenceLanguage,
) -> FarmProfile:
    translatable_fields = document.get(language.value) or {}
    invariant_data = dict(document)
    for key in FarmProfileInputInvariantFields.model_fields:
        value = document.get(key, translatable_fields.get(key))
        if value is not None:
            invariant_data[key] = value
    invariant_fields = FarmProfileInvariantFields.model_validate(invariant_data)
    return FarmProfile.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields,
        }
    )


def _touch(profile: FarmProfileDocument) -> FarmProfileDocument:
    return profile.model_copy(update={"updated_at": datetime.now(timezone.utc)})


async def create(profile: FarmProfileDocument) -> FarmProfileDocument:
    profile = _touch(profile)
    await get_farm_profiles_collection().insert_one(
        profile.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return profile


async def save(profile: FarmProfileDocument) -> FarmProfileDocument:
    existing = await get_farm_profiles_collection().find_one(
        {"_id": profile.id},
        {"created_at": 1},
    )
    if existing and existing.get("created_at") is not None:
        profile = profile.model_copy(update={"created_at": existing["created_at"]})
    profile = _touch(profile)
    await get_farm_profiles_collection().replace_one(
        {"_id": profile.id},
        profile.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return profile


async def save_language(
    profile: FarmProfile,
    language: PersistenceLanguage,
) -> FarmProfile:
    profile = profile.model_copy(update={"updated_at": datetime.now(timezone.utc)})
    translatable_fields = FarmProfileTranslatableFields.model_validate(
        profile
    ).model_dump(exclude_none=True, mode="json")
    invariant_fields = FarmProfileInputInvariantFields.model_validate(
        profile
    ).model_dump(exclude_none=True, mode="json")
    await get_farm_profiles_collection().update_one(
        {"_id": profile.id, "user_id": profile.user_id},
        {
            "$set": {
                "user_id": profile.user_id,
                **invariant_fields,
                "updated_at": profile.updated_at,
                language.value: translatable_fields,
            },
            "$setOnInsert": {"created_at": profile.created_at},
        },
        upsert=True,
    )
    return profile


async def get_by_id(
    farm_id: str,
    language: PersistenceLanguage,
    user_id: str | None = None,
) -> FarmProfile | None:
    query: dict[str, str] = {"_id": farm_id}
    if user_id:
        query["user_id"] = user_id
    projection = {
        "_id": 1,
        "user_id": 1,
        "soil_type": 1,
        "total_area": 1,
        "cultivated_area": 1,
        "water_source": 1,
        "irrigation_system": 1,
        "soil_test_properties": 1,
        "created_at": 1,
        "updated_at": 1,
        language.value: 1,
    }
    document = await get_farm_profiles_collection().find_one(query, projection)
    if not document:
        return None
    return _to_farm_profile(document, language)


async def exists_by_id(farm_id: str, user_id: str) -> bool:
    document = await get_farm_profiles_collection().find_one(
        {"_id": farm_id, "user_id": user_id},
        {"_id": 1},
    )
    return document is not None


async def list_by_user(
    user_id: str,
    language: PersistenceLanguage,
    limit: int = 100,
) -> list[FarmProfile]:
    projection = {
        "_id": 1,
        "user_id": 1,
        "soil_type": 1,
        "total_area": 1,
        "cultivated_area": 1,
        "water_source": 1,
        "irrigation_system": 1,
        "soil_test_properties": 1,
        "created_at": 1,
        "updated_at": 1,
        language.value: 1,
    }
    cursor = (
        get_farm_profiles_collection()
        .find({"user_id": user_id}, projection)
        .sort(f"{language.value}.name", 1)
        .limit(limit)
    )
    return [_to_farm_profile(document, language) async for document in cursor]


async def delete(farm_id: str, user_id: str | None = None) -> bool:
    query: dict[str, str] = {"_id": farm_id}
    if user_id:
        query["user_id"] = user_id
    result = await get_farm_profiles_collection().delete_one(query)
    return result.deleted_count > 0
