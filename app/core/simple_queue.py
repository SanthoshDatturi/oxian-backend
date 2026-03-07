import asyncio
import logging
from collections.abc import Awaitable, Callable

from app.core.config import settings

logger = logging.getLogger(__name__)

queue: asyncio.Queue[Callable[[], Awaitable[None]]] = asyncio.Queue()
semaphore = asyncio.Semaphore(settings.CONCURRENCY_LIMIT)


async def enqueue(job: Callable[[], Awaitable[None]]) -> None:
    await queue.put(job)


async def worker():
    while True:
        callable_process = await queue.get()

        async def wrapped():
            try:
                async with semaphore:
                    await callable_process()
            except Exception:
                logger.exception("Queued process failed.")
            finally:
                queue.task_done()

        asyncio.create_task(wrapped())
