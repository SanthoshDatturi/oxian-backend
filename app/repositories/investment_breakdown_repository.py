from datetime import datetime, timezone

from app.infrastructure.database.collections import get_investment_breakdowns_collection
from app.schemas.generic_types import PersistenceLanguage
from app.schemas.investment_breakdown import (
    InvestmentBreakdown,
    InvestmentBreakdownDocument,
    InvestmentBreakdownInvariantFields,
    InvestmentBreakdownTranslatableFields,
)


def _to_investment_breakdown(
    document: dict,
    language: PersistenceLanguage,
) -> InvestmentBreakdown:
    translatable_fields = document.get(language.value) or {}
    invariant_data = dict(document)
    for key in InvestmentBreakdownInvariantFields.model_fields:
        value = document.get(key, translatable_fields.get(key))
        if value is not None:
            invariant_data[key] = value
    invariant_fields = InvestmentBreakdownInvariantFields.model_validate(invariant_data)
    return InvestmentBreakdown.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields,
        }
    )


def _touch(breakdown: InvestmentBreakdownDocument) -> InvestmentBreakdownDocument:
    return breakdown.model_copy(update={"updated_at": datetime.now(timezone.utc)})


async def create(breakdown: InvestmentBreakdownDocument) -> InvestmentBreakdownDocument:
    breakdown = _touch(breakdown)
    await get_investment_breakdowns_collection().insert_one(
        breakdown.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return breakdown


async def save(breakdown: InvestmentBreakdownDocument) -> InvestmentBreakdownDocument:
    existing = await get_investment_breakdowns_collection().find_one(
        {"_id": breakdown.id},
        {"created_at": 1},
    )
    if existing and existing.get("created_at") is not None:
        breakdown = breakdown.model_copy(update={"created_at": existing["created_at"]})
    breakdown = _touch(breakdown)
    await get_investment_breakdowns_collection().replace_one(
        {"_id": breakdown.id},
        breakdown.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return breakdown


async def save_language(
    breakdown: InvestmentBreakdown,
    language: PersistenceLanguage,
) -> InvestmentBreakdown:
    breakdown = breakdown.model_copy(update={"updated_at": datetime.now(timezone.utc)})
    translatable_fields = InvestmentBreakdownTranslatableFields.model_validate(
        breakdown
    ).model_dump(exclude_none=True, mode="json")
    invariant_fields = InvestmentBreakdownInvariantFields.model_validate(
        breakdown
    ).model_dump(exclude_none=True, mode="json")
    await get_investment_breakdowns_collection().update_one(
        {"_id": breakdown.id, "crop_id": breakdown.crop_id},
        {
            "$set": {
                **invariant_fields,
                "updated_at": breakdown.updated_at,
                language.value: translatable_fields,
            },
            "$setOnInsert": {"created_at": breakdown.created_at},
        },
        upsert=True,
    )
    return breakdown


async def get_by_crop_id(
    crop_id: str,
    language: PersistenceLanguage,
) -> InvestmentBreakdown | None:
    projection = {
        "_id": 1,
        "crop_id": 1,
        "created_at": 1,
        "updated_at": 1,
        language.value: 1,
    }
    document = await get_investment_breakdowns_collection().find_one(
        {"crop_id": crop_id}, projection
    )
    if not document:
        return None
    return _to_investment_breakdown(document, language)


async def get_document_by_crop_id(
    crop_id: str,
) -> InvestmentBreakdownDocument | None:
    document = await get_investment_breakdowns_collection().find_one(
        {"crop_id": crop_id}
    )
    if not document:
        return None
    return InvestmentBreakdownDocument.model_validate(document)


async def get_crop_id_by_id(breakdown_id: str) -> str | None:
    document = await get_investment_breakdowns_collection().find_one(
        {"_id": breakdown_id},
        {"crop_id": 1},
    )
    if not document:
        return None
    return document.get("crop_id")


async def delete(breakdown_id: str, crop_id: str | None = None) -> bool:
    query: dict[str, str] = {"_id": breakdown_id}
    if crop_id:
        query["crop_id"] = crop_id
    result = await get_investment_breakdowns_collection().delete_one(query)
    return result.deleted_count > 0


async def delete_all_by_crop(crop_id: str) -> int:
    result = await get_investment_breakdowns_collection().delete_many(
        {"crop_id": crop_id}
    )
    return result.deleted_count
