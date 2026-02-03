---
description: Run database migration on Supabase
disable-model-invocation: true
---

# Run Database Migration

Execute SQL migration on Supabase PostgreSQL.

## Prerequisites

- Migration file in `supabase/migrations/XXX_name.sql`
- Database credentials in `.credentials/keys.md`

## Command

```bash
/opt/homebrew/Cellar/libpq/18.1/bin/psql "postgresql://postgres:PASSWORD@db.cfppunyxxelqutfwqfbi.supabase.co:5432/postgres" -f supabase/migrations/XXX.sql
```

## Steps

1. Read `.credentials/keys.md` for database password
2. Run migration with full psql path
3. Verify in Supabase Dashboard → Table Editor

## Naming Convention

- `001_initial.sql`
- `002_enhanced_profiles.sql`
- `003_vector_embeddings.sql`
- `004_sphere_city.sql`
- `005_speed_dating.sql`
- Next: `006_xxx.sql`
