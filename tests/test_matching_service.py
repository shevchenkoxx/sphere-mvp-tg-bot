"""
Tests for MatchingService — base scoring and matching logic.
"""

from core.services.matching_service import MatchingService


class TestBaseScore:
    """Tests for calculate_base_score — the pre-filter before LLM analysis."""

    def _make_service(self, mock_match_repo, mock_event_repo, mock_ai_service):
        return MatchingService(
            match_repo=mock_match_repo,
            event_repo=mock_event_repo,
            ai_service=mock_ai_service,
        )

    def test_complementary_skills_score_high(
        self, mock_match_repo, mock_event_repo, mock_ai_service, make_user
    ):
        """Users with complementary looking_for/can_help_with should score higher."""
        service = self._make_service(mock_match_repo, mock_event_repo, mock_ai_service)

        user_a = make_user(
            platform_user_id="1",
            looking_for="Technical co-founder for startup",
            can_help_with="Marketing and growth strategy",
            interests=["tech", "startups"],
        )
        user_b = make_user(
            platform_user_id="2",
            looking_for="Marketing growth help",
            can_help_with="Technical development and engineering",
            interests=["tech", "business"],
        )

        score = service.calculate_base_score(user_a, user_b)
        assert score > 0.0, "Complementary users should have positive score"

    def test_no_overlap_scores_low(
        self, mock_match_repo, mock_event_repo, mock_ai_service, make_user
    ):
        """Users with no common interests or skills should score low."""
        service = self._make_service(mock_match_repo, mock_event_repo, mock_ai_service)

        user_a = make_user(
            platform_user_id="1",
            looking_for=None,
            can_help_with=None,
            interests=["art"],
            goals=["dating"],
        )
        user_b = make_user(
            platform_user_id="2",
            looking_for=None,
            can_help_with=None,
            interests=["sport"],
            goals=["networking"],
        )

        score = service.calculate_base_score(user_a, user_b)
        assert score < 0.3, "Non-overlapping users should score low"

    def test_shared_interests_boost(
        self, mock_match_repo, mock_event_repo, mock_ai_service, make_user
    ):
        """Shared interests should contribute to score."""
        service = self._make_service(mock_match_repo, mock_event_repo, mock_ai_service)

        user_a = make_user(
            platform_user_id="1",
            interests=["tech", "crypto", "startups"],
            goals=["networking"],
        )
        user_b = make_user(
            platform_user_id="2",
            interests=["tech", "crypto", "design"],
            goals=["networking"],
        )

        score = service.calculate_base_score(user_a, user_b)
        assert score > 0.0, "Shared interests should produce positive score"

    def test_empty_profiles_dont_crash(
        self, mock_match_repo, mock_event_repo, mock_ai_service, make_user
    ):
        """Empty profiles should return 0 score, not crash."""
        service = self._make_service(mock_match_repo, mock_event_repo, mock_ai_service)

        user_a = make_user(
            platform_user_id="1",
            looking_for=None,
            can_help_with=None,
            interests=[],
            goals=[],
            bio=None,
        )
        user_b = make_user(
            platform_user_id="2",
            looking_for=None,
            can_help_with=None,
            interests=[],
            goals=[],
            bio=None,
        )

        score = service.calculate_base_score(user_a, user_b)
        assert isinstance(score, float)
        assert 0.0 <= score <= 1.0
