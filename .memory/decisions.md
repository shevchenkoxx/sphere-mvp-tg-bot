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
