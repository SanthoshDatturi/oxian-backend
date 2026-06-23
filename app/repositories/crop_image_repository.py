import re
from typing import Any

from pymongo import ASCENDING, TEXT, ReturnDocument
from pymongo.errors import OperationFailure

from app.core.config import settings
from app.infrastructure.database.collections import get_crop_images_collection
from app.schemas.crop_image import CropImageFile, RetrievedCropImageFile

EMBEDDING_VECTOR_INDEX_NAME = "crop_image_embedding_vector_index"
KEYWORD_TEXT_INDEX_NAME = "crop_image_keyword_text_index"
CROP_IMAGE_RETRIEVAL_PROJECTION: dict[str, int] = {
    "_id": 1,
    "crop_name": 1,
    "aliases": 1,
}


def _supports_search_indexes() -> bool:
    mongo_uri = settings.MONGO_DIRECT_URI or settings.MONGO_URI
    return "mongodb.net" in mongo_uri


async def ensure_indexes() -> None:
    collection = get_crop_images_collection()
    await collection.create_index([("crop_name", ASCENDING)])
    await collection.create_index([("aliases", ASCENDING)])
    await collection.create_index(
        [("crop_name", TEXT), ("aliases", TEXT)],
        name=KEYWORD_TEXT_INDEX_NAME,
        default_language="none",
    )

    if not _supports_search_indexes():
        return

    try:
        from pymongo.operations import SearchIndexModel
    except ImportError:
        return

    vector_index = SearchIndexModel(
        definition={
            "fields": [
                {
                    "type": "vector",
                    "path": "embedding",
                    "numDimensions": settings.CROP_IMAGE_EMBEDDING_DIMENSION,
                    "similarity": "cosine",
                }
            ]
        },
        name=EMBEDDING_VECTOR_INDEX_NAME,
        type="vectorSearch",
    )

    try:
        await collection.create_search_index(model=vector_index)
    except OperationFailure as exc:
        if exc.code != 59:
            raise
        # Atlas Search index creation is not available on every MongoDB deployment.
        # The CRUD and keyword indexes above are still valid for local/dev MongoDB.
        return


def _validate_embedding_dimension(embedding: list[float]) -> None:
    if len(embedding) != settings.CROP_IMAGE_EMBEDDING_DIMENSION:
        raise ValueError("Embedding dimension mismatch")


def _model_to_document(crop_image: CropImageFile) -> dict[str, Any]:
    return crop_image.model_dump(by_alias=True, exclude_none=True, mode="json")


def _document_to_retrieved_crop_image(document: dict[str, Any]) -> RetrievedCropImageFile:
    return RetrievedCropImageFile.model_validate(document)


def _dedupe_ids(crop_image_ids: list[str]) -> list[str]:
    return list(dict.fromkeys(crop_image_ids))


async def create(crop_image: CropImageFile) -> CropImageFile:
    await get_crop_images_collection().insert_one(_model_to_document(crop_image))
    return crop_image


async def save(crop_image: CropImageFile) -> CropImageFile:
    await get_crop_images_collection().replace_one(
        {"_id": crop_image.id},
        _model_to_document(crop_image),
        upsert=True,
    )
    return crop_image


async def get_by_id(crop_image_id: str) -> RetrievedCropImageFile | None:
    document = await get_crop_images_collection().find_one(
        {"_id": crop_image_id},
        CROP_IMAGE_RETRIEVAL_PROJECTION,
    )
    if not document:
        return None
    return _document_to_retrieved_crop_image(document)


async def get_many_by_ids(crop_image_ids: list[str]) -> list[RetrievedCropImageFile]:
    normalized_ids = _dedupe_ids(crop_image_ids)
    if not normalized_ids:
        return []

    cursor = get_crop_images_collection().find(
        {"_id": {"$in": normalized_ids}},
        CROP_IMAGE_RETRIEVAL_PROJECTION,
    )
    crop_images = [_document_to_retrieved_crop_image(document) async for document in cursor]
    crop_images_by_id = {crop_image.id: crop_image for crop_image in crop_images}
    return [
        crop_images_by_id[crop_image_id]
        for crop_image_id in normalized_ids
        if crop_image_id in crop_images_by_id
    ]


async def list_all(limit: int = 100, skip: int = 0) -> list[RetrievedCropImageFile]:
    cursor = (
        get_crop_images_collection()
        .find({}, CROP_IMAGE_RETRIEVAL_PROJECTION)
        .sort("crop_name", ASCENDING)
        .skip(skip)
        .limit(limit)
    )
    return [_document_to_retrieved_crop_image(document) async for document in cursor]


async def update(
    crop_image_id: str,
    *,
    crop_name: str | None = None,
    embedding: list[float] | None = None,
    aliases: list[str] | None = None,
) -> RetrievedCropImageFile | None:
    updates: dict[str, Any] = {}
    if crop_name is not None:
        updates["crop_name"] = crop_name
    if embedding is not None:
        _validate_embedding_dimension(embedding)
        updates["embedding"] = embedding
    if aliases is not None:
        updates["aliases"] = aliases

    if not updates:
        return await get_by_id(crop_image_id)

    document = await get_crop_images_collection().find_one_and_update(
        {"_id": crop_image_id},
        {"$set": updates},
        projection=CROP_IMAGE_RETRIEVAL_PROJECTION,
        return_document=ReturnDocument.AFTER,
    )
    if not document:
        return None
    return _document_to_retrieved_crop_image(document)


async def delete(crop_image_id: str) -> bool:
    result = await get_crop_images_collection().delete_one({"_id": crop_image_id})
    return result.deleted_count > 0


async def keyword_search(query: str, limit: int = 2) -> list[RetrievedCropImageFile]:
    normalized_query = query.strip()
    if not normalized_query or limit <= 0:
        return []

    try:
        text_cursor = (
            get_crop_images_collection()
            .find(
                {"$text": {"$search": normalized_query}},
                {**CROP_IMAGE_RETRIEVAL_PROJECTION, "score": {"$meta": "textScore"}},
            )
            .sort([("score", {"$meta": "textScore"})])
            .limit(limit)
        )
        text_matches = [
            _document_to_retrieved_crop_image(document) async for document in text_cursor
        ]
        if text_matches:
            return text_matches
    except Exception:
        pass

    escaped_query = re.escape(normalized_query)
    cursor = (
        get_crop_images_collection()
        .find(
            {
                "$or": [
                    {"crop_name": {"$regex": escaped_query, "$options": "i"}},
                    {"aliases": {"$regex": escaped_query, "$options": "i"}},
                ]
            },
            CROP_IMAGE_RETRIEVAL_PROJECTION,
        )
        .sort("crop_name", ASCENDING)
        .limit(limit)
    )
    return [_document_to_retrieved_crop_image(document) async for document in cursor]


async def similarity_search(
    embedding: list[float],
    limit: int = 3,
    num_candidates: int | None = None,
) -> list[RetrievedCropImageFile]:
    _validate_embedding_dimension(embedding)
    if limit <= 0 or not _supports_search_indexes():
        return []

    candidates = num_candidates or max(limit * 10, 100)
    pipeline: list[dict[str, Any]] = [
        {
            "$vectorSearch": {
                "index": EMBEDDING_VECTOR_INDEX_NAME,
                "path": "embedding",
                "queryVector": embedding,
                "numCandidates": candidates,
                "limit": limit,
            }
        },
        {"$project": CROP_IMAGE_RETRIEVAL_PROJECTION},
    ]
    cursor = get_crop_images_collection().aggregate(pipeline)
    return [_document_to_retrieved_crop_image(document) async for document in cursor]
