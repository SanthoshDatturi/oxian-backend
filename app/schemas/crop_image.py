import time
from typing import List, Optional
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field, field_validator

from app.core.config import settings


class CropImageFile(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
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
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    crop_name: str = Field(
        description="Name of the crop associated with the image. Example: Rice"
    )
    aliases: Optional[List[str]] = Field(
        default=None, description="List of alternative names for the crop."
    )


class HybridCropImageSearchResult(BaseModel):
    """Represents crop image matches found by both lexical and semantic search for one requested crop name."""

    crop_name: str = Field(
        description="Original crop name query provided by the caller. Example: Rice"
    )
    keyword_matches: list[RetrievedCropImageFile] = Field(
        default_factory=list,
        description=(
            "Crop image records found by keyword search against crop names and aliases."
        ),
    )
    similarity_matches: list[RetrievedCropImageFile] = Field(
        default_factory=list,
        description=(
            "Crop image records found by vector similarity search using the crop query embedding."
        ),
    )
