from datetime import date, datetime, timezone
from enum import StrEnum
from typing import List, Optional
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field

from .cultivation_crop import BaseCrop
from .farm_profile import CropYield
from .generic_types import Area, AreaUnit, Level, MoneyValue, TranslatedFields
from .intercropping_details import IntercropType, SpecificArrangement


class RecommendationGoal(StrEnum):
    """Represents the farmer's primary objective for crop recommendation."""

    MAXIMUM_PROFIT = "maximum_profit"
    LOW_INVESTMENT = "low_investment"
    LOW_RISK = "low_risk"
    SHORT_DURATION = "short_duration"
    LOW_WATER_USAGE = "low_water_usage"
    SOIL_IMPROVEMENT = "soil_improvement"
    ORGANIC_FARMING = "organic_farming"
    FODDER_PRODUCTION = "fodder_production"
    EXPORT_MARKET = "export_market"
    LOCAL_MARKET = "local_market"
    INTERCROPPING = "intercropping"
    HIGH_MARKET_DEMAND = "high_market_demand"
    SUSTAINABLE_FARMING = "sustainable_farming"


class RiskTolerance(StrEnum):
    """Represents how much cultivation or market risk the farmer is willing to accept."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class WaterAvailabilityPreference(StrEnum):
    """Represents water availability constraints or preferences."""

    LOW_WATER_ONLY = "low_water_only"
    MODERATE_WATER_USAGE = "moderate_water_usage"
    HIGH_WATER_USAGE_ALLOWED = "high_water_usage_allowed"
    RAINFED_ONLY = "rainfed_only"
    IRRIGATION_AVAILABLE = "irrigation_available"


class CropDurationPreference(StrEnum):
    """Represents preferred crop duration."""

    SHORT = "short"
    MEDIUM = "medium"
    LONG = "long"
    ANY = "any"


class FarmingMethodPreference(StrEnum):
    """Represents preferred farming practice."""

    ORGANIC = "organic"
    CONVENTIONAL = "conventional"
    LOW_CHEMICAL_INPUT = "low_chemical_input"
    NATURAL_FARMING = "natural_farming"
    ANY = "any"


class RecommendationType(StrEnum):
    """Represents the type of crop recommendation requested."""

    MONO_CROP = "mono_crop"
    INTERCROP = "intercrop"
    BOTH = "both"


class ProfitabilityPreference(StrEnum):
    """Represents profitability filtering preference."""

    ALL = "all"
    ONLY_HIGHLY_PROFITABLE = "only_highly_profitable"
    BALANCED_PROFITABILITY = "balanced_profitability"


class RecommendationCountPreference(BaseModel):
    """
    Represents how many recommendation candidates the farmer wants to receive.
    """

    mono_crop_count: int = Field(
        ge=0,
        le=5,
        default=3,
        description=(
            "Number of mono-crop recommendation candidates requested. Example: 3"
        ),
    )

    intercrop_count: int = Field(
        ge=0,
        le=5,
        default=2,
        description=(
            "Number of intercropping recommendation candidates requested. Example: 2"
        ),
    )

    top_profitable_crop_count: Optional[int] = Field(
        default=None,
        ge=1,
        le=5,
        description=(
            "Number of top highly profitable crop recommendations requested. Example: 3"
        ),
    )


class BudgetPerArea(BaseModel):
    """Represents maximum budget constraint per specific area unit."""

    budget: MoneyValue = Field(description="The budget amount and currency.")

    area_unit: AreaUnit = Field(description="The area unit for this budget.")


class ResourceConstraint(BaseModel):
    """Represents practical farm resource constraints."""

    limited_labor: bool = Field(
        default=False, description="Indicates whether labor availability is limited."
    )

    limited_machinery: bool = Field(
        default=False,
        description="Indicates whether machinery or farm equipment availability is limited.",
    )

    limited_water_supply: bool = Field(
        default=False,
        description="Indicates whether irrigation water availability is limited.",
    )

    limited_input_availability: bool = Field(
        default=False,
        description="Indicates whether fertilizers, pesticides, or seeds are difficult to obtain.",
    )

    storage_unavailable: bool = Field(
        default=False,
        description="Indicates whether post-harvest storage facilities are unavailable.",
    )


class CropRecommendationRequest(BaseModel):
    """
    Represents farmer preferences, goals, constraints, and filtering criteria
    used while generating crop recommendations.
    """

    recommendation_type: RecommendationType = Field(
        default=RecommendationType.BOTH,
        description=("Type of recommendation requested by the farmer."),
    )

    recommendation_counts: RecommendationCountPreference = Field(
        default_factory=RecommendationCountPreference,
        description=(
            "Controls how many recommendation candidates should be generated."
        ),
    )

    primary_goal: RecommendationGoal = Field(
        description=(
            "Primary objective the farmer wants to achieve through cultivation."
        ),
    )

    secondary_goals: Optional[List[RecommendationGoal]] = Field(
        default=None,
        description=(
            "Additional farming objectives that should influence recommendation ranking."
        ),
    )

    profitability_preference: ProfitabilityPreference = Field(
        default=ProfitabilityPreference.BALANCED_PROFITABILITY,
        description=(
            "Controls whether recommendations should prioritize highly profitable crops or balanced recommendations."
        ),
    )

    risk_tolerance: RiskTolerance = Field(
        default=RiskTolerance.MEDIUM,
        description=(
            "Indicates how much cultivation or market risk the farmer is willing to accept."
        ),
    )

    water_availability_preference: Optional[WaterAvailabilityPreference] = Field(
        default=None,
        description=("Water availability preference or irrigation constraint."),
    )

    crop_duration_preference: CropDurationPreference = Field(
        default=CropDurationPreference.ANY,
        description=("Preferred crop duration category."),
    )

    farming_method_preference: FarmingMethodPreference = Field(
        default=FarmingMethodPreference.ANY,
        description="Farming practice preference (e.g. organic).",
    )

    budget_per_area: Optional[BudgetPerArea] = Field(
        default=None, description="Cultivation budget constraints per area unit."
    )

    excluded_crops: Optional[List[str]] = Field(
        default=None,
        description=(
            "List of crops the farmer does not want to cultivate. Example: ['Cotton']"
        ),
    )

    resource_constraints: Optional[ResourceConstraint] = Field(
        default=None,
        description=("Practical resource limitations affecting crop selection."),
    )

    additional_context: Optional[str] = Field(
        default=None,
        description=(
            "Additional farmer instructions, requirements, or local context "
            "that may influence crop recommendations."
        ),
    )


class SowingWindow(BaseModel):
    """Represents the recommended sowing period for a crop."""

    start_date: date = Field(
        description="Earliest recommended sowing date for the crop."
    )

    end_date: date = Field(description="Last recommended sowing date for the crop.")

    optimal_date: date = Field(
        description="Most optimal sowing date expected to produce best results."
    )


class MarketTrend(StrEnum):
    """Represents expected short-term market direction."""

    INCREASING = "increasing"
    STABLE = "stable"
    DECREASING = "decreasing"
    VOLATILE = "volatile"


class FinancialSummary(BaseModel):
    """
    Represents high-level financial expectations for a crop recommendation.
    This is intended only for farmer decision support, not detailed accounting.
    """

    estimated_investment: MoneyValue = Field(
        description="Estimated cultivation investment required for the recommended crop."
    )

    estimated_revenue: MoneyValue = Field(
        description="Estimated gross revenue expected from cultivation."
    )

    estimated_profit: MoneyValue = Field(
        description="Estimated net profit after cultivation expenses."
    )

    market_price: MoneyValue = Field(
        description="Current approximate market selling price of the produce."
    )

    market_trend: MarketTrend = Field(
        description="Expected short-term market direction for the crop."
    )

    profitability_level: Level = Field(
        description="Overall profitability assessment considering investment, demand, and expected returns."
    )


class RiskFactor(BaseModel):
    """Represents a cultivation or market risk associated with a crop recommendation."""

    risk_name: str = Field(
        description="Short name of the identified risk. Example: Water shortage"
    )

    probability: float = Field(
        ge=0,
        le=1,
        description="Estimated probability of the risk occurring represented between 0 and 1.",
    )

    impact: Level = Field(description="Severity of impact if the risk occurs.")

    mitigation: str = Field(
        description="Simple farmer-friendly mitigation or prevention suggestion."
    )


class RecommendationReasonCategory(StrEnum):
    """Represents categories explaining why a crop is recommended."""

    SOIL = "soil"
    WATER = "water"
    WEATHER = "weather"
    MARKET = "market"
    LOW_RISK = "low_risk"
    HIGH_PROFIT = "high_profit"
    LOW_INVESTMENT = "low_investment"
    SHORT_DURATION = "short_duration"
    CROP_ROTATION = "crop_rotation"
    RESOURCE_FRIENDLY = "resource_friendly"


class RecommendationReason(BaseModel):
    """Represents a concise reason supporting the crop recommendation."""

    category: RecommendationReasonCategory = Field(
        description="Category explaining the recommendation logic."
    )

    summary: str = Field(
        description="Farmer-friendly explanation for why the crop is suitable."
    )


class CheckResult(StrEnum):
    """Represents result of a reasoning validation check."""

    PASS = "pass"
    CAUTION = "caution"
    FAIL = "fail"


class CrossVerificationCheck(BaseModel):
    """Represents an internal reasoning validation check across farm factors."""

    check_name: str = Field(
        description="Cross-verification label such as soil_x_crop, weather_x_crop, or water_x_crop."
    )

    result: CheckResult = Field(
        description="Outcome of the reasoning validation check."
    )

    summary: str = Field(description="Short explanation of the validation result.")


class CropRecommendationReasoningReport(BaseModel):
    """
    Represents structured reasoning and validation behind generated crop recommendations.
    Intended mainly for explainability, debugging, auditability, and trust.
    """

    weather_report: str = Field(
        description="Summary of weather suitability for the recommended crops."
    )

    water_report: str = Field(
        description="Summary of irrigation reliability and water availability."
    )

    soil_report: str = Field(
        description="Summary of soil suitability and nutrient compatibility."
    )

    farm_resource_report: str = Field(
        description="Summary of farm strengths, constraints, and operational feasibility."
    )

    cross_verification_checks: List[CrossVerificationCheck] = Field(
        description="Internal reasoning validation checks across weather, water, soil, market, and crop compatibility."
    )

    date_validity_report: str = Field(
        description="Validation summary confirming sowing windows align with local seasonal conditions."
    )


class MonoCropCandidate(BaseCrop):
    """
    Represents a single crop recommendation candidate suitable for cultivation on a farm.
    This model contains only high-level decision-support information required for crop selection.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier for the crop recommendation candidate. Generated by backend.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )

    rank: Optional[int] = Field(
        default=None,
        description="Relative recommendation ranking where 1 indicates the best recommendation.",
    )

    suitability_score: float = Field(
        ge=0,
        le=1,
        description="Normalized suitability score representing overall farm compatibility.",
    )

    confidence: float = Field(
        ge=0,
        le=1,
        description="AI confidence score for the recommendation represented between 0 and 1.",
    )

    expected_yield: CropYield = Field(
        description="Expected crop yield estimate under recommended cultivation conditions."
    )

    sowing_window: SowingWindow = Field(
        description="Recommended sowing period for the crop."
    )

    growing_period_days: int = Field(
        gt=0, description="Approximate crop duration from sowing to harvest in days."
    )

    financial_summary: FinancialSummary = Field(
        description="High-level investment, revenue, profit, and market outlook summary."
    )

    recommendation_reasons: List[RecommendationReason] = Field(
        description="List of important reasons explaining why the crop is recommended."
    )

    risk_factors: List[RiskFactor] = Field(
        description="List of major risks associated with cultivating the crop."
    )

    recommendation_summary: str = Field(
        description="Farmer-friendly summary explaining why this crop is suitable for the farm."
    )


