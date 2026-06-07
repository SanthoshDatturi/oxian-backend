from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import AliasChoices, BaseModel, Field

from .generic_types import Area, TranslatedFields


class BaseCrop(BaseModel):
    """
    Represents a crop entity used across recommendation,
    crop selection, and cultivation workflows.
    """

    name: str = Field(description="Name of the crop. Example: Rice")

    variety: Optional[str] = Field(
        default=None,
        description="Recommended or selected crop variety or cultivar. Example: BPT 5204",
    )

    image_file_id: Optional[str] = Field(
        default=None,
        description="Identifier of a reference image representing the crop or crop variety.",
    )

    description: str = Field(
        description=(
            "Farmer-friendly summary describing the crop, its key characteristics, "
            "benefits, suitability, or cultivation context. This description should "
            "remain meaningful in recommendation, selection, and cultivation workflows."
        )
    )


class CropState(str, Enum):
    """Represents the current lifecycle state of a cultivated crop."""

    SELECTED = "selected"
    PLANTED = "planted"
    GROWING = "growing"
    HARVESTED = "harvested"
    COMPLETE = "complete"
    FAILED = "failed"


class CultivationCropFields(BaseCrop):
    """
    Represents the core cultivation-specific information for a crop
    selected by the farmer for cultivation.
    """

    crop_state: CropState = Field(
        default=CropState.SELECTED,
        description=(
            "Current lifecycle state of the crop within the cultivation process."
        ),
    )

    selected_area: Area = Field(
        description=(
            "Area allocated for cultivating this crop. "
            "This may represent the full farm area or only a portion of the farm."
        )
    )


TranslatedCultivationCropFields = TranslatedFields[CultivationCropFields]


class CultivationCropMetadata(BaseModel):
    id: str = Field(
        description="Unique identifier of the cultivation crop instance.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )

    farm_id: str = Field(
        description="Unique identifier of the farm where the crop is being cultivated."
    )

    recommendation_id: Optional[str] = Field(
        default=None,
        description=(
            "Identifier of the crop recommendation from which this crop was selected. "
            "Null when the crop was manually added by the farmer."
        ),
    )

    intercropping_id: Optional[str] = Field(
        default=None,
        description=(
            "Identifier of the intercropping system this crop belongs to. "
            "Null when cultivated as a mono crop."
        ),
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC Timestamp when the cultivation crop record was created.",
    )

    updated_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC Timestamp when the cultivation crop record was last updated.",
    )


class CultivationCrop(CultivationCropMetadata, CultivationCropFields):
    """
    Represents an individual crop selected by the farmer for cultivation
    on a farm.
    """


# Backend-only model
class CultivationCropDocument(CultivationCropMetadata, TranslatedCultivationCropFields):
    """
    Represents the cultivation crop document stored in the database,
    including multilingual representations used for reasoning and display.
    """
