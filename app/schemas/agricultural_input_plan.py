from datetime import date, datetime, timezone
from enum import StrEnum
from typing import List, Optional
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field

from .generic_types import Quantity, TranslatedFields


class InputCategory(StrEnum):
    FERTILIZER = "fertilizer"
    PESTICIDE = "pesticide"
    HERBICIDE = "herbicide"
    FUNGICIDE = "fungicide"
    MICRONUTRIENT = "micronutrient"
    BIO_STIMULANT = "bio_stimulant"
    OTHER = "other"


class TreatmentApproach(StrEnum):
    CHEMICAL = "chemical"
    ORGANIC = "organic"
    BIOLOGICAL = "biological"
    INTEGRATED = "integrated"


class AgriculturalInputItem(BaseModel):
    """
    Represents a single agricultural input
    used as part of a treatment strategy.
    """

    input_name: str = Field(description="Name of the agricultural input or product.")
    category: InputCategory = Field(description="Category of the agricultural input.")
    dosage: Quantity = Field(description="Recommended quantity to apply.")
    application_method: str = Field(description="How the input should be applied.")
    precautions: List[str] = Field(
        default_factory=list, description="Safety and usage precautions."
    )
    purpose: str = Field(
        description="Purpose of including this input in the treatment strategy."
    )


class AgriculturalInputStrategy(BaseModel):
    """
    Represents one complete treatment strategy.
    A strategy may contain one or multiple inputs
    that should be used together.
    """

    approach: TreatmentApproach = Field(
        description="Treatment approach used by the strategy."
    )
    rank: int = Field(
        ge=1,
        description="Suitability ranking where 1 is best, unique for each strategy in the recommendation."
    )
    inputs: List[AgriculturalInputItem] = Field(
        min_length=1,
        description=("Inputs that collectively form this treatment strategy."),
    )
    application_steps: List[str] = Field(
        description=("Step-by-step application instructions for the entire strategy.")
    )
    explanation: str = Field(description=("Reason why this strategy is recommended."))
    expected_result: str = Field(
        description=("Expected outcome after applying the strategy.")
    )


class AgriculturalInputInvariantFields(BaseModel):
    """
    Fields for representing the core attributes of an agricultural input plan or recommendation, which are invariant and not translatable.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier of the agricultural input",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    cultivation_crop_id: str = Field(
        description=(
            "Identifier of the cultivation crop for which this input plan was created."
        )
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the agricultural input plan was created.",
    )


class AgriculturalInputTranslatableFields(BaseModel):
    """
    Fields for representing the core attributes of an agricultural input plan or recommendation, which are translatable.
    """

    title: str = Field(
        description=(
            "Short title of the agricultural input. Example: Fall Armyworm Control Plan"
        )
    )
    problem: str = Field(
        description=(
            "Problem, deficiency, disease, pest attack, growth stage, or "
            "cultivation objective addressed by this input plan."
        )
    )


class AgriculturalInputPlanInvariantFields(AgriculturalInputInvariantFields):
    """
    Fields for representing the core attributes of an agricultural input plan, which are invariant and not translatable.
    """

    recommendation_id: str = Field(
        description=(
            "Identifier of the agricultural input recommendation from which "
            "this plan was selected."
        )
    )
    application_date: Optional[date] = Field(
        default=None,
        description=("Actual date on which the selected strategy was applied."),
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the most recent update to the plan."
    )


class AgriculturalInputPlanTranslatableFields(BaseModel):
    """
    Fields for representing the core attributes of an agricultural input plan, which are translatable.
    """

    selected_strategy: AgriculturalInputStrategy = Field(
        description=(
            "Treatment strategy selected by the farmer. "
            "Contains all inputs required for execution."
        )
    )
    notes: Optional[str] = Field(
        default=None,
        description=(
            "Farmer notes, observations, or execution comments related to this input plan."
        ),
    )


class AgriculturalInputPlan(
    AgriculturalInputPlanInvariantFields, AgriculturalInputPlanTranslatableFields
):
    """
    Represents the agricultural input plan selected by the farmer from an
    AgriculturalInputRecommendation.

    This model becomes the operational record used for purchasing,
    application tracking, cost recording, and future analysis.
    """


TranslatedAgriculturalInputPlanFields = TranslatedFields[
    AgriculturalInputPlanTranslatableFields
]


class AgriculturalInputPlanDocument(
    AgriculturalInputPlanInvariantFields, TranslatedAgriculturalInputPlanFields
):
    """
    Represents the full agricultural input plan document as stored in the database, including both invariant and translatable fields.
    """
