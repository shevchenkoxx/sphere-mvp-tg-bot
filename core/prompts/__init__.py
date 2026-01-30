from core.prompts.templates import (
    # Conversational onboarding
    ONBOARDING_SYSTEM_PROMPT,
    PROFILE_EXTRACTION_PROMPT,
    # Legacy prompts
    USER_SUMMARY_PROMPT,
    MATCH_ANALYSIS_PROMPT,
    ICEBREAKER_PROMPT,
    PROFILE_ENRICHMENT_PROMPT,
    LINKEDIN_PARSE_PROMPT,
    format_prompt,
    get_user_summary_prompt,
    get_match_analysis_prompt,
)

from core.prompts.audio_onboarding import (
    AUDIO_GUIDE_PROMPT,
    AUDIO_GUIDE_PROMPT_RU,
    AUDIO_EXTRACTION_PROMPT,
    AUDIO_FOLLOWUP_PROMPT,
    AUDIO_CONFIRMATION_TEMPLATE,
    AUDIO_CONFIRMATION_TEMPLATE_RU,
)

__all__ = [
    # Conversational onboarding
    "ONBOARDING_SYSTEM_PROMPT",
    "PROFILE_EXTRACTION_PROMPT",
    # Audio onboarding
    "AUDIO_GUIDE_PROMPT",
    "AUDIO_GUIDE_PROMPT_RU",
    "AUDIO_EXTRACTION_PROMPT",
    "AUDIO_FOLLOWUP_PROMPT",
    "AUDIO_CONFIRMATION_TEMPLATE",
    "AUDIO_CONFIRMATION_TEMPLATE_RU",
    # Legacy prompts
    "USER_SUMMARY_PROMPT",
    "MATCH_ANALYSIS_PROMPT",
    "ICEBREAKER_PROMPT",
    "PROFILE_ENRICHMENT_PROMPT",
    "LINKEDIN_PARSE_PROMPT",
    "format_prompt",
    "get_user_summary_prompt",
    "get_match_analysis_prompt",
]
