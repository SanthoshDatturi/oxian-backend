from datetime import datetime, timezone
from math import isclose
from typing import List, Optional
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from .cultivation_task import InvestmentCategory
from .farm_profile import CropYield
from .generic_types import MoneyValue, TranslatedFields


class InvestmentItem(BaseModel):
    """
    Represents a phase of investment for a crop's cultivation.
    """

    category: InvestmentCategory = Field(
        ..., description="Resource category of the investment."
    )
    reason: str = Field(
        ..., description="Purpose or description of the investment item."
    )
    estimated_cost: MoneyValue = Field(..., description="Estimated cost for this item.")

    @field_validator("reason")
    def non_empty_reason(cls, v):
        if not v or not v.strip():
            raise ValueError("Investment reason must not be empty")
        return v


class Profitability(BaseModel):
    """
    Summarizes forecasted and actual profitability for a crop.
    """

    estimated_gross_income: MoneyValue = Field(
        ..., description="Expected total revenue."
    )
    estimated_total_cost: MoneyValue = Field(..., description="Sum of estimated costs.")
    estimated_net_profit: MoneyValue = Field(..., description="Estimated profit.")
    break_even_yield: CropYield = Field(
        ..., description="Yield per area needed to break even."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this investment breakdown was created.",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the last update to this breakdown."
    )


class InvestmentBreakdownInvariantFields(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="UUID of the investment breakdown record.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    crop_id: str = Field(
        ..., description="UUID of the CultivationCrop for which this breakdown applies."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this investment breakdown was created.",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the last update to this breakdown."
    )


class InvestmentBreakdownTranslatableFields(BaseModel):
    investments: List[InvestmentItem] = Field(
        ..., description="List of all investment items."
    )
    profitability: Profitability = Field(
        ..., description="Profitability summary based on costs and yields."
    )

    @field_validator("investments")
    @classmethod
    def non_empty_investments(cls, v):
        if not v:
            raise ValueError("At least one investment item must be provided")
        return v

    @model_validator(mode="after")
    def validate_profitability_totals(self):
        total_cost = sum(item.estimated_cost.amount for item in self.investments)
        investment_currencies = {
            item.estimated_cost.currency for item in self.investments
        }
        profitability_currency = self.profitability.estimated_total_cost.currency

        if len(investment_currencies) > 1:
            raise ValueError("All investment items must use the same currency")
        if profitability_currency not in investment_currencies:
            raise ValueError(
                "Profitability total cost currency must match investment currency"
            )

        gross_income = self.profitability.estimated_gross_income
        total_cost_value = self.profitability.estimated_total_cost
        net_profit = self.profitability.estimated_net_profit

        if gross_income.currency != profitability_currency:
            raise ValueError("Gross income currency must match total cost currency")
        if net_profit.currency != profitability_currency:
            raise ValueError("Net profit currency must match total cost currency")
        if not isclose(total_cost_value.amount, total_cost):
            raise ValueError(
                "Estimated total cost must equal the sum of investment costs"
            )
        if not isclose(net_profit.amount, gross_income.amount - total_cost_value.amount):
            raise ValueError(
                "Estimated net profit must equal gross income minus total cost"
            )
        return self


class InvestmentBreakdown(
    InvestmentBreakdownInvariantFields, InvestmentBreakdownTranslatableFields
):
    """
    Provides a full initial estimated financial breakdown of investments for a crop cultivation.
    Not meant for single items, but rather generalized investment summary for the entire cultivation cycle.
    """


TranslatedInvestmentBreakdownFields = TranslatedFields[
    InvestmentBreakdownTranslatableFields
]


class InvestmentBreakdownDocument(
    InvestmentBreakdownInvariantFields, TranslatedInvestmentBreakdownFields
):
    """
    Document model for storing investment breakdowns with translatable fields. The core metadata is used for identification and retrieval, while the fields can be translated into multiple languages as needed.
    """
