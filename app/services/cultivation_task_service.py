from app.repositories import cultivation_task_repository
from app.schemas.cultivation_task import (
    CultivationTask,
    CultivationTaskDocument,
)
from app.schemas.generic_types import PersistenceLanguage
from app.services import cultivation_crop_service


async def list_cultivation_tasks(
    *, crop_id: str, user_id: str, limit: int = 100
) -> list[CultivationTask]:
    if not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return []
    return await cultivation_task_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
        limit=limit,
    )


async def get_cultivation_task(*, task_id: str, user_id: str) -> CultivationTask | None:
    crop_id = await cultivation_task_repository.get_crop_id_by_id(task_id)
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return None
    return await cultivation_task_repository.get_by_id(
        task_id=task_id,
        crop_id=crop_id,
        language=PersistenceLanguage.USER_LANGUAGE,
    )


async def delete_cultivation_task(*, task_id: str, user_id: str) -> bool:
    crop_id = await cultivation_task_repository.get_crop_id_by_id(task_id)
    if not crop_id or not await cultivation_crop_service.has_crop_access(
        user_id=user_id, crop_id=crop_id
    ):
        return False
    return await cultivation_task_repository.delete(task_id=task_id, crop_id=crop_id)


async def _list_cultivation_tasks(
    crop_id: str, limit: int = 100
) -> list[CultivationTask]:
    return await cultivation_task_repository.list_by_crop(
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
        limit=limit,
    )


async def _get_cultivation_task(
    task_id: str, crop_id: str | None = None
) -> CultivationTask | None:
    return await cultivation_task_repository.get_by_id(
        task_id=task_id,
        crop_id=crop_id,
        language=PersistenceLanguage.ENGLISH,
    )


async def _create_cultivation_task(
    document: CultivationTaskDocument,
) -> CultivationTaskDocument:
    return await cultivation_task_repository.create(document)
