import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.integrations.database.mogodb import close_mongo_client, init_mongo_client
from app.repositories import (
    crop_image_repository,
    files_repository,
    notification_repository,
)
from app.services import storage_service
from app.workers.queue import worker

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

app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


app.include_router(api_router)
