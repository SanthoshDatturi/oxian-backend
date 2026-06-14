from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field

from .generic_types import Area, TranslatedFields
from .intercropping_details import IntercroppingDetails, IntercroppingDetailsInput


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


class CultivationCropInputInvariantFields(BaseModel):
    """Cultivation crop input fields that do not need translation."""

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


class CultivationCropInput(CultivationCropInputInvariantFields, BaseCrop):
    """Input payload for creating or updating a cultivation crop."""


TranslatedCultivationCropFields = TranslatedFields[BaseCrop]


class TranslatedCultivationCropInput(
    CultivationCropInputInvariantFields, TranslatedCultivationCropFields
):
    """Translated cultivation crop input including invariant fields."""


class CultivationCropInvariantFields(CultivationCropInputInvariantFields):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
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


class CultivationCrop(CultivationCropInvariantFields, BaseCrop):
    """
    Represents an individual crop selected by the farmer for cultivation
    on a farm.
    """


# Backend-only model
class CultivationCropDocument(
    CultivationCropInvariantFields, TranslatedCultivationCropFields
):
    """
    Represents the cultivation crop document stored in the database,
    including multilingual representations used for reasoning and display.
    """


class IntercroppingCultivationInput(BaseModel):
    """Input payload for creating or updating an intercropping cultivation group."""

    intercropping_details: IntercroppingDetailsInput = Field(
        description="Intercropping system details to create or update."
    )
    crops: List[CultivationCropInput] = Field(
        min_length=2,
        description="Cultivation crops that belong to the intercropping system.",
    )


class IntercroppingCultivation(BaseModel):
    """Intercropping cultivation group with details and related crops."""

    intercropping_details: IntercroppingDetails = Field(
        description="Stored intercropping system details."
    )
    crops: List[CultivationCrop] = Field(
        min_length=2,
        description="Stored cultivation crops that belong to the intercropping system.",
    )
