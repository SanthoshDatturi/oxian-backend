import logging

from app.core.errors import (
    CultivationCropNotFound,
    FarmProfileNotFound,
    IntercroppingCultivationNotFound,
)
from app.repositories import (
    cultivation_crop_repository,
    intercropping_details_repository,
)
from app.schemas.cultivation_crop import (
    BaseCrop,
    CultivationCrop,
    CultivationCropDocument,
    CultivationCropInput,
    CultivationCropInputInvariantFields,
    CultivationCropInvariantFields,
    IntercroppingCultivation,
    IntercroppingCultivationInput,
)
from app.schemas.generic_types import PersistenceLanguage
from app.schemas.intercropping_details import (
    IntercroppingDetails,
    IntercroppingDetailsDocument,
    IntercroppingDetailsInput,
    IntercroppingDetailsInputInvariantFields,
    IntercroppingDetailsInvariantFields,
    IntercroppingDetailsTranslatableFields,
)
from app.services import farm_profile_service, translation_service

logger = logging.getLogger(__name__)


def _to_cultivation_crop(
    document: CultivationCropDocument,
    translatable_fields: BaseCrop,
) -> CultivationCrop:
    invariant_fields = CultivationCropInvariantFields.model_validate(document)
    return CultivationCrop.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields.model_dump(mode="json"),
        }
    )


def _to_intercropping_details(
    document: IntercroppingDetailsDocument,
    translatable_fields: IntercroppingDetailsTranslatableFields,
) -> IntercroppingDetails:
    invariant_fields = IntercroppingDetailsInvariantFields.model_validate(document)
    return IntercroppingDetails.model_validate(
        {
            **invariant_fields.model_dump(mode="json"),
            **translatable_fields.model_dump(mode="json"),
        }
    )


async def _ensure_farm_access(user_id: str, farm_id: str) -> None:
    if not await farm_profile_service.has_farm_access(
        farm_id=farm_id,
        user_id=user_id,
    ):
        raise FarmProfileNotFound(farm_id)


async def has_crop_access(
    *,
    user_id: str,
    crop_id: str,
) -> bool:
    farm_id = await cultivation_crop_repository.get_farm_id_by_id(crop_id)
    if farm_id is None:
        return False
    return await farm_profile_service.has_farm_access(
        farm_id=farm_id,
        user_id=user_id,
    )


async def has_intercropping_access(
    *,
    user_id: str,
    intercropping_id: str,
) -> bool:
    farm_id = await intercropping_details_repository.get_farm_id_by_id(intercropping_id)
    if farm_id is None:
        return False
    return await farm_profile_service.has_farm_access(
        farm_id=farm_id,
        user_id=user_id,
    )


async def _build_crop_document(
    *,
    user_id: str,
    farm_id: str,
    input: CultivationCropInput,
    crop_id: str | None = None,
    recommendation_id: str | None = None,
    intercropping_id: str | None = None,
) -> CultivationCropDocument:
    input_invariant_fields = CultivationCropInputInvariantFields.model_validate(input)
    invariant_data = input_invariant_fields.model_dump()
    if crop_id is not None:
        invariant_data["id"] = crop_id
    invariant_fields = CultivationCropInvariantFields(
        farm_id=farm_id,
        recommendation_id=recommendation_id,
        intercropping_id=intercropping_id,
        **invariant_data,
    )
    translatable_fields = BaseCrop.model_validate(input)
    return CultivationCropDocument(
        **invariant_fields.model_dump(),
        english=await translation_service.to_english(
            user_id=user_id,
            fields=translatable_fields,
        ),
        user_language=translatable_fields,
    )


async def _build_intercropping_details_document(
    *,
    user_id: str,
    input: IntercroppingDetailsInput,
    intercropping_id: str | None = None,
    recommendation_id: str | None = None,
) -> IntercroppingDetailsDocument:
    input_invariant_fields = IntercroppingDetailsInputInvariantFields.model_validate(
        input
    )
    invariant_data = input_invariant_fields.model_dump()
    if intercropping_id is not None:
        invariant_data["id"] = intercropping_id
    invariant_fields = IntercroppingDetailsInvariantFields(
        recommendation_id=recommendation_id,
        **invariant_data,
    )
    translatable_fields = IntercroppingDetailsTranslatableFields.model_validate(input)
    return IntercroppingDetailsDocument(
        **invariant_fields.model_dump(),
        english=await translation_service.to_english(
            user_id=user_id,
            fields=translatable_fields,
        ),
        user_language=translatable_fields,
    )


