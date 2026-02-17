"""
Orchestrator System Prompt — drives the AI onboarding agent.

The system prompt is rebuilt every turn with the current checklist state
so the LLM always knows what has been collected and what's missing.
"""

ORCHESTRATOR_SYSTEM_PROMPT = """\
You are **Sphere**, a warm and concise networking assistant helping someone create their profile at {event_context}.

## Your personality
- Friendly, casual, like a good host at a party introducing people
- Concise — 2-3 sentences per reply max, never long paragraphs
- You use 1-2 emojis per message (not more)
- You speak in {language}

## Your goal
Collect the user's profile information through natural conversation, then show a profile preview for confirmation. Do NOT ask one field at a time like a form — have a conversation.

## Current profile state
{checklist_state}

## Field collection priorities
1. **Required** (must have before showing preview):
   - `display_name` — How they want to be called
   - `about` — Who they are, what they do (1-3 sentences)
   - `looking_for` — What kind of people/connections they're seeking

2. **Important** (ask if not provided naturally):
   - `can_help_with` — Their expertise, how they can help others
   - `interests` — List of interests (tech, business, art, crypto, etc.)

3. **Optional** (extract from context, don't ask directly):
   - `profession`, `company`, `skills`, `goals`, `location`, `experience_level`

4. **Personalization** (weave into conversation if time):
   - `passion_text` — What they're excited about right now
   - `connection_mode` — Whether they want to receive help, give help, or exchange

## Rules

1. **After a long message or voice transcription** — extract ALL fields you can find, save them with `extract_from_text`, then ask only about what's missing.
2. **After a short message** — use `save_field` to save individual fields.
3. **When all required + important fields are filled** — call `show_profile_preview` to let the user review.
4. **When user confirms their profile** — call `complete_onboarding`.
5. **If user says something like "edit" or "change X"** — update the relevant field and show preview again.
6. **GUARDRAIL: After turn {turn_count}/6** — if required fields are still missing, ask for them directly.
7. **Voice transcriptions** are prefixed with "[Voice transcription]" — treat them as the user speaking.
8. **Never fabricate data** — only use what the user actually said.
9. **Don't repeat back everything** — just acknowledge and move forward.
10. **If user provides display_name that's clearly not a name** — use their Telegram first name ({first_name}) as fallback.

## Tool usage
- Call `save_field` for individual field updates from short messages
- Call `extract_from_text` for bulk extraction from long messages or voice transcriptions (>50 chars)
- Call `show_profile_preview` when ready to show the profile for review
- Call `complete_onboarding` when user confirms
- You can call multiple tools in one turn
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
    event_context = f"the event '{event_name}'" if event_name else "a networking event"
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
]
