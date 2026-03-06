from typing import IO, Union

from app.integrations.storage import files
from app.integrations.storage.base import StorageEntity, StorageScope
from app.integrations.storage.errors import StorageDeleteError, StorageUploadError


async def validate_entity(entity: StorageEntity, entity_id: str):
    if not entity_id:
        raise ValueError("Entity id is required")

    # TODO: Validate entity once repositories are available.
    # Keeping this hook in place prevents silent acceptance of empty identifiers.


def _sanitize_prefix(prefix: str) -> str:
    cleaned = "/".join(segment for segment in prefix.split("/") if segment)
    return f"{cleaned}/" if cleaned else ""


def build_prefix(
    user_id: str,
    entity: StorageEntity,
    entity_id: str,
) -> str:
    raw_prefix = f"{user_id}/{entity.value}/{entity_id}"
    return _sanitize_prefix(raw_prefix)


async def upload_file(
    file_stream: Union[bytes, IO[bytes]],
    filename: str,
    user_id: str,
    entity: StorageEntity,
    entity_id: str,
    mime_type: str | None = None,
):
    # Validate enity to be used after implementing repositories
    try:
        await validate_entity(entity=entity, entity_id=entity_id)
    except ValueError as exc:
        raise StorageUploadError("Invalid upload request.") from exc

    return await files.upload(
        file_stream=file_stream,
        filename=filename,
        scope=StorageScope.USER,
        prefix=build_prefix(user_id=user_id, entity=entity, entity_id=entity_id),
        mime_type=mime_type,
    )


async def delete_file(blob_reference):
    try:
        container_name, blob_name = files.parse_blob_reference(blob_reference)
    except ValueError as exc:
        raise StorageDeleteError("Invalid blob reference.") from exc
    await files.delete(scope=StorageScope.USER, blob_name=blob_name)
