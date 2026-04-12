import time
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field

from app.schemas.generic_types import LatLang


class Role(StrEnum):
    HUMAN = "human"
    AI = "ai"


class PartType(StrEnum):
    TEXT = "text"
    FILE = "file"
    LOCATION = "location"
    FARM_PROFILE_REFERENCE = "farm_profile_reference"


class FileMediaKind(StrEnum):
    IMAGE = "image"
    AUDIO = "audio"
    DOCUMENT = "document"


class TextPart(BaseModel):
    type: Literal[PartType.TEXT] = PartType.TEXT
    text: str


class FilePart(BaseModel):
    type: Literal[PartType.FILE] = PartType.FILE
    blob_reference: str
    filename: str
    mime_type: str
    media_kind: FileMediaKind
    caption: str | None = None
    extracted_text: str | None = Field(
        default=None,
        description="Text summary/transcript persisted for future history reuse.",
    )


class LocationPart(BaseModel):
    type: Literal[PartType.LOCATION] = PartType.LOCATION
    location: LatLang
    label: str | None = None


class FarmProfileReferencePart(BaseModel):
    type: Literal[PartType.FARM_PROFILE_REFERENCE] = PartType.FARM_PROFILE_REFERENCE
    farm_id: str
    name: str


MessagePart = Annotated[
    TextPart | FilePart | LocationPart | FarmProfileReferencePart,
    Field(discriminator="type"),
]


class MessageUsage(BaseModel):
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    input_token_details: dict[str, Any] | None = None
    output_token_details: dict[str, Any] | None = None


class MessageError(BaseModel):
    code: str
    message: str
    details: dict[str, Any] | None = None


class MessageStatus(StrEnum):
    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETE = "complete"
    STOPPED = "stopped"
    ERROR = "error"


class Message(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    chat_id: str
    user_id: str
    role: Role
    status: MessageStatus = MessageStatus.PENDING
    parts: list[MessagePart] = Field(default_factory=list)
    usage: MessageUsage | None = None
    error: MessageError | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
