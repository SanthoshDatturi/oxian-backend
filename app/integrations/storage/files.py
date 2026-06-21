import inspect
import logging
from typing import IO, Union

from azure.core.exceptions import (
    AzureError,
    ClientAuthenticationError,
    HttpResponseError,
    ResourceNotFoundError,
    ServiceRequestError,
)
from datetime import datetime, timedelta, timezone
from azure.storage.blob import generate_blob_sas, BlobSasPermissions, ContentSettings

from .azure_blob_store import get_blob_service_client, get_container_client
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

logger = logging.getLogger(__name__)


def _guess_mime_type(data: bytes) -> str:
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8"):
        return "image/jpeg"
    if data.startswith(b"RIFF") and data[8:12] == b"WAVE":
        return "audio/wav"
    return "application/octet-stream"


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
    file_id: str,
    scope: StorageScope,
    mime_type: str | None = None,
):
    """
    Upload a file to the storage system.

    Args:
        file_stream: The file content as bytes or a file-like object.
        file_id: The file id used as the blob name.
        scope: The storage scope (user or system).
        mime_type: MIME type of the file.

    Returns:
        The URL or identifier of the uploaded file in the storage system.
    """
    try:
        data = await _read_bytes(file_stream)
        content_type = mime_type or _guess_mime_type(data)
        container_client = await get_container_client(scope.value)
        blob_client = container_client.get_blob_client(file_id)
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


async def generate_upload_url(
    file_id: str,
    scope: StorageScope,
    expires_in_seconds: int = 3600,
) -> str:
    """
    Generates a pre-signed URL (SAS token) for uploading a file to the storage system.

    Args:
        file_id: The file id used as the blob name.
        scope: The storage scope (user or system).
        expires_in_seconds: How long the upload URL should be valid.

    Returns:
        The pre-signed upload URL.
    """
    try:
        blob_service_client = get_blob_service_client()
        if not blob_service_client.account_name or not blob_service_client.credential or not hasattr(blob_service_client.credential, "account_key"):
            raise StorageBackendError("Invalid Azure storage credentials for SAS generation.")

        account_name = blob_service_client.account_name
        account_key = blob_service_client.credential.account_key
        container_name = scope.value

        # Ensure container exists
        container_client = await get_container_client(container_name)
        blob_client = container_client.get_blob_client(file_id)

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=file_id,
            account_key=account_key,
            permission=BlobSasPermissions(create=True, write=True),
            expiry=datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds),
        )

        return f"{blob_client.url}?{sas_token}"
    except ValueError as exc:
        raise StorageBackendError("Storage configuration error.") from exc
    except AzureError as exc:
        error_type = _map_azure_error(exc, operation="upload")
        raise error_type("Failed to generate upload url.") from exc


async def download(file_id: str, scope: StorageScope) -> bytes | None:
    """
    Download a file from the storage system.

    Args:
        file_id: The file id used as the blob name.
        scope: The storage scope (user or system).
    Returns:
        The content of the file as bytes.
    """
    try:
        container_client = await get_container_client(scope.value)
        blob_client = container_client.get_blob_client(file_id)
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


async def delete(scope: StorageScope, file_id: str):
    """
    Delete a file from the storage system.

    Args:
        file_id: The file id used as the blob name.
    """
    try:
        container_client = await get_container_client(scope.value)
        blob_client = container_client.get_blob_client(file_id)
        await blob_client.delete_blob()
    except ValueError as exc:
        raise StorageBackendError("Storage configuration error.") from exc
    except AzureError as exc:
        error_type = _map_azure_error(exc, operation="delete")
        raise error_type("Failed to delete file.") from exc


async def _blob_exists(file_id: str, scope: StorageScope) -> bool:
    container_client = await get_container_client(scope.value)
    blob_client = container_client.get_blob_client(file_id)
    try:
        await blob_client.get_blob_properties()
        return True
    except ResourceNotFoundError:
        return False


async def get_blob_content_type(file_id: str, scope: StorageScope) -> str | None:
    container_client = await get_container_client(scope.value)
    blob_client = container_client.get_blob_client(file_id)
    try:
        props = await blob_client.get_blob_properties()
        return props.content_settings.content_type
    except ResourceNotFoundError:
        return None


async def delete_many(
    file_ids: list[str],
    scope: StorageScope = StorageScope.USER,
) -> list[str]:
    """
    Delete all files in the storage system that match the given file ids.

    Args:
        scope: The storage scope (user or system).
        file_ids: File ids used as blob names to delete.
    """
    try:
        container_client = await get_container_client(scope.value)
        deleted_ids: list[str] = []
        for file_id in file_ids:
            try:
                blob_client = container_client.get_blob_client(file_id)
                await blob_client.delete_blob()
                deleted_ids.append(file_id)
            except AzureError as exc:
                error_type = _map_azure_error(exc, operation="delete")
                if error_type is StorageNotFoundError:
                    deleted_ids.append(file_id)
                    continue
                logger.exception(
                    "Failed to delete blob file_id=%s scope=%s",
                    file_id,
                    scope,
                )
        return deleted_ids
    except ValueError as exc:
        raise StorageBackendError("Storage configuration error.") from exc


async def delete_many_confirmed(
    file_ids: list[str],
    scope: StorageScope = StorageScope.USER,
) -> list[str]:
    """
    Delete blobs and return only ids confirmed absent from storage.
    """
    try:
        container_client = await get_container_client(scope.value)
        confirmed_ids: list[str] = []
        for file_id in file_ids:
            blob_client = container_client.get_blob_client(file_id)
            try:
                await blob_client.delete_blob()
            except AzureError as exc:
                error_type = _map_azure_error(exc, operation="delete")
                if error_type is not StorageNotFoundError:
                    logger.exception(
                        "Failed to delete blob file_id=%s scope=%s",
                        file_id,
                        scope,
                    )
                    continue

            try:
                if not await _blob_exists(file_id=file_id, scope=scope):
                    confirmed_ids.append(file_id)
            except AzureError:
                logger.exception(
                    "Failed to confirm blob deletion file_id=%s scope=%s",
                    file_id,
                    scope,
                )
        return confirmed_ids
    except ValueError as exc:
        raise StorageBackendError("Storage configuration error.") from exc
