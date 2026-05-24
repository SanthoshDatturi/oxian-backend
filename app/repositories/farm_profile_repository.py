from app.integrations.database.mogodb import get_farm_profiles_collection
from app.schemas.farm_profile import FarmProfile, FarmProfileFields, PersistenceFarmProfile
from app.schemas.generic_types import PersistenceLanguage


def _to_farm_profile(
    document: dict,
    language: PersistenceLanguage,
) -> FarmProfile:
    fields = document.get(language.value) or {}
    return FarmProfile.model_validate(
        {
            **fields,
            "id": document["_id"],
            "user_id": document["user_id"],
        }
    )


async def create(profile: PersistenceFarmProfile) -> PersistenceFarmProfile:
    await get_farm_profiles_collection().insert_one(
        profile.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return profile


async def save(profile: PersistenceFarmProfile) -> PersistenceFarmProfile:
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
    fields = FarmProfileFields.model_validate(profile).model_dump(
        exclude_none=True, mode="json"
    )
    await get_farm_profiles_collection().update_one(
        {"_id": profile.id, "user_id": profile.user_id},
        {"$set": {"user_id": profile.user_id, language.value: fields}},
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
    projection = {"_id": 1, "user_id": 1, language.value: 1}
    document = await get_farm_profiles_collection().find_one(query, projection)
    if not document:
        return None
    return _to_farm_profile(document, language)


async def list_by_user(
    user_id: str,
    language: PersistenceLanguage,
    limit: int = 100,
) -> list[FarmProfile]:
    projection = {"_id": 1, "user_id": 1, language.value: 1}
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
