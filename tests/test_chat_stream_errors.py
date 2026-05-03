import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

from pydantic import BaseModel, ValidationError
from fastapi import HTTPException

from app.api.rest import chat as chat_api
from app.schemas.chat import Chat
from app.schemas.message import Message, NewChatMessageInput, Role, TextPart
from app.schemas.process import Process, State
from app.services.chat import service


class InvalidPayload(BaseModel):
    value: int


class FailingAgent:
    def __init__(self, exc: Exception):
        self.exc = exc

    async def astream_events(self, *_args, **_kwargs):
        raise self.exc
        yield


async def _drain_events(queue: asyncio.Queue):
    events = []
    while True:
        event = await queue.get()
        if event is None:
            break
        events.append(event)
    return events


class ChatStreamErrorTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.chat = Chat(
            id="chat-1",
            user_id="user-1",
            title="Test chat",
        )
        self.user_message = Message(
            id="human-1",
            chat_id=self.chat.id,
            user_id=self.chat.user_id,
            role=Role.HUMAN,
            parts=[TextPart(text="hello")],
        )
        self.assistant_message = Message(
            id="ai-1",
            chat_id=self.chat.id,
            user_id=self.chat.user_id,
            role=Role.AI,
            parts=[],
        )
        self.process = Process(id="process-1", status=State.PENDING)
        self.events: asyncio.Queue = asyncio.Queue()
        self.saved_messages = []
        self.saved_processes = []

        async def save_message(message):
            self.saved_messages.append(message)
            return message

        async def save_process(process):
            self.saved_processes.append(process)
            return process

        self.patches = [
            patch.object(
                service.message_repository,
                "list_latest_by_chat",
                AsyncMock(return_value=[self.user_message, self.assistant_message]),
            ),
            patch.object(service.message_repository, "save", AsyncMock(side_effect=save_message)),
            patch.object(service.process_repository, "save", AsyncMock(side_effect=save_process)),
            patch.object(service.process_manager, "register", Mock()),
            patch.object(service.process_manager, "remove", Mock()),
            patch.object(service, "_build_prompt", AsyncMock(return_value="system prompt")),
            patch.object(service, "ChatGoogleGenerativeAI", Mock(return_value=object())),
        ]
        for patcher in self.patches:
            patcher.start()

    async def asyncTearDown(self):
        for patcher in reversed(self.patches):
            patcher.stop()

    async def _run_failing_turn(self, exc: Exception):
        with patch.object(service, "create_agent", Mock(return_value=FailingAgent(exc))):
            await service._run_turn(
                process=self.process,
                chat=self.chat,
                user_message=self.user_message,
                assistant_message=self.assistant_message,
                model_content=[{"type": "text", "text": "hello"}],
                events=self.events,
            )
        return await _drain_events(self.events)

    async def test_agent_error_persists_readable_message_and_emits_message_then_error(self):
        events = await self._run_failing_turn(RuntimeError("database URI leaked here"))

        saved_message = self.saved_messages[-1]
        self.assertEqual(saved_message.error.code, "agent_error")
        self.assertEqual(
            saved_message.error.message,
            "I couldn't complete this response right now. Please try again.",
        )
        self.assertEqual(saved_message.parts[0].text, saved_message.error.message)
        self.assertNotIn("database URI", saved_message.error.message)

        self.assertEqual([event["event"] for event in events], ["message", "error"])
        self.assertEqual(events[0]["data"]["message"]["error"]["code"], "agent_error")
        self.assertEqual(events[1]["data"]["code"], "agent_error")
        self.assertEqual(self.saved_processes[-1].status, State.FAILED)

    async def test_validation_error_persists_readable_message_and_emits_message_then_error(self):
        try:
            InvalidPayload.model_validate({"value": "not-an-int"})
        except ValidationError as exc:
            validation_error = exc

        events = await self._run_failing_turn(validation_error)

        saved_message = self.saved_messages[-1]
        self.assertEqual(saved_message.error.code, "validation_error")
        self.assertEqual(saved_message.parts[0].text, saved_message.error.message)
        self.assertNotIn("not-an-int", saved_message.error.message)

        self.assertEqual([event["event"] for event in events], ["message", "error"])
        self.assertEqual(events[0]["data"]["message"]["error"]["code"], "validation_error")
        self.assertEqual(events[1]["data"]["code"], "validation_error")
        self.assertEqual(self.saved_processes[-1].status, State.FAILED)


class ChatRouteErrorBoundaryTests(unittest.IsolatedAsyncioTestCase):
    async def test_new_chat_start_failure_returns_http_error_before_meta(self):
        payload = NewChatMessageInput(
            mode=self._general_mode(),
            parts=[TextPart(text="hello")],
        )

        with patch.object(
            chat_api,
            "start_new_chat_turn",
            AsyncMock(side_effect=RuntimeError("backend secret")),
        ):
            with self.assertRaises(HTTPException) as raised:
                await chat_api.create_chat_message(payload, {"uid": "user-1"})

        self.assertEqual(raised.exception.status_code, 500)
        self.assertEqual(
            raised.exception.detail,
            "Unable to start chat response right now.",
        )

    @staticmethod
    def _general_mode():
        from app.schemas.chat import ChatMode

        return ChatMode.GENERAL


if __name__ == "__main__":
    unittest.main()
