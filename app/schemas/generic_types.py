from pydantic import BaseModel, Field


class LatLang(BaseModel):
    latitude: float = Field(
        description="The latitude in degrees. It must be in the range [-90.0, +90.0].",
    )
    longitude: float = Field(
        description="The longitude in degrees. It must be in the range [-180.0, +180.0].",
    )
