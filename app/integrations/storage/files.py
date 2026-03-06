import inspect
from typing import IO, Union
from urllib.parse import urlparse

from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from azure.storage.blob import ContentSettings

from .azure_blob_store import get_container_client
from .base import StorageScope
from .errors import (
    StorageAuthError,
    StorageBackendError,
    StorageDeleteError,
    StorageDownloadError,
    StorageListError,
    StorageNotFoundError,
    StorageUploadError,
)


def _guess_mime_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    return "application/octet-stream"


def _normalize_prefix(prefix: str) -> str:
    if not prefix:
        return ""
    return prefix.lstrip("/")


def _build_blob_name(prefix: str, filename: str) -> str:
    if not prefix:
        return filename
    if prefix.endswith("/"):
        return f"{prefix}{filename}"
    return f"{prefix}/{filename}"


def parse_blob_reference(blob_reference: str) -> tuple[str, str]:
    parsed = urlparse(blob_reference)
    if parsed.scheme and parsed.netloc:
        path = parsed.path.lstrip("/")
        if "/" not in path:
            raise ValueError("Invalid blob reference URL.")
        container_name, blob_name = path.split("/", 1)
        return container_name, blob_name

    if "/" in blob_reference:
        container_name, blob_name = blob_reference.split("/", 1)
        if container_name and blob_name:
            return container_name, blob_name

    raise ValueError("Blob reference must be a URL or 'container/blob' identifier.")


def _split_prefix(prefix: str) -> tuple[str | None, str]:
    parsed = urlparse(prefix)
    if parsed.scheme and parsed.netloc:
        path = parsed.path.lstrip("/")
        if not path:
            return None, ""
        if "/" in path:
            container_name, blob_prefix = path.split("/", 1)
            return container_name, blob_prefix
        return path, ""

    normalized = _normalize_prefix(prefix)
    if "/" in normalized:
        container_name, blob_prefix = normalized.split("/", 1)
        if container_name in {scope.value for scope in StorageScope}:
            return container_name, blob_prefix
    return None, normalized


async def _read_bytes(file_stream: Union[bytes, IO[bytes]]) -> bytes:
    if isinstance(file_stream, (bytes, bytearray, memoryview)):
        return bytes(file_stream)

    if hasattr(file_stream, "read"):
        data = file_stream.read()
        if inspect.isawaitable(data):
            data = await data
        if isinstance(data, str):
            data = data.encode()
        if not isinstance(data, (bytes, bytearray, memoryview)):
            raise TypeError("file_stream.read() must return bytes.")
        return bytes(data)

    raise TypeError("file_stream must be bytes or a file-like object.")


def _map_azure_error(error: AzureError, *, operation: str):
    if isinstance(error, ClientAuthenticationError):
        return StorageAuthError
    if isinstance(error, ResourceNotFoundError):
        return StorageNotFoundError
    if isinstance(error, ServiceRequestError):
        return StorageBackendError
    if isinstance(error, HttpResponseError):
        status = getattr(error, "status_code", None)
        if status in (401, 403):
            return StorageAuthError
        if status == 404:
            return StorageNotFoundError
        if status and status >= 500:
            return StorageBackendError
    if operation == "upload":
        return StorageUploadError
    if operation == "download":
        return StorageDownloadError
    if operation == "delete":
        return StorageDeleteError
    if operation == "list":
        return StorageListError
    return StorageBackendError


async def upload(
    file_stream: Union[bytes, IO[bytes]],
    filename: str,
    scope: StorageScope,
    prefix: str,
    mime_type: str | None = None,
):
    """
    Upload a file to the storage system.

    Args:
        file_stream: The file content as bytes or a file-like object.
        filename: The name of the file to be stored.
        scope: The storage scope (user or system).
        prefix: prefix for the storage path.
        mime_type: MIME type of the file.

    Returns:
        The URL or identifier of the uploaded file in the storage system.
    """
    try:
        data = await _read_bytes(file_stream)
        content_type = mime_type or _guess_mime_type(data)
        container_client = await get_container_client(scope.value)
        blob_name = _build_blob_name(prefix, filename)
        blob_client = container_client.get_blob_client(blob_name)
        await blob_client.upload_blob(
            data,
            overwrite=True,
            content_settings=ContentSettings(content_type=content_type),
        )
        return blob_client.url
    except TypeError as exc:
        raise StorageUploadError("Invalid file stream.") from exc
    except ValueError as exc:
        raise StorageBackendError("Storage configuration error.") from exc
    except AzureError as exc:
        error_type = _map_azure_error(exc, operation="upload")
        raise error_type("Failed to upload file.") from exc


async def download(blob_reference: str) -> bytes | None:
    """
    Download a file from the storage system.

    Args:
        blob_reference: The URL or identifier of the file to be downloaded.
    Returns:
        The content of the file as bytes.
    """
    try:
        container_name, blob_name = parse_blob_reference(blob_reference)
    except ValueError as exc:
        raise StorageDownloadError("Invalid blob reference.") from exc
    try:
        container_client = await get_container_client(container_name)
        blob_client = container_client.get_blob_client(blob_name)
        downloader = await blob_client.download_blob()
        data = await downloader.readall()
        if isinstance(data, str):
            return data.encode()
        return data
    except ValueError as exc:
        raise StorageBackendError("Storage configuration error.") from exc
    except AzureError as exc:
        error_type = _map_azure_error(exc, operation="download")
        raise error_type("Failed to download file.") from exc


async def delete(scope: StorageScope, blob_name: str):
    """
    Delete a file from the storage system.

    Args:
        blob_reference: The URL or identifier of the file to be deleted.
    """
    try:
        container_client = await get_container_client(scope.value)
        blob_client = container_client.get_blob_client(blob_name)
        await blob_client.delete_blob()
    except ValueError as exc:
        raise StorageBackendError("Storage configuration error.") from exc
    except AzureError as exc:
        error_type = _map_azure_error(exc, operation="delete")
        raise error_type("Failed to delete file.") from exc


async def delete_many(scope: StorageScope, prefix: str):
    """
    Delete all files in the storage system that match a given prefix.

    Args:
        scope: The storage scope (user or system).
        prefix: The prefix to filter files by (e.g., "users/{user_id}/chats/").
    """
    try:
        container_client = await get_container_client(scope.value)
        async for blob in container_client.list_blobs(name_starts_with=prefix or None):
            blob_client = container_client.get_blob_client(blob.name)
            await blob_client.delete_blob()
    except ValueError as exc:
        raise StorageBackendError("Storage configuration error.") from exc
    except AzureError as exc:
        error_type = _map_azure_error(exc, operation="delete")
        raise error_type("Failed to delete files.") from exc
