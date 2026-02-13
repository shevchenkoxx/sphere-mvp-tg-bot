"""
Telegram adapter configuration.
Uses centralized feature flags.
"""

import logging
from config.features import features

# Onboarding mode from feature flags
# Options: 'v1' (buttons), 'v2' (conversation), 'audio' (voice), 'intent' (V1.1 intent-based)
_valid_modes = {"v1", "v2", "audio", "intent"}
_raw_mode = features.ONBOARDING_MODE
if _raw_mode not in _valid_modes:
    logging.getLogger(__name__).warning(
        f"Invalid ONBOARDING_MODE='{_raw_mode}', falling back to 'intent'. "
        f"Valid options: {_valid_modes}"
    )
    ONBOARDING_VERSION = "intent"
else:
    ONBOARDING_VERSION = _raw_mode
