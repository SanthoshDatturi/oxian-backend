from enum import StrEnum
from typing import Optional

from pydantic import BaseModel, Field


class LatLang(BaseModel):
    latitude: Optional[float] = Field(
        default=None,
        description="""The latitude in degrees. It must be in the range [-90.0, +90.0].""",
    )
    longitude: Optional[float] = Field(
        default=None,
        description="""The longitude in degrees. It must be in the range [-180.0, +180.0]""",
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
    service: Service = Field(description="which service is requested by the user")
    event: Event
    data: dict


class WebScoketOutboundMessage(BaseModel):
    service: Service = Field(description="The service giving this response")
    data: dict
