# Sphere Bot — Progress Tracker

## Branch: community-v1 (@Matchd_bot)

### Session: Feb 28, 2026

**Completed:**

1. **Story Onboarding V4** (from previous session context)
   - 3-phase flow: Hook → Character → Mechanism → Match Card → Game → CTA
   - Per-intent stories with bold outcomes
   - Intent passthrough to agent onboarding
   - Name bug fix (callback.message.from_user = bot → use FSM data)

2. **Agent Prompt V2 — Matching-Aware**
   - Field priorities restructured around matching weights (40% value exchange, 35% topic, 25% goals)
   - Turn 2 targets can_help_with specifically
   - Quality gate: about + specific looking_for + substance in can_help_with/interests

3. **Agent Prompt V3 — Production Fixes (this session)**
   - Removed ban on "How can you help others?" (user says it's fine)
   - "open" intent no longer pre-fills looking_for with vague "Open to all kinds of connections"
   - Minimum 3 turns enforced (prompt + server-side guard in orchestrator_service)
   - Quality gate rejects vague looking_for ("open to anything", "connections")
   - "First match" framing: "What would you like your first match to be like?"
   - Removed ban on direct questions ("What's your profession?" is fine)

**Commits (this session):**
- Previous: `0c73f4d`, `de617c9`, `afa1606`, `ffaa4f8` (story V4 + prompt rewrites)
- Pending: prompt V3 fixes + min 3 turns guard

**TODO:**
- [ ] Full production prompt rewrite (~1200 tokens, few-shot examples, canonical structure)
- [ ] Test end-to-end on @Matchd_bot
- [ ] Push to community-v1 for deploy

---

### Session: Feb 21, 2026

**Completed:**

1. **Dashboard Analytics Full Upgrade** (`adapters/telegram/web/stats.py`)
   - Added Chart.js CDN + HTMX chart cleanup (auto-destroy before swap)
   - New helpers: `_parse_range()`, `_date_range_picker_html()`, `_chart_html()`, `_funnel_html()`
   - CSS: filter bars, funnel visualization, activity heatmap grid
   - **Overview**: date range picker, daily signups line chart, conversion funnel, profile depth doughnut
   - **Users**: multi-filter (city/intent/onboarding/photo/date range dropdowns with counts)
   - **Onboarding (NEW tab)**: FSM state funnel, mode distribution doughnut, avg duration, completeness histogram
   - **Matches**: stat cards, score distribution bar chart, matches-over-time line chart, top 10 users
   - **Conversations**: summary cards, message type doughnut, activity heatmap (7×24), content search toggle

2. **New Repository Methods** (`infrastructure/database/conversation_log_repository.py`)
   - `get_fsm_state_logs(limit)` — logs with FSM state for onboarding funnel
   - `get_message_stats(cutoff, limit)` — message metadata for conversation analytics

**Files modified:** `adapters/telegram/web/stats.py` (1402→2182 lines), `infrastructure/database/conversation_log_repository.py` (+30 lines)

**Commits:** pending

---

### Session: Feb 18, 2026

**Completed:**

1. **Full Conversation Logging System**
   - DB migration `014_conversation_logs.sql` (run + verified)
   - `ConversationLogRepository` with fire-and-forget logging
   - Incoming middleware (`ConversationLoggingMiddleware`) — captures all messages + callbacks
   - Outgoing logger (`outgoing_logger.py`) — wraps `Bot.__call__` to log all bot responses
   - `ContentTypeMiddleware` — injects `data["content_type"]` for all message handlers
   - Dashboard "Conversations" tab with chat bubble UI (blue=user, green=bot)
   - Search, pagination, date separators, FSM state hints

2. **AI-Driven UI (interact_with_user tool)**
   - Added `interact_with_user` tool to orchestrator (onboarding agent)
   - `UIInstruction` dataclass for passing AI UI decisions
   - `build_ai_keyboard()` in `keyboards/inline.py`
   - Callback handler `handle_ai_choice` in `onboarding_agent.py`

3. **Post-Onboarding Agent Chat**
   - `agent_chat.py` handler — full AI chat with tool use (gpt-4o-mini)
   - 4 tools: `edit_profile_field`, `navigate_to`, `interact_with_user`, `end_chat`
   - Text, voice, photo, sticker support
   - "Chat with Sphere" button in main menu
   - `AgentChatStates` FSM state

4. **Bug Fixes (7 items from Sonnet code review)**
   - `trim_messages()` safety guard — never wipe all history
   - Conversations tab user lookup filters by tg_ids (was loading ALL users)
   - Command exit from agent chat shows menu keyboard + i18n
   - `edit_profile_field` type validation (list vs string fields)
   - `asyncio.create_task` done callback for background embedding regen
   - `build_ai_keyboard` returns None on empty options
   - Orchestrator JSON parse catches TypeError
   - Conversations search "No results" vs "No conversations yet"
   - Pagination total_pages=0 when no messages

**Commits:**
- `7a591c8` — Add conversation logging, AI-driven UI, post-onboarding agent chat (20 files, +1464)
- `b85ec3d` — Fix 7 bugs from code review (5 files, +43/-22)

**Deployed:** Pushed to `feature/agent-onboarding` → Railway auto-deploy

---

### Session: Feb 19, 2026

**Completed:**

1. **Critical Bug Fixes — Agent Onboarding Silent Bot**
   - `orchestrator_service.py`: Added `tool_choice="none"` to follow-up API call (was returning empty text)
   - Skip follow-up when show_profile/is_complete (save latency)
   - Fallback text when LLM returns empty string
   - `onboarding_agent.py`: Added `parse_mode="HTML"` to profile preview
   - HTML-escape user content in profile summary
   - Always send a response (fallback if LLM returns nothing)
   - Fixed user_id fallback (was using first_name as ID)
   - `orchestrator_models.py`: Fixed `trim_messages` to not break tool call groups
   - Fixed `from_dict` to use dataclass fields

2. **View Matches / Sphere City Fixes**
   - Fixed `show_matches` passing `None` as state to `sphere_city_entry` (crash)
   - Fixed double `callback.answer()` in show_matches
   - Sphere City: random 10-150 available matches count (engagement)
   - Show "🔒 Unlock" instead of @username in match list
   - Profile edit: handle URL/link text instead of "No changes detected"

3. **SOTA Orchestrator Prompt (major rewrite)**
   - Researched Pi, Character.ai, Replika, leaked GPT-5/Claude/Grok prompts
   - Full personality-driven prompt — "friend at a party" not "service bot"
   - Zero topic restrictions (hookups, dating, anything)
   - Stealth data extraction through stories not forms
   - Mirror matching: adapts to user's energy, formality, style
   - Banned corporate speak
   - Conversational markers: "Hmm", "Got it", "Wait really?"
   - Progressive disclosure: warm up → depth → fill gaps

4. **10 Fake Warsaw Users**
   - Inserted via SQL: diverse profiles (designer, engineer, marketer, VC, lawyer, etc.)
   - No usernames (hidden for "Unlock" feature)

**Commits:**
- `5f0294e` — Fix agent onboarding silent bot + matches + Sphere City
- `bc23d3e` — Generic orchestrator prompt + Sphere City UI polish
- `b33ca10` — SOTA orchestrator prompt — personality-driven, zero restrictions

**Deployed:** Pushed to `feature/agent-onboarding` → Railway auto-deploy

---

### Pending / TODO

- [ ] "Unlock" button → Reward page (what happens on click?)
- [ ] Memory/RAG for agent chat (episodic memory — deferred by user)
- [ ] Adaptive persona switching post-onboarding (Big Five traits, communication profile)
- [ ] User's prompt collection — compare and merge with current SOTA prompt
- [ ] Test SOTA prompt end-to-end on @Matchd_bot
- [ ] Consider upgrading agent chat model (gpt-4o-mini → gpt-4o) if quality insufficient
