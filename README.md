# AI Voice Calling Agent

An AI-powered outbound voice calling agent that makes real phone calls, converses naturally in Indian regional languages (Hindi, Gujarati, Tamil, Telugu, English), qualifies leads, and logs structured CRM data — all at **zero cost**.

---

## Architecture

```
Phone Call Audio
      │
      ▼
┌─────────────────┐
│  Twilio (PSTN)  │  ← handles real phone numbers
└────────┬────────┘
         │ WebSocket (G711 mulaw audio)
         ▼
┌─────────────────┐
│  FastAPI Server │  ← receives audio, returns audio
└────────┬────────┘
         │
    ┌────┴────────────────────┐
    ▼                         ▼
┌───────────┐         ┌──────────────┐
│ Groq STT  │         │  Edge-TTS    │
│ (Whisper) │         │  (free TTS)  │
└─────┬─────┘         └──────▲───────┘
      │ text                  │ text
      ▼                       │
┌─────────────────────────────┤
│    Gemini Flash (LLM)        │
│    + Master Prompt           │
└─────────────────────────────┘
         │
         ▼
┌─────────────────┐
│  Supabase       │  ← stores every turn + CRM data
│  PostgreSQL     │
└─────────────────┘
```

---

## Features

- **Real phone calls** via Twilio (inbound + outbound)
- **Multi-language** — Hindi, Gujarati, Tamil, Telugu, Marathi, English
- **Auto language detection** — Whisper detects what user speaks, agent responds in same language
- **Smart silence detection** — stops listening after 4 seconds of silence
- **Thinking phrases** — agent says "हाँ जी, एक second..." while processing
- **PostgreSQL logging** — every conversation turn saved in real time
- **CRM extraction** — structured data (interest level, objections, next action) extracted after each call
- **Zero cost** — Groq free tier + Gemini free tier + Edge-TTS (no key)
- **Personalized greeting** — agent greets caller by name in their language

---

## Tech Stack

| Component | Tool | Cost |
|---|---|---|
| Speech-to-Text | Groq Whisper large-v3 | Free tier |
| LLM | Google Gemini Flash | Free tier |
| Text-to-Speech | Microsoft Edge-TTS | Free, no key |
| Telephony | Twilio | $15 trial credit |
| Database | PostgreSQL on Supabase | Free 500MB |
| Server | FastAPI + Uvicorn | Free |
| Tunnel | ngrok | Free |

---

## Prerequisites

### System requirements
- Python 3.9+
- Windows 10/11, macOS, or Linux
- Microphone (for local testing)
- Internet connection

### Install system tools

**ffmpeg** (required for audio format conversion):
```bash
# Windows
winget install ffmpeg

# macOS
brew install ffmpeg

# Linux
sudo apt install ffmpeg
```

**ngrok** (required for Twilio webhooks):
```bash
# Windows
winget install Ngrok.Ngrok

# macOS
brew install ngrok

# Linux — download from ngrok.com
```

---

## Quick Start

### 1. Clone the repository

```bash
git clone https://github.com/YOUR_USERNAME/voice-agents.git
cd voice-agents
```

### 2. Create virtual environment

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up API keys

Copy the example environment file:
```bash
cp .env.example .env
```

Fill in your keys in `.env`:

