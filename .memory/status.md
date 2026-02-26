# Current Status

Branch: `community-v1`
Bot: @Matchd_bot
Deploy: **Railway deployed** — project `loving-possibility`, env `Community`, service `Service (Community)`
Dashboard: `https://humorous-enchantment-staging.up.railway.app/stats?token=sphere-admin-2026`
Last session: 2026-02-26

## Implementation Complete (All 3 Phases)

### Phase 1: Foundation (Tasks 1-11)
- DB migration (016_community_tables.sql) — executed on Supabase
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
- Code review: 6 agents total, 11 critical bugs fixed, dashboard hardened

## Known Issues — Prioritized

### Critical (blocks core functionality)
1. **Games never expire** — scheduler doesn't check `ends_at`, `post_game_results` never called → after first game, new games permanently blocked per community
2. **Bingo is dead code** — service initialized in loader but not wired to scheduler/handlers/keyboards
3. **Paywall counts ALL matches** — `count_cross_community_matches` includes own-community matches → paywall triggers after 1st match
4. **Pillow blocks event loop** — sync rendering of personality card + bingo card (needs `run_in_executor`)
5. **N+1 DB queries** — in `_generate_traits`, `create_mystery_profile`, `detect_common_ground`, `find_community_matches`

### Important (degraded behavior)
6. Community context lost for non-agent onboarding paths (audio, v2, intent)
7. Observation summary never refreshes after first generation (permanent suppression)
8. `auto_associate_user` is dead code — organic group users never get community-associated
9. Scheduler has no overlap protection (concurrent ticks possible if tick is slow)
10. Unbounded queries: `get_user_matches`, `get_community_topics`, `get_all_active` — no limits
11. `run_sync` uses default thread pool (6 threads on Railway) — exhaustion risk under load
12. New `AsyncOpenAI` client created per `generate_personality_summary` call (connection leak)
13. `parse_mode` not explicit in game post/reveal calls (relies on bot default)
14. FSM in memory — `MemoryStorage()` loses state on Railway restart

## Commits on community-v1
1. `de85478` — Python 3.9 compat + Phase 1 verification
2. `c1c17a8` — Game engine + 5 game types
3. `688cd31` — Personality Card
4. `3eb4b69` — Observation pipeline + pulse + bingo
5. `5deea9e` — Cross-community paywall + event-in-community + Sphere Global
6. `0935048` — 11 bug fixes from code review
7. `be660bd` — Full analytics dashboard
8. `e0fe182` — CLAUDE.md + .memory/ update
9. `a0ddb18` — Dashboard review fixes (XSS, Chart.js HTMX, query limits)

## Railway Structure
| Project | Environment | Service | Bot | Branch |
|---------|-------------|---------|-----|--------|
| `loving-possibility` | Main | `sphere-production` | @Spheresocial_bot | `main` |
| `loving-possibility` | Community | `Service (Community)` | @Matchd_bot | `community-v1` |
| `Sphere Marketing` | production | marketing agent | — | — |

## Worktree Layout
| Location | Branch | Purpose |
|----------|--------|---------|
| `sphere-bot/` | `main` | Archive |
| `worktrees/sphere-community/` | `community-v1` | Active dev (HERE) |
| `worktrees/sphere-global/` | `global-mode-v1` | Global mode testing |

## Next Steps
1. **Fix critical issues** — game expiry + results posting (issue #1 is most impactful)
2. **End-to-end test** — add bot to a group, onboard, play games, check dashboard
3. **Fix paywall counter** — exclude own-community matches from cross-community count
4. **Wire bingo** — connect to scheduler + add callback handlers, or remove
5. **Performance pass** — batch DB queries, async Pillow, bounded thread pool
6. **Consider merge strategy** — separate deploy vs merge into global-mode-v1
