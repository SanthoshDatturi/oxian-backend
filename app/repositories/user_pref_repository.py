import time

from app.integrations.database.mogodb import get_user_prefs_collection
from app.schemas.user_pref import UserPreference


def _touch(preference: UserPreference) -> UserPreference:
    return preference.model_copy(update={"updated_at": time.time()})


async def get_by_user_id(user_id: str) -> UserPreference | None:
    document = await get_user_prefs_collection().find_one({"user_id": user_id})
    if not document:
        return None
    return UserPreference.model_validate(document)


async def save(preference: UserPreference) -> UserPreference:
    preference = _touch(preference)
    await get_user_prefs_collection().replace_one(
        {"user_id": preference.user_id},
        preference.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return preference
