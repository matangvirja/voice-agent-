"""
Local Voice Pipeline — Mic → STT → LLM → TTS → Speaker
---------------------------------------------------------
Test the full voice agent on your laptop without any phone calls.
Speak into your mic, hear the agent respond in the same language.

Features:
- Smart silence detection (stops after 4 sec silence)
- Thinking phrases ("हाँ जी, एक second...") fill the gap
- Multi-language: Hindi, Gujarati, Tamil, Telugu, English
- Saves every turn to PostgreSQL
- Extracts CRM data when you press Ctrl+C

Run:
    python -m app.pipeline
"""

import asyncio
import os
import io
import sys
import subprocess
import random
from pathlib import Path

import sounddevice as sd
import scipy.io.wavfile as wavfile
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.stt       import transcribe
from app.llm       import get_response
from app.tts       import speak_to_file
from app.database  import init_db, start_call, log_turn, end_call
from app.extractor import extract_crm_data

# ── Settings ─────────────────────────────────────────────────
SAMPLE_RATE        = 16000
SILENCE_THRESHOLD  = 300    # volume below this = silence
SILENCE_SECONDS    = 4.0    # stop after 4 sec of silence
MAX_RECORD_SECONDS = 30     # never record more than 30 sec
CHUNK_DURATION     = 0.1    # check audio every 100ms

# ── Thinking phrases by language ─────────────────────────────
THINKING_PHRASES = {
    "hi":      ["हाँ जी, एक second...", "समझ गया, बताता हूँ...", "जी, देखता हूँ..."],
    "gu":      ["હા જી, એક second...", "સમજ્યો, જણાવું છું...", "જી, જોઉં છું..."],
    "ta":      ["ஒரு நிமிடம்...", "சரி, பார்க்கிறேன்..."],
    "te":      ["ఒక్క నిమిషం...", "చూస్తాను..."],
    "en":      ["Sure, one second...", "Let me check...", "Got it, give me a moment..."],
    "english": ["Sure, one second...", "Let me check..."],
    "hindi":   ["हाँ जी, एक second...", "समझ गया, बताता हूँ..."],
    "gujarati":["હા જી, એક second...", "સમજ્યો, જણાવું છું..."],
}


def normalize_lang(lang: str) -> str:
    return {
        "hindi":    "hi",
        "gujarati": "gu",
        "tamil":    "ta",
        "telugu":   "te",
        "english":  "en",
        "marathi":  "mr",
    }.get(lang.lower().strip(), lang.lower().strip())


def get_thinking_phrase(lang: str) -> str:
    lang = normalize_lang(lang)
    return random.choice(THINKING_PHRASES.get(lang, THINKING_PHRASES["hi"]))


# ── Smart Recording ──────────────────────────────────────────
def record_until_silence() -> bytes:
    """Record mic until 4 seconds of silence detected."""
    print("\n[Listening... stops after 4 sec silence]")
    chunks, silent_chunks, speaking_started = [], 0, False
    chunks_per_sec = int(1.0 / CHUNK_DURATION)
    silence_limit  = int(SILENCE_SECONDS * chunks_per_sec)
    max_chunks     = int(MAX_RECORD_SECONDS * chunks_per_sec)
    chunk_size     = int(SAMPLE_RATE * CHUNK_DURATION)

    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1,
                        dtype="int16") as stream:
        while len(chunks) < max_chunks:
            chunk, _ = stream.read(chunk_size)
            chunks.append(chunk.copy())
            volume = np.sqrt(np.mean(chunk.astype(np.float32) ** 2))
            if volume > SILENCE_THRESHOLD:
                speaking_started = True
                silent_chunks    = 0
                print(".", end="", flush=True)
            else:
                if speaking_started:
                    silent_chunks += 1
                    remaining = silence_limit - silent_chunks
                    if remaining <= 10:
                        print("_", end="", flush=True)
                if speaking_started and silent_chunks >= silence_limit:
                    print("\n[Silence detected — done]")
                    break

    buf = io.BytesIO()
    wavfile.write(buf, SAMPLE_RATE, np.concatenate(chunks, axis=0))
    return buf.getvalue()


