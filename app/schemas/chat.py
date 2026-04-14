import time
from enum import StrEnum
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field


class ChatMode(StrEnum):
    GENERAL = "general"
    FARM_SURVEY = "farm_survey"


class Chat(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    user_id: str
    mode: ChatMode = ChatMode.GENERAL
    farm_profile_id: str | None = None
    process_id: str | None = None
    title: str
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_activity_at: float = Field(default_factory=time.time)
