from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.dependencies import authenticate_rest
from app.integrations.storage.base import StorageEntity
from app.integrations.storage.errors import (
    StorageAuthError,
    StorageBackendError,
    StorageDeleteError,
    StorageNotFoundError,
    StorageUploadError,
)
from app.services.storage import service

router = APIRouter(prefix="/files", tags=["Files"])


class FileUploadResponse(BaseModel):
    blob_reference: str


def _raise_for_storage_error(exc: Exception):
    detail = str(exc) or "Storage operation failed."

    if isinstance(exc, StorageNotFoundError):
        raise HTTPException(status_code=404, detail=detail)
    if isinstance(exc, StorageAuthError):
        raise HTTPException(status_code=503, detail=detail)
    if isinstance(exc, StorageBackendError):
        raise HTTPException(status_code=503, detail=detail)
    if isinstance(exc, (StorageUploadError, StorageDeleteError)):
        status_code = 400 if "Invalid" in detail else 502
        raise HTTPException(status_code=status_code, detail=detail)

    raise HTTPException(status_code=500, detail="Unexpected storage error.")


@router.post("/", response_model=FileUploadResponse, status_code=201)
async def upload_file(
    file: UploadFile = File(...),
    filename: str = Form(...),
    entity: StorageEntity = Form(...),
    entity_id: str = Form(...),
    mime_type: str | None = Form(default=None),
    user_payload: dict = Depends(authenticate_rest),
) -> FileUploadResponse:
    """
    Uploads a file as multipart/form-data to Azure Blob Storage and returns the URL.
    """
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    resolved_mime_type = mime_type or file.content_type

    try:
        blob_reference = await service.upload_file(
            file_stream=file.file,
            filename=filename,
            user_id=user_id,
            entity=entity,
            entity_id=entity_id,
            mime_type=resolved_mime_type,
        )
    except (
        StorageUploadError,
        StorageAuthError,
        StorageBackendError,
        StorageNotFoundError,
    ) as exc:
        _raise_for_storage_error(exc)

    return FileUploadResponse(blob_reference=blob_reference)


@router.delete("/", status_code=204)
async def delete_file(
    blob_reference: str,
    user_payload: dict = Depends(authenticate_rest),
):
    """
    Deletes a file from Azure Blob Storage given its URL.
    """
    if not (user_payload.get("uid") or user_payload.get("sub")):
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    try:
        await service.delete_file(
            blob_reference=blob_reference,
        )
    except (
        StorageDeleteError,
        StorageAuthError,
        StorageBackendError,
        StorageNotFoundError,
    ) as exc:
        _raise_for_storage_error(exc)
    return
