from enum import StrEnum

from pydantic import BaseModel


class Service(StrEnum):
    CHAT = "chat"


class WebSocketMessage(BaseModel):
    service: Service
    event: StrEnum
    data: dict


services = {}


async def route_message(user_id: str, message: WebSocketMessage):

    service_name = message.service
    event = message.event
    data = message.data

    if service_name not in services:
        raise Exception("Unknown service")

    service = services[service_name]

    if event not in service:
        raise Exception("Unknown event")

    await service[event](user_id, data)
