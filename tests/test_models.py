"""
Tests for domain models — validates Pydantic validation, defaults, and enums.
"""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from core.domain.models import (
    EventCreate,
    MatchCreate,
    MatchResult,
    MatchResultWithId,
    MatchType,
    MessagePlatform,
    OnboardingData,
    User,
    UserCreate,
    UserUpdate,
)


class TestMessagePlatform:
    def test_telegram_value(self):
        assert MessagePlatform.TELEGRAM == "telegram"

    def test_all_platforms(self):
        assert set(MessagePlatform) == {
            MessagePlatform.TELEGRAM,
            MessagePlatform.WHATSAPP,
            MessagePlatform.WEB,
        }


class TestMatchType:
    def test_all_types(self):
        assert set(MatchType) == {
            MatchType.FRIENDSHIP,
            MatchType.PROFESSIONAL,
            MatchType.ROMANTIC,
            MatchType.CREATIVE,
        }


class TestUserCreate:
    def test_minimal_user(self):
        user = UserCreate(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id="123456",
        )
        assert user.platform == MessagePlatform.TELEGRAM
        assert user.interests == []
        assert user.goals == []
        assert user.bio is None

    def test_full_user(self):
        user = UserCreate(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id="123456",
            username="testuser",
            first_name="Test",
            display_name="Test User",
            interests=["tech", "art"],
            goals=["networking"],
            bio="Test bio",
        )
        assert user.username == "testuser"
        assert len(user.interests) == 2


class TestUser:
    def test_defaults(self, make_user):
        user = make_user()
        assert user.onboarding_completed is True
        assert user.is_active is True
        assert user.matching_mode == "event"
        assert user.referral_count == 0

    def test_activity_fields_default(self):
        user = User(
            id=uuid4(),
            platform=MessagePlatform.TELEGRAM,
            platform_user_id="123",
        )
        assert user.activity_categories is None
        assert user.activity_details is None
        assert user.custom_activity_text is None


class TestUserUpdate:
    def test_partial_update(self):
        update = UserUpdate(bio="new bio")
        assert update.bio == "new bio"
        assert update.display_name is None
        assert update.interests is None

    def test_activity_update(self):
        update = UserUpdate(
            activity_categories=["coffee", "sport"],
            activity_details={"sport": {"subcategories": ["running"]}},
        )
        assert len(update.activity_categories) == 2


class TestMatchResult:
    def test_valid_score(self):
        result = MatchResult(
            compatibility_score=0.85,
            match_type=MatchType.PROFESSIONAL,
            explanation="Good match",
            icebreaker="Talk about tech!",
        )
        assert result.compatibility_score == 0.85

    def test_score_bounds(self):
        with pytest.raises(ValidationError):
            MatchResult(
                compatibility_score=1.5,
                match_type=MatchType.PROFESSIONAL,
                explanation="test",
                icebreaker="test",
            )

        with pytest.raises(ValidationError):
            MatchResult(
                compatibility_score=-0.1,
                match_type=MatchType.PROFESSIONAL,
                explanation="test",
                icebreaker="test",
            )

    def test_match_result_with_id(self):
        match_id = uuid4()
        result = MatchResultWithId(
            match_id=match_id,
            compatibility_score=0.7,
            match_type=MatchType.FRIENDSHIP,
            explanation="test",
            icebreaker="test",
        )
        assert result.match_id == match_id


class TestMatchCreate:
    def test_event_match(self):
        match = MatchCreate(
            event_id=uuid4(),
            user_a_id=uuid4(),
            user_b_id=uuid4(),
            compatibility_score=0.9,
            match_type=MatchType.PROFESSIONAL,
            ai_explanation="test",
            icebreaker="test",
        )
        assert match.event_id is not None
        assert match.city is None

    def test_city_match(self):
        match = MatchCreate(
            user_a_id=uuid4(),
            user_b_id=uuid4(),
            compatibility_score=0.7,
            match_type=MatchType.FRIENDSHIP,
            ai_explanation="test",
            icebreaker="test",
            city="Berlin",
        )
        assert match.event_id is None
        assert match.city == "Berlin"


class TestOnboardingData:
    def test_defaults(self):
        data = OnboardingData()
        assert data.display_name is None
        assert data.selected_interests == []
        assert data.pending_event_code is None

    def test_with_event(self):
        data = OnboardingData(
            display_name="Test",
            selected_interests=["tech"],
            pending_event_code="TEST2024",
        )
        assert data.pending_event_code == "TEST2024"


class TestEventCreate:
    def test_default_settings(self):
        event = EventCreate(
            name="Test Event",
            organizer_platform=MessagePlatform.TELEGRAM,
            organizer_platform_id="123",
        )
        assert event.settings["auto_match"] is True
        assert event.settings["match_threshold"] == 0.6
