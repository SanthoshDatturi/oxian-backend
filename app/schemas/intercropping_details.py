from enum import StrEnum
from typing import List, Optional
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field

from .generic_types import TranslatedFields


class SpecificArrangement(BaseModel):
    """
    Describes how a specific crop is positioned within an intercropping system.
    """

    crop_name: str = Field(
        description=(
            "Name of the crop participating in the intercropping system. Example: Maize"
        )
    )
    variety: Optional[str] = Field(
        default=None,
        description=(
            "Variety or cultivar of the crop participating in the intercropping system. "
            "Example: DHM-117"
        ),
    )
    arrangement: str = Field(
        description=(
            "Specific spacing, row pattern, or placement of this crop within the "
            "intercropping system. Example: '6 rows of maize followed by 2 rows of beans'."
        )
    )


class IntercropType(StrEnum):
    """Represents common intercropping system types."""

    ROW = "row_intercropping"
    MIXED = "mixed_intercropping"
    STRIP = "strip_intercropping"
    RELAY = "relay_intercropping"
    MULTI_STOREY = "multi_storey_intercropping"
    OTHER = "other"


class IntercroppingDetailsTranslatableFields(BaseModel):
    """
    Farmer-facing intercropping details that can be translated.
    """

    arrangement: str = Field(
        description=(
            "Overall arrangement pattern of the intercropping system. "
            "Example: '6 rows of maize followed by 2 rows of beans'."
        )
    )
    specific_arrangement: List[SpecificArrangement] = Field(
        min_length=2,
        description=(
            "Detailed arrangement information for each crop participating in "
            "the intercropping system."
        ),
    )


class IntercroppingDetailsInputInvariantFields(BaseModel):
    """
    Intercropping details input fields that do not need translation.
    """

    intercrop_type: IntercropType = Field(
        description=(
            "Type of intercropping system selected. Examples include row "
            "intercropping, strip intercropping, relay intercropping, and mixed intercropping."
        )
    )


class IntercroppingDetailsInput(
    IntercroppingDetailsInputInvariantFields,
    IntercroppingDetailsTranslatableFields,
):
    """Input payload for creating or updating intercropping details."""


TranslatedIntercroppingDetailsFields = TranslatedFields[
    IntercroppingDetailsTranslatableFields
]


class TranslatedIntercroppingDetailsInput(
    IntercroppingDetailsInputInvariantFields,
    TranslatedIntercroppingDetailsFields,
):
    """Translated intercropping details input including invariant fields."""


class IntercroppingDetailsInvariantFields(IntercroppingDetailsInputInvariantFields):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier of the intercropping system.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    recommendation_id: Optional[str] = Field(
        default=None,
        description=(
            "Identifier of the intercropping recommendation candidate from which "
            "this intercropping system was selected. Null when created manually."
        ),
    )


class IntercroppingDetails(
    IntercroppingDetailsInvariantFields, IntercroppingDetailsTranslatableFields
):
    """
    Represents a selected intercropping system derived from an intercropping
    recommendation and associated with one or more cultivation crops.
    Stores only the intercropping-system-specific information and does not
    duplicate cultivation crop ownership relationships.
    """


class IntercroppingDetailsDocument(
    IntercroppingDetailsInvariantFields, TranslatedIntercroppingDetailsFields
):
    """
    Represents the MongoDB document structure for IntercroppingDetails, including
    translated fields for multi-language support.
    """
