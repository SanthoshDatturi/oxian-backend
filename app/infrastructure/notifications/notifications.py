import json
from datetime import timedelta
from typing import Any

from fastapi.concurrency import run_in_threadpool
from firebase_admin import messaging

from app.infrastructure.providers.firebase import initialize_firebase
from app.schemas.notification import (
    AndroidPriority,
    ApnsSound,
    NotificationRequest,
)


class NotificationProviderError(Exception):
    """Raised when Firebase messaging fails."""


def _build_notification(request: NotificationRequest) -> messaging.Notification | None:
    if request.content is None:
        return None

    return messaging.Notification(
        title=request.content.title,
        body=request.content.body,
        image=str(request.content.image) if request.content.image else None,
    )


def _build_data(request: NotificationRequest) -> dict[str, str]:
    data: dict[str, str] = {}

    if request.destination:
        data["destination"] = json.dumps(
            request.destination.model_dump(exclude_none=True, mode="json")
        )

    if request.actions:
        data["actions"] = json.dumps(
            [
                action.model_dump(exclude_none=True, mode="json")
                for action in request.actions
            ]
        )

    if request.data:
        data["data"] = json.dumps(request.data.model_dump(exclude_none=True, mode="json"))

    return data


def _build_android_config(
    request: NotificationRequest,
) -> messaging.AndroidConfig | None:
    if request.android is None:
        return None

    android_notification = None
    if request.android.notification is not None:
        android_notification = messaging.AndroidNotification(
            channel_id=str(request.android.notification.channel_id),
            sound=request.android.notification.sound,
            sticky=request.android.notification.sticky,
            notification_count=request.android.notification.notification_count,
        )

    ttl = (
        timedelta(seconds=request.android.ttl_seconds)
        if request.android.ttl_seconds is not None
        else None
    )
    priority = "high" if request.android.priority == AndroidPriority.HIGH else "normal"

    return messaging.AndroidConfig(
        collapse_key=request.android.collapse_key,
        priority=priority,
        ttl=ttl,
        notification=android_notification,
    )


def _build_apns_sound(sound: ApnsSound) -> str | messaging.CriticalSound:
    if sound.critical:
        return messaging.CriticalSound(
            name=sound.name,
            critical=True,
            volume=sound.volume,
        )
    return sound.name


def _build_apns_config(request: NotificationRequest) -> messaging.APNSConfig | None:
    if request.apns is None:
        return None

    aps = request.apns.aps
    aps_payload: dict[str, Any] = {}

    if aps.badge is not None:
        aps_payload["badge"] = aps.badge
    if aps.sound is not None:
        aps_payload["sound"] = _build_apns_sound(aps.sound)
    if aps.content_available:
        aps_payload["content_available"] = aps.content_available
    if aps.mutable_content:
        aps_payload["mutable_content"] = aps.mutable_content

    apns_payload = messaging.APNSPayload(aps=messaging.Aps(**aps_payload))
    headers: dict[str, str] = {}
    if aps.interruption_level is not None:
        headers["interruption-level"] = aps.interruption_level.value

    return messaging.APNSConfig(
        headers=headers or None,
        payload=apns_payload,
    )


async def send_to_tokens(
    request: NotificationRequest,
    tokens: list[str],
) -> messaging.BatchResponse:
    if not tokens:
        raise NotificationProviderError("At least one device token is required.")

    app = initialize_firebase()
    multicast_message = messaging.MulticastMessage(
        tokens=tokens,
        data=_build_data(request) or None,
        notification=_build_notification(request),
        android=_build_android_config(request),
        apns=_build_apns_config(request),
    )

    try:
        return await run_in_threadpool(
            messaging.send_each_for_multicast,
            multicast_message,
            False,
            app,
        )
    except Exception as exc:
        raise NotificationProviderError("Failed to send push notification.") from exc


async def send_to_topic(
    request: NotificationRequest,
) -> str:
    if not request.target.topic:
        raise NotificationProviderError("A topic name is required.")

    app = initialize_firebase()
    message = messaging.Message(
        topic=request.target.topic,
        data=_build_data(request) or None,
        notification=_build_notification(request),
        android=_build_android_config(request),
        apns=_build_apns_config(request),
    )

    try:
        return await run_in_threadpool(messaging.send, message, False, app)
    except Exception as exc:
        raise NotificationProviderError("Failed to send push notification.") from exc
