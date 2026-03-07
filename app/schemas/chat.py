import time
from enum import StrEnum
from typing import Annotated, Any, Literal
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field

from app.schemas.message import Message, UserMessagePart


class ChatMode(StrEnum):
    GENERAL = "general"
    FARM_SURVEY = "farm_survey"


class ChatStatus(StrEnum):
    ACTIVE = "active"
    ARCHIVED = "archived"


class Chat(BaseModel):
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    user_id: str
    title: str
    mode: ChatMode
    status: ChatStatus = ChatStatus.ACTIVE
    last_message_id: str | None = None
    last_process_id: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: float = Field(default_factory=time.time)
    updated_at: float = Field(default_factory=time.time)
    last_activity_at: float = Field(default_factory=time.time)


class CreateChatRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: str | None = None
    mode: ChatMode | None = None
    parts: list[UserMessagePart]


class NewMessageRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    chat_id: str
    parts: list[UserMessagePart]


NewChatOrMessageRequest = CreateChatRequest | NewMessageRequest


class ChatResumeRequest(BaseModel):
    chat_id: str
    process_id: str


class ChatRetryRequest(BaseModel):
    chat_id: str
    process_id: str


class ChatStopRequest(BaseModel):
    chat_id: str
    process_id: str


class ChatProcessPayload(BaseModel):
    chat_id: str
    user_message_id: str
    assistant_message_id: str
    mode: ChatMode
    partial_response: str = ""
    resume_count: int = 0
    retry_of_process_id: str | None = None
    saved_farm_id: str | None = None
    saved_farm_name: str | None = None


class ChatEventType(StrEnum):
    CHAT_UPSERTED = "chat_upserted"
    MESSAGE_UPSERTED = "message_upserted"
    MESSAGE_CHUNK = "message_chunk"
    MESSAGE_COMPLETED = "message_completed"
    FARM_PROFILE_SAVED = "farm_profile_saved"
    ERROR = "error"


class ChatUpsertedPayload(BaseModel):
    chat: Chat
    request_id: str | None = None


class MessageUpsertedPayload(BaseModel):
    chat_id: str
    message: Message


class MessageChunkPayload(BaseModel):
    chat_id: str
    process_id: str
    message_id: str
    delta: str


class MessageCompletedPayload(BaseModel):
    chat_id: str
    process_id: str
    message: Message


class FarmProfileSavedPayload(BaseModel):
    chat_id: str
    process_id: str
    message_id: str
    farm_id: str
    name: str


class ChatErrorPayload(BaseModel):
    code: str
    message: str
    chat_id: str | None = None
    process_id: str | None = None
    message_id: str | None = None


class ChatUpsertedEvent(BaseModel):
    event: Literal[ChatEventType.CHAT_UPSERTED] = ChatEventType.CHAT_UPSERTED
    payload: ChatUpsertedPayload


class MessageUpsertedEvent(BaseModel):
    event: Literal[ChatEventType.MESSAGE_UPSERTED] = ChatEventType.MESSAGE_UPSERTED
    payload: MessageUpsertedPayload


class MessageChunkEvent(BaseModel):
    event: Literal[ChatEventType.MESSAGE_CHUNK] = ChatEventType.MESSAGE_CHUNK
    payload: MessageChunkPayload


class MessageCompletedEvent(BaseModel):
    event: Literal[ChatEventType.MESSAGE_COMPLETED] = ChatEventType.MESSAGE_COMPLETED
    payload: MessageCompletedPayload


class FarmProfileSavedEvent(BaseModel):
    event: Literal[ChatEventType.FARM_PROFILE_SAVED] = ChatEventType.FARM_PROFILE_SAVED
    payload: FarmProfileSavedPayload


class ChatErrorEvent(BaseModel):
    event: Literal[ChatEventType.ERROR] = ChatEventType.ERROR
    payload: ChatErrorPayload


ChatOutboundEnvelope = Annotated[
    ChatUpsertedEvent
    | MessageUpsertedEvent
    | MessageChunkEvent
    | MessageCompletedEvent
    | FarmProfileSavedEvent
    | ChatErrorEvent,
    Field(discriminator="event"),
]
