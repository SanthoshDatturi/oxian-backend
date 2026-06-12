from typing import List

from pydantic import Field, field_validator

from .agricultural_input_plan import (
    AgriculturalInputInvariantFields,
    AgriculturalInputStrategy,
    AgriculturalInputTranslatableFields,
)
from .generic_types import TranslatedFields


class AgriculturalInputRecommendationTranslatableFields(
    AgriculturalInputTranslatableFields
):
    """
    Fields for representing the core attributes of an agricultural input recommendation, which are translatable.
    """

    strategies: List[AgriculturalInputStrategy] = Field(
        min_length=1,
        description=("Alternative treatment strategies available to the farmer."),
    )

    @field_validator("strategies")
    @classmethod
    def unique_strategy_ranks(cls, v):
        ranks = [strategy.rank for strategy in v]
        if len(ranks) != len(set(ranks)):
            raise ValueError("Strategy ranks must be unique")
        return v


class AgriculturalInputRecommendation(
    AgriculturalInputInvariantFields, AgriculturalInputRecommendationTranslatableFields
):
    """
    Represents an agricultural intervention recommendation
    generated for a crop issue, nutrient deficiency,
    growth stage, pest attack, disease, or management need.
    """


TranslatedAgriculturalInputRecommendationFields = TranslatedFields[
    AgriculturalInputRecommendationTranslatableFields
]


class AgriculturalInputRecommendationDocument(
    AgriculturalInputInvariantFields, TranslatedAgriculturalInputRecommendationFields
):
    """
    MongoDB document model for storing agricultural input recommendations with both invariant and translatable fields.
    """
