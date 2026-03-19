"""
Database Module — PostgreSQL on Supabase
-----------------------------------------
Manages all database operations using asyncpg connection pooling.
Logs every call turn in real time and saves CRM summary on call end.

Tables:
    turns — every conversation turn (user + agent)
    calls — one row per call with CRM outcome data

Usage:
    await init_db()
    call_id = await start_call("+919876543210")
    await log_turn(call_id, "user", "hi", "नमस्ते")
    await end_call(call_id, history, "hi", crm_data)
"""

import os
import asyncio
import asyncpg
import json
import uuid
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

DATABASE_URL = os.getenv("DATABASE_URL")

# ── Connection Pool ──────────────────────────────────────────
_pool = None


async def get_pool():
    """Return shared connection pool — creates it on first call."""
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            DATABASE_URL,
            min_size=1,
            max_size=10,
            command_timeout=30,
            ssl="require"
        )
        print("PostgreSQL connection pool ready.")
    return _pool


# ── Database Initialization ──────────────────────────────────
async def init_db():
    """Verify database connection. Tables must exist (created in Supabase)."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        result = await conn.fetchval("SELECT COUNT(*) FROM calls")
        print(f"Database connected. Existing calls: {result}")


# ── Call Lifecycle ───────────────────────────────────────────
async def start_call(phone: str = "local_test") -> str:
    """
    Create a new call record at the start of a call.

    Returns:
        call_id: Short unique ID (e.g. "a3f9b2c1")
    """
    call_id = str(uuid.uuid4())[:8]
    pool    = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            "INSERT INTO calls (call_id, phone, started) VALUES ($1, $2, NOW())",
            call_id, phone
        )
    print(f"Call started. ID: {call_id}")
    return call_id


async def log_turn(
    call_id: str,
    role: str,
    language: str,
    text: str
):
    """
    Save one conversation turn to the database immediately.

    Args:
        call_id:  Call identifier
        role:     "user" or "agent"
        language: Language code ("hi", "gu", "ta", etc.)
        text:     What was said
    """
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO turns (call_id, role, language, text)
               VALUES ($1, $2, $3, $4)""",
            call_id, role, language, text
        )


async def end_call(
    call_id: str,
    history: list,
    language_used: str,
    crm_data: dict
):
    """
    Save call summary and CRM data when call ends.

    Args:
        call_id:       Call identifier
        history:       Full conversation history
        language_used: Primary language of the call
        crm_data:      Structured CRM data from extractor
    """
    transcript = "\n".join([
        f"{t['role'].upper()}: {t['parts'][0]['text']}"
        for t in history
    ])
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE calls SET
                ended          = NOW(),
                total_turns    = $1,
                language_used  = $2,
                outcome        = $3,
                interest_level = $4,
                next_action    = $5,
                main_objection = $6,
                callback_time  = $7,
                transcript     = $8,
                crm_data       = $9
               WHERE call_id = $10""",
            len(history) // 2,
            language_used,
            crm_data.get("outcome",        "unknown"),
            crm_data.get("interest_level", "unknown"),
            crm_data.get("next_action",    "unknown"),
            crm_data.get("main_objection", "none"),
            crm_data.get("callback_time",  "none"),
            transcript,
            json.dumps(crm_data),
            call_id
        )
    print(f"Call {call_id} saved to PostgreSQL.")


async def show_recent_calls(limit: int = 5):
    """Print the most recent calls — useful for debugging."""
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT call_id, phone, started, total_turns,
                      language_used, outcome, interest_level
               FROM calls ORDER BY started DESC LIMIT $1""",
            limit
        )
    if not rows:
        print("No calls in database yet.")
        return
    print(f"\n{'─'*65}")
    print(f"  Last {limit} calls")
    print(f"{'─'*65}")
    for r in rows:
        print(
            f"  ID: {r['call_id']} | "
            f"Phone: {r['phone']} | "
            f"Lang: {r['language_used']} | "
            f"Turns: {r['total_turns']} | "
            f"Outcome: {r['outcome']} | "
            f"Interest: {r['interest_level']}"
        )
    print(f"{'─'*65}")


# ── Test Block ───────────────────────────────────────────────
if __name__ == "__main__":
    async def test():
        await init_db()

        call_id = await start_call("+919876543210")

        await log_turn(call_id, "user",  "hi", "नमस्ते, मुझे loan चाहिए")
        await log_turn(call_id, "agent", "hi", "जी हाँ! आपको कितने का loan चाहिए?")
        await log_turn(call_id, "user",  "hi", "50,000 रुपये चाहिए")
        await log_turn(call_id, "agent", "hi", "बिल्कुल! कल 10 बजे call करूँ?")

        crm = {
            "outcome":        "interested",
            "interest_level": "high",
            "next_action":    "callback",
            "main_objection": "none",
            "callback_time":  "tomorrow 10am",
            "customer_name":  "Test User",
            "key_facts":      ["wants 50k loan"]
        }
        history = [
            {"role": "user",  "parts": [{"text": "नमस्ते"}]},
            {"role": "model", "parts": [{"text": "जी हाँ!"}]},
        ]
        await end_call(call_id, history, "hi", crm)
        await show_recent_calls()

    asyncio.run(test())
