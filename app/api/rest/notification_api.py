from fastapi import APIRouter, Depends, HTTPException

from app.core.dependencies import authenticate_rest
from app.schemas.notification import DeviceRegistration, DeviceRegistrationInput
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


@router.delete("/devices/{device_token}", status_code=204)
async def deregister_device(
    device_token: str,
    user_payload: dict = Depends(authenticate_rest),
):
    user_id = _get_user_id(user_payload)
    deleted = await notification_service.deregister_device(
        user_id=user_id,
        device_token=device_token,
    )
    if not deleted:
        raise HTTPException(status_code=404, detail="Device registration not found")
    return
