import unittest
from unittest.mock import AsyncMock, patch

from app.schemas.chat import Chat, ChatMode, ChatProcessPayload, ChatResumeRequest
from app.schemas.message import Message, MessageStatus, Role, TextPart
from app.schemas.process import Process, State
from app.services.chat import handler


class ChatHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_start_new_chat_emits_chat_human_and_ai_messages(self):
        created_chat = Chat(user_id="user-1", mode=ChatMode.GENERAL, title="Hello")
        user_message = Message(
            chat_id=created_chat.id,
            user_id="user-1",
            process_id="process-1",
            role=Role.HUMAN,
            status=MessageStatus.COMPLETE,
            parts=[TextPart(text="Hello")],
        )
        assistant_message = Message(
            chat_id=created_chat.id,
            user_id="user-1",
            process_id="process-1",
            role=Role.AI,
            status=MessageStatus.PENDING,
            parts=[],
        )
        process = Process(
            id="process-1",
            status=State.PENDING,
            payload=ChatProcessPayload(
                chat_id=created_chat.id,
                user_message_id=user_message.id,
                assistant_message_id=assistant_message.id,
                mode=ChatMode.GENERAL,
            ).model_dump(mode="json"),
        )

        with (
            patch.object(
                handler, "_load_chat_for_start", AsyncMock(return_value=(created_chat, True))
            ),
            patch.object(
                handler,
                "_create_turn_records",
                AsyncMock(
                    return_value=(created_chat, process, user_message, assistant_message)
                ),
            ),
            patch.object(handler, "_queue_process", AsyncMock()) as queue_mock,
            patch.object(handler, "send_data", AsyncMock()) as send_mock,
        ):
            await handler.start(
                "user-1",
                {
                    "request_id": "req-1",
                    "mode": "general",
                    "parts": [{"type": "text", "text": "Hello"}],
                },
            )

        queue_mock.assert_awaited_once_with("user-1", process.id)
        self.assertEqual(send_mock.await_count, 3)
        chat_event = send_mock.await_args_list[0].args[1]
        self.assertEqual(chat_event.payload.request_id, "req-1")

    async def test_resume_reuses_same_process_and_increments_resume_count(self):
        chat = Chat(user_id="user-1", mode=ChatMode.GENERAL, title="Chat", id="chat-1")
        process = Process(
            status=State.STOPPED,
            payload=ChatProcessPayload(
                chat_id="chat-1",
                user_message_id="msg-user",
                assistant_message_id="msg-ai",
                mode=ChatMode.GENERAL,
                resume_count=0,
            ).model_dump(mode="json"),
        )

        with (
            patch.object(
                handler.chat_repository, "get_by_id", AsyncMock(return_value=chat)
            ),
            patch.object(
                handler.process_repository, "get_by_id", AsyncMock(return_value=process)
            ),
            patch.object(
                handler.process_repository,
                "save",
                AsyncMock(side_effect=lambda value: value),
            ) as save_mock,
            patch.object(handler, "_queue_process", AsyncMock()) as queue_mock,
        ):
            await handler.resume(
                "user-1",
                ChatResumeRequest(chat_id="chat-1", process_id=process.id).model_dump(
                    mode="json"
                ),
            )

        queue_mock.assert_awaited_once_with("user-1", process.id)
        save_call = save_mock.await_args
        self.assertIsNotNone(save_call)
        assert save_call is not None
        saved_process = save_call.args[0]
        payload = ChatProcessPayload.model_validate(saved_process.payload)
        self.assertEqual(saved_process.status, State.PENDING)
        self.assertEqual(payload.resume_count, 1)

    async def test_stop_marks_pending_process_stopped_when_not_active(self):
        chat = Chat(user_id="user-1", mode=ChatMode.GENERAL, title="Chat", id="chat-1")
        process = Process(
            status=State.PENDING,
            payload=ChatProcessPayload(
                chat_id="chat-1",
                user_message_id="msg-user",
                assistant_message_id="msg-ai",
                mode=ChatMode.GENERAL,
            ).model_dump(mode="json"),
        )
        assistant_message = Message(
            id="msg-ai",
            chat_id="chat-1",
            user_id="user-1",
            process_id=process.id,
            role=Role.AI,
            status=MessageStatus.PENDING,
            parts=[],
        )

        with (
            patch.object(
                handler.chat_repository, "get_by_id", AsyncMock(return_value=chat)
            ),
            patch.object(
                handler.process_repository, "get_by_id", AsyncMock(return_value=process)
            ),
            patch.object(
                handler.process_repository,
                "save",
                AsyncMock(side_effect=lambda value: value),
            ) as process_save_mock,
            patch.object(
                handler.message_repository,
                "get_by_id",
                AsyncMock(return_value=assistant_message),
            ),
            patch.object(
                handler.message_repository,
                "save",
                AsyncMock(side_effect=lambda value: value),
            ) as message_save_mock,
            patch.object(handler.process_manager, "cancel", return_value=False),
            patch.object(handler, "send_data", AsyncMock()) as send_mock,
        ):
            await handler.stop(
                "user-1",
                {"chat_id": "chat-1", "process_id": process.id},
            )

        process_save_call = process_save_mock.await_args
        message_save_call = message_save_mock.await_args
        self.assertIsNotNone(process_save_call)
        self.assertIsNotNone(message_save_call)
        assert process_save_call is not None
        assert message_save_call is not None
        saved_process = process_save_call.args[0]
        saved_message = message_save_call.args[0]
        self.assertEqual(saved_process.status, State.STOPPED)
        self.assertEqual(saved_message.status, MessageStatus.STOPPED)
        self.assertEqual(send_mock.await_count, 1)


if __name__ == "__main__":
    unittest.main()
