from datetime import date, datetime, timezone
from enum import Enum, StrEnum
from typing import List, Optional
from uuid import uuid4

from pydantic import (
    AliasChoices,
    BaseModel,
    Field,
    ValidationInfo,
    field_validator,
    model_validator,
)

from .generic_types import MoneyValue, TranslatedFields


class InvestmentCategory(StrEnum):
    SEED = "seed"
    AGRICULTURAL_INPUT = "agricultural_input"
    LABOR = "labor"
    MACHINERY = "machinery"
    IRRIGATION = "irrigation"
    TRANSPORT = "transport"
    STORAGE = "storage"
    OTHER = "other"


class Investment(BaseModel):
    """
    Represents a single line-item of investment for a crop's cultivation.
    """

    agricultural_input_plan_id: Optional[str] = Field(
        default=None,
        description=(
            "UUID of the AgriculturalInputPlan this investment belongs to, if applicable."
        ),
    )
    category: InvestmentCategory = Field(
        ..., description="Resource category of the investment."
    )
    reason: str = Field(
        ..., description="Purpose or description of the investment item."
    )
    estimated_cost: MoneyValue = Field(..., description="Estimated cost for this item.")
    actual_cost: Optional[MoneyValue] = Field(
        default=None,
        description="Actual cost spent for this item, if available, entered by user.",
    )


class TaskState(str, Enum):
    PENDING = "pending"
    COMPLETED = "completed"
    SKIPPED = "skipped"
    RE_SCHEDULED = "rescheduled"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class RescheduleRecord(BaseModel):
    """
    Records a rescheduling event for a task.
    """

    changed_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when the reschedule occurred.",
    )
    old_start_date: date = Field(..., description="Original scheduled start date.")
    old_end_date: date = Field(..., description="Original scheduled end date.")
    new_start_date: date = Field(
        ..., description="Updated start date after rescheduling."
    )
    new_end_date: date = Field(..., description="Updated end date after rescheduling.")
    reason: Optional[str] = Field(None, description="Reason or note for rescheduling.")

    @field_validator("new_start_date")
    @classmethod
    def validate_dates(cls, v: date, info: ValidationInfo):
        old_start_date = info.data.get("old_start_date")
        if old_start_date and v < old_start_date:
            raise ValueError("New start date cannot be before old start date")
        return v

    @field_validator("new_end_date")
    @classmethod
    def validate_end(cls, v: date, info: ValidationInfo):
        new_start_date = info.data.get("new_start_date")
        if new_start_date and v < new_start_date:
            raise ValueError("End date cannot be before start date")
        return v


class CultivationTaskInvariantFields(BaseModel):
    """
    Metadata fields for a cultivation task that are not translatable and are used for identification and scheduling.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier of the task.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    crop_id: str = Field(
        ..., description="Identifier of the crop this task belongs to."
    )
    sequence_number: int = Field(
        ..., description="Order of the task within the cultivation schedule."
    )
    planned_start_date: date = Field(
        ..., description="Original planned start date for the task."
    )
    planned_end_date: date = Field(
        ..., description="Original planned end date for the task."
    )
    status: TaskState = Field(
        default=TaskState.PENDING, description="Current execution status of the task."
    )
    priority: Priority = Field(..., description="Priority of the task.")
    skippable: bool = Field(
        default=False,
        description="Whether the task can be skipped without critically affecting crop success.",
    )
    completed_at: Optional[datetime] = Field(
        default=None, description="Timestamp when the task was marked completed."
    )

    @model_validator(mode="after")
    def validate_status_state(self):
        if self.status == TaskState.COMPLETED and self.completed_at is None:
            raise ValueError("completed_at is required when status is completed")
        if self.status != TaskState.COMPLETED and self.completed_at is not None:
            raise ValueError("completed_at can only be set when status is completed")
        if self.status == TaskState.SKIPPED and not self.skippable:
            raise ValueError("Only skippable tasks can be marked as skipped")
        return self


class CultivationTaskTranslatableFields(BaseModel):
    """
    Fields for representing the core attributes of a cultivation task, which are translatable.
    """

    task_name: str = Field(
        ..., description="Title of the cultivation activity (e.g., 'Apply Urea')."
    )
    description: Optional[str] = Field(
        None, description="Detailed description or instructions for the task."
    )
    notes: Optional[str] = Field(
        None, description="Additional notes or comments about the task."
    )
    reschedule_history: List[RescheduleRecord] = Field(
        default_factory=list,
        description="History of rescheduling events for this task.",
    )
    investments: List[Investment] = Field(
        default_factory=list,
        description=(
            "Investment line-items needed for this task. Investments with an "
            "agricultural_input_plan_id are tied to that plan; investments without one "
            "are general task-level costs."
        ),
    )
    agricultural_input_recommendation_id: Optional[str] = Field(
        None,
        description="UUID of the AgriculturalInputRecommendation this task is based on.",
    )


class CultivationTask(
    CultivationTaskInvariantFields, CultivationTaskTranslatableFields
):
    """
    Represents a single task or activity within a crop's cultivation calendar.
    """


TranslatedCultivationTaskFields = TranslatedFields[CultivationTaskTranslatableFields]


class CultivationTaskDocument(
    CultivationTaskInvariantFields, TranslatedCultivationTaskFields
):
    """
    Represents a cultivation task document stored in the database, with translated fields.
    """
