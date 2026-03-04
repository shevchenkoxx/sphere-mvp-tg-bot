---
description: Update project documentation after changes (CLAUDE.md, progress.md, memory)
---

# Update Docs

Update all project documentation to reflect current state after code changes.

## What to Update

### 1. `progress.md` — Session Progress

Add or update the current session entry at the TOP of the file:

- **Session date** (current date)
- **Completed items** — numbered list of what was done this session
  - Feature name + file path
  - Brief description of the change
  - Key details (new routes, new methods, line count changes)
- **Files modified** — list with before/after metrics
- **Commits** — hash + message (or "pending" if not committed yet)

### 2. `CLAUDE.md` — Project Knowledge Base

Update these sections:

- **Architecture tree** (`## Architecture`) — add/remove files if structure changed
- **Recent Session Changes** — add new entry at TOP with:
  - Date + title
  - Bullet points grouped by area (not individual lines)
  - **Files modified** list at the end
- **Current Status** section — if features added/completed, update the feature tables
- **Roadmap / TODO** — mark completed items, add new ones if discovered

### 3. Memory files (if applicable)

- `~/.claude/projects/.../memory/MEMORY.md` — update if:
  - New branch/bot mapping discovered
  - New credential added
  - New patterns learned
  - Workflow change

## Rules

- Keep entries **concise** — bullet points, not paragraphs
- Use **file paths** and **line counts** for traceability
- Always check `git diff --stat` and `git log --oneline -5` to see what actually changed
- Don't repeat information that's already in other sections
- Preserve all existing content — only ADD new session entries, don't delete old ones
- Recent Session Changes: most recent session goes FIRST (reverse chronological)

## Steps

1. Read `git diff --stat` and `git log --oneline -5` to understand changes
2. Read current `progress.md` header to understand format
3. Read `CLAUDE.md` Architecture + Recent Session Changes sections
4. Update `progress.md` with new session entry at top
5. Update `CLAUDE.md` Architecture tree if files added/removed
6. Update `CLAUDE.md` Recent Session Changes with new entry at top
7. Update memory files if applicable
