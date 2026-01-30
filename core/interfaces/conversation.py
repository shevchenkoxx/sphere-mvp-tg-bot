"""
Conversation interfaces - abstract contract for LLM-driven conversations.
Allows swapping LLM providers (OpenAI, Anthropic, local models).
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from enum import Enum


class ConversationRole(str, Enum):
    """Message roles in conversation"""
    SYSTEM = "system"
    ASSISTANT = "assistant"
    USER = "user"


@dataclass
class ConversationMessage:
    """Single message in conversation"""
    role: ConversationRole
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ConversationState:
    """Full conversation state - serializable for storage"""
    messages: List[ConversationMessage] = field(default_factory=list)
    system_prompt: str = ""
    context: Dict[str, Any] = field(default_factory=dict)  # Event name, user language, etc.
    step: int = 0
    is_complete: bool = False
    extracted_data: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for FSM storage"""
        return {
            "messages": [
                {"role": m.role.value, "content": m.content, "metadata": m.metadata}
                for m in self.messages
            ],
            "system_prompt": self.system_prompt,
            "context": self.context,
            "step": self.step,
            "is_complete": self.is_complete,
            "extracted_data": self.extracted_data
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConversationState":
        """Deserialize from FSM storage"""
        messages = [
            ConversationMessage(
                role=ConversationRole(m["role"]),
                content=m["content"],
                metadata=m.get("metadata", {})
            )
            for m in data.get("messages", [])
        ]
        return cls(
            messages=messages,
            system_prompt=data.get("system_prompt", ""),
            context=data.get("context", {}),
            step=data.get("step", 0),
            is_complete=data.get("is_complete", False),
            extracted_data=data.get("extracted_data", {})
        )

    def add_user_message(self, content: str) -> None:
        """Add user message to history"""
        self.messages.append(ConversationMessage(role=ConversationRole.USER, content=content))

    def add_assistant_message(self, content: str) -> None:
        """Add assistant response to history"""
        self.messages.append(ConversationMessage(role=ConversationRole.ASSISTANT, content=content))

    def get_history_for_llm(self) -> List[Dict[str, str]]:
        """Format messages for LLM API call"""
        result = []
        if self.system_prompt:
            result.append({"role": "system", "content": self.system_prompt})
        for msg in self.messages:
            result.append({"role": msg.role.value, "content": msg.content})
        return result


@dataclass
class ConversationResponse:
    """Response from LLM conversation"""
    message: str
    is_complete: bool = False  # True if PROFILE_COMPLETE marker found
    raw_response: str = ""
    tokens_used: int = 0


class IConversationAI(ABC):
    """Interface for LLM-driven conversations"""

    @abstractmethod
    async def generate_response(
        self,
        state: ConversationState,
        user_message: str
    ) -> ConversationResponse:
        """
        Generate next response in conversation.

        Args:
            state: Current conversation state with history
            user_message: Latest user message

        Returns:
            ConversationResponse with assistant's reply
        """
        pass

    @abstractmethod
    async def extract_profile_data(
        self,
        state: ConversationState
    ) -> Dict[str, Any]:
        """
        Extract structured profile data from completed conversation.

        Args:
            state: Completed conversation state

        Returns:
            Dict with extracted profile fields
        """
        pass


class IConversationStorage(ABC):
    """Interface for storing conversation state (FSM, Redis, DB)"""

    @abstractmethod
    async def get_state(self, user_id: str, platform: str) -> Optional[ConversationState]:
        """Get conversation state for user"""
        pass

    @abstractmethod
    async def save_state(self, user_id: str, platform: str, state: ConversationState) -> None:
        """Save conversation state"""
        pass

    @abstractmethod
    async def clear_state(self, user_id: str, platform: str) -> None:
        """Clear conversation state (on completion or reset)"""
        pass