async def list_cultivation_crops(
    *,
    user_id: str,
    farm_id: str,
    limit: int = 100,
) -> list[CultivationCrop]:
    await _ensure_farm_access(user_id=user_id, farm_id=farm_id)
    return await cultivation_crop_repository.list_by_farm(
        farm_id=farm_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        limit=limit,
    )


async def get_cultivation_crop(
    *,
    user_id: str,
    farm_id: str,
    crop_id: str,
) -> CultivationCrop | None:
    await _ensure_farm_access(user_id=user_id, farm_id=farm_id)
    return await cultivation_crop_repository.get_by_id(
        crop_id=crop_id,
        farm_id=farm_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )


async def _get_cultivation_crop(
    *,
    farm_id: str,
    crop_id: str,
) -> CultivationCrop | None:
    return await cultivation_crop_repository.get_by_id(
        crop_id=crop_id,
        farm_id=farm_id,
        language=PersistenceLanguage.ENGLISH,
    )


async def create_cultivation_crop(
    *,
    user_id: str,
    farm_id: str,
    input: CultivationCropInput,
) -> CultivationCrop:
    await _ensure_farm_access(user_id=user_id, farm_id=farm_id)
    try:
        crop_document = await _build_crop_document(
            user_id=user_id,
            farm_id=farm_id,
            input=input,
        )
        crop_document = await cultivation_crop_repository.create(crop_document)
        return _to_cultivation_crop(crop_document, crop_document.user_language)
    except Exception:
        logger.exception("Failed to create cultivation crop farm_id=%s", farm_id)
        raise


async def update_cultivation_crop(
    *,
    user_id: str,
    farm_id: str,
    crop_id: str,
    input: CultivationCropInput,
) -> CultivationCrop:
    await _ensure_farm_access(user_id=user_id, farm_id=farm_id)
    existing = await cultivation_crop_repository.get_by_id(
        crop_id=crop_id,
        farm_id=farm_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )
    if existing is None:
        raise CultivationCropNotFound(crop_id)
    try:
        crop_document = await _build_crop_document(
            user_id=user_id,
            farm_id=farm_id,
            crop_id=crop_id,
            input=input,
            recommendation_id=existing.recommendation_id,
            intercropping_id=existing.intercropping_id,
        )
        crop_document = await cultivation_crop_repository.save(crop_document)
        return _to_cultivation_crop(crop_document, crop_document.user_language)
    except Exception:
        logger.exception(
            "Failed to update cultivation crop crop_id=%s farm_id=%s",
            crop_id,
            farm_id,
        )
        raise


async def delete_cultivation_crop(
    *,
    user_id: str,
    farm_id: str,
    crop_id: str,
) -> bool:
    await _ensure_farm_access(user_id=user_id, farm_id=farm_id)
    try:
        return await cultivation_crop_repository.delete(
            crop_id=crop_id,
            farm_id=farm_id,
        )
    except Exception:
        logger.exception(
            "Failed to delete cultivation crop crop_id=%s farm_id=%s",
            crop_id,
            farm_id,
        )
        raise


async def create_intercropping_cultivation(
    *,
    user_id: str,
    farm_id: str,
    input: IntercroppingCultivationInput,
) -> IntercroppingCultivation:
    await _ensure_farm_access(user_id=user_id, farm_id=farm_id)
    crop_documents = []
    details_document: IntercroppingDetailsDocument | None = None
    try:
        details_document = await _build_intercropping_details_document(
            user_id=user_id,
            input=input.intercropping_details,
        )
        details_document = await intercropping_details_repository.create(
            details_document
        )
        for crop_input in input.crops:
            crop_document = await _build_crop_document(
                user_id=user_id,
                farm_id=farm_id,
                input=crop_input,
                intercropping_id=details_document.id,
            )
            crop_documents.append(
                await cultivation_crop_repository.create(crop_document)
            )
        return IntercroppingCultivation(
            intercropping_details=_to_intercropping_details(
                details_document,
                details_document.user_language,
            ),
            crops=[
                _to_cultivation_crop(crop_document, crop_document.user_language)
                for crop_document in crop_documents
            ],
        )
    except Exception:
        logger.exception(
            "Failed to create intercropping cultivation farm_id=%s details_id=%s",
            farm_id,
            details_document.id if details_document else None,
        )
        for crop_document in crop_documents:
            await cultivation_crop_repository.delete(
                crop_id=crop_document.id,
                farm_id=farm_id,
            )
        if details_document is not None:
            await intercropping_details_repository.delete(details_document.id)
        raise


