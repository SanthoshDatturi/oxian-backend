import logging
from enum import StrEnum

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.core.errors import (
    DependencyUnavailable,
    ErrorCode,
    ExternalServiceFailed,
    MessageNotFound,
    ValidationFailed,
)
from app.infrastructure.providers.gemini import is_gemini_dependency_error
from app.infrastructure.storage.enums import StorageEntity, StorageScope
from app.infrastructure.storage.errors import StorageError
from app.schemas.file import File, FileStatus
from app.schemas.message import FileMediaKind, FilePart, TextPart
from app.services import chat_service, storage_service

logger = logging.getLogger(__name__)

TTS_VOICE_NAME = "Kore"
TTS_MIME_TYPE = "audio/wav"


class TtsMode(StrEnum):
    MESSAGE = "message"
    CROP = "crop"


def _extract_audio_bytes(audio_payload: object) -> bytes:
    if isinstance(audio_payload, bytes):
        return audio_payload
    if isinstance(audio_payload, bytearray):
        return bytes(audio_payload)
    if isinstance(audio_payload, memoryview):
        return bytes(audio_payload)
    raise ExternalServiceFailed(
        "Unable to generate speech audio right now.",
        code=ErrorCode.AI_PROVIDER_UNAVAILABLE,
    )


async def generate_tts_file(
    *,
    entity_id: str,
    mode: TtsMode,
    user_id: str,
) -> str:
    storage_entity: StorageEntity
    storage_entity_id: str
    tts_input: str

    if mode == TtsMode.MESSAGE:
        message = await chat_service.get_message(message_id=entity_id, user_id=user_id)
        if message is None:
            raise MessageNotFound(entity_id)

        # Return existing audio file if already generated
        for part in message.parts:
            if isinstance(part, FilePart) and part.media_kind == FileMediaKind.AUDIO:
                return part.file_id

        text_parts = [
            part.text.strip()
            for part in message.parts
            if isinstance(part, TextPart) and part.text.strip()
        ]
        if not text_parts:
            raise ValidationFailed(
                "Message does not contain text to convert to speech.",
                code=ErrorCode.MESSAGE_TTS_UNAVAILABLE,
                context={"message_id": entity_id},
            )

        tts_input = "\n\n".join(text_parts)
        storage_entity = StorageEntity.CHAT
        storage_entity_id = message.chat_id
    elif mode == TtsMode.CROP:
        raise ValidationFailed(
            "Crop TTS is not supported yet.",
            code=ErrorCode.CROP_TTS_UNSUPPORTED,
        )
    else:
        raise ValidationFailed(
            "Unsupported TTS mode.",
            code=ErrorCode.UNSUPPORTED_TTS_MODE,
            context={"mode": mode},
        )

    try:
        tts_response = await ChatGoogleGenerativeAI(
            model=settings.GEMINI_TTS_MODEL,
            response_modalities=["AUDIO"],
        ).ainvoke(
            tts_input,
            speech_config={
                "voice_config": {
                    "prebuilt_voice_config": {"voice_name": TTS_VOICE_NAME}
                }
            },
        )
    except Exception as exc:
        if not is_gemini_dependency_error(exc):
            raise
        raise DependencyUnavailable(
            "AI TTS service is temporarily unavailable.",
            code=ErrorCode.AI_PROVIDER_UNAVAILABLE,
        ) from exc

    audio_payload = tts_response.additional_kwargs.get("audio")
    audio_bytes = _extract_audio_bytes(audio_payload)

    stored_file = File(
        user_id=user_id,
        filename=f"{storage_entity.value}-tts-{storage_entity_id}.wav",
        content_type=TTS_MIME_TYPE,
        storage_scope=StorageScope.USER,
        entity_id=storage_entity_id,
        status=FileStatus.ACTIVE,
    )

    try:
        await storage_service._upload_file(
            file_stream=audio_bytes,
            stored_file=stored_file,
        )
    except StorageError as exc:
        raise DependencyUnavailable(
            "File storage is temporarily unavailable.",
            code=ErrorCode.STORAGE_UNAVAILABLE,
        ) from exc

    if mode == TtsMode.MESSAGE:
        message.parts.append(
            FilePart(
                file_id=stored_file.id,
                media_kind=FileMediaKind.AUDIO,
            )
        )
        try:
            await chat_service.save_message(message)
        except Exception as exc:
            try:
                await storage_service._delete_files([stored_file])
            except Exception:
                logger.exception(
                    "Failed to rollback TTS file after message update failure file_id=%s message_id=%s",
                    stored_file.id,
                    entity_id,
                )
            raise DependencyUnavailable(
                "File storage is temporarily unavailable.",
                code=ErrorCode.STORAGE_UNAVAILABLE,
            ) from exc

    return stored_file.id