class IntercropComponentRole(StrEnum):
    """Represents the functional role of a crop inside an intercropping system."""

    MAIN_CROP = "main_crop"
    SUPPORT_CROP = "support_crop"
    NITROGEN_FIXING_CROP = "nitrogen_fixing_crop"
    TRAP_CROP = "trap_crop"
    SHADE_CROP = "shade_crop"
    COVER_CROP = "cover_crop"
    OTHER = "other"


class InterCropComponent(BaseCrop):
    """Represents a single crop component within an intercropping recommendation."""

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier for the intercrop component. Generated by backend.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    role: IntercropComponentRole = Field(
        description="Functional role of the crop within the intercropping system."
    )

    sowing_window: SowingWindow = Field(
        description="Recommended sowing period for the crop."
    )

    growing_period_days: int = Field(
        gt=0, description="Approximate crop duration from sowing to harvest in days."
    )

    expected_yield: CropYield = Field(
        description="Expected yield contribution of this crop within the intercropping system."
    )


class InterCropCandidate(BaseModel):
    """
    Represents an intercropping recommendation candidate suitable for the farm.
    Contains high-level decision-support information for selecting an intercropping system.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier for the intercropping recommendation candidate. Generated by backend.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )

    rank: int = Field(
        ge=1,
        description="Relative recommendation ranking where 1 indicates the best recommendation.",
    )

    intercrop_type: IntercropType = Field(
        description="Recommended intercropping system type."
    )

    crops: List[InterCropComponent] = Field(
        min_length=2,
        description="List of crop recommendation candidates participating in the intercropping system.",
    )

    arrangement: str = Field(
        description="High-level planting arrangement pattern. Example: 6:2 row pattern."
    )

    specific_arrangement: List[SpecificArrangement] = Field(
        description="Detailed arrangement configuration for each crop in the intercropping system."
    )

    suitability_score: float = Field(
        ge=0,
        le=1,
        description="Normalized suitability score representing overall compatibility of the intercropping system.",
    )

    confidence: float = Field(
        ge=0,
        le=1,
        description="AI confidence score for the intercropping recommendation.",
    )

    recommendation_reasons: List[RecommendationReason] = Field(
        description="Important reasons explaining why the intercropping system is suitable."
    )

    benefits: List[str] = Field(
        description="Farmer-friendly list of benefits expected from the intercropping system."
    )

    risk_factors: List[RiskFactor] = Field(
        description="Major risks associated with adopting the intercropping system."
    )

    recommendation_summary: str = Field(
        description="Farmer-friendly explanation describing why the intercropping system is suitable and beneficial."
    )


# Backend only Model
class CropRecommendationFields(BaseModel):
    """
    Represents the final crop recommendation result generated for a farm.
    Contains both mono-crop and intercropping recommendation candidates.
    """

    mono_crop_candidates: List[MonoCropCandidate] = Field(
        description="Ranked list of recommended mono-crop cultivation candidates."
    )

    inter_crop_candidates: List[InterCropCandidate] = Field(
        description="Ranked list of recommended intercropping candidates."
    )

    reasoning_report: CropRecommendationReasoningReport = Field(
        description="Optional structured reasoning and validation report explaining recommendation generation.",
    )

    expiration_date: date = Field(
        description="Date after which the recommendation result should be considered not usable."
    )


class CropRecommendationMetadata(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier of the crop recommendation result.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )

    farm_id: str = Field(
        description="Unique identifier of the farm for which the recommendation was generated."
    )

    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC Timestamp when the recommendation result was generated.",
    )


class CropRecommendation(CropRecommendationMetadata, CropRecommendationFields):
    request: CropRecommendationRequest = Field(
        description="Original crop recommendation request containing farmer preferences and constraints used for generating this recommendation.",
    )


TranslatedCropRecommendationFields = TranslatedFields[CropRecommendationFields]


# Backend only Model
class CropRecommendationDocument(
    CropRecommendationMetadata, TranslatedCropRecommendationFields
):
    request: CropRecommendationRequest = Field(
        description="Original crop recommendation request containing farmer preferences and constraints used for generating this recommendation.",
    )


class SelectCropRequest(BaseModel):
    crop_id: str
    selected_area: Area
