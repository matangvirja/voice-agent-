"""
Outbound Call Trigger
----------------------
Trigger the AI agent to call a specific phone number.
The agent will call the number, speak a greeting, and handle the conversation.

Usage:
    python make_call.py

Requirements:
    - Server must be running: python -m uvicorn app.main:voice_app --port 8000
    - ngrok must be running: ngrok http 8000
    - NGROK_URL must be set in .env
    - Target number must be verified in Twilio (trial accounts only)
"""

import os
from pathlib import Path
from dotenv import load_dotenv
from twilio.rest import Client

load_dotenv(Path(".env"))

client = Client(
    os.getenv("TWILIO_ACCOUNT_SID"),
    os.getenv("TWILIO_AUTH_TOKEN")
)

ngrok_url     = os.getenv("NGROK_URL", "").rstrip("/")
twilio_number = os.getenv("TWILIO_PHONE_NUMBER")

# ── Contact to call ──────────────────────────────────────────
# Edit these values before running
contact = {
    "phone": "+91XXXXXXXXXX",   # replace with target number
    "name":  "Rahul",           # used in personalized greeting
    "lang":  "hi",              # "hi", "gu", "ta", "te", "en"
}

# ── Pre-flight checks ────────────────────────────────────────
if not ngrok_url:
    print("ERROR: NGROK_URL not set in .env")
    print("Start ngrok: ngrok http 8000")
    print("Then copy the URL to .env as NGROK_URL=https://xxxx.ngrok-free.app")
    exit(1)

if not twilio_number:
    print("ERROR: TWILIO_PHONE_NUMBER not set in .env")
    exit(1)

# ── Make the call ────────────────────────────────────────────
print(f"Calling  : {contact['name']} ({contact['phone']})")
print(f"Language : {contact['lang']}")
print(f"Webhook  : {ngrok_url}/call/incoming")
print(f"From     : {twilio_number}")
print()

try:
    call = client.calls.create(
        to=contact["phone"],
        from_=twilio_number,
        url=(
            f"{ngrok_url}/call/incoming"
            f"?name={contact['name']}"
            f"&lang={contact['lang']}"
        ),
        method="POST"
    )
    print(f"Call initiated!")
    print(f"SID    : {call.sid}")
    print(f"Status : {call.status}")
    print()
    print("Your phone will ring in 10-15 seconds.")
    print("Watch the server terminal for live logs.")

except Exception as e:
    print(f"Call failed: {e}")
    print()
    print("Common causes:")
    print("  - Phone number not verified (add at Twilio → Verified Caller IDs)")
    print("  - NGROK_URL is wrong or ngrok is not running")
    print("  - Server is not running (start with uvicorn)")
