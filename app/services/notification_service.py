import logging
import time

from app.integrations.notifications.provider import (
    NotificationProviderError,
    notification_provider,
)
from app.repositories import notification_repository
from app.schemas.notification import (
    DeliveryStatus,
    DeviceRegistration,
    DeviceRegistrationInput,
    NotificationRecord,
    NotificationRequest,
    NotificationTargetType,
)

logger = logging.getLogger(__name__)


def _now() -> float:
    return time.time()


async def register_device(
    *,
    user_id: str,
    payload: DeviceRegistrationInput,
) -> DeviceRegistration:
    registration = DeviceRegistration(
        user_id=user_id,
        device_token=payload.device_token,
        platform=payload.platform,
        app_version=payload.app_version,
        device_name=payload.device_name,
        registered_at=_now(),
    )
    return await notification_repository.upsert_device_registration(registration)


async def deregister_device(
    *,
    user_id: str,
    device_token: str,
) -> bool:
    return await notification_repository.delete_device_registration(
        device_token=device_token,
        user_id=user_id,
    )


async def _create_notification_record(
    *,
    user_id: str,
    request: NotificationRequest,
    delivery_status: DeliveryStatus,
    delivered_at: float | None = None,
) -> NotificationRecord:
    if request.content is None:
        raise ValueError("Notification content is required.")

    record = NotificationRecord(
        user_id=user_id,
        title=request.content.title,
        body=request.content.body,
        delivery_status=delivery_status,
        delivered_at=delivered_at,
    )
    return await notification_repository.create_notification_record(record)


async def send_notification(request: NotificationRequest) -> NotificationRecord | None:
    if request.content is None:
        raise ValueError("Notification content is required.")

    if request.target.type == NotificationTargetType.TOPIC:
        await notification_provider.send_to_topic(request)
        return None

    if request.target.user_id is None:
        raise ValueError("A user target requires user_id.")

    user_id = request.target.user_id
    registrations = await notification_repository.list_device_registrations(user_id)
    tokens = [
        registration.device_token
        for registration in registrations
        if registration.device_token
    ]

    if not tokens:
        return await _create_notification_record(
            user_id=user_id,
            request=request,
            delivery_status=DeliveryStatus.FAILED,
        )

    try:
        response = await notification_provider.send_to_tokens(request, tokens)
    except NotificationProviderError:
        logger.exception("Push notification delivery failed for user_id=%s", user_id)
        return await _create_notification_record(
            user_id=user_id,
            request=request,
            delivery_status=DeliveryStatus.FAILED,
        )

    delivery_status = (
        DeliveryStatus.SENT if response.success_count > 0 else DeliveryStatus.FAILED
    )
    delivered_at = _now() if response.success_count > 0 else None
    return await _create_notification_record(
        user_id=user_id,
        request=request,
        delivery_status=delivery_status,
        delivered_at=delivered_at,
    )
