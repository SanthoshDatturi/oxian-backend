import logging
from datetime import datetime, timezone

from firebase_admin import exceptions as firebase_exceptions
from firebase_admin import messaging

from app.core.errors import (
    DeviceRegistrationNotFound,
    ErrorCode,
    ExternalServiceFailed,
    ValidationFailed,
)
from app.infrastructure.notifications import (
    NotificationProviderError,
    send_to_tokens,
    send_to_topic,
)
from app.repositories import notification_repository
from app.schemas.notification import (
    DeliveryStatus,
    DeviceRegistration,
    DeviceRegistrationInput,
    DeviceTokenRefreshInput,
    NotificationRecord,
    NotificationRequest,
    NotificationTargetType,
)

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


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


async def refresh_device_registration(
    *,
    user_id: str,
    device_id: str,
    payload: DeviceTokenRefreshInput,
) -> DeviceRegistration:
    existing_registration = await notification_repository.get_device_registration_by_id(
        device_id
    )
    if existing_registration is None or existing_registration.user_id != user_id:
        raise DeviceRegistrationNotFound(device_id)

    registration = DeviceRegistration(
        id=device_id,
        user_id=user_id,
        device_token=payload.device_token,
        platform=existing_registration.platform,
        app_version=existing_registration.app_version,
        device_name=existing_registration.device_name,
        registered_at=_now(),
    )
    return await notification_repository.upsert_device_registration(registration)


async def deregister_device(
    *,
    user_id: str,
    device_id: str,
) -> bool:
    return await notification_repository.delete_device_registration_by_id(
        device_id=device_id,
        user_id=user_id,
    )


def _should_prune_registration(exception: Exception | None) -> bool:
    return isinstance(
        exception,
        (
            firebase_exceptions.NotFoundError,
            firebase_exceptions.InvalidArgumentError,
            messaging.SenderIdMismatchError,
        ),
    )


async def _create_notification_record(
    *,
    user_id: str,
    request: NotificationRequest,
    delivery_status: DeliveryStatus,
    delivered_at: datetime | None = None,
) -> NotificationRecord:
    if request.content is None:
        raise ValidationFailed(
            "Notification content is required.",
            code=ErrorCode.NOTIFICATION_CONTENT_REQUIRED,
        )

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
        raise ValidationFailed(
            "Notification content is required.",
            code=ErrorCode.NOTIFICATION_CONTENT_REQUIRED,
        )

    if request.target.type == NotificationTargetType.TOPIC:
        try:
            await send_to_topic(request)
        except NotificationProviderError as exc:
            logger.exception("Topic push notification delivery failed.")
            raise ExternalServiceFailed(
                "Failed to send topic push notification.",
                code=ErrorCode.EXTERNAL_SERVICE_FAILED,
            ) from exc
        return None

    if request.target.user_id is None:
        raise ValidationFailed(
            "A user target requires user_id.",
            code=ErrorCode.NOTIFICATION_TARGET_INVALID,
        )

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
        response = await send_to_tokens(request, tokens)
    except NotificationProviderError:
        logger.exception("Push notification delivery failed for user_id=%s", user_id)
        return await _create_notification_record(
            user_id=user_id,
            request=request,
            delivery_status=DeliveryStatus.FAILED,
        )

    stale_registration_ids = [
        registration.id
        for registration, send_response in zip(registrations, response.responses)
        if not send_response.success
        and _should_prune_registration(send_response.exception)
    ]
    if stale_registration_ids:
        deleted_count = (
            await notification_repository.delete_device_registrations_by_ids(
                stale_registration_ids,
                user_id=user_id,
            )
        )
        logger.info(
            "Pruned %s stale device registrations for user_id=%s",
            deleted_count,
            user_id,
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
