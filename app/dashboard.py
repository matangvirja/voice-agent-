"""
Dashboard API Routes — v2
--------------------------
Endpoints:
    GET  /dashboard/          — serves dashboard HTML
    WS   /dashboard/live      — real-time transcript WebSocket
    GET  /dashboard/stats     — aggregated stats
    GET  /dashboard/recent    — recent calls table
    GET  /dashboard/call/{id} — single call detail
    GET  /dashboard/prompt    — read current master prompt
    POST /dashboard/prompt    — save + hot-reload master prompt
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi.responses import HTMLResponse

from app.database import get_pool

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# ── Path to master prompt ─────────────────────────────────────
PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "master_prompt.txt"


# ── WebSocket manager ─────────────────────────────────────────
class DashboardManager:
    def __init__(self):
        self.connections: list[WebSocket] = []

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self.connections.append(ws)
        print(f"[Dashboard] Client connected. Total: {len(self.connections)}")

    def disconnect(self, ws: WebSocket):
        if ws in self.connections:
            self.connections.remove(ws)

    async def broadcast(self, message: dict):
        if not self.connections:
            return
        payload = json.dumps(message, ensure_ascii=False, default=str)
        dead = []
        for ws in self.connections:
            try:
                await ws.send_text(payload)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.disconnect(ws)


manager = DashboardManager()


async def broadcast(message: dict):
    """Import and call this from call_handler.py to push live events."""
    await manager.broadcast(message)


# ── WebSocket ─────────────────────────────────────────────────
@router.websocket("/live")
async def dashboard_live(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except (WebSocketDisconnect, Exception):
        manager.disconnect(websocket)


# ── Stats ─────────────────────────────────────────────────────
@router.get("/stats")
async def dashboard_stats():
    pool = await get_pool()
    async with pool.acquire() as conn:
        total = await conn.fetchval(
            "SELECT COUNT(*) FROM calls WHERE ended IS NOT NULL"
        )
        avg_turns = await conn.fetchval(
            "SELECT AVG(total_turns) FROM calls WHERE ended IS NOT NULL AND total_turns > 0"
        )
        outcome_rows = await conn.fetch(
            "SELECT outcome, COUNT(*) as cnt FROM calls WHERE ended IS NOT NULL AND outcome IS NOT NULL GROUP BY outcome"
        )
        lang_rows = await conn.fetch(
            "SELECT language_used, COUNT(*) as cnt FROM calls WHERE ended IS NOT NULL AND language_used IS NOT NULL GROUP BY language_used ORDER BY cnt DESC"
        )
        daily_rows = await conn.fetch(
            "SELECT DATE(started) as date, COUNT(*) as count FROM calls WHERE started >= NOW() - INTERVAL '7 days' GROUP BY DATE(started) ORDER BY date ASC"
        )

    today    = datetime.utcnow().date()
    date_map = {str(r["date"]): r["count"] for r in daily_rows}
    daily    = [{"date": str(today - timedelta(days=i)), "count": date_map.get(str(today - timedelta(days=i)), 0)} for i in range(6,-1,-1)]

    return {
        "total_calls":  total or 0,
        "active_calls": len(manager.connections),
        "avg_turns":    float(avg_turns) if avg_turns else 0,
        "outcomes":     {r["outcome"]: r["cnt"] for r in outcome_rows},
        "languages":    {r["language_used"]: r["cnt"] for r in lang_rows},
        "daily":        daily,
    }


# ── Recent calls ──────────────────────────────────────────────
@router.get("/recent")
async def dashboard_recent(limit: int = Query(default=20, le=100)):
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT call_id, phone, started, ended, total_turns,
                      language_used, outcome, interest_level, next_action, main_objection
               FROM calls ORDER BY started DESC LIMIT $1""",
            limit
        )
    return {
        "calls": [{
            "call_id":       r["call_id"],
            "phone":         r["phone"],
            "started":       r["started"].isoformat() if r["started"] else None,
            "ended":         r["ended"].isoformat()   if r["ended"]   else None,
            "total_turns":   r["total_turns"],
            "language_used": r["language_used"],
            "outcome":       r["outcome"],
            "interest_level":r["interest_level"],
            "next_action":   r["next_action"],
            "main_objection":r["main_objection"],
        } for r in rows],
        "count": len(rows)
    }


# ── Single call detail ────────────────────────────────────────
@router.get("/call/{call_id}")
async def dashboard_call_detail(call_id: str):
    pool = await get_pool()
    async with pool.acquire() as conn:
        call  = await conn.fetchrow("SELECT * FROM calls WHERE call_id = $1", call_id)
        if not call:
            return {"error": "Call not found"}
        turns = await conn.fetch(
            "SELECT role, language, text, created FROM turns WHERE call_id = $1 ORDER BY created ASC",
            call_id
        )
    return {"call": dict(call), "turns": [dict(t) for t in turns]}


# ── Read prompt ───────────────────────────────────────────────
@router.get("/prompt")
async def get_prompt():
    """Read the current master prompt file."""
    try:
        content = PROMPT_PATH.read_text(encoding="utf-8")
        stat    = PROMPT_PATH.stat()
        return {
            "content":      content,
            "word_count":   len(content.split()),
            "char_count":   len(content),
            "line_count":   len(content.splitlines()),
            "last_modified": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            "path":         str(PROMPT_PATH),
        }
    except FileNotFoundError:
        return {"error": "Prompt file not found", "content": "", "path": str(PROMPT_PATH)}
    except Exception as e:
        return {"error": str(e), "content": ""}


# ── Save + hot-reload prompt ──────────────────────────────────
@router.post("/prompt")
async def save_prompt(body: dict):
    """
    Save new prompt content to file and hot-reload it into memory.
    The LLM module reloads MASTER_PROMPT from file on next request.
    """
    content = body.get("content", "").strip()
    if not content:
        return {"error": "Prompt content cannot be empty"}
    if len(content) < 50:
        return {"error": "Prompt too short — minimum 50 characters"}

    try:
        # Write to file
        PROMPT_PATH.parent.mkdir(parents=True, exist_ok=True)
        PROMPT_PATH.write_text(content, encoding="utf-8")

        # Hot-reload into LLM module memory
        try:
            import app.llm as llm_module
            llm_module.MASTER_PROMPT = content
            print(f"[Dashboard] Prompt hot-reloaded. Words: {len(content.split())}")
        except Exception as e:
            print(f"[Dashboard] Hot-reload warning: {e}")

        return {
            "success":    True,
            "word_count": len(content.split()),
            "saved_at":   datetime.now().isoformat(),
            "message":    "Prompt saved and reloaded successfully",
        }
    except Exception as e:
        return {"error": f"Failed to save: {str(e)}"}


# ── Serve HTML ────────────────────────────────────────────────
@router.get("/", response_class=HTMLResponse)
async def serve_dashboard():
    try:
        html = (Path(__file__).parent.parent / "dashboard" / "index.html").read_text(encoding="utf-8")
        return HTMLResponse(content=html)
    except FileNotFoundError:
        return HTMLResponse("<h2>dashboard/index.html not found</h2>", status_code=404)
