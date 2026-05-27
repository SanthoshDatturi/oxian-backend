from enum import StrEnum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field


# Backend only type
class PersistenceLanguage(StrEnum):
    ENGLISH = "english"
    USER_LANGUAGE = "user_language"


T = TypeVar("T", bound=BaseModel)


# Backend only type
class TranslatedFields(BaseModel, Generic[T]):
    """
    Generic multilingual wrapper for any model.

    Stores:
    - canonical English version for reasoning and analysis
    - user language version for farmer-facing UI
    """

    english: T = Field(
        description=(
            "Canonical English version of the data, used for reasoning and analysis."
            "Units should be same as provided by the user in both languages."
        )
    )
    user_language: T = Field(
        description=(
            "User language version of the data, used for farmer-facing UI."
            "Units should be same as provided by the user in both languages."
        )
    )


class LatLng(BaseModel):
    latitude: float = Field(
        description="The latitude in degrees. It must be in the range [-90.0, +90.0].",
    )
    longitude: float = Field(
        description="The longitude in degrees. It must be in the range [-180.0, +180.0].",
    )


class Currency(StrEnum):
    """Supported currencies for financial estimates and market values."""

    INR = "INR"
    USD = "USD"
    EUR = "EUR"
    NGN = "NGN"


class MoneyValue(BaseModel):
    """Represents a monetary value in a specific currency."""

    amount: float = Field(ge=0, description="Numeric monetary value. Example: 15000")

    currency: Currency = Field(
        description="Currency used for the monetary value. Example: INR"
    )


class QuantityUnit(StrEnum):
    """Supported quantity units."""

    KG = "kg"
    TONNE = "tonne"
    QUINTAL = "quintal"
    BUSHEL = "bushel"


class Quantity(BaseModel):
    """Represents a quantity measurement."""

    value: float = Field(
        gt=0,
        description="Numeric value representing the quantity. Example: 100",
    )

    unit: QuantityUnit = Field(
        description="Unit used to measure the quantity. Example: kg"
    )


class AreaUnit(StrEnum):
    """Supported land area units."""

    ACRE = "acre"
    HECTARE = "hectare"
    SQUARE_METER = "square_meter"


class Area(BaseModel):
    """Represents a land area measurement."""

    value: float = Field(
        gt=0,
        description="Numeric value representing the size of the land area. Example: 5",
    )

    unit: AreaUnit = Field(
        description="Unit used to measure the land area. Example: acre"
    )


class Level(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
