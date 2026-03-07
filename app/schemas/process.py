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
    """
    Used for hadling different events of a process.
    Process is used for storing the intermediate data of multi stage long running process.
    The process will be deleted if the process is completed or on cancel event etc,.
    """

    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    # The step that is currently being executed. It can be None if the process is only single step.
    # If there are multiple steps, it will be the name of the step that is currently being executed.
    step: Optional[StrEnum] = Field(
        default=None,
        description="Should be defined as a StrEnum by respective services",
    )
    status: State = Field(
        description="If the process is only single step, it will be the status of the process. If there are multiple steps, it will be the status of the current step."
    )
    pay_load: Optional[JsonString] = Field(
        default=None,
        description="A process does'nt care about the data, it just used for tracking the actual process happening",
    )
