from typing import List, Optional
from uuid import uuid4

from langchain_core.runnables.configurable import StrEnum
from pydantic import AliasChoices, BaseModel, Field

from .generic_types import LatLang


class SoilTexturePercentage(BaseModel):
    """Represents soil texture composition percentages."""

    sand: float = Field(
        ge=0, le=100, description="Percentage of sand content in soil. Example: 40"
    )

    silt: float = Field(
        ge=0, le=100, description="Percentage of silt content in soil. Example: 35"
    )

    clay: float = Field(
        ge=0, le=100, description="Percentage of clay content in soil. Example: 25"
    )


class SoilTestProperties(BaseModel):
    """Represents detailed soil properties obtained from a laboratory soil test."""

    soil_texture: SoilTexturePercentage = Field(
        description="Texture composition of the soil expressed as percentages of sand, silt, and clay."
    )

    ph_level: float = Field(
        ge=0,
        le=14,
        description="Soil pH level indicating acidity or alkalinity. Example: 6.8",
    )

    electrical_conductivity_ds_m: float = Field(
        ge=0,
        description="Electrical conductivity of the soil measured in dS/m indicating salinity. Example: 0.35",
    )

    organic_carbon_percent: float = Field(
        ge=0,
        le=100,
        description="Organic carbon content of soil as percentage. Example: 0.75",
    )

    nitrogen_kg_per_hectare: float = Field(
        ge=0,
        description="Available Nitrogen in the soil measured in kilograms per hectare. Example: 280",
    )

    phosphorus_kg_per_hectare: float = Field(
        ge=0,
        description="Available Phosphorus in the soil measured in kilograms per hectare. Example: 45",
    )

    potassium_kg_per_hectare: float = Field(
        ge=0,
        description="Available Potassium in the soil measured in kilograms per hectare. Example: 320",
    )

    sulphur_ppm: Optional[float] = Field(
        ge=0,
        default=None,
        description="Sulphur concentration in soil measured in parts per million. Example: 12",
    )

    zinc_ppm: Optional[float] = Field(
        ge=0,
        default=None,
        description="Zinc concentration in soil measured in parts per million. Example: 0.8",
    )

    boron_ppm: Optional[float] = Field(
        ge=0,
        default=None,
        description="Boron concentration in soil measured in parts per million. Example: 0.5",
    )

    iron_ppm: Optional[float] = Field(
        ge=0,
        default=None,
        description="Iron concentration in soil measured in parts per million. Example: 4.2",
    )


class AreaUnit(StrEnum):
    """Supported land area units."""

    ACRE = "acre"
    HECTARE = "hectare"
    SQUARE_METER = "square_meter"


class YieldQuantityUnit(StrEnum):
    """Supported crop yield quantity units."""

    KG = "kg"
    TONNE = "tonne"
    QUINTAL = "quintal"
    BUSHEL = "bushel"


class Area(BaseModel):
    """Represents a land area measurement."""

    value: float = Field(
        gt=0,
        description="Numeric value representing the size of the land area. Example: 5",
    )

    unit: AreaUnit = Field(
        description="Unit used to measure the land area. Example: acre"
    )


class CropYield(BaseModel):
    """Represents crop yield as quantity produced over a specific land area."""

    quantity: float = Field(
        gt=0, description="Total crop quantity harvested. Example: 20"
    )

    quantity_unit: YieldQuantityUnit = Field(
        description="Unit used to measure harvested crop quantity. Example: quintal"
    )

    area: float = Field(
        gt=0, description="Area over which the yield was measured. Example: 1"
    )

    area_unit: AreaUnit = Field(
        description="Unit of land area used for yield measurement. Example: acre. Together represents values like 20 quintal per acre."
    )


class WaterSource(StrEnum):
    """Possible water sources available for irrigation."""

    WELL = "Well"
    BOREWELL = "Borewell"
    CANAL = "Canal"
    RIVER = "River"
    LAKE = "Lake"
    RAINWATER_HARVESTING = "Rainwater Harvesting"
    MUNICIPAL_SUPPLY = "Municipal Supply"
    OTHER = "Other"


