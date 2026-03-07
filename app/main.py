import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, status

from app.api.rest.files import router as files_router
from app.api.websocket.connection_manager import manager
from app.api.websocket.router import route_message
from app.core.dev.dependencies import authenticate_websocket
from app.core.simple_queue import worker
from app.integrations.auth.errors import AuthError
from app.schemas.generic_types import WebSocketInboundMessage


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    worker_task = asyncio.create_task(worker())

    yield  # Application runs here

    # Shutdown logic (optional cleanup)
    worker_task.cancel()


app = FastAPI(lifespan=lifespan)

app.include_router(files_router)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    try:
        user_payload = await authenticate_websocket(websocket)
    except AuthError:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = user_payload["uid"]

    await manager.connect(user_id, websocket)

    try:
        while True:
            message = await websocket.receive_json()
            await route_message(
                user_id, WebSocketInboundMessage.model_validate_json(message)
            )

    except WebSocketDisconnect:
        manager.disconnect(user_id, websocket)
    except Exception:
        if user_id:
            manager.disconnect(user_id, websocket)
