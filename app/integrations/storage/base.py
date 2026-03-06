from enum import StrEnum


class StorageScope(StrEnum):
    USER = "user"
    SYSTEM = "system"


class StorageEntity(StrEnum):
    CHAT = "chat"
    CROP = "crop"
