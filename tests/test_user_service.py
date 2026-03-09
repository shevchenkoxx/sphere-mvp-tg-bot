"""
Tests for UserService — business logic with mocked repositories.
"""


import pytest

from core.domain.models import (
    MessagePlatform,
    OnboardingData,
    UserCreate,
    UserUpdate,
)
from core.services.user_service import UserService


class TestGetOrCreateUser:
    @pytest.mark.asyncio
    async def test_returns_existing_user(self, mock_user_repo, mock_ai_service, user_a):
        mock_user_repo.get_or_create.return_value = user_a
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)

        result = await service.get_or_create_user(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id="111",
            username="alice",
        )

        assert result.display_name == "Alice"
        mock_user_repo.get_or_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_passes_user_create_data(self, mock_user_repo, mock_ai_service, make_user):
        mock_user_repo.get_or_create.return_value = make_user(platform_user_id="999")
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)

        await service.get_or_create_user(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id="999",
            username="newuser",
            first_name="New",
        )

        call_args = mock_user_repo.get_or_create.call_args[0][0]
        assert isinstance(call_args, UserCreate)
        assert call_args.platform_user_id == "999"
        assert call_args.username == "newuser"


class TestUpdateUser:
    @pytest.mark.asyncio
    async def test_update_bio(self, mock_user_repo, mock_ai_service, user_a):
        mock_user_repo.update_by_platform_id.return_value = user_a
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)

        await service.update_user(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id="111",
            bio="Updated bio",
        )

        call_args = mock_user_repo.update_by_platform_id.call_args
        update_data = call_args[0][2]
        assert isinstance(update_data, UserUpdate)
        assert update_data.bio == "Updated bio"

    @pytest.mark.asyncio
    async def test_skips_none_values(self, mock_user_repo, mock_ai_service):
        mock_user_repo.update_by_platform_id.return_value = None
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)

        await service.update_user(
            platform=MessagePlatform.TELEGRAM,
            platform_user_id="111",
            bio="test",
            display_name=None,
        )

        call_args = mock_user_repo.update_by_platform_id.call_args
        update_data = call_args[0][2]
        assert update_data.bio == "test"
        assert update_data.display_name is None


class TestValidation:
    def test_valid_name(self, mock_user_repo, mock_ai_service):
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)
        valid, msg = service.validate_name("Alice")
        assert valid is True
        assert msg == ""

    def test_short_name(self, mock_user_repo, mock_ai_service):
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)
        valid, msg = service.validate_name("A")
        assert valid is False
        assert "at least" in msg

    def test_long_name(self, mock_user_repo, mock_ai_service):
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)
        valid, msg = service.validate_name("A" * 100)
        assert valid is False
        assert "at most" in msg

    def test_valid_interests(self, mock_user_repo, mock_ai_service):
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)
        valid, msg = service.validate_interests(["tech", "art"])
        assert valid is True

    def test_empty_interests(self, mock_user_repo, mock_ai_service):
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)
        valid, msg = service.validate_interests([])
        assert valid is False

    def test_too_many_interests(self, mock_user_repo, mock_ai_service):
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)
        valid, msg = service.validate_interests(["a", "b", "c", "d", "e", "f"])
        assert valid is False

    def test_valid_goals(self, mock_user_repo, mock_ai_service):
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)
        valid, msg = service.validate_goals(["networking"])
        assert valid is True

    def test_empty_goals(self, mock_user_repo, mock_ai_service):
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)
        valid, msg = service.validate_goals([])
        assert valid is False


class TestOnboardingCompleted:
    @pytest.mark.asyncio
    async def test_completed(self, mock_user_repo, mock_ai_service, user_a):
        mock_user_repo.get_by_platform_id.return_value = user_a
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)

        result = await service.is_onboarding_completed(
            MessagePlatform.TELEGRAM, "111"
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_not_completed(self, mock_user_repo, mock_ai_service, make_user):
        user = make_user(onboarding_completed=False)
        mock_user_repo.get_by_platform_id.return_value = user
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)

        result = await service.is_onboarding_completed(
            MessagePlatform.TELEGRAM, "123"
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_user_not_found(self, mock_user_repo, mock_ai_service):
        mock_user_repo.get_by_platform_id.return_value = None
        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)

        result = await service.is_onboarding_completed(
            MessagePlatform.TELEGRAM, "nonexistent"
        )
        assert result is False


class TestCompleteOnboarding:
    @pytest.mark.asyncio
    async def test_generates_summary(self, mock_user_repo, mock_ai_service, make_user):
        user = make_user(onboarding_completed=False)
        mock_user_repo.update_by_platform_id.return_value = user
        mock_user_repo.get_by_platform_id.return_value = user
        mock_ai_service.generate_user_summary.return_value = "Great profile!"

        service = UserService(user_repo=mock_user_repo, ai_service=mock_ai_service)

        data = OnboardingData(
            display_name="Test",
            selected_interests=["tech"],
            selected_goals=["networking"],
        )

        await service.complete_onboarding(
            MessagePlatform.TELEGRAM, "123", data
        )

        mock_ai_service.generate_user_summary.assert_called_once()
        assert mock_user_repo.update_by_platform_id.call_count == 2  # data + summary
