from adapters.telegram.handlers import start, onboarding, onboarding_v2, events, matches

# Choose onboarding version: 'v1' = scripted buttons, 'v2' = LLM conversation
ONBOARDING_VERSION = "v2"

routers = [
    start.router,
    # Include both for backwards compatibility, v2 states are different
    onboarding.router if ONBOARDING_VERSION == "v1" else onboarding_v2.router,
    events.router,
    matches.router,
]

__all__ = ["routers", "ONBOARDING_VERSION"]
