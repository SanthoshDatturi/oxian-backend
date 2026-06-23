from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.security import authenticate_rest
from app.infrastructure.storage.errors import (
    StorageAuthError,
    StorageBackendError,
    StorageDeleteError,
    StorageDownloadError,
    StorageNotFoundError,
    StorageUploadError,
)
from app.services import storage_service, tts_service
from app.services.tts_service import TtsMode

router = APIRouter(prefix="/files", tags=["Files"])


class FileUploadRequest(BaseModel):
    filename: str
    mime_type: str


class FileUploadResponse(BaseModel):
    file_id: str
    upload_url: str


class FileDownloadResponse(BaseModel):
    file_id: str
    download_url: str


class TtsFileRequest(BaseModel):
    mode: TtsMode
    entity_id: str


class TtsFileResponse(BaseModel):
    file_id: str


def _raise_for_storage_error(exc: Exception):
    detail = str(exc) or "Storage operation failed."

    if isinstance(exc, StorageNotFoundError):
        raise HTTPException(status_code=404, detail=detail)
    if isinstance(exc, StorageAuthError):
        raise HTTPException(status_code=503, detail=detail)
    if isinstance(exc, StorageBackendError):
        raise HTTPException(status_code=503, detail=detail)
    if isinstance(exc, (StorageUploadError, StorageDeleteError, StorageDownloadError)):
        status_code = 400 if "Invalid" in detail else 502
        raise HTTPException(status_code=status_code, detail=detail)

    raise HTTPException(status_code=500, detail="Unexpected storage error.")


@router.post("/", response_model=FileUploadResponse, status_code=201)
async def create_upload_url(
    payload: FileUploadRequest,
    user_payload: dict = Depends(authenticate_rest),
) -> FileUploadResponse:
    """
    Generates a pre-signed URL to upload a file directly to storage.
    """
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    if not payload.filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    try:
        file_id, upload_url = await storage_service.create_upload_url(
            filename=payload.filename,
            user_id=user_id,
            mime_type=payload.mime_type,
        )
    except (
        StorageUploadError,
        StorageAuthError,
        StorageBackendError,
        StorageNotFoundError,
    ) as exc:
        _raise_for_storage_error(exc)

    return FileUploadResponse(file_id=file_id, upload_url=upload_url)


@router.get("/{file_id}/url", response_model=FileDownloadResponse)
async def get_download_url(
    file_id: str,
    user_payload: dict = Depends(authenticate_rest),
) -> FileDownloadResponse:
    """
    Generates a pre-signed URL to download a file directly from storage.
    """
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    try:
        download_url = await storage_service.generate_download_url(
            file_id=file_id,
            user_id=user_id,
        )
    except (
        StorageDownloadError,
        StorageAuthError,
        StorageBackendError,
        StorageNotFoundError,
    ) as exc:
        _raise_for_storage_error(exc)

    return FileDownloadResponse(file_id=file_id, download_url=download_url)


@router.delete("/", status_code=204)
async def delete_file(
    file_id: str,
    user_payload: dict = Depends(authenticate_rest),
):
    """
    Deletes a temporary file by its file id.
    """
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    try:
        await storage_service.delete_file(
            file_id=file_id,
            user_id=user_id,
        )
    except (
        StorageDeleteError,
        StorageAuthError,
        StorageBackendError,
        StorageNotFoundError,
    ) as exc:
        _raise_for_storage_error(exc)
    return


@router.post("/tts", response_model=TtsFileResponse, status_code=201)
async def generate_tts_file(
    payload: TtsFileRequest,
    user_payload: dict = Depends(authenticate_rest),
) -> TtsFileResponse:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    try:
        file_id = await tts_service.generate_tts_file(
            entity_id=payload.entity_id,
            mode=payload.mode,
            user_id=user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except (
        StorageUploadError,
        StorageAuthError,
        StorageBackendError,
        StorageNotFoundError,
    ) as exc:
        _raise_for_storage_error(exc)

    return TtsFileResponse(file_id=file_id)
