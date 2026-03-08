from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.dependencies import authenticate_rest
from app.repositories import farm_profile_repository
from app.schemas.farm_profile import (
    Area,
    FarmProfile,
    IrrigationSystem,
    Location,
    PreviousCrops,
    SoilTestProperties,
    SoilType,
    WaterSource,
)

router = APIRouter(prefix="/farm-profiles", tags=["Farm Profiles"])


class FarmProfileInput(BaseModel):
    name: str
    location: Location
    soil_type: SoilType
    total_area: Area
    cultivated_area: Area
    water_source: WaterSource
    irrigation_system: IrrigationSystem | None = None
    crops: list[PreviousCrops] | None = None
    soil_test_properties: SoilTestProperties | None = None


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
    return await farm_profile_repository.list_by_user(user_id)


@router.get("/{farm_id}", response_model=FarmProfile)
async def get_farm_profile(
    farm_id: str,
    user_payload: dict = Depends(authenticate_rest),
) -> FarmProfile:
    user_id = _get_user_id(user_payload)
    profile = await farm_profile_repository.get_by_id(farm_id, user_id=user_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Farm profile not found")
    return profile


@router.post("/", response_model=FarmProfile, status_code=201)
async def create_farm_profile(
    payload: FarmProfileInput,
    user_payload: dict = Depends(authenticate_rest),
) -> FarmProfile:
    user_id = _get_user_id(user_payload)
    profile = FarmProfile(user_id=user_id, **payload.model_dump(mode="json"))
    return await farm_profile_repository.create(profile)


@router.put("/{farm_id}", response_model=FarmProfile)
async def update_farm_profile(
    farm_id: str,
    payload: FarmProfileInput,
    user_payload: dict = Depends(authenticate_rest),
) -> FarmProfile:
    user_id = _get_user_id(user_payload)
    existing = await farm_profile_repository.get_by_id(farm_id, user_id=user_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="Farm profile not found")

    profile = FarmProfile(
        id=farm_id,
        user_id=user_id,
        **payload.model_dump(mode="json"),
    )
    return await farm_profile_repository.save(profile)


@router.delete("/{farm_id}", status_code=204)
async def delete_farm_profile(
    farm_id: str,
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    deleted = await farm_profile_repository.delete(farm_id, user_id=user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Farm profile not found")
    return
