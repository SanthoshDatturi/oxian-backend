# handler.py is used for interacting with user, task management, and calling the service functions
from enum import StrEnum

from pydantic import BaseModel


class ChatEvent(StrEnum):
    START = "start"
    RETRY = "retry"
    STOP = "stop"


async def send_chunck(user_id: str, process_id: str, chunk: str):
    pass


async def send_data(user_id: str, process_id: str, data: BaseModel):
    pass


async def start(user_id: str, data: dict):
    """
    Create a new asyncio.create_task() and push it to the task queue.
    send_chunck() will be used as a callback function to send the generated response back to the user in real-time,
    with connection_manager.send_to_user() to send the message to the user's websocket connection.
    """
    pass


async def retry(user_id: str, data: dict):
    pass


async def stop(user_id: str, data: dict):
    """
    Cancel the running task for the user.
    """
    pass


chat_handlers = {ChatEvent.START: start, ChatEvent.RETRY: retry, ChatEvent.STOP: stop}
