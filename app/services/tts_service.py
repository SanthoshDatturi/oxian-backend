import logging
from enum import StrEnum

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.infrastructure.storage.enums import StorageEntity, StorageScope
from app.infrastructure.storage.errors import StorageBackendError, StorageUploadError
from app.repositories import message_repository
from app.schemas.file import File, FileStatus
from app.schemas.message import FileMediaKind, FilePart, Message, TextPart
from app.services import storage_service

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
    raise StorageUploadError("TTS model did not return audio bytes.")


def _extract_message_text(message: Message) -> str:
    text_parts = [
        part.text.strip()
        for part in message.parts
        if isinstance(part, TextPart) and part.text.strip()
    ]
    if not text_parts:
        raise ValueError("Message does not contain text to convert to speech.")
    return "\n\n".join(text_parts)


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
        message = await message_repository.get_by_id(entity_id)
        if message is None or message.user_id != user_id:
            raise ValueError("Message not found.")

        # Check if audio part already exists for the message
        for part in message.parts:
            if isinstance(part, FilePart) and part.media_kind == FileMediaKind.AUDIO:
                return part.file_id

        tts_input = _extract_message_text(message)
        storage_entity = StorageEntity.CHAT
        storage_entity_id = message.chat_id
    elif mode == TtsMode.CROP:
        raise ValueError("Crop TTS is not supported yet.")
    else:
        raise ValueError("Unsupported TTS mode.")

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

    await storage_service._upload_file(
        file_stream=audio_bytes,
        stored_file=stored_file,
    )

    if mode == TtsMode.MESSAGE:
        message.parts.append(
            FilePart(
                file_id=stored_file.id,
                media_kind=FileMediaKind.AUDIO,
            )
        )
        try:
            await message_repository.save(message)
        except Exception as exc:
            try:
                await storage_service._delete_files([stored_file])
            except Exception:
                logger.exception(
                    "Failed to rollback TTS file after message update failure file_id=%s message_id=%s",
                    stored_file.id,
                    message.id,
                )
            raise StorageBackendError(
                "Failed to update message with generated audio."
            ) from exc

    return stored_file.id
