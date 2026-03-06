# Any schema can be changed to mimic functionality of the applications like ChatGPT and optimized for langchain standards and db storage.
import time
from enum import StrEnum
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field


class ChatMode(StrEnum):
    GENERAL = "general"
    FARM_SURVEY = "farm_survey"


class Chat(BaseModel):
    # You can add additonal fields required according to app logic or business logic
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    title: str
    mode: ChatMode
    created_at: float = time.time()
