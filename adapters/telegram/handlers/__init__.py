from adapters.telegram.config import ONBOARDING_VERSION
from adapters.telegram.handlers import start, onboarding, onboarding_v2, onboarding_audio, events, matches

# Select onboarding router based on config
if ONBOARDING_VERSION == "v1":
    onboarding_router = onboarding.router
elif ONBOARDING_VERSION == "audio":
    onboarding_router = onboarding_audio.router
else:  # v2 (default)
    onboarding_router = onboarding_v2.router

routers = [
    start.router,
    onboarding_router,
    events.router,
    matches.router,
]

__all__ = ["routers", "ONBOARDING_VERSION"]
