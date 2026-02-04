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
    """FSM states for event creation and joining"""
    waiting_name = State()
    waiting_description = State()
    waiting_location = State()
    confirming_event = State()
    waiting_event_code = State()  # For joining event by code


class ChatStates(StatesGroup):
    """FSM states for chat"""
    chatting = State()


class ProfileEditStates(StatesGroup):
    """FSM states for profile editing"""
    choosing_mode = State()           # Quick edit vs conversational
    choosing_field = State()          # Which field to edit
    entering_value = State()          # Entering new value (text or voice)
    confirming_changes = State()      # Preview and confirm
    conversational = State()          # LLM conversation mode


class PersonalizationStates(StatesGroup):
    """FSM states for post-onboarding personalization flow"""
    waiting_passion = State()         # Step 1: "Чем ты горишь прямо сейчас?"
    choosing_connection_mode = State()  # Step 2: receive_help / give_help / exchange
    choosing_adaptive_option = State()  # Step 3: LLM-generated personalized buttons
    waiting_ideal_connection = State()  # Step 4: Open-ended "Опиши идеального человека"


class MatchesPhotoStates(StatesGroup):
    """FSM states for photo request in matches flow"""
    waiting_photo = State()  # Waiting for selfie when user opens matches without photo
