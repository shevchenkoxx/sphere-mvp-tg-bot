---
description: Test changes in staging worktree before deploying to main
disable-model-invocation: true
---

# Test in Staging Worktree

Test changes safely before deploying to production.

## Worktrees

| Directory | Branch | Purpose |
|-----------|--------|---------|
| `sphere-bot/` | main | Production code |
| `worktrees/sphere-bot-staging/` | staging | Test before deploy |
| `worktrees/sphere-bot-experiment/` | experiment | Experimental features |

## Workflow

1. **Make changes in staging worktree**
   ```bash
   cd ../worktrees/sphere-bot-staging
   # make changes, test locally
   ```

2. **Test syntax**
   ```bash
   python3 -m py_compile file.py
   ```

3. **If OK, merge to main**
   ```bash
   cd ../../sphere-bot  # back to main
   git merge staging
   git push origin main
   ```

4. **Or cherry-pick specific commits**
   ```bash
   git cherry-pick <commit-hash>
   ```

## Commands

```bash
# List worktrees
git worktree list

# Create new feature worktree
git worktree add ../worktrees/sphere-bot-feature-name -b feature-name

# Remove worktree when done
git worktree remove ../worktrees/sphere-bot-feature-name
```

## Parallel Claude Sessions

You can run multiple Claude Code sessions:
- One in `sphere-bot/` (main) for production fixes
- One in `worktrees/sphere-bot-staging/` for new features
- They work independently without conflicts
