"""
Agent Chat Prompts — drives the post-onboarding AI assistant.

The agent can show profile, edit fields, trigger matching,
navigate to features, and have natural conversation — all through tool use.
"""

AGENT_CHAT_SYSTEM_PROMPT = """\
You are **Sphere**, a friendly AI assistant inside a Telegram networking bot.
The user has already completed onboarding and has a profile. You help them navigate the app, improve their profile, and find connections.

## Your personality
- Warm, concise, helpful — like a smart friend who knows the app inside out
- 1-2 sentences per reply, never long paragraphs
- 1-2 emojis per message (not more)
- Speak in {language}

## Current user profile
{profile_state}

## What you can do
1. **Answer questions** about the app, features, how matching works
2. **Edit profile fields** when user asks to change something
3. **Navigate** the user to app features (matches, profile, events, city matching)
4. **Have casual conversation** — but always steer back to networking value

## Rules
1. If the user asks to change/update/add something → use `edit_profile_field`
2. If user wants to see matches/profile/events → use `navigate_to` (it will open that screen)
3. If user is just chatting → respond naturally, but suggest something useful after 2-3 exchanges
4. Use `interact_with_user` to offer buttons when appropriate (especially for navigation)
5. Never fabricate data. Only reference what's in the profile.
6. If you don't know something about the app → say so honestly
7. Keep it SHORT. This is Telegram, not email.
"""


def build_agent_chat_prompt(profile_dict: dict, lang: str = "en") -> str:
    """Build system prompt with current profile state."""
    language = "Russian" if lang == "ru" else "English"

    profile_lines = []
    field_labels = {
        "display_name": "Name", "bio": "Bio", "looking_for": "Looking for",
        "can_help_with": "Can help with", "interests": "Interests",
        "goals": "Goals", "profession": "Profession", "company": "Company",
        "skills": "Skills", "city_current": "City",
        "experience_level": "Experience", "passion_text": "Passion",
    }

    for key, label in field_labels.items():
        val = profile_dict.get(key)
        if val:
            if isinstance(val, list):
                val = ", ".join(str(v) for v in val)
            profile_lines.append(f"- {label}: {val}")
        else:
            profile_lines.append(f"- {label}: (empty)")

    profile_state = "\n".join(profile_lines)

    return AGENT_CHAT_SYSTEM_PROMPT.format(
        language=language,
        profile_state=profile_state,
    )


AGENT_CHAT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "edit_profile_field",
            "description": "Update a user's profile field. Use when user asks to change, add, or remove something from their profile.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "enum": [
                            "display_name", "bio", "looking_for", "can_help_with",
                            "interests", "goals", "profession", "company", "skills",
                            "city_current", "experience_level",
                        ],
                        "description": "The profile field to update",
                    },
                    "value": {
                        "description": "New value. String for text fields, array of strings for list fields.",
                    },
                },
                "required": ["field_name", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate_to",
            "description": "Navigate user to an app screen. Use when user wants to see their profile, matches, events, etc.",
            "parameters": {
                "type": "object",
                "properties": {
                    "screen": {
                        "type": "string",
                        "enum": ["profile", "matches", "events", "sphere_city", "vibe_check", "menu"],
                        "description": "Which screen to open",
                    },
                },
                "required": ["screen"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "interact_with_user",
            "description": "Send a message with optional interactive buttons. Use 'inline_choice' for navigation or multiple options. Use 'quick_replies' for yes/no.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_text": {
                        "type": "string",
                        "description": "The text to send",
                    },
                    "ui_type": {
                        "type": "string",
                        "enum": ["none", "quick_replies", "inline_choice"],
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Button labels (2-6 items)",
                    },
                },
                "required": ["message_text", "ui_type"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "end_chat",
            "description": "End the AI chat session and return to the main menu. Use when user says 'menu', 'back', 'done', 'exit', etc.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
]
