# Current Status

Branch: `community-v1`
Bot: @Matchd_bot
Deploy: Not yet deployed (Railway needs branch config)
Last session: 2026-02-26

## Implementation Complete (All 3 Phases)

### Phase 1: Foundation (Tasks 1-11)
- DB migration (016_community_tables.sql)
- Domain models: Community, CommunityMember, GameSession, GameResponse
- Repositories: CommunityRepository, GameRepository
- CommunityService: bot lifecycle, admin sync, deep links, Sphere Global
- Group handler: bot added/removed, passive message observation
- Deep link attribution parser
- Community-scoped matching (within community candidates)
- Community-aware onboarding (context injection)
- Periodic scheduler (hourly reminders)
- Basic admin dashboard (communities tab, HTMX)
- Full loader wiring (13 routers)

### Phase 2: Games (Tasks 12-18)
- Game engine with 5 types: Mystery Profile, This or That, Vibe Check, Hot Take, Common Ground
- Question banks (20 this_or_that, 10 vibe_check, 15 hot_take)
- LLM clue generation for Mystery Profile
- Inline button callbacks for all game interactions
- Personality Card: Pillow 800x1000px dark-themed card + QR code
- Scheduler integration for auto-launching games

### Phase 3: Intelligence (Tasks 19-26)
- Message observation pipeline (batch LLM extraction, topics + sentiment)
- Community pulse (weekly AI digest)
- Bingo game (3x3 trait grid, Pillow rendering)
- Cross-community paywall (free tier = 1 match limit)
- Event-in-community (events linked to communities)
- Sphere Global (virtual community, sentinel group_id = -1)
- Full analytics dashboard (growth chart, funnel, games, topics, attribution)
- Code review: 3 agents found 26 issues, 11 critical bugs fixed

## What's Broken / Known Issues
1. Cross-community paywall counter counts ALL community matches, not just cross-community
2. Sync Pillow rendering blocks event loop (personality card, bingo)
3. `post_game_results` never called (dead code)
4. N+1 DB queries in bingo_service._generate_traits
5. FSM in memory — MemoryStorage() loses state on restart

## Commits on community-v1
1. `de85478` — Python 3.9 compat + Phase 1 verification
2. `c1c17a8` — Game engine + 5 game types
3. `688cd31` — Personality Card
4. `3eb4b69` — Observation pipeline + pulse + bingo
5. `5deea9e` — Cross-community paywall + event-in-community + Sphere Global
6. `0935048` — 11 bug fixes from code review
7. `be660bd` — Full analytics dashboard
8. (pending) — CLAUDE.md + .memory/ update

## Worktree Layout
| Location | Branch | Purpose |
|----------|--------|---------|
| `sphere-bot/` | `main` | Archive |
| `worktrees/sphere-community/` | `community-v1` | Active dev (HERE) |
| `worktrees/sphere-global/` | `global-mode-v1` | Global mode testing |

## Next Steps
- Deploy to Railway (configure community-v1 branch)
- Run migration 016_community_tables.sql on Supabase
- End-to-end testing: add bot to a group, onboard, play games
- Fix remaining known issues (paywall counter, Pillow async, game results)
- Consider merge strategy (merge into global-mode-v1? separate deploy?)
