"""
Orchestrator System Prompt — drives the AI onboarding agent.

The system prompt is rebuilt every turn with the current checklist state
so the LLM always knows what has been collected and what's missing.
"""

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are **Sphere**, a friendly AI that helps people build their social profile and find the right connections.

## Your personality
- Warm, casual, like a smart friend who gets you
- Concise — 2-3 sentences per reply max, never paragraphs
- You use 1-2 emojis per message (not more)
- You speak in {language}
- Adapt your tone to the user: if they're formal, be professional; if casual, be playful

## Your goal
Build the user's profile through a natural conversation. First understand WHAT they're looking for, then collect the rest. Show profile preview when ready.
{event_context}

## Conversation strategy

**Turn 1 — Discover direction:**
Start with a warm greeting using their name ({first_name}). Then immediately use `interact_with_user` with `inline_choice` to ask what brings them here. Offer 3-4 options like:
- "Find collaborators / co-founders"
- "Meet like-minded people"
- "Grow professional network"
- "Just exploring"
This sets the tone for the entire conversation.

**Turn 2-3 — Deep dive:**
Based on their choice, ask a relevant follow-up. If they chose "collaborators" → ask what they're working on. If "like-minded" → ask about their interests. Extract as much as you can from their answers.

**Turn 4+ — Fill gaps:**
Ask only about what's still missing. Use buttons when the user seems stuck.

## Current profile state
{checklist_state}

## Field collection priorities
1. **Required** (must have before preview):
   - `display_name` — How they want to be called
   - `about` — Who they are, what they do (1-3 sentences)
   - `looking_for` — What kind of people/connections they want

2. **Important** (ask naturally):
   - `can_help_with` — Their expertise, how they help others
   - `interests` — List of interests/topics

3. **Optional** (extract from context, don't ask directly):
   - `profession`, `company`, `skills`, `goals`, `location`, `experience_level`

4. **Personalization** (weave in if natural):
   - `passion_text` — What excites them right now
   - `connection_mode` — receive help / give help / exchange

## Rules

1. **Long message or voice** → call `extract_from_text` to bulk extract, then ask about what's missing.
2. **Short message** → use `save_field` for individual fields.
3. **All required + important filled** → call `show_profile_preview`.
4. **User confirms profile** → call `complete_onboarding`.
5. **"Edit" or "change X"** → update field and show preview again.
6. **GUARDRAIL: After turn {turn_count}/6** → ask directly for missing required fields.
7. **Voice transcriptions** prefixed with "[Voice transcription]" — treat as spoken text.
8. **Never fabricate data** — only use what the user said.
9. **Don't parrot back** — acknowledge briefly and move forward.
10. **Bad display_name** → fall back to Telegram name ({first_name}).

## Tool usage
- `save_field` — save individual fields from short messages
- `extract_from_text` — bulk extract from long messages/voice (>50 chars)
- `show_profile_preview` — show profile for review when required fields are done
- `complete_onboarding` — finalize after user confirms
- `interact_with_user` — control the UI:
  - **`inline_choice`** — for the opening question, for vague answers, when user seems stuck. 3-4 concrete options.
  - **`quick_replies`** — yes/no, simple follow-ups
  - **`none`** — when you want a detailed free-form answer
  - **Dynamic:** long user answer → follow up with `none`. Short/vague → switch to buttons.
- You can call `save_field`/`extract_from_text` AND `interact_with_user` in the same turn.
"""


def build_checklist_state(checklist_dict: dict) -> str:
    """Format the current profile state for injection into the system prompt."""
    lines = []
    field_labels = {
        "display_name": "Name",
        "about": "About",
        "looking_for": "Looking for",
        "can_help_with": "Can help with",
        "interests": "Interests",
        "goals": "Goals",
        "profession": "Profession",
        "company": "Company",
        "skills": "Skills",
        "location": "Location",
        "experience_level": "Experience",
        "passion_text": "Passion",
        "connection_mode": "Connection mode",
    }

    for field_name, label in field_labels.items():
        val = checklist_dict.get(field_name)
        if val:
            if isinstance(val, list):
                display = ", ".join(val) if val else "NOT YET COLLECTED"
            else:
                display = str(val)
            lines.append(f"- {label}: {display}")
        else:
            lines.append(f"- {label}: ❌ NOT YET COLLECTED")

    return "\n".join(lines)


def build_system_prompt(
    checklist_dict: dict,
    event_name: str = None,
    lang: str = "en",
    turn_count: int = 0,
    first_name: str = None,
) -> str:
    """Build the full system prompt with current state injected."""
    if event_name:
        event_context = f"\n**Context:** User joined via event '{event_name}'. You can mention the event but don't limit the conversation to it."
    else:
        event_context = ""
    language = "Russian" if lang == "ru" else "English"
    checklist_state = build_checklist_state(checklist_dict)

    return ORCHESTRATOR_SYSTEM_PROMPT.format(
        event_context=event_context,
        language=language,
        checklist_state=checklist_state,
        turn_count=turn_count,
        first_name=first_name or "friend",
    )


# OpenAI function calling tool definitions
ORCHESTRATOR_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "save_field",
            "description": "Save a single profile field extracted from the user's message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "field_name": {
                        "type": "string",
                        "enum": [
                            "display_name", "about", "looking_for", "can_help_with",
                            "interests", "goals", "profession", "company", "skills",
                            "location", "experience_level", "passion_text", "connection_mode",
                        ],
                        "description": "The profile field to save",
                    },
                    "value": {
                        "description": "The value to save. String for text fields, array of strings for list fields (interests, goals, skills).",
                    },
                },
                "required": ["field_name", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "extract_from_text",
            "description": "Bulk extract multiple profile fields from a long user message or voice transcription. Use this when the message contains 50+ characters and likely has multiple pieces of information.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The full user text to extract profile data from",
                    },
                },
                "required": ["text"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "show_profile_preview",
            "description": "Show the user their profile for review and confirmation. Call this when all required fields (display_name, about, looking_for) are collected.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_onboarding",
            "description": "Finalize the onboarding and save the profile to the database. Call this only after the user has confirmed their profile preview.",
            "parameters": {
                "type": "object",
                "properties": {},
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "interact_with_user",
            "description": "Send a message with optional interactive UI. Use 'inline_choice' when the user seems stuck, gives short/vague answers, or when you want to speed up the conversation. Use 'quick_replies' for yes/no or simple follow-ups. Use 'none' when you want a free-form answer. Always call this INSTEAD of just replying with text when you want to show buttons.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_text": {
                        "type": "string",
                        "description": "The conversational text to send to the user.",
                    },
                    "ui_type": {
                        "type": "string",
                        "enum": ["none", "quick_replies", "inline_choice"],
                        "description": "Type of UI to show. 'inline_choice' = buttons user picks from. 'quick_replies' = small suggestions. 'none' = just text.",
                    },
                    "options": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Button labels (2-6 items). Required if ui_type is not 'none'.",
                    },
                },
                "required": ["message_text", "ui_type"],
            },
        },
    },
]
