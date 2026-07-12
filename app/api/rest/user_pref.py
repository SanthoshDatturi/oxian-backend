from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import get_current_user_id
from app.repositories import user_pref_repository
from app.schemas.user_pref import UserPreference

router = APIRouter(prefix="/user-preferences", tags=["User Preferences"])


class UserPreferenceUpdate(BaseModel):
    language_code: str | None = None
    voice_response_enabled: bool | None = None


@router.get("/", response_model=UserPreference)
async def get_user_preference(
    user_id: str = Depends(get_current_user_id),
) -> UserPreference:
    preference = await user_pref_repository.get_by_user_id(user_id)
    if preference is None:
        return UserPreference(user_id=user_id)
    return preference


@router.put("/", response_model=UserPreference)
async def update_user_preference(
    payload: UserPreferenceUpdate,
    user_id: str = Depends(get_current_user_id),
) -> UserPreference:
    existing = await user_pref_repository.get_by_user_id(user_id)

    if existing is None:
        preference = UserPreference(user_id=user_id)
    else:
        preference = existing

    updates = payload.model_dump(exclude_unset=True)
    preference = preference.model_copy(update=updates)
    return await user_pref_repository.save(preference)
