from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import get_current_user_id
from app.core.errors import ErrorCode, ValidationFailed
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


@router.post("/", response_model=FileUploadResponse, status_code=201)
async def create_upload_url(
    payload: FileUploadRequest,
    user_id: str = Depends(get_current_user_id),
) -> FileUploadResponse:
    """
    Generates a pre-signed URL to upload a file directly to storage.
    """
    if not payload.filename:
        raise ValidationFailed(
            "Filename is required.",
            code=ErrorCode.FILENAME_REQUIRED,
        )

    file_id, upload_url = await storage_service.create_upload_url(
        filename=payload.filename,
        user_id=user_id,
        mime_type=payload.mime_type,
    )

    return FileUploadResponse(file_id=file_id, upload_url=upload_url)


@router.get("/{file_id}/url", response_model=FileDownloadResponse)
async def get_download_url(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
) -> FileDownloadResponse:
    """
    Generates a pre-signed URL to download a file directly from storage.
    """
    download_url = await storage_service.generate_download_url(
        file_id=file_id,
        user_id=user_id,
    )

    return FileDownloadResponse(file_id=file_id, download_url=download_url)


@router.delete("/", status_code=204)
async def delete_file(
    file_id: str,
    user_id: str = Depends(get_current_user_id),
):
    """
    Deletes a temporary file by its file id.
    """
    await storage_service.delete_file(
        file_id=file_id,
        user_id=user_id,
    )
    return


@router.post("/tts", response_model=TtsFileResponse, status_code=201)
async def generate_tts_file(
    payload: TtsFileRequest,
    user_id: str = Depends(get_current_user_id),
) -> TtsFileResponse:
    file_id = await tts_service.generate_tts_file(
        entity_id=payload.entity_id,
        mode=payload.mode,
        user_id=user_id,
    )

    return TtsFileResponse(file_id=file_id)
