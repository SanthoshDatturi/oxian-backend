from fastapi import APIRouter, Depends, HTTPException

from app.core.security import authenticate_rest
from app.schemas.notification import (
    DeviceRegistration,
    DeviceRegistrationInput,
    DeviceTokenRefreshInput,
)
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


def _get_user_id(user_payload: dict) -> str:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")
    return user_id


@router.post("/devices", response_model=DeviceRegistration, status_code=201)
async def register_device(
    payload: DeviceRegistrationInput,
    user_payload: dict = Depends(authenticate_rest),
) -> DeviceRegistration:
    user_id = _get_user_id(user_payload)
    return await notification_service.register_device(user_id=user_id, payload=payload)


@router.patch("/devices/{device_id}", response_model=DeviceRegistration)
async def refresh_device_registration(
    device_id: str,
    payload: DeviceTokenRefreshInput,
    user_payload: dict = Depends(authenticate_rest),
) -> DeviceRegistration:
    user_id = _get_user_id(user_payload)
    try:
        return await notification_service.refresh_device_registration(
            user_id=user_id,
            device_id=device_id,
            payload=payload,
        )
    except LookupError as exc:
        raise HTTPException(
            status_code=404, detail="Device registration not found"
        ) from exc


@router.delete("/devices/{device_id}", status_code=204)
async def deregister_device(
    device_id: str,
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    deleted = await notification_service.deregister_device(
        user_id=user_id,
        device_id=device_id,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Device registration not found")
    return
