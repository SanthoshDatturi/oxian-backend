import asyncio
from typing import Awaitable, Callable

from app.core.config import settings

queue: asyncio.Queue[Callable[[], Awaitable[None]]] = asyncio.Queue()

semaphore = asyncio.Semaphore(settings.CONCURRENCY_LIMIT)


async def worker():
    while True:
        callable_process = await queue.get()

        async def wrapped():
            async with semaphore:
                await callable_process()

        asyncio.create_task(wrapped())
