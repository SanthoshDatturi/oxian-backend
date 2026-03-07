from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class LatLang(BaseModel):
    latitude: float | None = Field(
        default=None,
        description="The latitude in degrees. It must be in the range [-90.0, +90.0].",
    )
    longitude: float | None = Field(
        default=None,
        description="The longitude in degrees. It must be in the range [-180.0, +180.0].",
    )


class Event(StrEnum):
    START = "start"
    RESUME = "resume"
    RETRY = "retry"
    STOP = "stop"


class Service(StrEnum):
    CHAT = "chat"
    CROP_RECOMMENDATION = "crop_recommendation"


class WebSocketInboundMessage(BaseModel):
    service: Service = Field(description="Which service is requested by the user.")
    event: Event
    data: dict[str, Any]


class WebSocketOutboundMessage(BaseModel):
    service: Service = Field(description="The service that produced this response.")
    data: dict[str, Any]


# Backward-compatible alias for the misspelled schema name already used in the repo.
WebScoketOutboundMessage = WebSocketOutboundMessage
