# Git Memory Format

Long-term project memory tracked in git. Every Claude session reads this on start and writes to it on finish. Git commits themselves serve as the detailed audit trail — `.memory/` is the index.

## Structure

```
.memory/
  FORMAT.md        # This file — format rules
  status.md        # Current state: branch, deploy, what works, what's broken
  decisions.md     # Key decisions with rationale (append-only log)
  sessions/        # Per-session changelogs
    YYYY-MM-DD.md  # One file per day (append if multiple sessions)
```

## Git Commits as Memory

**Commits ARE the primary long-term memory.** Write them so that `git log --oneline` tells the full project story.

### Commit message format:
```
<type>: <what changed> — <why>

[body: context, alternatives considered, gotchas for future sessions]

Files: path/to/key/file.py, path/to/other.py
Refs: #issue, design doc, related commit hash

Co-Authored-By: Claude Opus 4.6 <noreply@anthropic.com>
```

### Types:
- `feat:` new functionality
- `fix:` bug fix
- `refactor:` code restructuring (no behavior change)
- `docs:` documentation / plans / memory updates
- `chore:` config, deps, CI, cleanup
- `test:` test additions or fixes

### What makes a good commit message:
- **Subject:** imperative, <70 chars, describes the change
- **Body:** WHY this was done, what was considered, what to watch out for
- **Files:** key files changed (helps `git log --all -- path/to/file`)
- **Self-contained:** someone reading just the commit should understand the context

### How to use git as memory:
- `git log --oneline -20` — quick overview of recent work
- `git log --all --oneline --graph` — see all branches
- `git log --grep="community"` — find all community-related changes
- `git show <hash>` — full context of a specific change
- `git log -- path/to/file.py` — history of a specific file

## .memory/ Rules

1. **Session file** — Create/append `sessions/YYYY-MM-DD.md` after every session
2. **status.md** — Update at end of every session (overwrite, not append)
3. **decisions.md** — Append new decisions only; never edit past entries
4. **Keep it terse** — Bullet points, not paragraphs. Code snippets only when essential.
5. **Link to files** — Reference `path/to/file.py:123` not copy-paste code
6. **Link to commits** — Reference commit hashes for detailed context

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
