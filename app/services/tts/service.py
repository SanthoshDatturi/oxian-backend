import logging
from enum import StrEnum

from langchain_google_genai import ChatGoogleGenerativeAI

from app.core.config import settings
from app.integrations.storage import files
from app.integrations.storage.base import StorageEntity, StorageScope
from app.integrations.storage.errors import StorageBackendError, StorageUploadError
from app.prompts.prompt_manager import PromptManager
from app.repositories import files_repository, message_repository
from app.schemas.file import File, FileStatus
from app.schemas.message import FileMediaKind, FilePart

logger = logging.getLogger(__name__)

TTS_VOICE_NAME = "Kore"
TTS_MIME_TYPE = "audio/wav"


class TtsMode(StrEnum):
    MESSAGE = "message"
    CROP = "crop"


def _build_prompt(*, mode: TtsMode, text_or_json_data: str) -> str:
    return PromptManager.get_prompt(
        "tts",
        mode=mode.value,
        text_or_json_data=text_or_json_data,
    )


def _extract_audio_bytes(audio_payload: object) -> bytes:
    if isinstance(audio_payload, bytes):
        return audio_payload
    if isinstance(audio_payload, bytearray):
        return bytes(audio_payload)
    if isinstance(audio_payload, memoryview):
        return bytes(audio_payload)
    raise StorageUploadError("TTS model did not return audio bytes.")


async def generate_tts_file(
    *,
    entity_id: str,
    mode: TtsMode,
    text_or_json_data: str | None,
    user_id: str,
) -> str:
    storage_entity: StorageEntity
    storage_entity_id: str
    prompt_payload: str

    if mode == TtsMode.MESSAGE:
        if not text_or_json_data or not text_or_json_data.strip():
            raise ValueError("text_or_json_data is required.")
        message = await message_repository.get_by_id(entity_id)
        if message is None or message.user_id != user_id:
            raise ValueError("Message not found.")
        prompt_payload = text_or_json_data
        storage_entity = StorageEntity.CHAT
        storage_entity_id = message.chat_id
    elif mode == TtsMode.CROP:
        if not text_or_json_data or not text_or_json_data.strip():
            raise ValueError("text_or_json_data is required.")
        prompt_payload = text_or_json_data
        storage_entity = StorageEntity.CROP
        storage_entity_id = entity_id
    else:
        raise ValueError("Unsupported TTS mode.")

    prompt = _build_prompt(mode=mode, text_or_json_data=prompt_payload)
    tts_response = await ChatGoogleGenerativeAI(
        model=settings.GEMINI_TTS_MODEL,
        response_modalities=["AUDIO"],
    ).ainvoke(
        prompt,
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

    await files.upload(
        file_stream=audio_bytes,
        file_id=stored_file.id,
        scope=stored_file.storage_scope,
        mime_type=stored_file.content_type,
    )

    try:
        await files_repository.save_active_file(stored_file, entity=storage_entity)
    except Exception as exc:
        try:
            await files.delete(scope=stored_file.storage_scope, file_id=stored_file.id)
        except Exception:
            logger.exception(
                "Failed to rollback TTS blob for file_id=%s user_id=%s",
                stored_file.id,
                user_id,
            )

        if isinstance(exc, ValueError):
            raise exc
        raise StorageBackendError("Failed to persist TTS file metadata.") from exc

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
                await files.delete(scope=stored_file.storage_scope, file_id=stored_file.id)
                await files_repository.delete_many_by_ids([stored_file.id])
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
