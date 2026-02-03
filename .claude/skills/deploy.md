---
description: Deploy to production via Railway
disable-model-invocation: true
---

# Deploy to Production

Deploy the current branch to Railway (production).

## Steps

1. Check syntax of all modified Python files
2. Run git status to see changes
3. Stage and commit with descriptive message
4. Push to origin/main
5. Railway auto-deploys from main branch

## Commands

```bash
# Check syntax
python3 -m py_compile adapters/telegram/**/*.py infrastructure/**/*.py core/**/*.py

# Deploy
git add -A && git commit -m "MESSAGE" && git push origin main
```

## Post-deploy

- Wait ~1-2 minutes for Railway deployment
- Test bot: t.me/Matchd_bot
- Check Railway logs if issues
