import asyncio
import logging
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.api.router import api_router
from app.infrastructure.providers.mongodb import close_mongo_client, init_mongo_client
from app.repositories import (
    crop_image_repository,
    files_repository,
    notification_repository,
)
from app.workers.queue import worker

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_mongo_client()
    await files_repository.ensure_indexes()
    await crop_image_repository.ensure_indexes()
    await notification_repository.ensure_indexes()
    worker_task = asyncio.create_task(worker())

    yield

    worker_task.cancel()
    with suppress(asyncio.CancelledError):
        await worker_task
    await close_mongo_client()


app = FastAPI(lifespan=lifespan)

app.mount("/static", StaticFiles(directory="app/public/static"), name="static")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


static_html_app = StaticFiles(directory="app/public/html")


@app.get("/")
async def serve_index(request: Request):
    return await static_html_app.get_response("index.html", request.scope)


app.include_router(api_router)
