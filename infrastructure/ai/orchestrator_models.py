"""
Orchestrator Models — State and response models for the AI onboarding agent.

ProfileChecklist tracks which fields have been collected.
OnboardingAgentState holds the full conversation state (stored in FSM data).
OrchestratorResponse is what the orchestrator returns to the handler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from html import escape as html_escape
from typing import Any, Dict, List, Optional


# Fields the orchestrator tracks
REQUIRED_FIELDS = {"display_name", "about", "looking_for"}
IMPORTANT_FIELDS = {"can_help_with", "interests"}
OPTIONAL_FIELDS = {
    "profession", "company", "skills", "goals",
    "location", "experience_level",
}
PERSONALIZATION_FIELDS = {"passion_text", "connection_mode"}

ALL_PROFILE_FIELDS = REQUIRED_FIELDS | IMPORTANT_FIELDS | OPTIONAL_FIELDS | PERSONALIZATION_FIELDS


@dataclass
class ProfileChecklist:
    """Tracks which profile fields have been collected so far."""

    display_name: Optional[str] = None
    about: Optional[str] = None
    looking_for: Optional[str] = None
    can_help_with: Optional[str] = None
    interests: Optional[List[str]] = None
    goals: Optional[List[str]] = None
    profession: Optional[str] = None
    company: Optional[str] = None
    skills: Optional[List[str]] = None
    location: Optional[str] = None
    experience_level: Optional[str] = None
    passion_text: Optional[str] = None
    connection_mode: Optional[str] = None
    photo_url: Optional[str] = None

    # ---- helpers ----

    def missing_required(self) -> List[str]:
        missing = []
        for f in ("display_name", "about", "looking_for"):
            if not getattr(self, f):
                missing.append(f)
        return missing

    def missing_important(self) -> List[str]:
        missing = []
        if not self.can_help_with:
            missing.append("can_help_with")
        if not self.interests:
            missing.append("interests")
        return missing

    def completeness_score(self) -> float:
        """0.0 – 1.0 how complete the profile is."""
        total = 0
        filled = 0
        weights = {
            "display_name": 2, "about": 3, "looking_for": 3,
            "can_help_with": 2, "interests": 1, "goals": 1,
            "profession": 1, "company": 1, "skills": 1,
            "location": 0.5, "experience_level": 0.5,
            "passion_text": 1, "connection_mode": 0.5,
        }
        for f, w in weights.items():
            total += w
            val = getattr(self, f, None)
            if val:
                filled += w
        return round(filled / total, 2) if total else 0.0

    def set_field(self, name: str, value: Any) -> bool:
        """Set a field if it exists. Returns True on success."""
        if not hasattr(self, name):
            return False
        setattr(self, name, value)
        return True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "display_name": self.display_name,
            "about": self.about,
            "looking_for": self.looking_for,
            "can_help_with": self.can_help_with,
            "interests": self.interests,
            "goals": self.goals,
            "profession": self.profession,
            "company": self.company,
            "skills": self.skills,
            "location": self.location,
            "experience_level": self.experience_level,
            "passion_text": self.passion_text,
            "connection_mode": self.connection_mode,
            "photo_url": self.photo_url,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ProfileChecklist":
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        return cls(**{k: v for k, v in d.items() if k in valid_fields})

    def profile_summary_text(self) -> str:
        """Human-readable summary for the confirmation message (HTML-safe)."""
        lines = []
        e = html_escape  # shorthand

        if self.display_name:
            lines.append(f"👤 <b>{e(self.display_name)}</b>")

        if self.profession and self.company:
            lines.append(f"💼 {e(self.profession)} @ {e(self.company)}")
        elif self.profession:
            lines.append(f"💼 {e(self.profession)}")
        elif self.company:
            lines.append(f"💼 {e(self.company)}")

        if self.location:
            city = self.location.split(",")[0].strip()
            lines.append(f"📍 {e(city)}")

        if self.about:
            lines.append(f"\n📝 {e(self.about)}")

        if self.looking_for:
            lines.append(f"\n🔍 <b>Looking for:</b> {e(self.looking_for)}")

        if self.can_help_with:
            lines.append(f"💪 <b>Can help with:</b> {e(self.can_help_with)}")

        tags = []
        for i in (self.interests or [])[:5]:
            tags.append(f"#{e(i)}")
        for s in (self.skills or [])[:5]:
            tag = s.replace(" ", "_").lower()
            if f"#{tag}" not in tags:
                tags.append(f"#{e(tag)}")
        if tags:
            lines.append(f"\n🏷 {' '.join(tags[:8])}")

        if self.passion_text:
            lines.append(f"\n🔥 <b>Passion:</b> {e(self.passion_text)}")

        return "\n".join(lines)


@dataclass
class OnboardingAgentState:
    """Full conversation state, serialised into FSM data."""

    messages: List[Dict[str, str]] = field(default_factory=list)
    checklist: Dict[str, Any] = field(default_factory=dict)
    turn_count: int = 0
    phase: str = "collecting"  # collecting | confirming | complete
    event_code: Optional[str] = None
    event_name: Optional[str] = None
    lang: str = "en"
    first_name: Optional[str] = None

    def get_checklist(self) -> ProfileChecklist:
        return ProfileChecklist.from_dict(self.checklist)

    def set_checklist(self, cl: ProfileChecklist) -> None:
        self.checklist = cl.to_dict()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_messages": self.messages,
            "agent_checklist": self.checklist,
            "agent_turn_count": self.turn_count,
            "agent_phase": self.phase,
            "agent_event_code": self.event_code,
            "agent_event_name": self.event_name,
            "agent_lang": self.lang,
            "agent_first_name": self.first_name,
        }

    @classmethod
    def from_fsm_data(cls, data: Dict[str, Any]) -> "OnboardingAgentState":
        return cls(
            messages=data.get("agent_messages", []),
            checklist=data.get("agent_checklist", {}),
            turn_count=data.get("agent_turn_count", 0),
            phase=data.get("agent_phase", "collecting"),
            event_code=data.get("agent_event_code"),
            event_name=data.get("agent_event_name"),
            lang=data.get("agent_lang", "en"),
            first_name=data.get("agent_first_name"),
        )

    def trim_messages(self, max_turns: int = 20) -> None:
        """Keep only the last *max_turns* pairs to stay within context limits.
        Avoids breaking tool call groups (assistant+tool messages must stay together).
        """
        max_msgs = max_turns * 2
        if len(self.messages) <= max_msgs:
            return

        # Find a safe cut point — never split in the middle of a tool call group
        cut_target = len(self.messages) - max_msgs
        cut_at = cut_target

        # Walk forward from cut_target to find a safe boundary
        while cut_at < len(self.messages):
            msg = self.messages[cut_at]
            # Don't start on a tool result or an assistant message with tool_calls
            if msg.get("role") == "tool":
                cut_at += 1
            elif msg.get("role") == "assistant" and msg.get("tool_calls"):
                cut_at += 1
            else:
                break

        self.messages = self.messages[cut_at:]


@dataclass
class UIInstruction:
    """AI-chosen UI element to render alongside the text response."""
    ui_type: str = "none"  # "none" | "quick_replies" | "inline_choice"
    options: List[str] = field(default_factory=list)
    callback_prefix: str = "ai_choice"  # prefix for callback_data


@dataclass
class OrchestratorResponse:
    """What the orchestrator returns to the Telegram handler."""

    text: str
    show_profile: bool = False
    is_complete: bool = False
    keyboard_hint: Optional[str] = None  # "confirm" | "none" | None
    ui: Optional[UIInstruction] = None  # AI-chosen UI element
