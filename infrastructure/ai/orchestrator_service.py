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
    PROFILE_SYNTHESIS_PROMPT,
    build_system_prompt,
)
from infrastructure.ai.orchestrator_models import (
    OnboardingAgentState,
    OrchestratorResponse,
    ProfileChecklist,
    UIInstruction,
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
            community_name=agent_state.community_name,
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
            ui_instruction: Optional[UIInstruction] = None

            if assistant_msg.tool_calls:
                # IMPORTANT: Only execute ONE category of tools per turn.
                # If LLM calls extract_from_text + show_profile_preview together,
                # we execute extraction but SKIP show_profile — force another turn.
                did_extraction = False

                for tool_call in assistant_msg.tool_calls:
                    tool_name = tool_call.function.name

                    # Block show_profile if extraction happened in the SAME turn
                    if tool_name == "show_profile_preview" and did_extraction:
                        logger.info("Blocked show_profile_preview — extraction was in same turn. Forcing next question.")
                        tool_results.append({
                            "action": "blocked",
                            "reason": "You just extracted data. You MUST ask the next step question before showing profile. Do NOT call show_profile_preview in the same turn as extract_from_text.",
                        })
                        continue

                    result = await self._execute_tool(
                        tool_name,
                        tool_call.function.arguments,
                        agent_state,
                    )
                    tool_results.append(result)

                    if tool_name in ("extract_from_text", "save_field"):
                        did_extraction = True

                    if result.get("action") == "show_profile":
                        show_profile = True
                        keyboard_hint = "confirm"
                    elif result.get("action") == "complete":
                        is_complete = True
                    elif result.get("action") == "interact":
                        ui_type = result.get("ui_type", "none")
                        options = result.get("options", [])
                        if ui_type != "none" and options:
                            ui_instruction = UIInstruction(
                                ui_type=ui_type,
                                options=options[:6],
                            )

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

                # Skip follow-up API call if we're showing profile, completing, or interact_with_user
                if show_profile or is_complete or ui_instruction:
                    # For interact_with_user, prefer the tool's message_text
                    if ui_instruction:
                        for tc in assistant_msg.tool_calls:
                            if tc.function.name == "interact_with_user":
                                try:
                                    iargs = json.loads(tc.function.arguments)
                                    reply_text = iargs.get("message_text", assistant_msg.content or "")
                                except Exception:
                                    reply_text = assistant_msg.content or ""
                                break
                        else:
                            reply_text = assistant_msg.content or ""
                    else:
                        reply_text = assistant_msg.content or ""
                    if reply_text:
                        agent_state.messages.append({"role": "assistant", "content": reply_text})
                else:
                    # Get follow-up response after tool execution
                    messages_after = [{"role": "system", "content": system_prompt}] + agent_state.messages
                    follow_up = await self.client.chat.completions.create(
                        model=self.model,
                        messages=messages_after,
                        tool_choice="none",
                        max_tokens=300,
                        temperature=0.7,
                    )
                    reply_text = follow_up.choices[0].message.content or ""

                    # Fallback if LLM returned empty text — NEVER auto-show profile here
                    if not reply_text.strip():
                        reply_text = self._fallback_next_question(agent_state)

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
                ui=ui_instruction,
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
        except (json.JSONDecodeError, TypeError):
            return {"error": "Invalid JSON arguments"}

        checklist = agent_state.get_checklist()

        if tool_name == "save_field":
            return self._tool_save_field(args, checklist, agent_state)

        elif tool_name == "extract_from_text":
            result = await self._tool_extract_from_text(args, checklist, agent_state)
            return result

        elif tool_name == "show_profile_preview":
            # Hard guard: count REAL user messages — exclude greeting and button clicks
            real_user_msgs = 0
            for m in agent_state.messages:
                if m.get("role") != "user":
                    continue
                content = m.get("content", "")
                # Skip synthetic messages: greeting prompt + button callbacks
                if content.startswith("Hi, I'm ") and "Ask me about myself" in content:
                    continue
                if content.startswith("User selected:"):
                    continue
                real_user_msgs += 1
            if real_user_msgs < 3:
                logger.info(f"Blocked early show_profile: only {real_user_msgs} real user messages (need 3+)")
                return {
                    "action": "blocked",
                    "reason": f"Too early — only {real_user_msgs} real user messages (need 3). You MUST complete all 3 steps: Step 1 = about themselves, Step 2 = what they can help with, Step 3 = who they want to meet. Ask the next step question.",
                }

            # Check mandatory fields — all 3 steps must be done
            missing_steps = []
            if not checklist.about and not checklist.profession:
                missing_steps.append("Step 1 (about themselves)")
            if not checklist.can_help_with:
                missing_steps.append("Step 2 (what they can help with)")
            if not checklist.looking_for or self._is_placeholder(checklist.looking_for):
                missing_steps.append("Step 3 (who they want to meet)")

            if missing_steps:
                logger.info(f"Blocked show_profile: missing steps: {missing_steps} (real_user_msgs={real_user_msgs})")
                return {
                    "action": "blocked",
                    "reason": f"Profile incomplete — missing: {', '.join(missing_steps)}. Ask the user about these. Don't show profile until ALL 3 steps are done.",
                }

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

        elif tool_name == "interact_with_user":
            return {
                "action": "interact",
                "ui_type": args.get("ui_type", "none"),
                "options": args.get("options", []),
            }

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    _PLACEHOLDER_VALUES = {
        "", "null", "none", "n/a", "not mentioned", "not specified",
        "unknown", "not provided", "unspecified", "no data",
    }

    def _is_placeholder(self, val: Any) -> bool:
        """Check if a value is a placeholder that should be treated as empty."""
        if val is None:
            return True
        if isinstance(val, str):
            cleaned = val.strip().lower()
            return cleaned in self._PLACEHOLDER_VALUES or cleaned.startswith("not ")
        if isinstance(val, list) and not val:
            return True
        return False

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

        if self._is_placeholder(value):
            return {"error": f"Value is a placeholder — skip saving empty/unknown fields"}

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

    # Fields extraction is allowed to fill from user text.
    # IMPORTANT: looking_for and can_help_with should only be extracted
    # if the user EXPLICITLY stated them. Short inputs can't produce these.
    _SHORT_TEXT_SAFE_FIELDS = {
        "display_name", "profession", "company", "location",
        "experience_level", "matching_scope", "meeting_preference",
    }
    _LONG_TEXT_FIELDS = {
        "about", "looking_for", "can_help_with", "interests",
        "goals", "skills",
    }

    async def _tool_extract_from_text(
        self,
        args: Dict[str, Any],
        checklist: ProfileChecklist,
        agent_state: OnboardingAgentState,
    ) -> Dict[str, Any]:
        """Bulk extract fields from text using the extraction prompt.

        IMPORTANT: For short inputs (<50 chars), only extract basic facts
        (profession, company, location). Never fabricate looking_for, can_help_with,
        or about from a 2-word answer.
        """
        text = args.get("text", "")
        if not text:
            return {"error": "No text provided"}

        is_short = len(text.strip()) < 50  # "AI startups" = 12 chars = short

        try:
            prompt = AUDIO_EXTRACTION_PROMPT.format(
                transcription=text,
                event_name=agent_state.event_name or "networking event",
                language=agent_state.lang,
            )

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1200,
                temperature=0.1,
            )

            raw = response.choices[0].message.content or ""

            extracted = self._parse_extraction_json(raw)
            if not extracted:
                return {"error": "Could not parse extraction result", "raw": raw[:200]}

            # Merge extracted data into checklist
            fields_updated = []
            all_fields = self._SHORT_TEXT_SAFE_FIELDS | self._LONG_TEXT_FIELDS

            for ext_key in all_fields:
                val = extracted.get(ext_key)
                if not val or self._is_placeholder(val):
                    continue

                # For SHORT inputs, skip fields that require rich user expression
                # The LLM fabricates looking_for, can_help_with, about from 2 words
                if is_short and ext_key in self._LONG_TEXT_FIELDS:
                    # Exception: allow interests as list of keywords from short text
                    if ext_key == "interests" and isinstance(val, list):
                        pass  # allow
                    else:
                        logger.info(f"Skipping '{ext_key}' extraction from short text ({len(text)} chars)")
                        continue

                # Don't overwrite existing values with worse ones
                existing = getattr(checklist, ext_key, None)
                if not existing or (isinstance(val, str) and len(val) > len(str(existing or ""))):
                    checklist.set_field(ext_key, val)
                    fields_updated.append(ext_key)
                elif isinstance(val, list) and val:
                    checklist.set_field(ext_key, val)
                    fields_updated.append(ext_key)

            agent_state.set_checklist(checklist)

            return {
                "fields_updated": fields_updated,
                "missing_required": checklist.missing_required(),
                "completeness": checklist.completeness_score(),
                "note": f"Short text ({len(text)} chars) — only extracted safe fields" if is_short else None,
            }

        except Exception as e:
            logger.error(f"extract_from_text failed: {e}", exc_info=True)
            if not checklist.about and len(text) > 30:
                checklist.set_field("about", text[:500])
                agent_state.set_checklist(checklist)
            return {"error": str(e), "fallback": "Stored as about" if len(text) > 30 else "Text too short"}

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
    # Fallback when LLM fails — NEVER auto-shows profile
    # ------------------------------------------------------------------

    def _fallback_next_question(self, agent_state: OnboardingAgentState) -> str:
        """Return the next step question based on what's missing. NEVER returns show_profile."""
        checklist = agent_state.get_checklist()
        lang = agent_state.lang

        # Determine which step we're on based on what's filled
        has_about = bool(checklist.about or checklist.profession)
        has_help = bool(checklist.can_help_with)
        has_looking = bool(checklist.looking_for) and not self._is_placeholder(checklist.looking_for)

        if not has_about:
            return (
                "So what's your deal — what do you do?" if lang == "en"
                else "Расскажи, чем занимаешься?"
            )
        elif not has_help:
            return (
                "What do people usually come to you for? What's your expertise?" if lang == "en"
                else "За чем к тебе обычно обращаются? В чём твоя экспертиза?"
            )
        elif not has_looking:
            return (
                "Now the fun part — who would you like to meet first?" if lang == "en"
                else "А теперь самое интересное — кого хочешь встретить первым?"
            )
        else:
            # All 3 steps done — ask if ready to see profile (but don't auto-show)
            return (
                "I think I've got a good picture. Want to see your profile?" if lang == "en"
                else "Думаю, у меня хорошая картина. Показать профиль?"
            )

    def _fallback_response(self, agent_state: OnboardingAgentState) -> OrchestratorResponse:
        """Full fallback response for exception handler. NEVER auto-shows profile."""
        text = self._fallback_next_question(agent_state)
        return OrchestratorResponse(text=text)

    # ------------------------------------------------------------------
    # Profile synthesis — separate step after conversation ends
    # ------------------------------------------------------------------

    async def synthesize_profile(
        self,
        agent_state: OnboardingAgentState,
    ) -> Dict[str, Any]:
        """
        Take the full conversation + raw checklist and produce a polished profile.
        Called ONCE when show_profile_preview is triggered.
        Returns synthesized profile dict (or raw checklist on failure).
        """
        checklist = agent_state.get_checklist()

        # Build conversation string from history
        conversation_lines = []
        for msg in agent_state.messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "user":
                conversation_lines.append(f"User: {content}")
            elif role == "assistant" and content:
                conversation_lines.append(f"Sphere: {content}")
            # Skip tool messages
        conversation = "\n".join(conversation_lines)

        # Raw data from checklist
        raw_data = json.dumps(checklist.to_dict(), ensure_ascii=False, indent=2)

        prompt = PROFILE_SYNTHESIS_PROMPT.format(
            conversation=conversation,
            raw_data=raw_data,
        )

        try:
            response = await self.client.chat.completions.create(
                model=self.model,  # GPT-4o for quality
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1000,
                temperature=0.3,
            )

            raw = response.choices[0].message.content or ""
            parsed = self._parse_extraction_json(raw)

            if parsed:
                logger.info(f"Profile synthesis successful: {list(parsed.keys())}")
                return parsed
            else:
                logger.warning("Profile synthesis returned unparseable JSON, using raw checklist")
                return checklist.to_dict()

        except Exception as e:
            logger.error(f"Profile synthesis failed: {e}", exc_info=True)
            return checklist.to_dict()
