# service.py is used for handling the business logic
# and interacting with other services like database, llm, etc.
from pydantic import BaseModel


async def chat(data: BaseModel, send_data):
    pass
