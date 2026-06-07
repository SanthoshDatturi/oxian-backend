from datetime import datetime, timezone
from enum import StrEnum
from typing import List, Optional
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field, field_validator

from .farm_profile import CropYield
from .generic_types import MoneyValue


class InvestmentCategory(StrEnum):
    SEED = "seed"
    AGRICULTURAL_INPUT = "agricultural_input"
    LABOR = "labor"
    MACHINERY = "machinery"
    IRRIGATION = "irrigation"
    TRANSPORT = "transport"
    STORAGE = "storage"
    OTHER = "other"


class InvestmentItem(BaseModel):
    """
    Represents a single line-item of investment for a crop's cultivation.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="UUID of the investment item.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    category: InvestmentCategory = Field(
        ..., description="Resource category of the investment."
    )
    reason: str = Field(
        ..., description="Purpose or description of the investment item."
    )
    estimated_cost: MoneyValue = Field(..., description="Estimated cost for this item.")
    actual_cost: Optional[MoneyValue] = Field(
        default=None, description="Actual cost spent for this item, if available."
    )
    input_id: Optional[str] = Field(
        default=None,
        description="ID of the AgriculturalInput (if any) associated with this investment.",
    )
    last_updated: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the estimated cost was last generated or updated.",
    )

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


class InvestmentBreakdown(BaseModel):
    """
    Provides a detailed financial breakdown of investments for a crop cultivation.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="UUID of the investment breakdown record.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    crop_id: str = Field(
        ..., description="UUID of the CultivationCrop for which this breakdown applies."
    )
    investments: List[InvestmentItem] = Field(
        ..., description="List of all investment items."
    )
    profitability: Profitability = Field(
        ..., description="Profitability summary based on costs and yields."
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this investment breakdown was created.",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the last update to this breakdown."
    )

    @field_validator("investments")
    def non_empty_investments(cls, v):
        if not v:
            raise ValueError("At least one investment item must be provided")
        return v
