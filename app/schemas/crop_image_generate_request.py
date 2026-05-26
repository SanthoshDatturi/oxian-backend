import time
from uuid import uuid4

from pydantic import AliasChoices, Field

from .crop_image import BaseCropImageFields


class CropImageGenerateRequest(BaseCropImageFields):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
        description="The unique identifier for the crop image generation request.",
    )
    image_file_id: str = Field(
        ..., description="The ID of the image file to be generated."
    )
    created_at: float = Field(
        default_factory=time.time,
    )

