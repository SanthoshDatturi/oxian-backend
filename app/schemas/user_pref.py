import time
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field


class UserPreference(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    user_id: str
    language_code: str | None = None
    voice_response_enabled: bool = False
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