async def update_intercropping_cultivation(
    *,
    user_id: str,
    farm_id: str,
    intercropping_id: str,
    input: IntercroppingCultivationInput,
) -> IntercroppingCultivation:
    await _ensure_farm_access(user_id=user_id, farm_id=farm_id)
    old_details_document = await intercropping_details_repository.get_document_by_id(
        intercropping_id
    )
    if old_details_document is None:
        raise IntercroppingCultivationNotFound(intercropping_id)
    old_crop_documents = (
        await cultivation_crop_repository.list_documents_by_intercropping(
            intercropping_id=intercropping_id,
            farm_id=farm_id,
        )
    )
    if not old_crop_documents:
        raise IntercroppingCultivationNotFound(intercropping_id)
    crop_documents = []
    try:
        details_document = await _build_intercropping_details_document(
            user_id=user_id,
            intercropping_id=intercropping_id,
            input=input.intercropping_details,
            recommendation_id=old_details_document.recommendation_id,
        )
        details_document = await intercropping_details_repository.save(details_document)
        await cultivation_crop_repository.delete_all_by_intercropping(
            intercropping_id=intercropping_id,
            farm_id=farm_id,
        )
        for crop_input in input.crops:
            crop_document = await _build_crop_document(
                user_id=user_id,
                farm_id=farm_id,
                input=crop_input,
                intercropping_id=intercropping_id,
            )
            crop_documents.append(
                await cultivation_crop_repository.create(crop_document)
            )
        return IntercroppingCultivation(
            intercropping_details=_to_intercropping_details(
                details_document,
                details_document.user_language,
            ),
            crops=[
                _to_cultivation_crop(crop_document, crop_document.user_language)
                for crop_document in crop_documents
            ],
        )
    except Exception:
        logger.exception(
            "Failed to update intercropping cultivation intercropping_id=%s farm_id=%s",
            intercropping_id,
            farm_id,
        )
        await cultivation_crop_repository.delete_all_by_intercropping(
            intercropping_id=intercropping_id,
            farm_id=farm_id,
        )
        await intercropping_details_repository.save(old_details_document)
        for old_crop_document in old_crop_documents:
            await cultivation_crop_repository.save(old_crop_document)
        raise


async def delete_intercropping_cultivation(
    *,
    user_id: str,
    farm_id: str,
    intercropping_id: str,
) -> bool:
    await _ensure_farm_access(user_id=user_id, farm_id=farm_id)
    details_document = await intercropping_details_repository.get_document_by_id(
        intercropping_id
    )
    if details_document is None:
        return False
    crop_documents = await cultivation_crop_repository.list_documents_by_intercropping(
        intercropping_id=intercropping_id,
        farm_id=farm_id,
    )
    if not crop_documents:
        return False
    try:
        await cultivation_crop_repository.delete_all_by_intercropping(
            intercropping_id=intercropping_id,
            farm_id=farm_id,
        )
        deleted = await intercropping_details_repository.delete(intercropping_id)
        if not deleted:
            for crop_document in crop_documents:
                await cultivation_crop_repository.save(crop_document)
            return False
        return True
    except Exception:
        logger.exception(
            "Failed to delete intercropping cultivation intercropping_id=%s farm_id=%s",
            intercropping_id,
            farm_id,
        )
        await intercropping_details_repository.save(details_document)
        for crop_document in crop_documents:
            await cultivation_crop_repository.save(crop_document)
        raise


async def _create_cultivation_crop(cultivation_crop_document: CultivationCropDocument):
    try:
        return await cultivation_crop_repository.create(cultivation_crop_document)
    except Exception:
        logger.exception(
            "Failed to create cultivation crop farm_id=%s",
            cultivation_crop_document.farm_id,
        )
        raise


async def _create_intercropping_details(
    intercropping_details_document: IntercroppingDetailsDocument,
) -> IntercroppingDetailsDocument:
    try:
        return await intercropping_details_repository.create(
            intercropping_details_document
        )
    except Exception:
        logger.exception(
            "Failed to create intercropping details recommendation_id=%s",
            intercropping_details_document.recommendation_id,
        )
        raise


async def _get_intercropping_details(
    *,
    intercropping_id: str,
) -> IntercroppingDetailsDocument | None:
    return await intercropping_details_repository.get_document_by_id(intercropping_id)
