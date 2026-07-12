import logging
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import IO, Union

from app.core.errors import (
    DependencyUnavailable,
    ErrorCode,
    ValidationFailed,
)
from app.core.errors import (
    FileNotFound as FileNotFoundAppError,
)
from app.infrastructure.storage import operations as files
from app.infrastructure.storage.enums import StorageEntity, StorageScope
from app.infrastructure.storage.errors import (
    StorageBackendError,
    StorageDeleteError,
    StorageNotFoundError,
)
from app.repositories import files_repository
from app.repositories.errors import RepositoryError
from app.schemas.file import File, FileStatus

logger = logging.getLogger(__name__)

TEMP_FILE_RETENTION = timedelta(hours=5)


def _storage_unavailable() -> DependencyUnavailable:
    return DependencyUnavailable(
        "File storage is temporarily unavailable.",
        code=ErrorCode.STORAGE_UNAVAILABLE,
    )


async def _delete_blob_if_exists(file: File) -> bool:
    try:
        await files.delete(scope=file.storage_scope, file_id=file.id)
        return True
    except StorageNotFoundError:
        return True


async def create_upload_url(
    filename: str,
    user_id: str,
    mime_type: str,
) -> tuple[str, str]:
    """
    Public upload API. Use this at external boundaries to generate a
    signed URL for direct upload.
    """
    stored_file = File(
        user_id=user_id,
        filename=filename,
        content_type=mime_type or "application/octet-stream",
        status=FileStatus.TEMP,
    )

    try:
        await files_repository.create(stored_file)
    except Exception as exc:
        raise _storage_unavailable() from exc

    try:
        upload_url = await files.generate_upload_url(
            file_id=stored_file.id,
            scope=stored_file.storage_scope,
        )
    except Exception as exc:
        try:
            await files_repository.delete_many_by_ids([stored_file.id])
        except Exception:
            logger.exception(
                "Failed to rollback file metadata for file_id=%s user_id=%s",
                stored_file.id,
                stored_file.user_id,
            )
        raise _storage_unavailable() from exc

    return stored_file.id, upload_url


async def generate_download_url(file_id: str, user_id: str) -> str:
    """
    Public API to generate a signed download URL. Validates ownership.
    """
    stored_file = await files_repository.get_by_id(file_id=file_id, user_id=user_id)
    if stored_file is None or stored_file.status == FileStatus.DELETING:
        raise FileNotFoundAppError(file_id)

    try:
        download_url = await files.generate_download_url(
            file_id=stored_file.id,
            scope=stored_file.storage_scope,
        )
    except Exception as exc:
        raise _storage_unavailable() from exc

    return download_url


async def _upload_file(
    file_stream: Union[bytes, IO[bytes]],
    stored_file: File,
) -> File:
    """
    Private upload API for callers that have already built trusted metadata.
    """
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
                stored_file.user_id,
            )
        raise StorageBackendError("Failed to persist file metadata.") from exc

    return stored_file


async def _delete_files(
    stored_files: list[File],
) -> int:
    if not stored_files:
        return 0

    try:
        marked_files = await files_repository.mark_many_deleting(
            [stored_file.id for stored_file in stored_files]
        )
    except Exception as exc:
        raise StorageDeleteError("Failed to mark files for deletion.") from exc

    if not marked_files:
        raise StorageDeleteError("Failed to mark files for deletion.")

    confirmed_deleted_ids: list[str] = []
    file_ids_by_scope: dict[StorageScope, list[str]] = defaultdict(list)

    for stored_file in marked_files:
        file_ids_by_scope[stored_file.storage_scope].append(stored_file.id)

    for storage_scope, file_ids in file_ids_by_scope.items():
        try:
            confirmed_deleted_ids.extend(
                await files.delete_many_confirmed(
                    file_ids=file_ids,
                    scope=storage_scope,
                )
            )
        except Exception:
            logger.exception(
                "Failed to delete files for scope=%s file_ids=%s",
                storage_scope,
                file_ids,
            )

    if confirmed_deleted_ids:
        await files_repository.delete_many_by_ids(confirmed_deleted_ids)

    return len(confirmed_deleted_ids)


async def delete_file(file_id: str, user_id: str) -> None:
    """
    Public delete API. Validates that the file belongs to the user and is still
    temporary before removing it.
    """
    stored_file = await files_repository.mark_temp_deleting(
        file_id=file_id,
        user_id=user_id,
    )
    if stored_file is None:
        raise FileNotFoundAppError(file_id)

    try:
        await _delete_files([stored_file])
    except StorageDeleteError as exc:
        raise _storage_unavailable() from exc


async def _delete_files_by_entity(entity_id: str, user_id: str) -> None:
    """
    Private delete API for callers that already validated entity ownership.
    """
    stored_files = await files_repository.list_by_entity(
        entity_id=entity_id,
        user_id=user_id,
    )
    await _delete_files(stored_files)


async def _activate_files(
    file_ids: list[str],
    entity: StorageEntity,
    entity_id: str,
    user_id: str,
) -> list[File]:
    """
    Private activation API for internal services.
    """
    try:
        activated_files = await files_repository.activate_for_entity(
            file_ids=file_ids,
            entity=entity,
            entity_id=entity_id,
            user_id=user_id,
        )

        for stored_file in activated_files:
            try:
                actual_content_type = await files.get_blob_content_type(
                    file_id=stored_file.id, scope=stored_file.storage_scope
                )
                if (
                    actual_content_type
                    and actual_content_type != stored_file.content_type
                ):
                    await files_repository.update_content_type(
                        stored_file.id, actual_content_type
                    )
                    stored_file.content_type = actual_content_type
            except Exception:
                logger.exception(
                    "Failed to sync blob content type for file_id=%s", stored_file.id
                )

        return activated_files
    except RepositoryError as exc:
        raise ValidationFailed(
            str(exc),
            code=ErrorCode.INVALID_FILE_STATE,
        ) from exc


async def download_file(file_id: str, user_id: str) -> tuple[File, bytes]:
    """
    Public download API. Validates ownership before reading blob data.
    """
    stored_file = await files_repository.get_by_id(file_id=file_id, user_id=user_id)
    if stored_file is None or stored_file.status == FileStatus.DELETING:
        raise FileNotFoundAppError(file_id)

    return await _download_file(stored_file)


async def _download_file(stored_file: File) -> tuple[File, bytes]:
    """
    Private download API for callers that already validated the File object.
    """
    if stored_file.status == FileStatus.DELETING:
        raise FileNotFoundAppError(stored_file.id)

    data = await files.download(file_id=stored_file.id, scope=stored_file.storage_scope)
    if data is None:
        raise FileNotFoundAppError(stored_file.id)

    return stored_file, data


async def cleanup_expired_temporary_files() -> int:
    cutoff_at = datetime.now(timezone.utc) - TEMP_FILE_RETENTION
    expired_files = await files_repository.list_expired_temp(cutoff_at=cutoff_at)
    deleting_files = await files_repository.list_deleting()
    files_by_id = {stored_file.id: stored_file for stored_file in deleting_files}
    files_by_id.update({stored_file.id: stored_file for stored_file in expired_files})
    return await _delete_files(list(files_by_id.values()))
