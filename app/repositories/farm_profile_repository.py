from app.integrations.database.mogodb import get_farm_profiles_collection
from app.schemas.farm_profile import FarmProfile


async def create(profile: FarmProfile) -> FarmProfile:
    await get_farm_profiles_collection().insert_one(
        profile.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return profile


async def save(profile: FarmProfile) -> FarmProfile:
    await get_farm_profiles_collection().replace_one(
        {"_id": profile.id},
        profile.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return profile


async def get_by_id(farm_id: str, user_id: str | None = None) -> FarmProfile | None:
    query: dict[str, str] = {"_id": farm_id}
    if user_id:
        query["user_id"] = user_id
    document = await get_farm_profiles_collection().find_one(query)
    if not document:
        return None
    return FarmProfile.model_validate(document)


async def list_by_user(user_id: str, limit: int = 100) -> list[FarmProfile]:
    cursor = (
        get_farm_profiles_collection()
        .find({"user_id": user_id})
        .sort("name", 1)
        .limit(limit)
    )
    return [FarmProfile.model_validate(document) async for document in cursor]


async def delete(farm_id: str, user_id: str | None = None) -> bool:
    query: dict[str, str] = {"_id": farm_id}
    if user_id:
        query["user_id"] = user_id
    result = await get_farm_profiles_collection().delete_one(query)
    return result.deleted_count > 0
