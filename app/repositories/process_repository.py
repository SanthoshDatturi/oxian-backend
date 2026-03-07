import time

from app.integrations.database.mogodb import get_processes_collection
from app.schemas.process import Process, State


def _touch(process: Process) -> Process:
    updates: dict[str, float | None] = {"updated_at": time.time()}
    if process.status == State.COMPLETED and process.completed_at is None:
        updates["completed_at"] = time.time()
    return process.model_copy(update=updates)


async def create(process: Process) -> Process:
    process = _touch(process)
    await get_processes_collection().insert_one(
        process.model_dump(by_alias=True, exclude_none=True, mode="json")
    )
    return process


async def save(process: Process) -> Process:
    process = _touch(process)
    await get_processes_collection().replace_one(
        {"_id": process.id},
        process.model_dump(by_alias=True, exclude_none=True, mode="json"),
        upsert=True,
    )
    return process


async def get_by_id(process_id: str) -> Process | None:
    document = await get_processes_collection().find_one({"_id": process_id})
    if not document:
        return None
    return Process.model_validate(document)


async def delete(process_id: str) -> None:
    await get_processes_collection().delete_one({"_id": process_id})
