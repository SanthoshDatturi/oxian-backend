from pymongo import DESCENDING

from app.infrastructure.database.mogodb import get_crop_image_generate_requests_collection
from app.schemas.crop_image_generate_request import CropImageGenerateRequest


async def create(
    request: CropImageGenerateRequest,
) -> CropImageGenerateRequest:
    await get_crop_image_generate_requests_collection().insert_one(
        request.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return request


async def save(
    request: CropImageGenerateRequest,
) -> CropImageGenerateRequest:
    await get_crop_image_generate_requests_collection().replace_one(
        {"_id": request.id},
        request.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return request


async def get_by_id(request_id: str) -> CropImageGenerateRequest | None:
    document = await get_crop_image_generate_requests_collection().find_one(
        {"_id": request_id}
    )
    if not document:
        return None
    return CropImageGenerateRequest.model_validate(document)


async def get_by_image_file_id(
    image_file_id: str,
) -> CropImageGenerateRequest | None:
    document = await get_crop_image_generate_requests_collection().find_one(
        {"image_file_id": image_file_id}
    )
    if not document:
        return None
    return CropImageGenerateRequest.model_validate(document)


async def list_all(limit: int = 50) -> list[CropImageGenerateRequest]:
    cursor = (
        get_crop_image_generate_requests_collection()
        .find()
        .sort("created_at", DESCENDING)
        .limit(limit)
    )
    return [
        CropImageGenerateRequest.model_validate(document)
        async for document in cursor
    ]


async def delete(request_id: str) -> bool:
    result = await get_crop_image_generate_requests_collection().delete_one(
        {"_id": request_id}
    )
    return result.deleted_count > 0
