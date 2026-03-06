import time
from enum import StrEnum
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, Field


class Role(StrEnum):
    # Define roles based on the LangChain standard roles
    HUMAN = "human"
    AI = "ai"
    pass


class Content(BaseModel):
    # Define the structure of the content based on the LangChain standard
    # How text, images, or other media types are structured in the message content
    # When sending history image and other files sent by user should only be send for first time only
    # If media or files in prev message history, they should be handled with RAG or for audio alt text should be generated (may be returned by AI when respoding).
    # can also contain data like LatLand from generic_types.py
    pass


class Message(BaseModel):
    # Define the structure of a message in the chat, including the role of the sender and the content of the message
    id: str = Field(
        default_factory=lambda: uuid4().hex,
        validation_alias=AliasChoices("id", "_id"),
        serialization_alias="_id",
    )
    chat_id: str
    role: Role
    content: Content
    created_at: float = time.time()
