import time
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field

from app.schemas.chat import ChatMode
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
    file_id: str
    media_kind: FileMediaKind | None = None
    caption: str | None = None


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


IncomingMessagePart = Annotated[
    TextPart | FilePart | LocationPart,
    Field(discriminator="type"),
]


class NewChatMessageInput(BaseModel):
    mode: ChatMode
    parts: list[IncomingMessagePart]
    farm_profile_id: str | None = None


class ChatMessageInput(BaseModel):
    parts: list[IncomingMessagePart]


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


class Message(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    chat_id: str
    user_id: str
    role: Role
    parts: list[MessagePart] = Field(default_factory=list)
    usage: MessageUsage | None = None
    error: MessageError | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
