from typing import IO, Union

from langchain_google_genai import GoogleGenerativeAIEmbeddings

from app.core.config import settings
from app.integrations.storage import files
from app.integrations.storage.base import StorageScope
from app.integrations.storage.errors import StorageError
from app.repositories import crop_image_repository
from app.schemas.crop_image import CropImageFile


def _normalize_aliases(aliases: list[str] | None) -> list[str] | None:
    if aliases is None:
        return None

    normalized = list(
        dict.fromkeys(alias.strip() for alias in aliases if alias.strip())
    )
    return normalized or None


def _embedding_text(crop_name: str, aliases: list[str] | None) -> str:
    parts = [f"Crop name: {crop_name.strip()}"]
    if aliases:
        parts.append(f"Aliases: {', '.join(aliases)}")
    return "\n".join(parts)


async def _generate_embedding(crop_name: str, aliases: list[str] | None) -> list[float]:
    embeddings = GoogleGenerativeAIEmbeddings(
        model=settings.CROP_IMAGE_EMBEDDING_MODEL,
        task_type="SEMANTIC_SIMILARITY",
        output_dimensionality=settings.CROP_IMAGE_EMBEDDING_DIMENSION,
    )
    try:
        return await embeddings.aembed_query(
            _embedding_text(crop_name=crop_name, aliases=aliases)
        )
    except Exception as exc:
        raise RuntimeError("Failed to generate crop image embedding.") from exc


async def upload_new_image(
    file_stream: Union[bytes, IO[bytes]],
    crop_name: str,
    mime_type: str,
    aliases: list[str] | None = None,
) -> CropImageFile:
    normalized_crop_name = crop_name.strip()
    if not normalized_crop_name:
        raise ValueError("Crop name is required.")

    normalized_aliases = _normalize_aliases(aliases)

    embedding = await _generate_embedding(
        crop_name=normalized_crop_name,
        aliases=normalized_aliases,
    )

    crop_image = CropImageFile(
        crop_name=normalized_crop_name,
        aliases=normalized_aliases,
        embedding=embedding,
    )

    crop_image = await crop_image_repository.create(crop_image)

    try:
        await files.upload(
            file_stream=file_stream,
            file_id=crop_image.id,
            scope=StorageScope.SYSTEM,
            mime_type=mime_type,
        )
    except StorageError as exc:
        await crop_image_repository.delete(crop_image.id)
        raise exc

    return crop_image
