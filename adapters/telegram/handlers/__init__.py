from adapters.telegram.handlers import start, onboarding, events, matches

routers = [
    start.router,
    onboarding.router,
    events.router,
    matches.router,
]

__all__ = ["routers"]
