from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)

from app.core.config import settings

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


def _get_mongo_uri() -> str:
    mongo_uri = settings.MONGO_URI or settings.MONGO_DIRECT_URI
    if not mongo_uri:
        raise ValueError("Mongo connection string is not configured.")
    return mongo_uri


async def init_mongo_client() -> None:
    global _client, _database
    if _client is None:
        _client = AsyncIOMotorClient(_get_mongo_uri(), uuidRepresentation="standard")
    if _database is None:
        _database = _client[settings.MONGO_DB_NAME]


async def close_mongo_client() -> None:
    global _client, _database
    if _client is not None:
        _client.close()
    _client = None
    _database = None


def _get_collection(collection_name: str) -> AsyncIOMotorCollection:
    global _client, _database
    if _client is None:
        _client = AsyncIOMotorClient(_get_mongo_uri(), uuidRepresentation="standard")
    if _database is None:
        _database = _client[settings.MONGO_DB_NAME]
    return _database[collection_name]


def get_processes_collection() -> AsyncIOMotorCollection:
    return _get_collection("processes")


def get_chats_collection() -> AsyncIOMotorCollection:
    return _get_collection("chats")


def get_messages_collection() -> AsyncIOMotorCollection:
    return _get_collection("messages")


def get_files_collection() -> AsyncIOMotorCollection:
    return _get_collection("files")


def get_farm_profiles_collection() -> AsyncIOMotorCollection:
    return _get_collection("farm_profiles")


def get_user_prefs_collection() -> AsyncIOMotorCollection:
    return _get_collection("user_prefs")
