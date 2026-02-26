# Decisions

## 2026-02-24 — Enable Events on Global Mode Branch
**Context:** User wants to run CORAD event on @Matchd_bot (global-mode-v1 branch). Events were disabled by default.
**Decision:** Changed `EVENTS_ENABLED` default to `true` in `config/features.py` and set Railway env var.
**Rationale:** Global mode and events are not mutually exclusive. Events add a scoped context on top of global matching.

## 2026-02-24 — Programmatic QR Generation
**Context:** QR codes were previously generated manually and committed as static PNGs. `qrcode[pil]` was in requirements but unused.
**Decision:** Created `core/utils/qr_generator.py` — generates labeled QR PNGs at runtime. Integrated into `/quickevent` and `/create_event`.
**Rationale:** Manual QR generation doesn't scale. Admin should get QR instantly when creating an event.

## 2026-02-24 — Git Memory Format (.memory/)
**Context:** Session context was lost between Claude conversations. `progress.md` existed but had no enforced structure.
**Decision:** Created `.memory/` directory with structured format: `status.md` (current state), `decisions.md` (append-only log), `sessions/YYYY-MM-DD.md` (changelogs).
**Rationale:** Git-tracked memory persists across branches, sessions, and machines. Structured format ensures consistency.

## 2026-02-24 — /quickevent One-Step Command
**Context:** Creating events required a 3-step FSM flow (/create_event → name → description → location). QR had to be made separately.
**Decision:** Added `/quickevent <name>` — single message creates event with derived code, generates QR, and sends both.
**Rationale:** Fastest possible event creation for live situations. Full FSM still available via `/create_event`.

## 2026-02-25 — Same DB for All Modes
**Context:** Community mode needs new tables (communities, community_members, etc.). Could use separate DB or shared.
**Decision:** Share the same Supabase DB across all modes/branches. New tables prefixed with purpose.
**Rationale:** No cross-DB joins needed, simpler infra, Supabase free tier limits. Users are the same across modes.

## 2026-02-25 — Branch from global-mode-v1 (not main)
**Context:** Community-v1 needs all global mode features as foundation.
**Decision:** Branch `community-v1` from `global-mode-v1`, not `main`. Main stays as archive.
**Rationale:** global-mode-v1 has agent onboarding, vector matching, expansion flow — all needed for community mode.

## 2026-02-25 — One Bot, Multiple Modes
**Context:** Could have separate bots per mode or one bot handling all.
**Decision:** Single bot (@Matchd_bot) handles community + event + global modes. Mode determined by entry context.
**Rationale:** Users shouldn't manage multiple bots. Deep link prefix determines context.

## 2026-02-25 — Games Drive DM Traffic via Deep Links
**Context:** Bot can't initiate DMs (Telegram API limitation). Need to get group users into DM.
**Decision:** In-group games (Mystery Profile, This or That, etc.) post results with deep link buttons to DM.
**Rationale:** Only way to reach users in DM. Games provide value AND drive onboarding.

## 2026-02-25 — Monetization: Free Community, Paid Cross-Community
**Context:** Need revenue model for community matching.
**Decision:** Free matching within community. 1 free cross-community match, then $3/match or $10/mo Pro.
**Rationale:** Free community matching drives adoption. Cross-community is premium value.

## 2026-02-25 — Git Commits as Primary Long-Term Memory
**Context:** `.memory/` files provide structured overview but lack detail.
**Decision:** Write commit messages as self-contained memory units (WHY, context, gotchas). `.memory/` is the index, commits are the detail.
**Rationale:** `git log --grep` makes commits searchable. No duplication between memory and commits.

## 2026-02-25 — Events as Separate Future Branch
**Context:** Offline events have different flow from community mode.
**Decision:** Plan `events-v2` as separate branch, not part of community-v1.
**Rationale:** Different UX (QR scan → quick onboard → event-scoped matching). Mixing concerns would slow both.

## 2026-02-25 — Three Worktrees by Purpose
**Context:** Had messy worktree setup (v1.1, unnamed).
**Decision:** Three clear worktrees: `sphere-bot/` (main/archive), `worktrees/sphere-community/` (community-v1), `worktrees/sphere-global/` (global-mode-v1).
**Rationale:** Each worktree = one product line. Clear naming prevents mistakes.

## 2026-02-26 — Observation Queue Uses deque(maxlen=1000)
**Context:** community_group.py used list with pop(0) for observation queue, which is O(N).
**Decision:** Switched to `collections.deque(maxlen=1000)` for O(1) eviction and bounded size.
**Rationale:** Hot path (every group message) needs to be fast. deque handles both.

## 2026-02-26 — Scheduler Skips Sphere Global Sentinel
**Context:** Sphere Global has telegram_group_id=-1. Scheduler iterated all communities including this virtual one, firing Bot API calls with invalid -1 group ID.
**Decision:** Skip communities with `telegram_group_id == -1` in scheduler tick and auto_associate_user.
**Rationale:** Virtual communities should never trigger real TG API calls.

## 2026-02-26 — First-Run Guard for New Communities
**Context:** New communities with no `last_game_at` or `last_pulse_at` timestamps would immediately trigger games/pulse on first tick.
**Decision:** On first tick for a community, initialize timestamps to "now" and return. Games/pulse start after the configured interval.
**Rationale:** Prevents immediate LLM calls on community creation. Games should start after enough members join.

## 2026-02-26 — Code Review as Standard Practice
**Context:** 26 issues found by 3 parallel review agents across Phase 2+3 code. 11 were critical runtime crashes.
**Decision:** Run code review agents after each phase completion, before merging.
**Rationale:** Catches bugs that compile-checks miss: wrong enum types, missing model fields, broken method calls, race conditions.
