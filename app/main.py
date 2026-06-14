import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from app.api.rest.admin_api import router as admin_router
from app.api.rest.chat_api import router as chat_router
from app.api.rest.crop_recommendation_api import router as crop_recommendation_router
from app.api.rest.cultivation_crop_api import router as cultivation_crop_router
from app.api.rest.farm_profile_api import router as farm_profile_router
from app.api.rest.files_api import router as files_router
from app.api.rest.notification_api import router as notification_router
from app.api.rest.user_pref_api import router as user_pref_router
from app.api.rest.weather_api import router as weather_router
from app.core.simple_queue import worker
from app.integrations.database.mogodb import close_mongo_client, init_mongo_client
from app.repositories import crop_image_repository, files_repository, notification_repository
from app.services import storage_service

logger = logging.getLogger(__name__)

FILE_CLEANUP_INTERVAL_SECONDS = 5 * 60 * 60


async def _cleanup_temporary_files_loop() -> None:
    while True:
        try:
            await storage_service.cleanup_expired_temporary_files()
        except Exception:
            logger.exception("Temporary file cleanup failed.")
        await asyncio.sleep(FILE_CLEANUP_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_mongo_client()
    await files_repository.ensure_indexes()
    await crop_image_repository.ensure_indexes()
    await notification_repository.ensure_indexes()
    worker_task = asyncio.create_task(worker())
    cleanup_task = asyncio.create_task(_cleanup_temporary_files_loop())

    yield

    worker_task.cancel()
    cleanup_task.cancel()
    with suppress(asyncio.CancelledError):
        await worker_task
    with suppress(asyncio.CancelledError):
        await cleanup_task
    await close_mongo_client()


app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health_check():
    return {"status": "ok"}

app.include_router(files_router)
app.include_router(chat_router)
app.include_router(farm_profile_router)
app.include_router(user_pref_router)
app.include_router(weather_router)
app.include_router(admin_router)
app.include_router(crop_recommendation_router)
app.include_router(cultivation_crop_router)
app.include_router(notification_router)
