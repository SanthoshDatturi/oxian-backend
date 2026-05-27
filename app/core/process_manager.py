import asyncio


class ProcessManager:
    def __init__(self):
        self.active_processes: dict[str, asyncio.Task] = {}
        self.pending_cancellations: set[str] = set()

    def register(self, process_id: str, process: asyncio.Task):
        self.active_processes[process_id] = process
        if process_id in self.pending_cancellations and not process.done():
            process.cancel()

    def get(self, process_id: str) -> asyncio.Task | None:
        return self.active_processes.get(process_id)

    def is_active(self, process_id: str) -> bool:
        task = self.active_processes.get(process_id)
        return task is not None and not task.done()

    def cancel(self, process_id: str) -> bool:
        self.pending_cancellations.add(process_id)
        process = self.active_processes.get(process_id)
        if process and not process.done():
            process.cancel()
        return True

    def remove(self, process_id: str):
        self.active_processes.pop(process_id, None)
        self.pending_cancellations.discard(process_id)


process_manager = ProcessManager()
