import unittest

from core.interfaces.conversation import ConversationState, ConversationResponse
from core.services.conversation_service import ConversationService


class FakeConversationAI:
    async def generate_response(self, state: ConversationState, user_message: str) -> ConversationResponse:
        if user_message == "complete":
            return ConversationResponse(
                message="done",
                is_complete=True,
                raw_response="done",
            )
        return ConversationResponse(
            message=f"echo:{user_message}",
            is_complete=False,
            raw_response=f"echo:{user_message}",
        )

    async def extract_profile_data(self, state: ConversationState):
        return {"display_name": "Test", "interests": ["tech"], "goals": ["networking"]}


class ConversationServiceTests(unittest.IsolatedAsyncioTestCase):
    async def test_process_message_adds_single_user_and_assistant_message(self):
        service = ConversationService(FakeConversationAI())
        state = service.create_onboarding_state(user_first_name="Alex")

        state, result = await service.process_message(state, "hello")

        self.assertEqual(state.step, 1)
        self.assertFalse(result.is_complete)
        self.assertEqual(len(state.messages), 2)
        self.assertEqual(state.messages[0].role.value, "user")
        self.assertEqual(state.messages[0].content, "hello")
        self.assertEqual(state.messages[1].role.value, "assistant")
        self.assertEqual(state.messages[1].content, "echo:hello")

    async def test_start_conversation_does_not_persist_synthetic_user_message(self):
        service = ConversationService(FakeConversationAI())
        state = service.create_onboarding_state(user_first_name="Alex")

        state, greeting = await service.start_conversation(state)

        self.assertEqual(greeting, "echo:Hi, I'm Alex")
        self.assertEqual(len(state.messages), 1)
        self.assertEqual(state.messages[0].role.value, "assistant")

    async def test_process_message_extracts_profile_on_completion(self):
        service = ConversationService(FakeConversationAI())
        state = service.create_onboarding_state()

        state, result = await service.process_message(state, "complete")

        self.assertTrue(result.is_complete)
        self.assertIsNotNone(result.profile_data)
        self.assertEqual(state.extracted_data.get("display_name"), "Test")


if __name__ == "__main__":
    unittest.main()
