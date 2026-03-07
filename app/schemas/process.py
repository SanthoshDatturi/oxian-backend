import time
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field


class State(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    STOPPED = "stopped"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class Process(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    status: State
    payload: dict[str, Any] | None = Field(
        default=None,
        description="Service-specific resumable execution payload.",
    )
    error: ProcessError | None = None
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    completed_at: float | None = None
