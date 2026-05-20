import logging
import time
from collections import defaultdict
from typing import IO, Union

from app.integrations.storage import files
from app.integrations.storage.base import StorageEntity, StorageScope
from app.integrations.storage.errors import (
    StorageBackendError,
    StorageDeleteError,
    StorageNotFoundError,
    StorageUploadError,
)
from app.repositories import files_repository
from app.schemas.file import File, FileStatus

logger = logging.getLogger(__name__)

TEMP_FILE_RETENTION_SECONDS = 5 * 60 * 60


async def _delete_blob_if_exists(file: File) -> bool:
    try:
        await files.delete(scope=file.storage_scope, file_id=file.id)
        return True
    except StorageNotFoundError:
        return True


async def upload_file(
    file_stream: Union[bytes, IO[bytes]],
    filename: str,
    user_id: str,
    mime_type: str | None = None,
) -> str:
    stored_file = File(
        user_id=user_id,
        filename=filename,
        content_type=mime_type or "application/octet-stream",
        status=FileStatus.TEMP,
    )

    await files.upload(
        file_stream=file_stream,
        file_id=stored_file.id,
        scope=stored_file.storage_scope,
        mime_type=stored_file.content_type,
    )

    try:
        await files_repository.create(stored_file)
    except Exception as exc:
        try:
            await _delete_blob_if_exists(stored_file)
        except Exception:
            logger.exception(
                "Failed to rollback uploaded blob for file_id=%s user_id=%s",
                stored_file.id,
                user_id,
            )
        raise StorageBackendError("Failed to persist file metadata.") from exc

    return stored_file.id


async def delete_file(file_id: str, user_id: str) -> None:
    stored_file = await files_repository.get_by_id(file_id=file_id, user_id=user_id)
    if stored_file is None or stored_file.status != FileStatus.TEMP:
        raise StorageNotFoundError("File not found.")

    await _delete_blob_if_exists(stored_file)
    deleted = await files_repository.delete_temp(file_id=file_id, user_id=user_id)
    if deleted is None:
        raise StorageDeleteError("Failed to delete temporary file metadata.")


async def activate_files(
    file_ids: list[str],
    entity: StorageEntity,
    entity_id: str,
    user_id: str,
) -> list[File]:
    try:
        return await files_repository.activate_for_entity(
            file_ids=file_ids,
            entity=entity,
            entity_id=entity_id,
            user_id=user_id,
        )
    except ValueError as exc:
        raise StorageUploadError(str(exc)) from exc


async def download_file(file_id: str, user_id: str) -> tuple[File, bytes]:
    stored_file = await files_repository.get_by_id(file_id=file_id, user_id=user_id)
    if stored_file is None:
        raise StorageNotFoundError("File not found.")

    data = await files.download(file_id=stored_file.id, scope=stored_file.storage_scope)
    if data is None:
        raise StorageNotFoundError("File data not found in storage backend.")

    return stored_file, data


async def cleanup_expired_temporary_files() -> int:
    cutoff_ts = time.time() - TEMP_FILE_RETENTION_SECONDS
    expired_files = await files_repository.list_expired_temp(cutoff_ts=cutoff_ts)
    deleted_ids: list[str] = []
    file_ids_by_scope: dict[StorageScope, list[str]] = defaultdict(list)

    for stored_file in expired_files:
        file_ids_by_scope[stored_file.storage_scope].append(stored_file.id)

    for storage_scope, file_ids in file_ids_by_scope.items():
        try:
            deleted_ids.extend(
                await files.delete_many(file_ids=file_ids, scope=storage_scope)
            )
        except Exception:
            logger.exception(
                "Failed to delete expired blobs for scope=%s file_ids=%s",
                storage_scope,
                file_ids,
            )

    if deleted_ids:
        await files_repository.delete_many_by_ids(deleted_ids)

    return len(deleted_ids)
