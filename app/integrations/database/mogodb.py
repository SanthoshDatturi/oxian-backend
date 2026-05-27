from urllib.parse import urlsplit

from motor.motor_asyncio import (
    AsyncIOMotorClient,
    AsyncIOMotorCollection,
    AsyncIOMotorDatabase,
)
from pymongo.errors import ConfigurationError, PyMongoError
from pymongo.uri_parser import parse_uri

from app.core.config import settings

_client: AsyncIOMotorClient | None = None
_database: AsyncIOMotorDatabase | None = None


def _get_mongo_uris() -> list[str]:
    mongo_uris = [uri for uri in (settings.MONGO_URI, settings.MONGO_DIRECT_URI) if uri]
    if not mongo_uris:
        raise ValueError("Mongo connection string is not configured.")
    return mongo_uris


def _redact_mongo_uri(mongo_uri: str) -> str:
    try:
        split_uri = urlsplit(mongo_uri)
        if split_uri.scheme in {"mongodb", "mongodb+srv"} and split_uri.hostname:
            auth = f"{split_uri.username}:***@" if split_uri.username else ""
            port = f":{split_uri.port}" if split_uri.port else ""
            return f"{split_uri.scheme}://{auth}{split_uri.hostname}{port}/..."
    except ValueError:
        pass

    try:
        parsed = parse_uri(mongo_uri, validate=True, warn=True)
    except Exception:
        return "<invalid Mongo URI>"

    username = parsed.get("username")
    nodelist = parsed.get("nodelist", [])
    hosts = ",".join(f"{host}:{port}" for host, port in nodelist) or "<unknown-host>"
    scheme = "mongodb+srv" if parsed.get("fqdn") else "mongodb"
    auth = f"{username}:***@" if username else ""
    return f"{scheme}://{auth}{hosts}/..."


def _database_name() -> str:
    if not settings.MONGO_DB_NAME:
        raise ValueError("Mongo database name is not configured.")
    return settings.MONGO_DB_NAME


async def _create_verified_client(mongo_uri: str) -> AsyncIOMotorClient:
    client = AsyncIOMotorClient(
        mongo_uri,
        uuidRepresentation="standard",
        serverSelectionTimeoutMS=5000,
    )
    try:
        await client.admin.command("ping")
    except Exception:
        client.close()
        raise
    return client


async def _connect() -> tuple[AsyncIOMotorClient, AsyncIOMotorDatabase]:
    errors: list[str] = []
    for mongo_uri in _get_mongo_uris():
        try:
            client = await _create_verified_client(mongo_uri)
            return client, client[_database_name()]
        except PyMongoError as exc:
            errors.append(f"{_redact_mongo_uri(mongo_uri)}: {exc}")

    if errors:
        details = " | ".join(errors)
        raise ConfigurationError(f"Could not connect to MongoDB. {details}")

    raise ValueError("Mongo connection string is not configured.")


async def init_mongo_client() -> None:
    global _client, _database
    if _client is None or _database is None:
        _client, _database = await _connect()


async def close_mongo_client() -> None:
    global _client, _database
    if _client is not None:
        _client.close()
    _client = None
    _database = None


def _get_collection(collection_name: str) -> AsyncIOMotorCollection:
    if _database is None:
        raise RuntimeError("Mongo client is not initialized.")
    return _database[collection_name]


def get_processes_collection() -> AsyncIOMotorCollection:
    return _get_collection("processes")


def get_chats_collection() -> AsyncIOMotorCollection:
    return _get_collection("chats")


def get_messages_collection() -> AsyncIOMotorCollection:
    return _get_collection("messages")


def get_files_collection() -> AsyncIOMotorCollection:
    return _get_collection("files")


def get_crop_images_collection() -> AsyncIOMotorCollection:
    return _get_collection("crop_images")


def get_farm_profiles_collection() -> AsyncIOMotorCollection:
    return _get_collection("farm_profiles")


def get_user_prefs_collection() -> AsyncIOMotorCollection:
    return _get_collection("user_prefs")


def get_crop_image_generate_requests_collection() -> AsyncIOMotorCollection:
    return _get_collection("crop_image_generate_requests")


def get_crop_recommendations_collection() -> AsyncIOMotorCollection:
    return _get_collection("crop_recommendations")
