from datetime import date, datetime, timezone
from enum import Enum
from typing import List, Optional
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field, field_validator

from .generic_types import TranslatedFields


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
    def validate_dates(cls, v, values):
        if "old_start_date" in values and v < values["old_start_date"]:
            raise ValueError("New start date cannot be before old start date")
        return v

    @field_validator("new_end_date")
    def validate_end(cls, v, values):
        if "new_start_date" in values and v < values["new_start_date"]:
            raise ValueError("End date cannot be before start date")
        return v


class CultivationTask(BaseModel):
    """
    Represents a single task or activity within a crop's cultivation calendar.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="Unique identifier of the task.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    task_name: str = Field(
        ..., description="Title of the cultivation activity (e.g., 'Apply Urea')."
    )
    description: Optional[str] = Field(
        None, description="Detailed description or instructions for the task."
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
    notes: Optional[str] = Field(
        None, description="Additional notes or comments about the task."
    )
    reschedule_history: List[RescheduleRecord] = Field(
        default_factory=list,
        description="History of rescheduling events for this task.",
    )
    investment_ids: List[str] = Field(
        default_factory=list,
        description="List of IDs of Investment items associated with this task.",
    )


class CultivationCalendarFields(BaseModel):
    tasks: List[CultivationTask] = Field(
        ..., description="List of all cultivation tasks in this calendar."
    )


class CultivationCalendarMetadata(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        description="UUID of the cultivation calendar.",
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    crop_id: str = Field(
        ..., description="UUID of the CultivationCrop to which this calendar belongs."
    )
    start_date: date = Field(
        ..., description="Starting date of the cultivation schedule."
    )
    end_date: date = Field(..., description="Ending date of the cultivation schedule.")
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="Timestamp when this calendar was created.",
    )
    updated_at: Optional[datetime] = Field(
        default=None, description="Timestamp of the last update to this calendar."
    )

    @field_validator("end_date")
    def validate_schedule_dates(cls, v, values):
        if "start_date" in values and v < values["start_date"]:
            raise ValueError("Calendar end_date must be on or after start_date")
        return v


class CultivationCalendar(CultivationCalendarMetadata, CultivationCalendarFields):
    """
    Represents the cultivation calendar for a specific crop, containing its scheduled tasks.
    """


TranslatedCultivationCalendarFields = TranslatedFields[CultivationCalendarFields]


class CultivationCalendarDocument(
    CultivationCalendarMetadata, TranslatedCultivationCalendarFields
):
    """
    Represents a cultivation calendar document stored in the database, with translated fields.
    """
