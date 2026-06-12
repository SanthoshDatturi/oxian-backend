from app.integrations.database.mogodb import get_intercropping_details_collection
from app.schemas.generic_types import PersistenceLanguage
from app.schemas.intercropping_details import (
    IntercroppingDetails,
    IntercroppingDetailsDocument,
    IntercroppingDetailsTranslatableFields,
)


def _to_intercropping_details(
    document: dict,
    language: PersistenceLanguage,
) -> IntercroppingDetails:
    fields = document.get(language.value) or {}
    data = {
        **fields,
        "id": document["_id"],
        "intercrop_type": document["intercrop_type"],
    }
    if document.get("recommendation_id") is not None:
        data["recommendation_id"] = document["recommendation_id"]
    return IntercroppingDetails.model_validate(data)


async def create(
    details: IntercroppingDetailsDocument,
) -> IntercroppingDetailsDocument:
    await get_intercropping_details_collection().insert_one(
        details.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return details


async def save(
    details: IntercroppingDetailsDocument,
) -> IntercroppingDetailsDocument:
    await get_intercropping_details_collection().replace_one(
        {"_id": details.id},
        details.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return details


async def save_language(
    details: IntercroppingDetails,
    language: PersistenceLanguage,
) -> IntercroppingDetails:
    fields = IntercroppingDetailsTranslatableFields.model_validate(
        details
    ).model_dump(exclude_none=True, mode="json")
    await get_intercropping_details_collection().update_one(
        {"_id": details.id},
        {
            "$set": {
                "recommendation_id": details.recommendation_id,
                "intercrop_type": details.intercrop_type,
                language.value: fields,
            },
        },
        upsert=True,
    )
    return details


async def get_by_id(
    intercropping_id: str,
    language: PersistenceLanguage,
) -> IntercroppingDetails | None:
    projection = {
        "_id": 1,
        "recommendation_id": 1,
        "intercrop_type": 1,
        language.value: 1,
    }
    document = await get_intercropping_details_collection().find_one(
        {"_id": intercropping_id},
        projection,
    )
    if not document:
        return None
    return _to_intercropping_details(document, language)


async def get_document_by_id(
    intercropping_id: str,
) -> IntercroppingDetailsDocument | None:
    document = await get_intercropping_details_collection().find_one(
        {"_id": intercropping_id},
    )
    if not document:
        return None
    return IntercroppingDetailsDocument.model_validate(document)


async def delete(intercropping_id: str) -> bool:
    result = await get_intercropping_details_collection().delete_one(
        {"_id": intercropping_id}
    )
    return result.deleted_count > 0
