"""
OpenAI-based conversation AI for onboarding.
Modular - can be swapped for Anthropic, local models, etc.
"""

import json
import re
import logging
from typing import Dict, Any
from openai import AsyncOpenAI

from core.interfaces.conversation import (
    IConversationAI,
    ConversationState,
    ConversationResponse,
)
from core.prompts import ONBOARDING_SYSTEM_PROMPT, PROFILE_EXTRACTION_PROMPT
from config.settings import settings

logger = logging.getLogger(__name__)


class OpenAIConversationAI(IConversationAI):
    """OpenAI implementation of conversation AI"""

    # Marker that signals profile completion
    COMPLETION_MARKER = "PROFILE_COMPLETE"

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        max_tokens: int = 500,
        temperature: float = 0.7
    ):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature

    def _build_system_prompt(self, context: Dict[str, Any]) -> str:
        """Build system prompt with context"""
        event_name = context.get("event_name", "")
        return ONBOARDING_SYSTEM_PROMPT.format(event_name=event_name or "this event")

    async def generate_response(
        self,
        state: ConversationState,
        user_message: str
    ) -> ConversationResponse:
        """Generate next response in conversation"""

        # Add user message to state
        state.add_user_message(user_message)

        # Build messages for API
        system_prompt = self._build_system_prompt(state.context)
        messages = [{"role": "system", "content": system_prompt}]

        for msg in state.messages:
            messages.append({"role": msg.role.value, "content": msg.content})

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=self.max_tokens,
                temperature=self.temperature
            )

            assistant_message = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0

            # Check for completion marker
            is_complete = self.COMPLETION_MARKER in assistant_message

            # Clean marker from display message
            display_message = assistant_message.replace(f"🎉 {self.COMPLETION_MARKER} 🎉", "").strip()

            # Add assistant message to state
            state.add_assistant_message(assistant_message)
            state.is_complete = is_complete

            return ConversationResponse(
                message=display_message,
                is_complete=is_complete,
                raw_response=assistant_message,
                tokens_used=tokens_used
            )

        except Exception as e:
            logger.error(f"OpenAI conversation error: {e}")
            # Fallback response
            return ConversationResponse(
                message="Sorry, I had a technical issue. Could you repeat that?",
                is_complete=False,
                raw_response=str(e)
            )

    async def extract_profile_data(
        self,
        state: ConversationState
    ) -> Dict[str, Any]:
        """Extract structured profile from conversation"""

        # Build conversation history as text
        conversation_text = ""
        for msg in state.messages:
            role = "User" if msg.role.value == "user" else "Assistant"
            conversation_text += f"{role}: {msg.content}\n\n"

        prompt = PROFILE_EXTRACTION_PROMPT.format(
            conversation_history=conversation_text
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800,
                temperature=0.1  # Low temperature for consistent extraction
            )

            text = response.choices[0].message.content

            # Clean JSON from markdown blocks
            text = re.sub(r'```json\s*', '', text)
            text = re.sub(r'```\s*', '', text)
            text = text.strip()

            data = json.loads(text)

            # Validate and clean data
            return self._validate_extracted_data(data)

        except json.JSONDecodeError as e:
            logger.error(f"Profile extraction JSON error: {e}")
            return self._extract_fallback(state)
        except Exception as e:
            logger.error(f"Profile extraction error: {e}")
            return self._extract_fallback(state)

    def _validate_extracted_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize extracted data"""
        valid_interests = {
            "tech", "business", "startups", "crypto", "design", "art",
            "music", "books", "travel", "sport", "wellness", "psychology",
            "gaming", "ecology", "cooking", "cinema"
        }
        valid_goals = {
            "networking", "friends", "business", "mentorship",
            "cofounders", "creative", "learning", "dating"
        }

        # Filter to valid values
        interests = [i for i in data.get("interests", []) if i in valid_interests]
        goals = [g for g in data.get("goals", []) if g in valid_goals]

        # Ensure minimum selections
        if not interests:
            interests = ["networking"]  # Default
        if not goals:
            goals = ["networking"]

        return {
            "display_name": data.get("display_name"),
            "about": data.get("about", ""),
            "looking_for": data.get("looking_for", ""),
            "can_help_with": data.get("can_help_with", ""),
            "link": data.get("link"),
            "language": data.get("language", "en"),
            "interests": interests[:5],  # Max 5
            "goals": goals[:3],  # Max 3
        }

    def _extract_fallback(self, state: ConversationState) -> Dict[str, Any]:
        """Fallback extraction from conversation text"""
        # Simple extraction from user messages
        user_messages = [m.content for m in state.messages if m.role.value == "user"]

        about = user_messages[0] if len(user_messages) > 0 else ""
        looking_for = user_messages[1] if len(user_messages) > 1 else ""
        can_help_with = user_messages[2] if len(user_messages) > 2 else ""

        return {
            "display_name": None,
            "about": about[:500],
            "looking_for": looking_for[:500],
            "can_help_with": can_help_with[:500],
            "link": None,
            "language": "en",
            "interests": ["networking"],
            "goals": ["networking"],
        }


# Factory function for easy instantiation
def create_conversation_ai(
    provider: str = "openai",
    **kwargs
) -> IConversationAI:
    """
    Factory to create conversation AI instance.

    Args:
        provider: "openai", "anthropic" (future), "local" (future)
        **kwargs: Provider-specific options

    Returns:
        IConversationAI implementation
    """
    if provider == "openai":
        return OpenAIConversationAI(**kwargs)
    # Future: add Anthropic, local models
    else:
        raise ValueError(f"Unknown conversation AI provider: {provider}")
