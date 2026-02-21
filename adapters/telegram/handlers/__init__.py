from adapters.telegram.config import ONBOARDING_VERSION
from adapters.telegram.handlers import start, onboarding, onboarding_v2, onboarding_audio, events, matches, profile_edit, sphere_city, personalization, meetup, vibe_check, agent_chat
from config.features import Features

# Build list of onboarding routers based on config
# Audio mode includes v2 router because users can switch to text mode
onboarding_routers = []
personalization_routers = []

if ONBOARDING_VERSION == "agent":
    from adapters.telegram.handlers import onboarding_agent
    onboarding_routers = [onboarding_agent.router]
    # Agent handles personalization internally — no separate personalization router
    personalization_routers = []
elif ONBOARDING_VERSION == "v1":
    onboarding_routers = [onboarding.router]
    personalization_routers = [personalization.router]
elif ONBOARDING_VERSION == "intent":
    # V1.1 intent-based onboarding + daily questions + profile enrichment
    from adapters.telegram.handlers import onboarding_intent, daily_question, profile_enrichment
    onboarding_routers = [onboarding_intent.router, daily_question.router, profile_enrichment.router]
elif ONBOARDING_VERSION == "audio":
    # Include both audio AND v2 routers - users can switch to text mode
    onboarding_routers = [onboarding_audio.router, onboarding_v2.router]
    personalization_routers = [personalization.router]
else:  # v2 (default)
    onboarding_routers = [onboarding_v2.router]
    personalization_routers = [personalization.router]

# IMPORTANT: State-specific routers must be BEFORE start router
# because start.py has fallback handlers that would catch callbacks/messages
routers = [
    *onboarding_routers,  # Must be first to handle state-specific callbacks
    *personalization_routers,  # Post-onboarding personalization - before start.py
    profile_edit.router,  # Profile editing - before start.py
    sphere_city.router,   # Sphere City - before start.py
    agent_chat.router,    # Agent Chat - has FSM states (AgentChatStates), must be before start.py
    vibe_check.router,    # Vibe Check - has FSM states (VibeCheckStates), must be before start.py
    meetup.router,        # Meetup proposals - has FSM states, must be before start.py
    matches.router,       # Matches - has FSM states (MatchFeedbackStates), must be before start.py
]

# Only include events router when events are enabled
if Features.EVENTS_ENABLED:
    routers.append(events.router)

routers.append(start.router)  # Last: has catch-all handlers

__all__ = ["routers", "ONBOARDING_VERSION"]
