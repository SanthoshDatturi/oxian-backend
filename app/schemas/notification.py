import json
from datetime import datetime
from enum import StrEnum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

# ============================================================================
# ENUMS
# ============================================================================


class DevicePlatform(StrEnum):
    ANDROID = "android"
    IOS = "ios"


class NotificationTargetType(StrEnum):
    USER = "user"
    TOPIC = "topic"


class DestinationType(StrEnum):
    APP_ROUTE = "app_route"
    EXTERNAL_URL = "external_url"


class DeliveryStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class AndroidPriority(StrEnum):
    NORMAL = "normal"
    HIGH = "high"


class NotificationChannel(StrEnum):
    ALERTS = "alerts"
    UPDATES = "updates"


class ApnsInterruptionLevel(StrEnum):
    PASSIVE = "passive"
    ACTIVE = "active"
    TIME_SENSITIVE = "time-sensitive"
    CRITICAL = "critical"


class DataType(StrEnum):
    CROP_RECOMMENDATION = "crop_recommendation"


# ============================================================================
# TARGET
# ============================================================================


class NotificationTarget(BaseModel):
    """
    Device tokens are resolved internally
    by NotificationService.
    """

    type: NotificationTargetType

    user_id: Optional[UUID] = Field(default=None)

    topic: Optional[str] = Field(default=None)


# ============================================================================
# CONTENT
# ============================================================================


class NotificationContent(BaseModel):
    """
    Visible notification content.

    Maps to FCM/APNS notification payload.
    """

    title: str

    body: str

    image: Optional[HttpUrl] = Field(default=None)


# ============================================================================
# DESTINATION
# ============================================================================


class Destination(BaseModel):
    """
    Navigation target when the user taps
    the notification itself.
    """

    type: DestinationType

    url: Optional[HttpUrl] = Field(default=None)

    destination: Optional[str] = Field(default=None)

    params: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# ACTIONS
# ============================================================================


class NotificationAction(BaseModel):
    """
    Action button displayed inside
    notification UI.
    """

    id: str

    label: str

    payload: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# BUSINESS DATA
# ============================================================================


class NotificationData(BaseModel):
    """
    Actual business payload delivered
    to the application.
    """

    type: DataType

    fields: Dict[str, Any] = Field(default_factory=dict)


# ============================================================================
# ANDROID
# ============================================================================


class AndroidNotification(BaseModel):
    channel_id: NotificationChannel

    sound: Optional[str] = Field(default=None)

    sticky: bool = Field(default=False)

    notification_count: Optional[int] = Field(default=None)


class AndroidConfig(BaseModel):
    priority: AndroidPriority = Field(default=AndroidPriority.HIGH)

    ttl_seconds: Optional[int] = Field(default=None)

    collapse_key: Optional[str] = Field(default=None)

    notification: Optional[AndroidNotification] = Field(default=None)


# ============================================================================
# IOS / APNS
# ============================================================================


class ApnsSound(BaseModel):
    name: str

    critical: bool = Field(default=False)

    volume: Optional[float] = Field(default=None)


class ApnsAps(BaseModel):
    badge: Optional[int] = Field(default=None)

    sound: Optional[ApnsSound] = Field(default=None)

    content_available: bool = Field(default=False, alias="content-available")

    mutable_content: bool = Field(default=False, alias="mutable-content")

    interruption_level: Optional[ApnsInterruptionLevel] = Field(
        default=None, alias="interruption-level"
    )

    model_config = {"populate_by_name": True}


class ApnsConfig(BaseModel):
    aps: ApnsAps = Field(default_factory=ApnsAps)


# ============================================================================
# MAIN REQUEST
# ============================================================================


class NotificationRequest(BaseModel):
    """
    Canonical notification request used
    by all backend services.
    """

    target: NotificationTarget

    content: Optional[NotificationContent] = Field(default=None)

    destination: Optional[Destination] = Field(default=None)

    actions: List[NotificationAction] = Field(default_factory=list)

    data: Optional[NotificationData] = Field(default=None)

    android: Optional[AndroidConfig] = Field(default=None)

    apns: Optional[ApnsConfig] = Field(default=None)

    scheduled_at: Optional[datetime] = Field(default=None)


# ============================================================================
# DEVICE REGISTRATION
# ============================================================================


class DeviceRegistration(BaseModel):
    user_id: UUID

    device_token: str

    platform: DevicePlatform

    app_version: Optional[str] = Field(default=None)

    device_name: Optional[str] = Field(default=None)

    registered_at: datetime


# ============================================================================
# STORED NOTIFICATION
# ============================================================================


class NotificationRecord(BaseModel):
    id: UUID

    user_id: UUID

    title: str

    body: str

    is_read: bool = Field(default=False)

    read_at: Optional[datetime] = Field(default=None)

    delivery_status: DeliveryStatus

    created_at: datetime

    delivered_at: Optional[datetime] = Field(default=None)


# ============================================================================
# MAPPER
# ============================================================================


def to_fcm_payload(
    request: NotificationRequest,
) -> Dict[str, Any]:

    payload: Dict[str, Any] = {}

    if request.content:
        payload["notification"] = request.content.model_dump(
            exclude_none=True, mode="json"
        )

    fcm_data: Dict[str, str] = {}

    if request.destination:
        fcm_data["destination"] = json.dumps(
            request.destination.model_dump(exclude_none=True, mode="json")
        )

    if request.actions:
        fcm_data["actions"] = json.dumps(
            [
                action.model_dump(exclude_none=True, mode="json")
                for action in request.actions
            ]
        )

    if request.data:
        fcm_data["data"] = json.dumps(
            request.data.model_dump(exclude_none=True, mode="json")
        )

    if fcm_data:
        payload["data"] = fcm_data

    if request.target.type == NotificationTargetType.TOPIC:
        payload["topic"] = request.target.topic

    if request.android:
        android_dict = request.android.model_dump(exclude_none=True, mode="json")

        if request.android.ttl_seconds is not None:
            android_dict["ttl"] = f"{request.android.ttl_seconds}s"
            android_dict.pop("ttl_seconds", None)

        payload["android"] = android_dict

    if request.apns:
        payload["apns"] = {
            "payload": {
                "aps": request.apns.aps.model_dump(
                    by_alias=True, exclude_none=True, mode="json"
                )
            }
        }

    return payload
