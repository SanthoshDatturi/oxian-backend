from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel

from app.core.dependencies import authenticate_rest
from app.integrations.storage.errors import (
    StorageAuthError,
    StorageBackendError,
    StorageDeleteError,
    StorageNotFoundError,
    StorageUploadError,
)
from app.services.storage import service
from app.services.tts import service as tts_service
from app.services.tts.service import TtsMode

router = APIRouter(prefix="/files", tags=["Files"])


class FileUploadResponse(BaseModel):
    file_id: str


class TtsFileRequest(BaseModel):
    mode: TtsMode
    entity_id: str
    text_or_json_data: str


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
    filename: str | None = Form(default=None),
    mime_type: str | None = Form(default=None),
    user_payload: dict = Depends(authenticate_rest),
) -> FileUploadResponse:
    """
    Uploads a file as multipart/form-data and stores temporary metadata.
    """
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    resolved_filename = filename or file.filename
    if not resolved_filename:
        raise HTTPException(status_code=400, detail="Filename is required")

    resolved_mime_type = mime_type or file.content_type

    try:
        file_id = await service.upload_file(
            file_stream=file.file,
            filename=resolved_filename,
            user_id=user_id,
            mime_type=resolved_mime_type,
        )
    except (
        StorageUploadError,
        StorageAuthError,
        StorageBackendError,
        StorageNotFoundError,
    ) as exc:
        _raise_for_storage_error(exc)

    return FileUploadResponse(file_id=file_id)


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
        await service.delete_file(
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


@router.post("/tts", response_model=FileUploadResponse, status_code=201)
async def generate_tts_file(
    payload: TtsFileRequest,
    user_payload: dict = Depends(authenticate_rest),
) -> FileUploadResponse:
    user_id = user_payload.get("uid") or user_payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    try:
        file_id = await tts_service.generate_tts_file(
            entity_id=payload.entity_id,
            mode=payload.mode,
            text_or_json_data=payload.text_or_json_data,
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

    return FileUploadResponse(file_id=file_id)
