from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_current_user_id
from app.core.errors import CultivationCropNotFound, IntercroppingCultivationNotFound
from app.schemas.cultivation_crop import (
    CultivationCrop,
    CultivationCropInput,
    IntercroppingCultivation,
    IntercroppingCultivationInput,
)
from app.services import cultivation_crop_service
from app.services.crop_planning_service import CropPlan, generate_crop_plan

router = APIRouter(prefix="/cultivation-crops", tags=["Cultivation Crops"])


@router.get("/farms/{farm_id}", response_model=list[CultivationCrop])
async def list_cultivation_crops(
    farm_id: str,
    limit: int = Query(default=100, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
) -> list[CultivationCrop]:
    return await cultivation_crop_service.list_cultivation_crops(
        user_id=user_id,
        farm_id=farm_id,
        limit=limit,
    )


@router.post(
    "/farms/{farm_id}",
    response_model=CultivationCrop,
    status_code=201,
)
async def create_cultivation_crop(
    farm_id: str,
    input: CultivationCropInput,
    user_id: str = Depends(get_current_user_id),
) -> CultivationCrop:
    return await cultivation_crop_service.create_cultivation_crop(
        user_id=user_id,
        farm_id=farm_id,
        input=input,
    )


@router.get(
    "/farms/{farm_id}/{crop_id}",
    response_model=CultivationCrop,
)
async def get_cultivation_crop(
    farm_id: str,
    crop_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CultivationCrop:
    crop = await cultivation_crop_service.get_cultivation_crop(
        user_id=user_id,
        farm_id=farm_id,
        crop_id=crop_id,
    )
    if crop is None:
        raise CultivationCropNotFound(crop_id)
    return crop


@router.put(
    "/farms/{farm_id}/{crop_id}",
    response_model=CultivationCrop,
)
async def update_cultivation_crop(
    farm_id: str,
    crop_id: str,
    input: CultivationCropInput,
    user_id: str = Depends(get_current_user_id),
) -> CultivationCrop:
    return await cultivation_crop_service.update_cultivation_crop(
        user_id=user_id,
        farm_id=farm_id,
        crop_id=crop_id,
        input=input,
    )


@router.delete("/farms/{farm_id}/{crop_id}", status_code=204)
async def delete_cultivation_crop(
    farm_id: str,
    crop_id: str,
    user_id: str = Depends(get_current_user_id),
):
    deleted = await cultivation_crop_service.delete_cultivation_crop(
        user_id=user_id,
        farm_id=farm_id,
        crop_id=crop_id,
    )
    if not deleted:
        raise CultivationCropNotFound(crop_id)
    return


@router.post(
    "/farms/{farm_id}/intercropping",
    response_model=IntercroppingCultivation,
    status_code=201,
)
async def create_intercropping_cultivation(
    farm_id: str,
    input: IntercroppingCultivationInput,
    user_id: str = Depends(get_current_user_id),
) -> IntercroppingCultivation:
    return await cultivation_crop_service.create_intercropping_cultivation(
        user_id=user_id,
        farm_id=farm_id,
        input=input,
    )


@router.put(
    "/farms/{farm_id}/intercropping/{intercropping_id}",
    response_model=IntercroppingCultivation,
)
async def update_intercropping_cultivation(
    farm_id: str,
    intercropping_id: str,
    input: IntercroppingCultivationInput,
    user_id: str = Depends(get_current_user_id),
) -> IntercroppingCultivation:
    return await cultivation_crop_service.update_intercropping_cultivation(
        user_id=user_id,
        farm_id=farm_id,
        intercropping_id=intercropping_id,
        input=input,
    )


@router.delete("/farms/{farm_id}/intercropping/{intercropping_id}", status_code=204)
async def delete_intercropping_cultivation(
    farm_id: str,
    intercropping_id: str,
    user_id: str = Depends(get_current_user_id),
):
    deleted = await cultivation_crop_service.delete_intercropping_cultivation(
        user_id=user_id,
        farm_id=farm_id,
        intercropping_id=intercropping_id,
    )
    if not deleted:
        raise IntercroppingCultivationNotFound(intercropping_id)
    return


@router.post(
    "/farms/{farm_id}/{crop_id}/plan",
    response_model=CropPlan,
    status_code=202,
)
async def create_crop_plan(
    farm_id: str,
    crop_id: str,
    user_id: str = Depends(get_current_user_id),
) -> CropPlan:
    return await generate_crop_plan(
        user_id=user_id,
        farm_id=farm_id,
        crop_id=crop_id,
    )
