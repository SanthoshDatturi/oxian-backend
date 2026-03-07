from app.schemas.generic_types import Service, WebSocketInboundMessage
from app.services.chat.handler import chat_handlers
from app.services.crop_recommendation.handler import (
    crop_recommendation_handlers,
)

services = {
    Service.CHAT: chat_handlers,
    Service.CROP_RECOMMENDATION: crop_recommendation_handlers,
}


async def route_message(user_id: str, message: WebSocketInboundMessage):
    service_name = message.service
    event = message.event
    data = message.data

    if service_name not in services:
        raise ValueError("Unknown service")

    handler = services[service_name]

    if event not in handler:
        raise ValueError("Unknown event")

    await handler[event](user_id, data)
