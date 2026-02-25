# Current Status

Branch: `community-v1`
Bot: @Matchd_bot
Deploy: Not yet deployed (Railway needs branch config)
Last session: 2026-02-25

## What Works (inherited from global-mode-v1)
- Agent onboarding (AI-driven, personalized)
- Global matching (vector + LLM re-ranking)
- Sphere City (city-based matching)
- Profile expansion flow
- Agent chat (post-onboarding AI conversation)
- Vibe Check (AI compatibility game)
- Share/referral system
- Admin dashboard (HTMX)
- Events system (enabled, /quickevent + QR)
- Conversation logging

## What's New on This Branch
- Design doc: `docs/plans/2026-02-25-community-v1-design.md`
- Implementation plan: `docs/plans/2026-02-25-community-v1-implementation.md`
- Nothing implemented yet — plan is ready, execution next

## What's Broken / WIP
- No community/group handling yet (Phase 1 not started)
- Event join ordering bug fixed on global-mode-v1 (inherited)

## Worktree Layout
| Location | Branch | Purpose |
|----------|--------|---------|
| `sphere-bot/` | `main` | Archive |
| `worktrees/sphere-community/` | `community-v1` | Active dev (HERE) |
| `worktrees/sphere-global/` | `global-mode-v1` | Global mode testing |

## Next Steps
- Execute Phase 1, Task 1: DB migration (016_community_tables.sql)
- Follow implementation plan task by task
