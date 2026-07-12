from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user_id
from app.core.errors import FarmProfileNotFound
from app.schemas.farm_profile import FarmProfile, FarmProfileInput
from app.services import farm_profile_service

router = APIRouter(prefix="/farm-profiles", tags=["Farm Profiles"])


@router.get("/", response_model=list[FarmProfile])
async def list_farm_profiles(
    user_id: str = Depends(get_current_user_id),
) -> list[FarmProfile]:
    return await farm_profile_service.list_all_farms(user_id)


@router.get("/{farm_id}", response_model=FarmProfile)
async def get_farm_profile(
    farm_id: str,
    user_id: str = Depends(get_current_user_id),
) -> FarmProfile:
    profile = await farm_profile_service.get_farm_profile(farm_id, user_id=user_id)
    if profile is None:
        raise FarmProfileNotFound(farm_id)
    return profile


@router.post("/", response_model=FarmProfile, status_code=201)
async def create_farm_profile(
    input: FarmProfileInput,
    user_id: str = Depends(get_current_user_id),
) -> FarmProfile:
    return await farm_profile_service.create_farm_profile(
        user_id=user_id,
        input=input,
    )


@router.put("/{farm_id}", response_model=FarmProfile)
async def update_farm_profile(
    farm_id: str,
    input: FarmProfileInput,
    user_id: str = Depends(get_current_user_id),
) -> FarmProfile:
    existing = await farm_profile_service.get_farm_profile(farm_id, user_id=user_id)
    if existing is None:
        raise FarmProfileNotFound(farm_id)

    return await farm_profile_service.update_farm_profile(
        farm_id=farm_id,
        user_id=user_id,
        input=input,
    )


@router.delete("/{farm_id}", status_code=204)
async def delete_farm_profile(
    farm_id: str,
    user_id: str = Depends(get_current_user_id),
):
    deleted = await farm_profile_service.delete_farm_profile(farm_id, user_id=user_id)
    if not deleted:
        raise FarmProfileNotFound(farm_id)
    return
