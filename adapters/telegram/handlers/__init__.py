from adapters.telegram.config import ONBOARDING_VERSION
from adapters.telegram.handlers import start, onboarding, onboarding_v2, onboarding_audio, events, matches, profile_edit, sphere_city, personalization

# Build list of onboarding routers based on config
# Audio mode includes v2 router because users can switch to text mode
onboarding_routers = []

if ONBOARDING_VERSION == "v1":
    onboarding_routers = [onboarding.router]
elif ONBOARDING_VERSION == "audio":
    # Include both audio AND v2 routers - users can switch to text mode
    onboarding_routers = [onboarding_audio.router, onboarding_v2.router]
else:  # v2 (default)
    onboarding_routers = [onboarding_v2.router]

# IMPORTANT: Onboarding routers must be BEFORE start router
# because start.py has fallback handlers that would catch onboarding callbacks
routers = [
    *onboarding_routers,  # Must be first to handle state-specific callbacks
    personalization.router,  # Post-onboarding personalization - before start.py
    profile_edit.router,  # Profile editing - before start.py
    sphere_city.router,   # Sphere City - before start.py
    start.router,
    events.router,
    matches.router,
]

__all__ = ["routers", "ONBOARDING_VERSION"]
