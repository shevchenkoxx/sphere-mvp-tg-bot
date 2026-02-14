"""
Feature Flags - Easy on/off toggle for features.
Change values here to enable/disable functionality.
"""

import os


class Features:
    """Feature toggles - set via env vars or defaults"""

    # === ONBOARDING MODE ===
    # Options: "v1" (buttons), "v2" (conversation), "audio" (voice message), "intent" (V1.1 intent-based)
    ONBOARDING_MODE: str = os.getenv("ONBOARDING_MODE", "intent")

    # === MATCHING ===
    MATCHING_ENABLED: bool = os.getenv("MATCHING_ENABLED", "true").lower() == "true"
    AUTO_MATCH_ON_JOIN: bool = os.getenv("AUTO_MATCH_ON_JOIN", "true").lower() == "true"
    SHOW_TOP_MATCHES: int = int(os.getenv("SHOW_TOP_MATCHES", "5"))
    MIN_MATCH_SCORE: float = float(os.getenv("MIN_MATCH_SCORE", "0.5"))

    # === DEEP PROFILING ===
    DEEP_PROFILE_ENABLED: bool = os.getenv("DEEP_PROFILE_ENABLED", "true").lower() == "true"

    # === SOCIAL PARSING ===
    LINKEDIN_PARSING_ENABLED: bool = os.getenv("LINKEDIN_PARSING_ENABLED", "false").lower() == "true"
    PROXYCURL_API_KEY: str = os.getenv("PROXYCURL_API_KEY", "")

    # === VOICE ===
    VOICE_ENABLED: bool = os.getenv("VOICE_ENABLED", "true").lower() == "true"
    MAX_VOICE_DURATION: int = int(os.getenv("MAX_VOICE_DURATION", "120"))  # seconds

    # === NOTIFICATIONS ===
    NOTIFY_NEW_MATCH: bool = os.getenv("NOTIFY_NEW_MATCH", "true").lower() == "true"
    NOTIFY_PROFILE_VIEWS: bool = os.getenv("NOTIFY_PROFILE_VIEWS", "false").lower() == "true"

    # === DEBUG ===
    DEBUG_MODE: bool = os.getenv("DEBUG", "false").lower() == "true"
    LOG_AI_RESPONSES: bool = os.getenv("LOG_AI_RESPONSES", "false").lower() == "true"

    @classmethod
    def to_dict(cls) -> dict:
        """Get all features as dict (useful for logging)"""
        return {
            "onboarding_mode": cls.ONBOARDING_MODE,
            "matching_enabled": cls.MATCHING_ENABLED,
            "auto_match_on_join": cls.AUTO_MATCH_ON_JOIN,
            "show_top_matches": cls.SHOW_TOP_MATCHES,
            "deep_profile_enabled": cls.DEEP_PROFILE_ENABLED,
            "linkedin_parsing_enabled": cls.LINKEDIN_PARSING_ENABLED,
            "voice_enabled": cls.VOICE_ENABLED,
            "debug_mode": cls.DEBUG_MODE,
        }

    @classmethod
    def log_status(cls):
        """Print current feature status"""
        print("\n=== Feature Flags ===")
        for key, value in cls.to_dict().items():
            status = "✅" if value else "❌" if isinstance(value, bool) else f"= {value}"
            print(f"  {key}: {status}")
        print("====================\n")


# Shortcut
features = Features()
