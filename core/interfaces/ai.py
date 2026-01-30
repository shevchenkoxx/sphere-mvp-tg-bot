"""
AI service interfaces - abstractions for AI operations.
Allows swapping between providers (Claude, GPT, local models, etc.)
"""

from abc import ABC, abstractmethod
from typing import Dict, Any
from core.domain.models import MatchResult


class IAIService(ABC):
    """Interface for AI analysis services"""

    @abstractmethod
    async def generate_user_summary(self, user_data: Dict[str, Any]) -> str:
        """Generate AI summary of user profile for matching"""
        pass

    @abstractmethod
    async def analyze_match(
        self,
        user_a: Dict[str, Any],
        user_b: Dict[str, Any],
        event_context: str = None
    ) -> MatchResult:
        """Analyze compatibility between two users"""
        pass

    @abstractmethod
    async def generate_icebreaker(
        self,
        user_a: Dict[str, Any],
        user_b: Dict[str, Any],
        match_type: str
    ) -> str:
        """Generate conversation starter for a match"""
        pass


class IVoiceService(ABC):
    """Interface for voice transcription services"""

    @abstractmethod
    async def transcribe(self, audio_file_path: str, language: str = "ru") -> str:
        """Transcribe audio file to text"""
        pass

    @abstractmethod
    async def download_and_transcribe(self, file_url: str, language: str = "ru") -> str:
        """Download audio from URL and transcribe"""
        pass
