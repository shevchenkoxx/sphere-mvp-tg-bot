---
description: Review code for bugs, security issues, and best practices
---

# Code Review

Comprehensive code review checklist for Sphere Bot.

## Review Checklist

### 1. Syntax & Imports
- [ ] All files pass `python3 -m py_compile`
- [ ] No unused imports
- [ ] Imports are from correct modules

### 2. Async/Await
- [ ] All async functions are awaited
- [ ] No blocking calls in async context
- [ ] `run_sync` decorator used for Supabase operations

### 3. Error Handling
- [ ] Try/except around external calls (OpenAI, Supabase)
- [ ] Proper logging with `logger.error()` / `logger.warning()`
- [ ] User-friendly error messages in both EN/RU

### 4. Telegram Handlers
- [ ] `callback.answer()` called exactly once
- [ ] State cleared after flow completion (`state.clear()`)
- [ ] Language detected correctly (`detect_lang()`)

### 5. Database
- [ ] UUIDs converted to strings for Supabase
- [ ] Foreign key constraints respected
- [ ] Indexes on frequently queried columns

### 6. Security
- [ ] No hardcoded credentials
- [ ] Input validation for user data
- [ ] SQL injection prevented (using parameterized queries)

### 7. Performance
- [ ] Embeddings generated in background (`asyncio.create_task`)
- [ ] Caching where appropriate
- [ ] No N+1 query patterns

## Quick Commands

```bash
# Check syntax of all Python files
find . -name "*.py" -exec python3 -m py_compile {} \;

# Find TODOs
grep -r "TODO" --include="*.py" .

# Find print statements (should use logger)
grep -r "print(" --include="*.py" .
```
