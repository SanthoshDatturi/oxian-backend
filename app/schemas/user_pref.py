from datetime import datetime, timezone
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
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
