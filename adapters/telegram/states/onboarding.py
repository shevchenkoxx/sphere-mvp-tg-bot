"""
FSM States for Telegram bot.
"""

from aiogram.fsm.state import State, StatesGroup


class OnboardingStates(StatesGroup):
    """FSM states for user onboarding"""
    waiting_name = State()
    waiting_city_born = State()
    waiting_city_current = State()
    waiting_interests = State()
    waiting_goals = State()
    waiting_bio = State()
    confirming_profile = State()


class EventStates(StatesGroup):
    """FSM states for event creation"""
    waiting_name = State()
    waiting_description = State()
    waiting_location = State()
    confirming_event = State()


class ChatStates(StatesGroup):
    """FSM states for chat"""
    chatting = State()
