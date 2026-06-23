from datetime import datetime, timezone
from enum import StrEnum
from typing import Optional
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field

from app.infrastructure.storage.enums import StorageScope


class FileStatus(StrEnum):
    TEMP = "temp"
    ACTIVE = "active"
    DELETING = "deleting"


class File(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    user_id: str
    filename: str
    content_type: str
    storage_scope: StorageScope = StorageScope.USER
    entity_id: Optional[str] = Field(default=None)
    status: FileStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
