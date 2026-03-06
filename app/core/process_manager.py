import asyncio
from typing import Dict


class ProcessManager:
    def __init__(self):
        self.active_processes: Dict[str, asyncio.Task] = {}

    def register(self, process_id: str, process: asyncio.Task):
        self.active_processes[process_id] = process

    def cancel(self, process_id: str):
        process = self.active_processes.get(process_id)
        if process:
            process.cancel()

    def remove(self, process_id: str):
        self.active_processes.pop(process_id, None)


process_manager = ProcessManager()
