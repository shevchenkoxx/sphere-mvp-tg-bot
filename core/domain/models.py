"""
Domain models - the core of business logic.
These models are transport-agnostic (work with Telegram, WhatsApp, API, etc.)
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from uuid import UUID
from enum import Enum


# === ENUMS ===

class MatchType(str, Enum):
    FRIENDSHIP = "friendship"
    PROFESSIONAL = "professional"
    ROMANTIC = "romantic"
    CREATIVE = "creative"


class MatchStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"


class MeetupStatus(str, Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    DECLINED = "declined"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class MessagePlatform(str, Enum):
    """Platform abstraction for future multi-messenger support"""
    TELEGRAM = "telegram"
    WHATSAPP = "whatsapp"
    WEB = "web"


# === USER ===

class UserBase(BaseModel):
    """Base user data - platform agnostic"""
    display_name: Optional[str] = None
    city_born: Optional[str] = None
    city_current: Optional[str] = None
    interests: List[str] = Field(default_factory=list)
    goals: List[str] = Field(default_factory=list)
    bio: Optional[str] = None
    looking_for: Optional[str] = None  # What connections they want
    can_help_with: Optional[str] = None  # Their expertise/how they help


class UserCreate(UserBase):
    """Data for creating a new user"""
    platform: MessagePlatform
    platform_user_id: str  # telegram_id, whatsapp_id, etc.
    username: Optional[str] = None
    first_name: Optional[str] = None


class User(UserBase):
    """Full user model"""
    id: UUID
    platform: MessagePlatform
    platform_user_id: str
    username: Optional[str] = None
    first_name: Optional[str] = None
    photo_url: Optional[str] = None
    voice_intro_url: Optional[str] = None
    social_links: Dict[str, str] = Field(default_factory=dict)
    ai_summary: Optional[str] = None
    onboarding_completed: bool = False
    is_active: bool = True
    current_event_id: Optional[UUID] = None
    matching_mode: str = "event"  # 'event' or 'city'
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    # Vector embeddings for similarity matching
    profile_embedding: Optional[List[float]] = None
    interests_embedding: Optional[List[float]] = None
    expertise_embedding: Optional[List[float]] = None
    # Professional info (from extraction)
    profession: Optional[str] = None
    company: Optional[str] = None
    skills: Optional[List[str]] = None
    experience_level: Optional[str] = None  # junior/mid/senior/founder/executive
    # Personalization fields (post-onboarding)
    passion_text: Optional[str] = None
    passion_themes: Optional[List[str]] = None
    connection_mode: Optional[str] = None
    personalization_preference: Optional[str] = None
    ideal_connection: Optional[str] = None

    class Config:
        from_attributes = True


class UserUpdate(BaseModel):
    """Data for updating user"""
    display_name: Optional[str] = None
    first_name: Optional[str] = None
    city_born: Optional[str] = None
    city_current: Optional[str] = None
    interests: Optional[List[str]] = None
    goals: Optional[List[str]] = None
    bio: Optional[str] = None
    looking_for: Optional[str] = None
    can_help_with: Optional[str] = None
    photo_url: Optional[str] = None
    voice_intro_url: Optional[str] = None
    social_links: Optional[Dict[str, str]] = None
    ai_summary: Optional[str] = None
    onboarding_completed: Optional[bool] = None
    current_event_id: Optional[str] = None  # String UUID for JSON serialization
    # Professional info (from extraction)
    profession: Optional[str] = None
    company: Optional[str] = None
    skills: Optional[List[str]] = None
    # Matching mode
    matching_mode: Optional[str] = None  # 'event' or 'city'
    # Personalization fields (post-onboarding flow)
    passion_text: Optional[str] = None  # "What are you passionate about right now?"
    passion_themes: Optional[List[str]] = None  # Extracted themes from passion_text
    connection_mode: Optional[str] = None  # 'receive_help' / 'give_help' / 'exchange'
    personalization_preference: Optional[str] = None  # Selected adaptive button text
    ideal_connection: Optional[str] = None  # Free-form description of ideal person to meet


# === EVENT ===

class EventCreate(BaseModel):
    """Data for creating an event"""
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    event_date: Optional[datetime] = None
    organizer_platform: MessagePlatform
    organizer_platform_id: str
    settings: Dict[str, Any] = Field(default_factory=lambda: {
        "auto_match": True,
        "match_threshold": 0.6
    })


class Event(BaseModel):
    """Full event model"""
    id: UUID
    code: str
    name: str
    description: Optional[str] = None
    location: Optional[str] = None
    event_date: Optional[datetime] = None
    organizer_id: Optional[UUID] = None
    image_url: Optional[str] = None
    is_active: bool = True
    settings: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# === MATCH ===

class MatchResult(BaseModel):
    """AI analysis result for a potential match"""
    compatibility_score: float = Field(ge=0.0, le=1.0)
    match_type: MatchType
    explanation: str
    icebreaker: str


class MatchResultWithId(MatchResult):
    """MatchResult with match ID for notifications"""
    match_id: UUID


class MatchCreate(BaseModel):
    """Data for creating a match"""
    event_id: Optional[UUID] = None
    user_a_id: UUID
    user_b_id: UUID
    compatibility_score: float
    match_type: MatchType
    ai_explanation: str
    icebreaker: str
    city: Optional[str] = None  # For Sphere City matches


class Match(BaseModel):
    """Full match model"""
    id: UUID
    event_id: Optional[UUID] = None
    user_a_id: UUID
    user_b_id: UUID
    compatibility_score: float
    match_type: MatchType
    ai_explanation: str
    icebreaker: str
    status: MatchStatus = MatchStatus.PENDING
    user_a_notified: bool = False
    user_b_notified: bool = False
    city: Optional[str] = None  # For Sphere City matches
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# === MESSAGE ===

class MessageCreate(BaseModel):
    """Data for creating a message"""
    match_id: UUID
    sender_id: UUID
    content: str


class Message(BaseModel):
    """Full message model"""
    id: UUID
    match_id: UUID
    sender_id: UUID
    content: str
    is_read: bool = False
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# === ONBOARDING STATE ===

class OnboardingData(BaseModel):
    """Temporary data during onboarding process"""
    display_name: Optional[str] = None
    city_born: Optional[str] = None
    city_current: Optional[str] = None
    selected_interests: List[str] = Field(default_factory=list)
    selected_goals: List[str] = Field(default_factory=list)
    bio: Optional[str] = None
    pending_event_code: Optional[str] = None  # Event to join after onboarding


# === MEETUP PROPOSAL ===

class MeetupProposal(BaseModel):
    """Structured meetup proposal between matched users"""
    id: UUID
    short_id: str
    match_id: UUID
    proposer_id: UUID
    receiver_id: UUID
    event_id: Optional[UUID] = None
    time_slots: List[int]
    location: str
    ai_why_meet: Optional[str] = None
    ai_topics: Optional[List[str]] = None
    status: MeetupStatus = MeetupStatus.PENDING
    accepted_time_slot: Optional[int] = None
    created_at: Optional[datetime] = None
    responded_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True
