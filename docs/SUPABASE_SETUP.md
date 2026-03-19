# Supabase PostgreSQL Setup

## Step 1 — Create free account

1. Go to [supabase.com](https://supabase.com) → Sign up free
2. Create new project → name it `voice-agent`
3. Region: **Southeast Asia (Singapore)** — lowest latency from India
4. Set a database password — **save this**
5. Wait ~2 minutes for project to initialize

---

## Step 2 — Get connection string

1. Go to **Project Settings** → **Database**
2. Scroll to **"Connection string"** section
3. Click **"Session pooler"** tab
4. Copy the connection string — it looks like:
   ```
   postgresql://postgres.YOURREF:[YOUR-PASSWORD]@aws-0-ap-southeast-1.pooler.supabase.com:6543/postgres
   ```
5. Replace `[YOUR-PASSWORD]` with your actual password
6. Paste into your `.env` as `DATABASE_URL`

---

## Step 3 — Create tables

Go to **SQL Editor** → **New Query** → paste this SQL → click **Run**:

```sql
-- Every conversation turn (user + agent)
CREATE TABLE IF NOT EXISTS turns (
    id         SERIAL PRIMARY KEY,
    call_id    TEXT NOT NULL,
    role       TEXT NOT NULL,
    language   TEXT DEFAULT 'hi',
    text       TEXT NOT NULL,
    created    TIMESTAMPTZ DEFAULT NOW()
);

-- One row per call with CRM outcome data
CREATE TABLE IF NOT EXISTS calls (
    call_id        TEXT PRIMARY KEY,
    phone          TEXT DEFAULT 'local_test',
    started        TIMESTAMPTZ DEFAULT NOW(),
    ended          TIMESTAMPTZ,
    total_turns    INTEGER DEFAULT 0,
    language_used  TEXT DEFAULT 'hi',
    outcome        TEXT DEFAULT 'unknown',
    interest_level TEXT DEFAULT 'unknown',
    next_action    TEXT DEFAULT 'unknown',
    main_objection TEXT DEFAULT 'none',
    callback_time  TEXT DEFAULT 'none',
    transcript     TEXT DEFAULT '',
    crm_data       JSONB DEFAULT '{}'
);

-- Indexes for fast queries
CREATE INDEX IF NOT EXISTS idx_calls_phone    ON calls(phone);
CREATE INDEX IF NOT EXISTS idx_turns_call_id  ON turns(call_id);
```

You should see **"Success. No rows returned"** — tables are created.

---

## Step 4 — View your data

Go to **Table Editor** in the Supabase dashboard:
- `calls` table — one row per call, with CRM data
- `turns` table — every conversation turn with timestamps

This is your live CRM dashboard — updates in real time during calls.

---

## Troubleshooting

| Error | Fix |
|---|---|
| `getaddrinfo failed` | Wrong hostname — use Session pooler URL, not direct URL |
| `Tenant not found` | Username must be `postgres.YOURPROJECTREF` (with project ref) |
| `SSL required` | Add `?sslmode=require` to DATABASE_URL or `ssl="require"` in code |
| Port 5432 refused | Use port **6543** for Session pooler (not 5432) |
