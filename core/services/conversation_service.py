"""
Conversation Service - orchestrates LLM-driven onboarding.
Platform-agnostic, modular, extensible.
"""

import logging
from typing import Dict, Any, Optional, Tuple
from dataclasses import dataclass

from core.interfaces.conversation import (
    IConversationAI,
    ConversationState,
    ConversationResponse,
)
from core.domain.models import MessagePlatform, OnboardingData

logger = logging.getLogger(__name__)


@dataclass
class OnboardingResult:
    """Result of onboarding conversation step"""
    response_text: str
    is_complete: bool
    profile_data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


class ConversationService:
    """
    Service for managing LLM-driven conversations.
    Handles onboarding flow, profile extraction, state management.
    """

    def __init__(self, conversation_ai: IConversationAI):
        self.conversation_ai = conversation_ai

    def create_onboarding_state(
        self,
        event_name: Optional[str] = None,
        user_language: Optional[str] = None,
        user_first_name: Optional[str] = None
    ) -> ConversationState:
        """
        Create initial conversation state for onboarding.

        Args:
            event_name: Event context for personalization
            user_language: Detected/preferred language
            user_first_name: User's first name if known

        Returns:
            Fresh ConversationState ready for conversation
        """
        return ConversationState(
            messages=[],
            system_prompt="",  # Will be built by AI from context
            context={
                "event_name": event_name,
                "user_language": user_language,
                "user_first_name": user_first_name,
                "type": "onboarding"
            },
            step=0,
            is_complete=False
        )

    async def process_message(
        self,
        state: ConversationState,
        user_message: str
    ) -> Tuple[ConversationState, OnboardingResult]:
        """
        Process user message and return response.

        Args:
            state: Current conversation state
            user_message: User's message

        Returns:
            Tuple of (updated state, result)
        """
        try:
            # CRITICAL: Add user message BEFORE LLM call
            # This ensures message is recorded even if LLM fails,
            # preventing infinite retry loops with identical state
            state.add_user_message(user_message)
            logger.debug(f"Added user message to history. Step will advance: {state.step} → {state.step + 1}")

            # Generate response
            response = await self.conversation_ai.generate_response(state, user_message)

            # Increment step (guaranteed to happen since message already added)
            state.step += 1
            logger.debug(f"Incremented conversation step to {state.step}")

            # If complete, extract profile
            profile_data = None
            if response.is_complete:
                state.is_complete = True
                profile_data = await self.conversation_ai.extract_profile_data(state)
                state.extracted_data = profile_data
                logger.info(f"Onboarding conversation complete. Extracted profile fields: {list(profile_data.keys())}")

            result = OnboardingResult(
                response_text=response.message,
                is_complete=response.is_complete,
                profile_data=profile_data
            )

            return state, result

        except Exception as e:
            logger.error(f"Conversation processing error: {e}")
            # NOTE: State is already updated with user message added and step will be consistent
            # on next call. This prevents infinite retry loops where same error occurs repeatedly.
            result = OnboardingResult(
                response_text="Sorry, something went wrong. Let's try again.",
                is_complete=False,
                error=str(e)
            )
            return state, result  # State already modified - message recorded, step consistent

    async def start_conversation(
        self,
        state: ConversationState
    ) -> Tuple[ConversationState, str]:
        """
        Start conversation with initial greeting.

        Returns greeting message without needing user input.
        """
        # Create initial assistant message to start conversation
        event_name = state.context.get("event_name", "")
        user_name = state.context.get("user_first_name", "")

        # Generate first message by sending empty trigger
        # The LLM will see it's a fresh conversation and greet
        initial_trigger = f"Hi" if not user_name else f"Hi, I'm {user_name}"

        response = await self.conversation_ai.generate_response(state, initial_trigger)

        # Actually, let's handle this differently - we want the bot to speak first
        # Remove the user message we just added and keep only assistant response
        if state.messages and state.messages[-1].role.value == "user":
            # Keep the conversation but mark it as started
            pass

        return state, response.message

    def convert_to_onboarding_data(
        self,
        extracted_data: Dict[str, Any],
        pending_event_code: Optional[str] = None
    ) -> OnboardingData:
        """
        Convert extracted profile data to OnboardingData model.

        Args:
            extracted_data: Data extracted from conversation
            pending_event_code: Event code if joining from QR

        Returns:
            OnboardingData ready for user service
        """
        return OnboardingData(
            display_name=extracted_data.get("display_name"),
            city_born=None,  # Not collected in conversational flow
            city_current=None,
            selected_interests=extracted_data.get("interests", []),
            selected_goals=extracted_data.get("goals", []),
            bio=self._build_bio_from_extracted(extracted_data),
            pending_event_code=pending_event_code
        )

    def _build_bio_from_extracted(self, data: Dict[str, Any]) -> str:
        """Build bio from extracted fields"""
        parts = []

        if data.get("about"):
            parts.append(data["about"])

        if data.get("looking_for"):
            parts.append(f"Looking for: {data['looking_for']}")

        if data.get("can_help_with"):
            parts.append(f"Can help with: {data['can_help_with']}")

        return " | ".join(parts)[:500] if parts else ""


# === Conversation State Helpers ===

def serialize_state(state: ConversationState) -> Dict[str, Any]:
    """Serialize state for FSM storage"""
    return state.to_dict()


def deserialize_state(data: Dict[str, Any]) -> ConversationState:
    """Deserialize state from FSM storage"""
    return ConversationState.from_dict(data)
