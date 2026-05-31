from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.dependencies import authenticate_rest
from app.schemas.crop_recommendation import CropRecommendation, CropRecommendationRequest
from app.services import crop_recommendation_service

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
    _get_user_id(user_payload)
    return await crop_recommendation_service.list_recommendations(
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
    _get_user_id(user_payload)
    recommendation = await crop_recommendation_service.get_recommendation(
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
    _get_user_id(user_payload)
    deleted = await crop_recommendation_service.delete_recommendation(
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
    _get_user_id(user_payload)
    count = await crop_recommendation_service.delete_all_recommendations_for_farm(
        farm_id=farm_id,
    )
    return {"deleted_count": count}