| Key | Where to get |
|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com) — free |
| `GEMINI_API_KEY` | [aistudio.google.com](https://aistudio.google.com) — free |
| `TWILIO_*` | [twilio.com](https://twilio.com) — $15 free credit |
| `DATABASE_URL` | [supabase.com](https://supabase.com) — free 500MB |

### 5. Set up the database

See [docs/SUPABASE_SETUP.md](docs/SUPABASE_SETUP.md) for step-by-step instructions.

### 6. Customize the agent

Edit `prompts/master_prompt.txt` to define:
- Your company and product details
- Conversation flow and scripts
- Language preferences
- Compliance rules

---

## Usage

### Test locally (no phone needed)

Speak into your mic → hear agent respond in the same language:

```bash
python -m app.pipeline
```

Press `Ctrl+C` to end the call and see the CRM summary.

---

### Run as phone server

Open 3 terminals:

**Terminal 1 — Start the server:**
```bash
python -m uvicorn app.main:voice_app --host 0.0.0.0 --port 8000 --reload
```

**Terminal 2 — Start ngrok:**
```bash
ngrok http 8000
```

Copy the `https://xxxx.ngrok-free.app` URL.

**Set Twilio webhook:**
```
Twilio Console → Phone Numbers → Active Numbers
→ click your number → Voice Configuration
→ "A call comes in" → Webhook
→ paste: https://xxxx.ngrok-free.app/call/incoming
→ Save
```

Update `.env`:
```
NGROK_URL=https://xxxx.ngrok-free.app
```

**Terminal 3 — Make an outbound call:**

Edit `make_call.py` with your target phone number, then:
```bash
python make_call.py
```

Your phone will ring within 15 seconds. Speak in Hindi or Gujarati.

---

## Project Structure

```
voice-agents/
├── app/
│   ├── __init__.py         # Package marker
│   ├── stt.py              # Speech-to-Text (Groq Whisper)
│   ├── llm.py              # LLM responses (Gemini Flash)
│   ├── tts.py              # Text-to-Speech (Edge-TTS)
│   ├── pipeline.py         # Local voice loop (no phone)
│   ├── database.py         # PostgreSQL operations (Supabase)
│   ├── extractor.py        # CRM data extraction
│   ├── call_handler.py     # Twilio WebSocket call handler
│   └── main.py             # FastAPI server
├── prompts/
│   └── master_prompt.txt   # Agent personality + instructions
├── docs/
│   ├── SUPABASE_SETUP.md   # Database setup guide
│   └── TWILIO_SETUP.md     # Twilio setup guide
├── make_call.py            # Trigger outbound calls
├── requirements.txt        # Python dependencies
├── .env.example            # Environment variables template
├── .gitignore              # Files to exclude from git
└── README.md               # This file
```

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/call/incoming` | Twilio webhook — handles inbound calls |
| `WS` | `/audio-stream/{call_id}` | Live audio WebSocket |
| `POST` | `/call/outbound` | Trigger an outbound call |
| `GET` | `/` | Health check |

### Make outbound call via API

```bash
curl -X POST http://localhost:8000/call/outbound \
  -H "Content-Type: application/json" \
  -d '{
    "to": "+919876543210",
    "name": "Rahul",
    "lang": "hi"
  }'
```

---

## Database Schema

### `calls` table
| Column | Type | Description |
|---|---|---|
| `call_id` | TEXT | Unique call identifier |
| `phone` | TEXT | Caller's phone number |
| `started` | TIMESTAMPTZ | Call start time |
| `ended` | TIMESTAMPTZ | Call end time |
| `total_turns` | INTEGER | Number of conversation turns |
| `language_used` | TEXT | Primary language detected |
| `outcome` | TEXT | interested/not_interested/callback/etc. |
| `interest_level` | TEXT | high/medium/low/none |
| `next_action` | TEXT | callback/send_info/close/do_not_call |
| `transcript` | TEXT | Full conversation text |
| `crm_data` | JSONB | Structured CRM JSON |

### `turns` table
| Column | Type | Description |
|---|---|---|
| `call_id` | TEXT | Links to calls table |
| `role` | TEXT | "user" or "agent" |
| `language` | TEXT | Language code of this turn |
| `text` | TEXT | What was said |
| `created` | TIMESTAMPTZ | Timestamp |

---

## Customization

### Change the agent's language
Edit `prompts/master_prompt.txt` — update the language rules section.

### Change the TTS voice
Edit `app/tts.py` — update the `VOICES` dictionary.

Available Indian voices (Edge-TTS, all free):
```python
VOICES = {
    "hi": "hi-IN-SwaraNeural",    # Hindi female
    "gu": "gu-IN-DhwaniNeural",   # Gujarati female
    "ta": "ta-IN-PallaviNeural",  # Tamil female
    "te": "te-IN-MoazamNeural",   # Telugu male
    "mr": "mr-IN-AarohiNeural",   # Marathi female
    "en": "en-IN-NeerjaNeural",   # Indian English female
}
```

### Adjust silence detection
Edit `app/pipeline.py` or `app/call_handler.py`:
```python
SILENCE_THRESHOLD = 300   # increase if cutting off too early
SILENCE_SECONDS   = 4.0   # increase for slower speakers
```

### Add a new conversation flow
Edit `prompts/master_prompt.txt` — the CONVERSATION FLOW section defines the agent's goals and scripts.

---

## Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `ffmpeg not recognized` | ffmpeg not in PATH | Restart terminal after installing |
| `ModuleNotFoundError: app` | Wrong run command | Use `python -m app.module` not `python app/module.py` |
| `AuthenticationError` | Wrong API key | Check `.env` for spaces or quotes around keys |
| `getaddrinfo failed` | Wrong DB hostname | Use Supabase Session Pooler URL |
| `Tenant not found` | Wrong DB username | Username must be `postgres.YOURPROJECTREF` |
| `Url is not valid URL` | Using localhost | ngrok must be running, NGROK_URL must be set |
| `429 RESOURCE_EXHAUSTED` | Gemini rate limit | Wait 1 minute or use backup API key |
| No audio on phone call | stream_sid issue | Greeting sent after "start" event (already fixed) |
| STT not detecting voice | Silence threshold | Lower `SILENCE_THRESHOLD` in call_handler.py |
| `venv\Scripts\activate` disabled | Windows policy | Run `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser` |

---

## Free Tier Limits

| Service | Free Limit | Sufficient for |
|---|---|---|
| Groq Whisper | 2,000 req/day | ~133 calls/day |
| Gemini Flash | 1,500 req/day | ~100 calls/day |
| Edge-TTS | Unlimited | All calls |
| Supabase | 500MB storage | ~1M+ call records |
| Twilio | $15 credit | ~100 test calls |
| ngrok | 1 tunnel | Development only |

---

## Ethics & Compliance

- **TRAI regulations** — Only call between 9 AM – 9 PM IST
- **DND compliance** — Check TRAI DND registry before calling
- **Disclosure** — Agent identifies itself as AI at the start of every call
- **Opt-out** — Immediately honor "do not call" requests
- **DPDP Act 2023** — Delete user data on request
- **Data security** — Never collect Aadhaar, OTP, or card numbers

---

## License

MIT License — see LICENSE file for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/your-feature`
3. Commit your changes: `git commit -m "Add your feature"`
4. Push to the branch: `git push origin feature/your-feature`
5. Open a Pull Request

---

## Acknowledgements

- [Groq](https://groq.com) — ultra-fast Whisper inference
- [Google Gemini](https://ai.google.dev) — multilingual LLM
- [Microsoft Edge TTS](https://github.com/rany2/edge-tts) — free Indian voices
- [Twilio](https://twilio.com) — telephony infrastructure
- [Supabase](https://supabase.com) — free PostgreSQL hosting
