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
