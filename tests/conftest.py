"""
Shared test fixtures for sphere-bot.
Provides mock objects for repositories, AI services, and domain models.
"""

from datetime import datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from core.domain.models import (
    Event,
    Match,
    MatchResult,
    MatchStatus,
    MatchType,
    MessagePlatform,
    User,
)
from core.interfaces.ai import IAIService
from core.interfaces.repositories import IEventRepository, IMatchRepository, IUserRepository

# === Domain Model Fixtures ===

@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def event_id():
    return uuid4()


@pytest.fixture
def make_user():
    """Factory fixture for creating User instances with defaults."""
    def _make(**overrides):
        defaults = {
            "id": uuid4(),
            "platform": MessagePlatform.TELEGRAM,
            "platform_user_id": "123456789",
            "username": "testuser",
            "first_name": "Test",
            "display_name": "Test User",
            "interests": ["tech", "startups"],
            "goals": ["networking"],
            "bio": "Test bio",
            "looking_for": "Co-founders and mentors",
            "can_help_with": "Tech and product development",
            "onboarding_completed": True,
            "created_at": datetime.now(),
        }
        defaults.update(overrides)
        return User(**defaults)
    return _make


@pytest.fixture
def user_a(make_user):
    return make_user(
        platform_user_id="111",
        username="alice",
        display_name="Alice",
        looking_for="Technical co-founder",
        can_help_with="Marketing and growth",
        interests=["tech", "startups", "business"],
    )


@pytest.fixture
def user_b(make_user):
    return make_user(
        platform_user_id="222",
        username="bob",
        display_name="Bob",
        looking_for="Marketing expertise",
        can_help_with="Full-stack development",
        interests=["tech", "business", "crypto"],
    )


@pytest.fixture
def sample_event(event_id):
    return Event(
        id=event_id,
        code="TEST2024",
        name="Test Event",
        description="A test event",
        is_active=True,
        settings={"auto_match": True, "match_threshold": 0.6},
    )


@pytest.fixture
def sample_match(user_a, user_b, event_id):
    return Match(
        id=uuid4(),
        event_id=event_id,
        user_a_id=user_a.id,
        user_b_id=user_b.id,
        compatibility_score=0.85,
        match_type=MatchType.PROFESSIONAL,
        ai_explanation="Both interested in tech startups",
        icebreaker="Talk about your startup ideas!",
        status=MatchStatus.PENDING,
    )


# === Mock Repository Fixtures ===

@pytest.fixture
def mock_user_repo():
    repo = AsyncMock(spec=IUserRepository)
    return repo


@pytest.fixture
def mock_event_repo():
    repo = AsyncMock(spec=IEventRepository)
    return repo


@pytest.fixture
def mock_match_repo():
    repo = AsyncMock(spec=IMatchRepository)
    return repo


@pytest.fixture
def mock_ai_service():
    service = AsyncMock(spec=IAIService)
    service.generate_user_summary.return_value = "AI-generated summary"
    service.analyze_match.return_value = MatchResult(
        compatibility_score=0.8,
        match_type=MatchType.PROFESSIONAL,
        explanation="Good match",
        icebreaker="Talk about tech!",
    )
    return service
