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

## Master Prompt — The Agent's Brain

The master prompt is the single most important file in the project. It lives at `prompts/master_prompt.txt` and controls **everything** the agent says and does — no conversation logic is hardcoded in Python. Changing the prompt is all you need to do to deploy this agent for a completely different business or use case.

### What the master prompt controls

| Section | What it defines |
|---|---|
| Identity & Role | Who the agent is, what company it represents, what its job is |
| Language Rules | Which languages to support, when to switch, what script to use |
| Personality & Tone | Formal vs casual, how to address users, filler phrases |
| Conversation Flow | The exact sequence: greeting → qualify → present → objection → close |
| Scripts | Word-for-word lines for greetings, objection handling, goodbyes |
| Output Format | Response length limits, no markdown, numbers in words |
| Safety & Compliance | Calling hours, DND handling, AI disclosure rules |

### Structure of the master prompt

```
prompts/master_prompt.txt
│
├── # IDENTITY & ROLE
│   What company, what product, what the agent's job is
│
├── # LANGUAGE DETECTION & SWITCHING RULES
│   Mirror user's language exactly. Hindi → Hindi, Gujarati → Gujarati.
│   Never respond in English if user spoke in a regional language.
│
├── # PERSONALITY & TONE
│   Warm, professional, Indian call center style.
│   Use "आप" not "तुम". Address as Sir/Ma'am or by name.
│   Keep responses under 35 words — phone calls need brevity.
│
├── # CONVERSATION FLOW
│   GREETING → QUALIFY → PRESENT → HANDLE_OBJECTION → COLLECT_INFO → CLOSE → GOODBYE
│   Each stage has specific goals and transition conditions.
│
├── # SCRIPTS (optional but recommended)
│   Word-for-word lines for common situations:
│   - Opening greeting in Hindi and Gujarati
│   - Response to "too expensive"
│   - Response to "I already have one"
│   - Response to "I'm busy"
│   - Site visit booking script
│
├── # OUTPUT FORMAT RULES
│   Spoken text only — no bullets, no asterisks, no markdown.
│   Numbers in words: "das hazaar" not "10,000".
│   End every turn with exactly one question.
│
└── # SAFETY & COMPLIANCE
    Never claim to be human. Never collect OTPs or Aadhaar.
    Call only 9AM–9PM IST. Honor DND requests immediately.
```

### How the prompt is loaded

The prompt is loaded **once at startup** into memory and reused for every call — no file read per turn:

```python
# app/llm.py
with open("prompts/master_prompt.txt", "r", encoding="utf-8") as f:
    MASTER_PROMPT = f.read()

# Injected as system_instruction on every LLM call
response = client.models.generate_content(
    model="gemini-2.0-flash-lite",
    contents=messages,
    config=types.GenerateContentConfig(
        system_instruction=MASTER_PROMPT,  # ← your prompt goes here
        temperature=0.7,
        max_output_tokens=500,
    )
)
```

To update the agent's behavior just edit `master_prompt.txt` and restart the server. No code changes needed.

### Customizing the prompt for your business

The default prompt is a generic voice assistant. To use this for a specific business, replace these sections:

**For a real estate company:**
```
# IDENTITY & ROLE
You are Priya — AI voice assistant for XYZ Construction.
Your job: call potential buyers about Skyline Residences, Ahmedabad.
Qualify leads, answer questions, book site visits.

# PROJECT DETAILS
- 2 BHK: 1050 sq ft, starting ₹58 lakhs
- 3 BHK: 1450 sq ft, starting ₹82 lakhs
- Amenities: pool, gym, 24/7 security, EV charging
- Possession: December 2026 | RERA: RAA12345678
```

**For a loan company:**
```
# IDENTITY & ROLE
You are Rahul — AI loan advisor for QuickLoan Finance.
Your job: qualify leads for personal/home/business loans.
Collect: loan amount, purpose, employment type, monthly income.
```

**For customer support:**
```
# IDENTITY & ROLE
You are Maya — AI support agent for Flipkart.
Your job: resolve order issues, process returns, escalate to human if needed.
```

### Prompt writing tips for phone calls

**Keep responses short.** Phone users hang up if the agent talks too long. The prompt must enforce this:
```
RESPONSE LENGTH — CRITICAL:
- Maximum 35 words per response
- One idea per sentence
- Always end with ONE question
- Never read lists aloud — say "we have two options" not a full list
```

**Mirror the user's language strictly.** The most common mistake is the agent switching to English. Be explicit:
```
LANGUAGE RULES:
- User speaks Hindi → respond ONLY in Hindi (Devanagari script)
- NEVER respond in English if user spoke in Hindi or Gujarati
- If unsure → default to Hindi
```

**Handle objections gracefully.** Pre-write objection responses so the LLM doesn't improvise badly:
```
"Bahut mehnga hai" (Too expensive):
→ "Samajh sakta hoon. 20 saal ke loan par sirf ₹18,000 EMI hai.
   Kya main ek baar figure share karoon?"
```

**Set a clear end condition.** Without this, the agent never closes the call:
```
CLOSE THE CALL when:
- User books a site visit → confirm date/time → thank → goodbye
- User says not interested → offer callback → goodbye
- User says DND/remove → apologize → end immediately
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

### Change the agent's persona and business
Edit `prompts/master_prompt.txt` — this single file controls everything the agent says and does. See the [Master Prompt](#master-prompt--the-agents-brain) section above for a full guide.

### Change the agent's language
Edit the `# LANGUAGE DETECTION & SWITCHING RULES` section in `prompts/master_prompt.txt`. To add a new language, also add its voice to `app/tts.py`.

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
Edit the `# CONVERSATION FLOW` section in `prompts/master_prompt.txt`. The flow is defined as a sequence of stages — no Python changes needed.

### Deploy for a different industry
The prompt is the only file you need to change. Here are ready-to-use starting points:

| Industry | What to change in the prompt |
|---|---|
| Real estate | Add project details, pricing, amenities, RERA number, site visit booking |
| Loans / NBFC | Add loan products, interest rates, eligibility criteria, document checklist |
| Insurance | Add policy details, premium ranges, claim process, renewal reminders |
| EdTech | Add course details, fees, demo class booking, scholarship info |
| Healthcare | Add clinic details, appointment booking, doctor availability |
| E-commerce | Add order status handling, return policy, refund process |

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

## Roadmap

### v1.1 — In Progress
- [x] Campaign manager (bulk calling from CSV)
- [x] Live dashboard with real-time transcripts
- [x] Smart callback scheduler

### v1.2 — Planned
- [ ] Upgrade to Gemini 2.5 Flash Native Audio
      (eliminates STT+TTS latency, true real-time conversation)
- [ ] WhatsApp follow-up after call ends
- [ ] A/B testing for different prompt scripts

### v2.0 — Vision
- [ ] Multi-tenant SaaS with client portal
- [ ] Call recording + replay with transcript sync
- [ ] Sentiment analysis and quality scoring
- [ ] CRM integrations (Salesforce, HubSpot, Zoho)




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
