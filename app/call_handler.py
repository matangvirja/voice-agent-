"""
Twilio Call Handler
--------------------
Handles live phone call audio over WebSocket.
Receives G711 mulaw audio from Twilio, converts it to WAV,
runs STT → LLM → TTS pipeline, and streams audio back to caller.

Flow:
    Twilio WebSocket → mulaw audio → ffmpeg → WAV → Groq Whisper
    → Gemini LLM → Edge-TTS → MP3 → ffmpeg → mulaw → Twilio WebSocket
"""

import asyncio
import base64
import json
import os
import sys
import subprocess
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.stt      import transcribe
from app.llm      import get_response
from app.tts      import speak_to_bytes
from app.database import log_turn

# ── Audio Settings ───────────────────────────────────────────
SILENCE_THRESHOLD  = 50    # volume below this = silence (phone audio is quiet)
SILENCE_CHUNKS     = 15    # 1.5 seconds of silence = end of utterance
MIN_SPEECH_CHUNKS  = 3     # minimum chunks to count as speech
CHUNK_SIZE         = 160   # 20ms chunks at 8kHz for Twilio


def convert_mulaw_to_wav(mulaw_bytes: bytes) -> bytes:
    """Convert Twilio 8kHz G711 mulaw audio → 16kHz WAV for Whisper."""
    proc = subprocess.run([
        "ffmpeg",
        "-f", "mulaw", "-ar", "8000", "-ac", "1",
        "-i", "pipe:0",
        "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1",
        "-loglevel", "quiet"
    ], input=mulaw_bytes, capture_output=True)
    return proc.stdout


def convert_mp3_to_mulaw(mp3_bytes: bytes) -> bytes:
    """Convert Edge-TTS MP3 output → 8kHz G711 mulaw for Twilio playback."""
    proc = subprocess.run([
        "ffmpeg",
        "-i", "pipe:0",
        "-ar", "8000", "-ac", "1", "-f", "mulaw", "pipe:1",
        "-loglevel", "quiet"
    ], input=mp3_bytes, capture_output=True)
    return proc.stdout


class CallHandler:
    """Handles one phone call from start to end."""

    def __init__(
        self,
        websocket,
        call_id: str,
        name: str = "Sir/Ma'am",
        lang: str = "hi"
    ):
        self.ws             = websocket
        self.call_id        = call_id
        self.name           = name
        self.lang           = lang
        self.stream_sid     = None
        self.history        = []
        self.audio_chunks   = []
        self.silent_count   = 0
        self.speech_started = False

    def _get_greeting(self) -> str:
        """Return personalized greeting in the user's language."""
        greetings = {
            "hi": (
                f"नमस्ते {self.name}जी! मैं एक AI voice assistant हूँ। "
                "आपकी क्या मदद करूँ?"
            ),
            "gu": (
                f"નમસ્તે {self.name}જી! હું AI voice assistant છું. "
                "કઈ રીતે મદદ કરી શકું?"
            ),
            "en": (
                f"Hello {self.name}! I'm an AI voice assistant. "
                "How may I help you?"
            ),
        }
        return greetings.get(self.lang, greetings["hi"])

    async def handle(self):
        """Main WebSocket loop — processes Twilio audio events."""
        print(f"[Call {self.call_id}] Connected — {self.name} ({self.lang})")

        async for message in self.ws.iter_text():
            try:
                data  = json.loads(message)
                event = data.get("event")

                if event == "start":
                    self.stream_sid = data["start"]["streamSid"]
                    print(f"[Call {self.call_id}] Stream started")
                    # Greet caller AFTER stream_sid is confirmed
                    await self._speak(self._get_greeting(), self.lang)

                elif event == "media":
                    await self._process_audio_chunk(data)

                elif event == "stop":
                    print(f"[Call {self.call_id}] Call ended")
                    break

            except Exception as e:
                print(f"[Call {self.call_id}] Error: {e}")

    async def _process_audio_chunk(self, data: dict):
        """Accumulate audio and detect when user stops speaking."""
        audio_bytes = base64.b64decode(data["media"]["payload"])
        audio_arr   = np.frombuffer(audio_bytes, dtype=np.uint8).astype(np.float32)
        volume      = int(np.std(audio_arr))

        if volume > SILENCE_THRESHOLD:
            self.speech_started = True
            self.silent_count   = 0
            self.audio_chunks.append(audio_bytes)
        else:
            if self.speech_started:
                self.silent_count += 1
                self.audio_chunks.append(audio_bytes)
                if self.silent_count >= SILENCE_CHUNKS:
                    await self._process_utterance()

    async def _process_utterance(self):
        """Run STT → LLM → TTS on the accumulated audio."""
        if len(self.audio_chunks) < MIN_SPEECH_CHUNKS:
            self._reset_audio()
            return

        print(f"[Call {self.call_id}] Processing speech...")
        combined_mulaw = b"".join(self.audio_chunks)
        self._reset_audio()

        # Convert mulaw → WAV for Whisper
        wav_bytes = convert_mulaw_to_wav(combined_mulaw)
        if not wav_bytes:
            return

        # STT
        text, raw_lang = await transcribe(wav_bytes)
        if not text.strip():
            return

        lang_map = {
            "hindi":    "hi", "gujarati": "gu", "tamil": "ta",
            "telugu":   "te", "english":  "en", "marathi": "mr",
        }
        self.lang = lang_map.get(raw_lang.lower(), raw_lang.lower())
        print(f"[Call {self.call_id}] User ({self.lang}): {text}")
        await log_turn(self.call_id, "user", self.lang, text)

        # LLM
        reply = await get_response(text, self.history, self.lang)
        print(f"[Call {self.call_id}] Agent ({self.lang}): {reply}")
        await log_turn(self.call_id, "agent", self.lang, reply)

        # TTS → send to caller
        await self._speak(reply, self.lang)

        # Update history
        self.history.append({"role": "user",  "parts": [{"text": text}]})
        self.history.append({"role": "model", "parts": [{"text": reply}]})
        if len(self.history) > 20:
            self.history = self.history[-20:]

    async def _speak(self, text: str, lang: str):
        """Convert text to speech and stream back to Twilio caller."""
        try:
            mp3_bytes = await speak_to_bytes(text, lang)
            if not mp3_bytes:
                return

            mulaw_bytes = convert_mp3_to_mulaw(mp3_bytes)
            if not mulaw_bytes:
                return

            for i in range(0, len(mulaw_bytes), CHUNK_SIZE):
                chunk   = mulaw_bytes[i:i + CHUNK_SIZE]
                payload = base64.b64encode(chunk).decode("utf-8")
                await self.ws.send_json({
                    "event":     "media",
                    "streamSid": self.stream_sid,
                    "media":     {"payload": payload}
                })
            print(f"[Call {self.call_id}] Spoken: {text[:60]}...")

        except Exception as e:
            print(f"[Call {self.call_id}] Speak error: {e}")

    def _reset_audio(self):
        """Clear audio buffer after processing."""
        self.audio_chunks   = []
        self.silent_count   = 0
        self.speech_started = False