# ── Audio Playback ───────────────────────────────────────────
def play_audio(path: str):
    if os.name == "nt":
        os.startfile(path)
    elif sys.platform == "darwin":
        subprocess.run(["open", path])
    else:
        subprocess.run(["xdg-open", path])


async def play_thinking_phrase(lang: str):
    phrase = get_thinking_phrase(lang)
    f      = str(Path(__file__).parent.parent / "thinking.mp3")
    await speak_to_file(phrase, lang, f)
    play_audio(f)
    print(f"[Thinking: '{phrase}']")


# ── One Conversation Turn ────────────────────────────────────
async def run_one_turn(
    history: list,
    call_id: str,
    last_lang: str
) -> tuple:
    # 1. Record
    audio_bytes = record_until_silence()

    # 2. STT
    text, raw_lang = await transcribe(audio_bytes)
    lang = normalize_lang(raw_lang)

    if not text.strip():
        print("[No speech detected]")
        return history, last_lang

    print(f"\nYou  ({lang}) : {text}")
    await log_turn(call_id, "user", lang, text)

    # 3. Thinking phrase + LLM (run simultaneously)
    thinking_task = asyncio.create_task(play_thinking_phrase(lang))
    llm_task      = asyncio.create_task(get_response(text, history, lang))
    await asyncio.gather(thinking_task, llm_task)
    reply = llm_task.result()
    print(f"Agent ({lang}) : {reply}")
    await log_turn(call_id, "agent", lang, reply)

    # 4. TTS + play
    reply_file = str(Path(__file__).parent.parent / "reply.mp3")
    await speak_to_file(reply, lang, reply_file)
    play_audio(reply_file)

    # 5. Update history (keep last 10 turns)
    history.append({"role": "user",  "parts": [{"text": text}]})
    history.append({"role": "model", "parts": [{"text": reply}]})
    if len(history) > 20:
        history = history[-20:]

    return history, lang


# ── Main Loop ────────────────────────────────────────────────
async def main():
    print("=" * 50)
    print("  Voice Agent — Groq + Gemini + Edge-TTS")
    print("=" * 50)
    print("  Speak Hindi, Gujarati, Tamil or English")
    print("  Press Ctrl+C to end call and save to database")
    print("=" * 50)

    await init_db()
    call_id    = await start_call("local_test")
    history    = []
    last_lang  = "hi"
    turn_count = 0

    try:
        while True:
            turn_count += 1
            print(f"\n{'─'*40}\n  Turn {turn_count}\n{'─'*40}")
            history, last_lang = await run_one_turn(
                history, call_id, last_lang
            )
            await asyncio.sleep(1)

    except KeyboardInterrupt:
        print("\n\nCall ended. Saving to database...")

    finally:
        if history:
            print("[Extracting call summary...]")
            transcript = "\n".join([
                f"{t['role'].upper()}: {t['parts'][0]['text']}"
                for t in history
            ])
            try:
                crm_data = await extract_crm_data(transcript, last_lang)
            except Exception:
                crm_data = {
                    "outcome": "unknown", "interest_level": "unknown",
                    "next_action": "unknown", "main_objection": "none",
                    "callback_time": "none", "customer_name": "unknown",
                    "key_facts": []
                }
            await end_call(call_id, history, last_lang, crm_data)
            print(f"\n{'='*50}")
            print(f"  Call saved to Supabase!")
            print(f"  Call ID    : {call_id}")
            print(f"  Turns      : {len(history)//2}")
            print(f"  Outcome    : {crm_data.get('outcome')}")
            print(f"  Interest   : {crm_data.get('interest_level')}")
            print(f"  Next action: {crm_data.get('next_action')}")
            print(f"{'='*50}")
        else:
            print("No conversation to save.")


if __name__ == "__main__":
    asyncio.run(main())
