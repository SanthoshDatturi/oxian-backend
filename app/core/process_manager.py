import asyncio
from typing import Dict


class ProcessManager:
    def __init__(self):
        self.active_processes: Dict[str, asyncio.Task] = {}

    def register(self, process_id: str, process: asyncio.Task):
        self.active_processes[process_id] = process

    def get(self, process_id: str) -> asyncio.Task | None:
        return self.active_processes.get(process_id)

    def is_active(self, process_id: str) -> bool:
        task = self.active_processes.get(process_id)
        return task is not None and not task.done()

    def cancel(self, process_id: str) -> bool:
        process = self.active_processes.get(process_id)
        if process and not process.done():
            process.cancel()
            return True
        return False

    def remove(self, process_id: str):
        self.active_processes.pop(process_id, None)


process_manager = ProcessManager()
