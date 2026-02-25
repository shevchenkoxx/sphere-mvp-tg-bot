# Git Memory Format

Long-term project memory tracked in git. Every Claude session reads this on start and writes to it on finish.

## Structure

```
.memory/
  FORMAT.md        # This file — format rules
  status.md        # Current state: branch, deploy, what works, what's broken
  decisions.md     # Key decisions with rationale (append-only log)
  sessions/        # Per-session changelogs
    YYYY-MM-DD.md  # One file per day (append if multiple sessions)
```

## Rules

1. **Session file** — Create/append `sessions/YYYY-MM-DD.md` after every session
2. **status.md** — Update at end of every session (overwrite, not append)
3. **decisions.md** — Append new decisions only; never edit past entries
4. **Keep it terse** — Bullet points, not paragraphs. Code snippets only when essential.
5. **Link to files** — Reference `path/to/file.py:123` not copy-paste code

## Session File Format

```markdown
# YYYY-MM-DD — [focus area]

## Context
Branch: xxx | Bot: @xxx | Deploy: Railway/local

## Changes
- [feat] Description — `file1.py`, `file2.py`
- [fix] Description — `file.py:42`
- [config] Description

## Commits
- `abc1234` — Commit message

## Blockers
- Issue description (if any)

## Next
- What to do next session (if known)
```

## status.md Format

```markdown
# Current Status

Branch: xxx
Bot: @xxx
Deploy: platform + status
Last session: YYYY-MM-DD

## What Works
- Feature A
- Feature B

## What's Broken / WIP
- Issue X

## Environment
- Key env vars and their values
```

## decisions.md Format

```markdown
# Decisions

## YYYY-MM-DD — Decision Title
**Context:** Why this came up
**Decision:** What we chose
**Rationale:** Why
```
