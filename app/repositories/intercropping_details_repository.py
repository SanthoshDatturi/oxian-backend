from app.infrastructure.database.mogodb import (
    get_cultivation_crops_collection,
    get_intercropping_details_collection,
)
from app.schemas.generic_types import PersistenceLanguage
from app.schemas.intercropping_details import (
    IntercroppingDetails,
    IntercroppingDetailsDocument,
    IntercroppingDetailsInputInvariantFields,
    IntercroppingDetailsInvariantFields,
    IntercroppingDetailsTranslatableFields,
)


def _to_intercropping_details(
    document: dict,
    language: PersistenceLanguage,
) -> IntercroppingDetails:
    translatable_fields = document.get(language.value) or {}
    invariant_data = dict(document)
    for key in IntercroppingDetailsInvariantFields.model_fields:
        value = document.get(key, translatable_fields.get(key))
        if value is not None:
            invariant_data[key] = value
    invariant_fields = IntercroppingDetailsInvariantFields.model_validate(
        invariant_data
    )
    return IntercroppingDetails.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields,
        }
    )


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
    translatable_fields = IntercroppingDetailsTranslatableFields.model_validate(
        details
    ).model_dump(exclude_none=True, mode="json")
    invariant_fields = IntercroppingDetailsInputInvariantFields.model_validate(
        details
    ).model_dump(exclude_none=True, mode="json")
    await get_intercropping_details_collection().update_one(
        {"_id": details.id},
        {
            "$set": {
                "recommendation_id": details.recommendation_id,
                **invariant_fields,
                language.value: translatable_fields,
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


async def get_farm_id_by_id(intercropping_id: str) -> str | None:
    document = await get_cultivation_crops_collection().find_one(
        {"intercropping_id": intercropping_id},
        {"farm_id": 1},
    )
    if not document:
        return None
    return document.get("farm_id")


async def delete(intercropping_id: str) -> bool:
    result = await get_intercropping_details_collection().delete_one(
        {"_id": intercropping_id}
    )
    return result.deleted_count > 0
