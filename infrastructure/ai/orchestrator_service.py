"""
OrchestratorService — The brain of the AI onboarding agent.

Uses OpenAI function calling to drive a natural onboarding conversation.
Rebuilds the system prompt each turn with the current profile checklist.
Executes tool calls (save_field, extract_from_text, show_profile_preview,
complete_onboarding) and returns an OrchestratorResponse to the handler.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from config.settings import settings
from core.prompts.audio_onboarding import AUDIO_EXTRACTION_PROMPT
from core.prompts.orchestrator_prompts import (
    ORCHESTRATOR_TOOLS,
    build_system_prompt,
)
from infrastructure.ai.orchestrator_models import (
    OnboardingAgentState,
    OrchestratorResponse,
    ProfileChecklist,
)

logger = logging.getLogger(__name__)

# Configurable model — change here to switch between gpt-4o / gpt-4o-mini
ORCHESTRATOR_MODEL = "gpt-4o"
MAX_HISTORY_TURNS = 20


class OrchestratorService:
    """Drives the onboarding conversation via OpenAI function calling."""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=30.0)
        self.model = ORCHESTRATOR_MODEL

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def process_turn(
        self,
        agent_state: OnboardingAgentState,
        user_message: str,
        message_type: str = "text",  # "text" | "voice" | "photo"
    ) -> OrchestratorResponse:
        """
        Process one turn of conversation.

        1. Build system prompt with current checklist
        2. Append user message to history
        3. Call OpenAI with function calling
        4. Execute any tool calls
        5. Return response text + flags
        """
        agent_state.turn_count += 1
        checklist = agent_state.get_checklist()

        # Auto-set display_name from Telegram first_name if not yet set
        if not checklist.display_name and agent_state.first_name:
            checklist.display_name = agent_state.first_name
            agent_state.set_checklist(checklist)

        # Prefix voice transcriptions
        if message_type == "voice":
            user_message = f"[Voice transcription] {user_message}"

        # Add user message to history
        agent_state.messages.append({"role": "user", "content": user_message})
        agent_state.trim_messages(MAX_HISTORY_TURNS)

        # Build system prompt
        system_prompt = build_system_prompt(
            checklist_dict=checklist.to_dict(),
            event_name=agent_state.event_name,
            lang=agent_state.lang,
            turn_count=agent_state.turn_count,
            first_name=agent_state.first_name,
        )

        # Build messages for API call
        messages = [{"role": "system", "content": system_prompt}] + agent_state.messages

        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=ORCHESTRATOR_TOOLS,
                tool_choice="auto",
                max_tokens=500,
                temperature=0.7,
            )

            choice = response.choices[0]
            assistant_msg = choice.message

            # Process tool calls if any
            tool_results = []
            show_profile = False
            is_complete = False
            keyboard_hint = None

            if assistant_msg.tool_calls:
                for tool_call in assistant_msg.tool_calls:
                    result = await self._execute_tool(
                        tool_call.function.name,
                        tool_call.function.arguments,
                        agent_state,
                    )
                    tool_results.append(result)

                    if result.get("action") == "show_profile":
                        show_profile = True
                        keyboard_hint = "confirm"
                    elif result.get("action") == "complete":
                        is_complete = True

                # Store assistant message with tool calls
                agent_state.messages.append({
                    "role": "assistant",
                    "content": assistant_msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                        }
                        for tc in assistant_msg.tool_calls
                    ],
                })

                # Add tool results
                for i, tool_call in enumerate(assistant_msg.tool_calls):
                    agent_state.messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": json.dumps(tool_results[i]),
                    })

                # Skip follow-up API call if we're showing profile or completing
                if show_profile or is_complete:
                    reply_text = assistant_msg.content or ""
                    if reply_text:
                        agent_state.messages.append({"role": "assistant", "content": reply_text})
                else:
                    # Get final response after tool execution
                    messages_after = [{"role": "system", "content": system_prompt}] + agent_state.messages
                    follow_up = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages_after,
                        tool_choice="none",
                        max_tokens=300,
                        temperature=0.7,
                    )
                    reply_text = follow_up.choices[0].message.content or ""

                    # Fallback if LLM returned empty text after tools
                    if not reply_text.strip():
                        checklist = agent_state.get_checklist()
                        missing = checklist.missing_required()
                        if missing:
                            reply_text = self._fallback_response(agent_state).text
                        else:
                            missing_imp = checklist.missing_important()
                            if missing_imp:
                                reply_text = self._fallback_response(agent_state).text
                            else:
                                reply_text = "Got it! Let me show you your profile." if agent_state.lang == "en" else "Отлично! Покажу твой профиль."
                                show_profile = True
                                keyboard_hint = "confirm"

                    agent_state.messages.append({"role": "assistant", "content": reply_text})

            else:
                # No tool calls — just a text response
                reply_text = assistant_msg.content or ""
                agent_state.messages.append({"role": "assistant", "content": reply_text})

            return OrchestratorResponse(
                text=reply_text,
                show_profile=show_profile,
                is_complete=is_complete,
                keyboard_hint=keyboard_hint,
            )

        except Exception as e:
            logger.error(f"Orchestrator LLM error: {e}", exc_info=True)
            return self._fallback_response(agent_state)

    # ------------------------------------------------------------------
    # Tool execution
    # ------------------------------------------------------------------

    async def _execute_tool(
        self,
        tool_name: str,
        arguments_json: str,
        agent_state: OnboardingAgentState,
    ) -> Dict[str, Any]:
        """Execute a single tool call and return the result dict."""
        try:
            args = json.loads(arguments_json)
        except json.JSONDecodeError:
            return {"error": "Invalid JSON arguments"}

        checklist = agent_state.get_checklist()

        if tool_name == "save_field":
            return self._tool_save_field(args, checklist, agent_state)

        elif tool_name == "extract_from_text":
            result = await self._tool_extract_from_text(args, checklist, agent_state)
            return result

        elif tool_name == "show_profile_preview":
            agent_state.phase = "confirming"
            agent_state.set_checklist(checklist)
            return {
                "action": "show_profile",
                "profile_summary": checklist.profile_summary_text(),
                "completeness": checklist.completeness_score(),
            }

        elif tool_name == "complete_onboarding":
            agent_state.phase = "complete"
            agent_state.set_checklist(checklist)
            return {"action": "complete", "status": "ok"}

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    def _tool_save_field(
        self,
        args: Dict[str, Any],
        checklist: ProfileChecklist,
        agent_state: OnboardingAgentState,
    ) -> Dict[str, Any]:
        """Save a single field to the checklist."""
        field_name = args.get("field_name", "")
        value = args.get("value")

        if not field_name or value is None:
            return {"error": "Missing field_name or value"}

        success = checklist.set_field(field_name, value)
        agent_state.set_checklist(checklist)

        if success:
            return {
                "saved": field_name,
                "value": value,
                "missing_required": checklist.missing_required(),
                "completeness": checklist.completeness_score(),
            }
        return {"error": f"Unknown field: {field_name}"}

    async def _tool_extract_from_text(
        self,
        args: Dict[str, Any],
        checklist: ProfileChecklist,
        agent_state: OnboardingAgentState,
    ) -> Dict[str, Any]:
        """Bulk extract fields from long text using the chain-of-thought extraction prompt."""
        text = args.get("text", "")
        if not text:
            return {"error": "No text provided"}

        try:
            prompt = AUDIO_EXTRACTION_PROMPT.format(
                transcription=text,
                event_name=agent_state.event_name or "networking event",
                language=agent_state.lang,
            )

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use mini for extraction (cheaper)
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1200,
                temperature=0.1,
            )

            raw = response.choices[0].message.content or ""

            # Parse JSON from chain-of-thought response
            extracted = self._parse_extraction_json(raw)
            if not extracted:
                return {"error": "Could not parse extraction result", "raw": raw[:200]}

            # Merge extracted data into checklist
            fields_updated = []
            field_mapping = {
                "display_name": "display_name",
                "about": "about",
                "looking_for": "looking_for",
                "can_help_with": "can_help_with",
                "interests": "interests",
                "goals": "goals",
                "profession": "profession",
                "company": "company",
                "skills": "skills",
                "location": "location",
                "experience_level": "experience_level",
            }

            for ext_key, cl_key in field_mapping.items():
                val = extracted.get(ext_key)
                if val and val not in ["", "N/A", "null", "None"]:
                    # Don't overwrite existing values with worse ones
                    existing = getattr(checklist, cl_key, None)
                    if not existing or (isinstance(val, str) and len(val) > len(str(existing or ""))):
                        checklist.set_field(cl_key, val)
                        fields_updated.append(cl_key)
                    elif isinstance(val, list) and val:
                        checklist.set_field(cl_key, val)
                        fields_updated.append(cl_key)

            agent_state.set_checklist(checklist)

            return {
                "fields_updated": fields_updated,
                "missing_required": checklist.missing_required(),
                "completeness": checklist.completeness_score(),
            }

        except Exception as e:
            logger.error(f"extract_from_text failed: {e}", exc_info=True)
            # Fallback: store as about
            if not checklist.about:
                checklist.set_field("about", text[:500])
                agent_state.set_checklist(checklist)
            return {"error": str(e), "fallback": "Stored as about"}

    def _parse_extraction_json(self, raw: str) -> Optional[Dict[str, Any]]:
        """Parse JSON from a chain-of-thought extraction response."""
        json_text = raw

        if "## JSON:" in raw:
            json_text = raw.split("## JSON:")[-1]
        elif "```json" in raw:
            json_text = raw.split("```json")[-1].split("```")[0]
        elif "{" in raw:
            start = raw.rfind("{")
            end = raw.rfind("}") + 1
            if start != -1 and end > start:
                json_text = raw[start:end]

        json_text = re.sub(r"```json\s*", "", json_text)
        json_text = re.sub(r"```\s*", "", json_text)
        json_text = json_text.strip()

        try:
            return json.loads(json_text)
        except json.JSONDecodeError:
            logger.warning(f"Failed to parse extraction JSON: {json_text[:200]}")
            return None

    # ------------------------------------------------------------------
    # Fallback when LLM fails
    # ------------------------------------------------------------------

    def _fallback_response(self, agent_state: OnboardingAgentState) -> OrchestratorResponse:
        """Static fallback question for the next missing required field."""
        checklist = agent_state.get_checklist()
        missing = checklist.missing_required()
        lang = agent_state.lang

        if not missing:
            missing = checklist.missing_important()

        if not missing:
            # All fields collected — show profile
            return OrchestratorResponse(
                text="",
                show_profile=True,
                keyboard_hint="confirm",
            )

        next_field = missing[0]
        questions = {
            "en": {
                "display_name": "What's your name? 👋",
                "about": "Tell me a bit about yourself — what do you do? 🙋",
                "looking_for": "What kind of people or connections are you looking for? 🔍",
                "can_help_with": "How can you help others? What's your expertise? 💡",
                "interests": "What are your main interests? (tech, business, art, etc.) 🏷",
            },
            "ru": {
                "display_name": "Как тебя зовут? 👋",
                "about": "Расскажи немного о себе — чем занимаешься? 🙋",
                "looking_for": "Каких людей или знакомств ты ищешь? 🔍",
                "can_help_with": "Чем ты можешь помочь другим? В чём твоя экспертиза? 💡",
                "interests": "Какие у тебя основные интересы? (tech, бизнес, art, etc.) 🏷",
            },
        }

        lang_questions = questions.get(lang, questions["en"])
        text = lang_questions.get(next_field, lang_questions.get("about", "Tell me about yourself!"))

        # Store in history so context is maintained
        agent_state.messages.append({"role": "assistant", "content": text})

        return OrchestratorResponse(text=text)
