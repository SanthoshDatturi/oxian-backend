from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import authenticate_rest
from app.schemas.farm_profile import FarmProfile, FarmProfileInput
from app.services import farm_profile_service

router = APIRouter(prefix="/farm-profiles", tags=["Farm Profiles"])


def _get_user_id(user_payload: dict) -> str:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return user_id


@router.get("/", response_model=list[FarmProfile])
async def list_farm_profiles(
    user_payload: dict = Depends(authenticate_rest),
) -> list[FarmProfile]:
    user_id = _get_user_id(user_payload)
    return await farm_profile_service.list_all_farms(user_id)


@router.get("/{farm_id}", response_model=FarmProfile)
async def get_farm_profile(
    farm_id: str,
    user_payload: dict = Depends(authenticate_rest),
) -> FarmProfile:
    user_id = _get_user_id(user_payload)
    profile = await farm_profile_service.get_farm_profile(farm_id, user_id=user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Farm profile not found")
    return profile


@router.post("/", response_model=FarmProfile, status_code=201)
async def create_farm_profile(
    input: FarmProfileInput,
    user_payload: dict = Depends(authenticate_rest),
) -> FarmProfile:
    user_id = _get_user_id(user_payload)
    return await farm_profile_service.create_farm_profile(
        user_id=user_id,
        input=input,
    )


@router.put("/{farm_id}", response_model=FarmProfile)
async def update_farm_profile(
    farm_id: str,
    input: FarmProfileInput,
    user_payload: dict = Depends(authenticate_rest),
) -> FarmProfile:
    user_id = _get_user_id(user_payload)
    existing = await farm_profile_service.get_farm_profile(farm_id, user_id=user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Farm profile not found")

    return await farm_profile_service.update_farm_profile(
        farm_id=farm_id,
        user_id=user_id,
        input=input,
    )


@router.delete("/{farm_id}", status_code=204)
async def delete_farm_profile(
    farm_id: str,
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    deleted = await farm_profile_service.delete_farm_profile(farm_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Farm profile not found")
    return
