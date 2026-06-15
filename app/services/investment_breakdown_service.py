from app.repositories import investment_breakdown_repository
from app.schemas.generic_types import PersistenceLanguage
from app.schemas.investment_breakdown import (
    InvestmentBreakdown,
    InvestmentBreakdownDocument,
)
from app.services import cultivation_crop_service


async def get_investment_breakdown(
    *, breakdown_id: str, user_id: str
) -> InvestmentBreakdown | None:
    crop_id = await investment_breakdown_repository.get_crop_id_by_id(breakdown_id)
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return None
    return await investment_breakdown_repository.get_by_crop_id(
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )


async def delete_investment_breakdown(*, breakdown_id: str, user_id: str) -> bool:
    crop_id = await investment_breakdown_repository.get_crop_id_by_id(breakdown_id)
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return False
    return await investment_breakdown_repository.delete(
        breakdown_id=breakdown_id, crop_id=crop_id
    )


async def _get_investment_breakdown(crop_id: str) -> InvestmentBreakdown | None:
    return await investment_breakdown_repository.get_by_crop_id(
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
    )


async def _create_investment_breakdown(
    document: InvestmentBreakdownDocument,
) -> InvestmentBreakdownDocument:
    return await investment_breakdown_repository.create(document)
