import time
from typing import List, Optional

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app.core.config import settings


class CropImageFile(BaseModel):
    id: str = Field(
        description="ID of the crop image File.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    crop_name: str = Field(
        description="Name of the crop associated with the image. Example: Rice"
    )
    embedding: List[float]
    aliases: Optional[List[str]] = Field(
        default=None, description="List of alternative names for the crop."
    )
    created_at: float = Field(default_factory=time.time)

    @field_validator("embedding")
    @classmethod
    def validate_embedding(cls, v: List[float]) -> List[float]:
        if len(v) != settings.CROP_IMAGE_EMBEDDING_DIMENSION:
            raise ValueError("Embedding dimension mismatch")
        return v


class RetrievedCropImageFile(BaseModel):
    id: str = Field(
        description="ID of the crop image File.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    crop_name: str = Field(
        description="Name of the crop associated with the image. Example: Rice"
    )
    aliases: Optional[List[str]] = Field(
        default=None, description="List of alternative names for the crop."
    )
