from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.security import authenticate_rest
from app.schemas.cultivation_crop import (
    CultivationCrop,
    CultivationCropInput,
    IntercroppingCultivation,
    IntercroppingCultivationInput,
)
from app.services import cultivation_crop_service
from app.services.crop_planning_service import CropPlan, generate_crop_plan

router = APIRouter(prefix="/cultivation-crops", tags=["Cultivation Crops"])


def _get_user_id(user_payload: dict) -> str:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return user_id


@router.get("/farms/{farm_id}", response_model=list[CultivationCrop])
async def list_cultivation_crops(
    farm_id: str,
    limit: int = Query(default=100, ge=1, le=100),
    user_payload: dict = Depends(authenticate_rest),
) -> list[CultivationCrop]:
    user_id = _get_user_id(user_payload)
    try:
        return await cultivation_crop_service.list_cultivation_crops(
            user_id=user_id,
            farm_id=farm_id,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post(
    "/farms/{farm_id}",
    response_model=CultivationCrop,
    status_code=201,
)
async def create_cultivation_crop(
    farm_id: str,
    input: CultivationCropInput,
    user_payload: dict = Depends(authenticate_rest),
) -> CultivationCrop:
    user_id = _get_user_id(user_payload)
    try:
        return await cultivation_crop_service.create_cultivation_crop(
            user_id=user_id,
            farm_id=farm_id,
            input=input,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/farms/{farm_id}/{crop_id}",
    response_model=CultivationCrop,
)
async def get_cultivation_crop(
    farm_id: str,
    crop_id: str,
    user_payload: dict = Depends(authenticate_rest),
) -> CultivationCrop:
    user_id = _get_user_id(user_payload)
    try:
        crop = await cultivation_crop_service.get_cultivation_crop(
            user_id=user_id,
            farm_id=farm_id,
            crop_id=crop_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if crop is None:
        raise HTTPException(status_code=404, detail="Cultivation crop not found")
    return crop


@router.put(
    "/farms/{farm_id}/{crop_id}",
    response_model=CultivationCrop,
)
async def update_cultivation_crop(
    farm_id: str,
    crop_id: str,
    input: CultivationCropInput,
    user_payload: dict = Depends(authenticate_rest),
) -> CultivationCrop:
    user_id = _get_user_id(user_payload)
    try:
        return await cultivation_crop_service.update_cultivation_crop(
            user_id=user_id,
            farm_id=farm_id,
            crop_id=crop_id,
            input=input,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/farms/{farm_id}/{crop_id}", status_code=204)
async def delete_cultivation_crop(
    farm_id: str,
    crop_id: str,
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    try:
        deleted = await cultivation_crop_service.delete_cultivation_crop(
            user_id=user_id,
            farm_id=farm_id,
            crop_id=crop_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not deleted:
        raise HTTPException(status_code=404, detail="Cultivation crop not found")
    return


@router.post(
    "/farms/{farm_id}/intercropping",
    response_model=IntercroppingCultivation,
    status_code=201,
)
async def create_intercropping_cultivation(
    farm_id: str,
    input: IntercroppingCultivationInput,
    user_payload: dict = Depends(authenticate_rest),
) -> IntercroppingCultivation:
    user_id = _get_user_id(user_payload)
    try:
        return await cultivation_crop_service.create_intercropping_cultivation(
            user_id=user_id,
            farm_id=farm_id,
            input=input,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put(
    "/farms/{farm_id}/intercropping/{intercropping_id}",
    response_model=IntercroppingCultivation,
)
async def update_intercropping_cultivation(
    farm_id: str,
    intercropping_id: str,
    input: IntercroppingCultivationInput,
    user_payload: dict = Depends(authenticate_rest),
) -> IntercroppingCultivation:
    user_id = _get_user_id(user_payload)
    try:
        return await cultivation_crop_service.update_intercropping_cultivation(
            user_id=user_id,
            farm_id=farm_id,
            intercropping_id=intercropping_id,
            input=input,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.delete("/farms/{farm_id}/intercropping/{intercropping_id}", status_code=204)
async def delete_intercropping_cultivation(
    farm_id: str,
    intercropping_id: str,
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    try:
        deleted = await cultivation_crop_service.delete_intercropping_cultivation(
            user_id=user_id,
            farm_id=farm_id,
            intercropping_id=intercropping_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    if not deleted:
        raise HTTPException(
            status_code=404,
            detail="Intercropping cultivation not found",
        )
    return


@router.post(
    "/farms/{farm_id}/{crop_id}/plan",
    response_model=CropPlan,
    status_code=202,
)
async def create_crop_plan(
    farm_id: str,
    crop_id: str,
    user_payload: dict = Depends(authenticate_rest),
) -> CropPlan:
    user_id = _get_user_id(user_payload)
    try:
        return await generate_crop_plan(
            user_id=user_id,
            farm_id=farm_id,
            crop_id=crop_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
