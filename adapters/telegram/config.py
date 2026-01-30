"""
Telegram adapter configuration.
Uses centralized feature flags.
"""

from config.features import features

# Onboarding mode from feature flags
# Options: 'v1' (buttons), 'v2' (conversation), 'audio' (voice)
ONBOARDING_VERSION = features.ONBOARDING_MODE
