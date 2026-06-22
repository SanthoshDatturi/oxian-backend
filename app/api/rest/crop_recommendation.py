from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from app.core.security import authenticate_rest
from app.schemas.crop_recommendation import (
    CropRecommendation,
    CropRecommendationRequest,
    SelectCropRequest,
)
from app.schemas.cultivation_crop import CultivationCrop
from app.schemas.intercropping_details import IntercroppingDetails
from app.services import crop_recommendation_service, cultivation_crop_service


class SelectCropResponse(BaseModel):
    crops: list[CultivationCrop]
    intercropping_details: IntercroppingDetails | None


router = APIRouter(prefix="/crop-recommendations", tags=["Crop Recommendations"])


def _get_user_id(user_payload: dict) -> str:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return user_id


@router.post(
    "/farms/{farm_id}/generate",
    response_model=CropRecommendation,
    status_code=201,
)
async def generate_recommendation(
    farm_id: str,
    payload: CropRecommendationRequest,
    user_payload: dict = Depends(authenticate_rest),
) -> CropRecommendation:
    user_id = _get_user_id(user_payload)
    try:
        return await crop_recommendation_service.generate_crop_recommendation(
            user_id=user_id,
            farm_id=farm_id,
            request=payload,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get(
    "/farms/{farm_id}",
    response_model=list[CropRecommendation],
)
async def list_recommendations(
    farm_id: str,
    limit: int = Query(default=20, ge=1, le=100),
    user_payload: dict = Depends(authenticate_rest),
) -> list[CropRecommendation]:
    user_id = _get_user_id(user_payload)
    return await crop_recommendation_service.list_recommendations(
        user_id=user_id,
        farm_id=farm_id,
        limit=limit,
    )


@router.get(
    "/{recommendation_id}",
    response_model=CropRecommendation,
)
async def get_recommendation(
    recommendation_id: str,
    farm_id: str | None = Query(default=None),
    user_payload: dict = Depends(authenticate_rest),
) -> CropRecommendation:
    user_id = _get_user_id(user_payload)
    recommendation = await crop_recommendation_service.get_recommendation(
        user_id=user_id,
        recommendation_id=recommendation_id,
        farm_id=farm_id,
    )
    if recommendation is None:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return recommendation


@router.delete("/{recommendation_id}", status_code=204)
async def delete_recommendation(
    recommendation_id: str,
    farm_id: str | None = Query(default=None),
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    deleted = await crop_recommendation_service.delete_recommendation(
        user_id=user_id,
        recommendation_id=recommendation_id,
        farm_id=farm_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Recommendation not found")
    return


@router.delete("/farms/{farm_id}", status_code=200)
async def delete_all_recommendations(
    farm_id: str,
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    count = await crop_recommendation_service.delete_all_recommendations_for_farm(
        user_id=user_id,
        farm_id=farm_id,
    )
    return {"deleted_count": count}


@router.post(
    "/{recommendation_id}/farms/{farm_id}/select",
    response_model=SelectCropResponse,
    status_code=201,
)
async def select_mono_crop(
    recommendation_id: str,
    farm_id: str,
    payload: SelectCropRequest,
    user_payload: dict = Depends(authenticate_rest),
) -> SelectCropResponse:
    user_id = _get_user_id(user_payload)
    try:
        crop = await crop_recommendation_service.select_mono_crop_from_recommendation(
            user_id=user_id,
            farm_id=farm_id,
            recommendation_id=recommendation_id,
            crop_id=payload.crop_id,
            selected_area=payload.selected_area,
        )
        return SelectCropResponse(
            crops=[
                cultivation_crop_service._to_cultivation_crop(crop, crop.user_language)
            ],
            intercropping_details=None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post(
    "/{recommendation_id}/farms/{farm_id}/select/intercrop/{intercrop_id}",
    response_model=SelectCropResponse,
    status_code=201,
)
async def select_intercrop(
    recommendation_id: str,
    farm_id: str,
    intercrop_id: str,
    payload: list[SelectCropRequest],
    user_payload: dict = Depends(authenticate_rest),
) -> SelectCropResponse:
    user_id = _get_user_id(user_payload)
    try:
        (
            crops,
            details,
        ) = await crop_recommendation_service.select_intercrop_from_recommendation(
            user_id=user_id,
            farm_id=farm_id,
            recommendation_id=recommendation_id,
            intercrop_id=intercrop_id,
            payload=payload,
        )
        return SelectCropResponse(
            crops=[
                cultivation_crop_service._to_cultivation_crop(c, c.user_language)
                for c in crops
            ],
            intercropping_details=cultivation_crop_service._to_intercropping_details(
                details, details.user_language
            )
            if details
            else None,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
