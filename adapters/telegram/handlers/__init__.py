from adapters.telegram.config import ONBOARDING_VERSION
from adapters.telegram.handlers import start, onboarding, onboarding_v2, events, matches

routers = [
    start.router,
    # Include both for backwards compatibility, v2 states are different
    onboarding.router if ONBOARDING_VERSION == "v1" else onboarding_v2.router,
    events.router,
    matches.router,
]

__all__ = ["routers", "ONBOARDING_VERSION"]
