from enum import StrEnum
from typing import Optional, TypeAlias
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field

JsonString: TypeAlias = str


class State(StrEnum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Process(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    # The step that is currently being executed. It can be None if the process is only single step.
    # If there are multiple steps, it will be the name of the step that is currently being executed.
    step: Optional[StrEnum] = None
    # If the process is only single step, it will be the status of the process. If there are multiple steps, it will be the status of the current step.
    status: State
    data: JsonString