class IrrigationSystem(StrEnum):
    """Types of irrigation systems used in agriculture."""

    DRIP = "Drip"
    SPRINKLER = "Sprinkler"
    FLOOD = "Flood"
    FURROW = "Furrow"
    CENTER_PIVOT = "Center Pivot"
    MANUAL = "Manual"
    OTHER = "Other"


class SoilType(StrEnum):
    """Common global soil classifications recognizable visually or from soil databases."""

    BLACK = "Black soil"
    RED = "Red soil"
    ALLUVIAL = "Alluvial soil"
    LATERITE = "Laterite soil"
    DESERT = "Desert soil"
    FOREST = "Forest soil"
    SALINE = "Saline/Alkaline soil"
    SANDY = "Sandy soil"
    CLAY = "Clay soil"
    SILTY = "Silty soil"
    LOAMY = "Loamy soil"


class CropSeason(StrEnum):
    """Agricultural growing seasons used globally."""

    KHARIF = "Kharif"
    RABI = "Rabi"
    ZAID = "Zaid"
    SPRING = "Spring"
    SUMMER = "Summer"
    AUTUMN = "Autumn"
    WINTER = "Winter"


class Location(BaseModel):
    """Represents the geographical location of the farm."""

    lat_lang: LatLang = Field(
        description="Represents the Geographic co-ordinates of the farm"
    )

    village: Optional[str] = Field(
        default=None,
        description="Village or smallest local administrative region where the farm is located. Example: Mydukur",
    )

    mandal: Optional[str] = Field(
        default=None,
        description="Sub-district administrative unit used in some countries such as India. Example: Mydukur",
    )

    district: Optional[str] = Field(
        default=None,
        description="District or equivalent administrative division. Example: YSR Kadapa",
    )

    state: str = Field(
        description="State, province, or region where the farm is located. Example: Andhra Pradesh"
    )

    country: str = Field(
        default="India", description="Country where the farm is located. Example: India"
    )

    postal_code: str = Field(
        description="Postal or ZIP code for the farm's location. Example: 516172"
    )


class PreviousCrops(BaseModel):
    """Represents crops previously cultivated on the farm."""

    crop_name: str = Field(description="Name of the crop grown. Example: Rice")

    year: int = Field(
        description="Year in which the crop was cultivated. Example: 2024"
    )

    season: CropSeason = Field(
        description="Agricultural season in which the crop was cultivated. Example: Kharif"
    )

    crop_yield: Optional[CropYield] = Field(
        default=None,
        description="Measured crop yield expressed as quantity over a specific land area. Example: 20 quintal harvested from 1 acre.",
    )

    fertilizers_used: Optional[List[str]] = Field(
        default=None,
        description="List of fertilizers applied for the crop. Example: ['Urea', 'DAP']",
    )

    pesticides_used: Optional[List[str]] = Field(
        default=None,
        description="List of pesticides used for the crop. Example: ['Chlorpyrifos']",
    )


class FarmProfile(BaseModel):
    """
    Represents the complete profile of a farm including location,
    land characteristics, irrigation resources, soil health, and cropping history.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier for the farm profile.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )

    user_id: str = Field(
        description="Unique identifier of the farmer who owns or manages the farm."
    )

    name: str = Field(
        description="Name or nickname used to identify the farm. Example: Green Valley Farm"
    )

    location: Location = Field(description="Geographical location details of the farm.")

    soil_type: SoilType = Field(
        description="Dominant soil type present in the farm. Example: Black soil"
    )

    total_area: Area = Field(
        description="Total land area of the farm. Example: 5 acres."
    )

    cultivated_area: Area = Field(
        description="Area of the farm currently used for cultivation. Example: 4 acres."
    )

    water_source: WaterSource = Field(
        description="Primary water source used for irrigation. Example: Borewell"
    )

    irrigation_system: Optional[IrrigationSystem] = Field(
        default=None,
        description="Irrigation system used for watering crops if available. Example: Drip",
    )

    crops: Optional[List[PreviousCrops]] = Field(
        default=None,
        description="Historical list of crops previously cultivated on the farm.",
    )

    soil_test_properties: Optional[SoilTestProperties] = Field(
        default=None,
        description=(
            "Detailed soil test results including nutrient levels and soil characteristics."
            "Should upload images or PDF documents of the test, extract from them."
        ),
    )
