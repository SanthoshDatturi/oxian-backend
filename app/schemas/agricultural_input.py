from datetime import date, datetime, timezone
from enum import StrEnum
from typing import List, Optional
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field, field_validator

from .generic_types import Quantity


class InputCategory(StrEnum):
    FERTILIZER = "fertilizer"
    PESTICIDE = "pesticide"
    HERBICIDE = "herbicide"
    FUNGICIDE = "fungicide"
    MICRONUTRIENT = "micronutrient"
    BIO_STIMULANT = "bio_stimulant"
    OTHER = "other"


class InputType(StrEnum):
    CHEMICAL = "chemical"
    ORGANIC = "organic"
    BIOLOGICAL = "biological"


class InputStage(StrEnum):
    RECOMMENDED = "recommended"
    SELECTED = "selected"
    APPLIED = "applied"


class InputOption(BaseModel):
    """
    Represents a recommended input option for a InputType.
    """

    input_name: str = Field(..., description="Name of the input product or item.")
    input_type: InputType = Field(..., description="Type of agricultural input.")
    stage: InputStage = Field(
        default=InputStage.RECOMMENDED,
        description="Current stage of usage/recommendation of the input.",
    )
    dosage: Quantity = Field(
        ..., description="Dosage or quantity of the input recommended per area."
    )
    application_steps: Optional[str] = Field(
        None, description="Detailed steps for applying the input."
    )
    precautions: List[str] = Field(
        default_factory=list, description="Safety or usage precautions for this input."
    )
    explanation: Optional[str] = Field(
        None,
        description="Justification or notes for recommending this input on the crop.",
    )


class AgriculturalInput(BaseModel):
    """
    Represents an agricultural input (e.g., pesticide, fertilizer) for a crop.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="UUID of the agricultural input.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    category: InputCategory = Field(..., description="Category of the input.")
    options: List[InputOption] = Field(
        ...,
        description=(
            "List of recommended input options for this category for each InputType. "
            "User selects one option per InputType option and applies it."
        ),
    )
    applied_date: Optional[date] = Field(
        default=None, description="Date when the input was actually applied."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this input record was created.",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the last update to this input record."
    )

    @field_validator("input_name")
    def non_empty_name(cls, v):
        if not v or not v.strip():
            raise ValueError("Input name must not be empty")
        return v
