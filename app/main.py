import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.rest.chat import router as chat_router
from app.api.rest.farm_profile import router as farm_profile_router
from app.api.rest.files import router as files_router
from app.core.simple_queue import worker
from app.integrations.database.mogodb import close_mongo_client, init_mongo_client


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    await init_mongo_client()
    worker_task = asyncio.create_task(worker())

    yield  # Application runs here

    # Shutdown logic (optional cleanup)
    worker_task.cancel()
    await close_mongo_client()


app = FastAPI(lifespan=lifespan)

app.include_router(files_router)
app.include_router(chat_router)
app.include_router(farm_profile_router)
