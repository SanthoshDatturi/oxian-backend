from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import authenticate_rest
from app.repositories import user_pref_repository
from app.schemas.user_pref import UserPreference

router = APIRouter(prefix="/user-preferences", tags=["User Preferences"])


class UserPreferenceUpdate(BaseModel):
    language_code: str | None = None
    voice_response_enabled: bool | None = None


def _get_user_id(user_payload: dict) -> str:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return user_id


@router.get("/", response_model=UserPreference)
async def get_user_preference(
    user_payload: dict = Depends(authenticate_rest),
) -> UserPreference:
    user_id = _get_user_id(user_payload)
    preference = await user_pref_repository.get_by_user_id(user_id)
    if preference is None:
        return UserPreference(user_id=user_id)
    return preference


@router.put("/", response_model=UserPreference)
async def update_user_preference(
    payload: UserPreferenceUpdate,
    user_payload: dict = Depends(authenticate_rest),
) -> UserPreference:
    user_id = _get_user_id(user_payload)
    existing = await user_pref_repository.get_by_user_id(user_id)

    if existing is None:
        preference = UserPreference(user_id=user_id)
    else:
        preference = existing

    updates = payload.model_dump(exclude_unset=True)
    preference = preference.model_copy(update=updates)
    return await user_pref_repository.save(preference)
