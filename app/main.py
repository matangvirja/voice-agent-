"""
FastAPI Server — Twilio Voice Agent
-------------------------------------
Handles incoming and outgoing phone calls via Twilio.
Exposes three endpoints:
    POST /call/incoming  — webhook called by Twilio when someone calls your number
    WS   /audio-stream   — WebSocket for live audio streaming
    POST /call/outbound  — trigger an outbound call to a number
    GET  /               — health check

Run:
    python -m uvicorn app.main:voice_app --host 0.0.0.0 --port 8000 --reload
"""

import os
import sys
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import PlainTextResponse
from twilio.rest import Client
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(Path(__file__).parent.parent / ".env")

from app.database     import init_db, start_call, end_call
from app.call_handler import CallHandler
from app.extractor    import extract_crm_data

# ── App Setup ────────────────────────────────────────────────
voice_app = FastAPI(
    title="AI Voice Calling Agent",
    description="Groq STT + Gemini LLM + Edge-TTS + Twilio",
    version="1.0.0"
)

twilio_client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)
TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
NGROK_URL     = os.getenv("NGROK_URL", "").rstrip("/")

# Track active calls in memory
active_calls: dict[str, CallHandler] = {}


# ── Startup ──────────────────────────────────────────────────
@voice_app.on_event("startup")
async def startup():
    await init_db()
    print("Server ready. Waiting for calls...")


# ── Inbound Call Webhook ─────────────────────────────────────
@voice_app.post("/call/incoming")
async def incoming_call(request: Request):
    """
    Twilio calls this URL when someone calls your Twilio number.
    Returns TwiML telling Twilio to open a WebSocket audio stream.
    """
    form   = await request.form()
    caller = form.get("From", "unknown")
    name   = request.query_params.get("name", "Sir/Ma'am")
    lang   = request.query_params.get("lang", "hi")

    print(f"Incoming call from: {caller} | Name: {name} | Lang: {lang}")

    call_id = await start_call(caller)
    host    = request.headers.get("host", "localhost")
    ws_url  = f"wss://{host}/audio-stream/{call_id}?name={name}&lang={lang}"

    twiml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Connect>
    <Stream url="{ws_url}">
      <Parameter name="call_id" value="{call_id}"/>
    </Stream>
  </Connect>
</Response>"""
    return PlainTextResponse(twiml, media_type="text/xml")


# ── WebSocket Audio Stream ───────────────────────────────────
@voice_app.websocket("/audio-stream/{call_id}")
async def audio_stream(websocket: WebSocket, call_id: str):
    """
    Live audio stream for an active phone call.
    Receives mulaw audio from Twilio, processes it, sends back response audio.
    """
    await websocket.accept()

    name = websocket.query_params.get("name", "Sir/Ma'am")
    lang = websocket.query_params.get("lang", "hi")

    handler = CallHandler(websocket, call_id, name=name, lang=lang)
    active_calls[call_id] = handler

    try:
        await handler.handle()
    finally:
        active_calls.pop(call_id, None)

        # Save call summary when call ends
        if handler.history:
            transcript = "\n".join([
                f"{t['role'].upper()}: {t['parts'][0]['text']}"
                for t in handler.history
            ])
            try:
                crm = await extract_crm_data(transcript, handler.lang)
            except Exception:
                crm = {
                    "outcome":        "unknown",
                    "interest_level": "unknown",
                    "next_action":    "unknown",
                    "main_objection": "none",
                    "callback_time":  "none",
                    "customer_name":  "unknown",
                    "key_facts":      []
                }
            await end_call(call_id, handler.history, handler.lang, crm)
            print(f"Call {call_id} saved. Outcome: {crm.get('outcome')}")


# ── Outbound Call ────────────────────────────────────────────
@voice_app.post("/call/outbound")
async def make_outbound_call(request: Request):
    """
    Trigger an outbound call to a phone number.

    Body:
        to:   Phone number to call (e.g. "+919876543210")
        name: Contact name for personalized greeting
        lang: Language code ("hi", "gu", "en", etc.)
    """
    body      = await request.json()
    to_number = body.get("to")
    name      = body.get("name", "Sir/Ma'am")
    lang      = body.get("lang", "hi")

    if not to_number:
        return {"error": "to number is required"}

    if not NGROK_URL:
        return {"error": "NGROK_URL not set in .env"}

    call = twilio_client.calls.create(
        to=to_number,
        from_=TWILIO_NUMBER,
        url=f"{NGROK_URL}/call/incoming?name={name}&lang={lang}",
        method="POST"
    )
    print(f"Outbound call → {to_number} | {name} | SID: {call.sid}")
    return {"call_sid": call.sid, "status": "initiated", "to": to_number}


# ── Health Check ─────────────────────────────────────────────
@voice_app.get("/")
async def health():
    return {
        "status":       "running",
        "active_calls": len(active_calls),
        "version":      "1.0.0"
    }


# ── Direct Run ───────────────────────────────────────────────
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:voice_app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
