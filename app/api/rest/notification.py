from fastapi import APIRouter, Depends

from app.api.dependencies import get_current_user_id
from app.core.errors import DeviceRegistrationNotFound
from app.schemas.notification import (
    DeviceRegistration,
    DeviceRegistrationInput,
    DeviceTokenRefreshInput,
)
from app.services import notification_service

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.post("/devices", response_model=DeviceRegistration, status_code=201)
async def register_device(
    payload: DeviceRegistrationInput,
    user_id: str = Depends(get_current_user_id),
) -> DeviceRegistration:
    return await notification_service.register_device(user_id=user_id, payload=payload)


@router.patch("/devices/{device_id}", response_model=DeviceRegistration)
async def refresh_device_registration(
    device_id: str,
    payload: DeviceTokenRefreshInput,
    user_id: str = Depends(get_current_user_id),
) -> DeviceRegistration:
    return await notification_service.refresh_device_registration(
        user_id=user_id,
        device_id=device_id,
        payload=payload,
    )


@router.delete("/devices/{device_id}", status_code=204)
async def deregister_device(
    device_id: str,
    user_id: str = Depends(get_current_user_id),
):
    deleted = await notification_service.deregister_device(
        user_id=user_id,
        device_id=device_id,
    )
    if not deleted:
        raise DeviceRegistrationNotFound(device_id)
    return
