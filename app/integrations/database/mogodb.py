from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)

from app.core.config import settings

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


async def init_mongo_client() -> None:
    global _client, _database
    if _client is None:
        mongo_uri = settings.MONGO_DIRECT_URI or settings.MONGO_URI
        _client = AsyncIOMotorClient(mongo_uri, uuidRepresentation="standard")
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
        mongo_uri = settings.MONGO_DIRECT_URI or settings.MONGO_URI
        _client = AsyncIOMotorClient(mongo_uri, uuidRepresentation="standard")
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
