"""
Twilio Call Handler — with Live Dashboard Broadcasting
-------------------------------------------------------
Every conversation turn is broadcast to all connected
dashboard clients via WebSocket in real time.
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

from app.stt       import transcribe
from app.llm       import get_response
from app.tts       import speak_to_bytes
from app.database  import log_turn
from app.dashboard import broadcast

SILENCE_THRESHOLD  = 50
SILENCE_CHUNKS     = 15
MIN_SPEECH_CHUNKS  = 3
CHUNK_SIZE         = 160


def convert_mulaw_to_wav(mulaw_bytes: bytes) -> bytes:
    proc = subprocess.run([
        "ffmpeg", "-f", "mulaw", "-ar", "8000", "-ac", "1",
        "-i", "pipe:0",
        "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1",
        "-loglevel", "quiet"
    ], input=mulaw_bytes, capture_output=True)
    return proc.stdout


def convert_mp3_to_mulaw(mp3_bytes: bytes) -> bytes:
    proc = subprocess.run([
        "ffmpeg", "-i", "pipe:0",
        "-ar", "8000", "-ac", "1", "-f", "mulaw", "pipe:1",
        "-loglevel", "quiet"
    ], input=mp3_bytes, capture_output=True)
    return proc.stdout


class CallHandler:

    def __init__(self, websocket, call_id: str,
                 name: str = "Sir/Ma'am", lang: str = "hi"):
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
        greetings = {
            "hi": f"नमस्ते {self.name}जी! मैं एक AI voice assistant हूँ। आपकी क्या मदद करूँ?",
            "gu": f"નમસ્તે {self.name}જી! હું AI voice assistant છું. કઈ રીતે મદદ કરી શકું?",
            "en": f"Hello {self.name}! I'm an AI voice assistant. How may I help you?",
        }
        return greetings.get(self.lang, greetings["hi"])

    async def handle(self):
        print(f"[Call {self.call_id}] Connected — {self.name} ({self.lang})")

        await broadcast({
            "type":    "call_started",
            "call_id": self.call_id,
            "phone":   self.name,
            "lang":    self.lang,
        })

        async for message in self.ws.iter_text():
            try:
                data  = json.loads(message)
                event = data.get("event")

                if event == "start":
                    self.stream_sid = data["start"]["streamSid"]
                    print(f"[Call {self.call_id}] Stream started — sid: {self.stream_sid}")
                    greeting = self._get_greeting()
                    await self._speak(greeting, self.lang)

                    await broadcast({
                        "type":     "turn",
                        "call_id":  self.call_id,
                        "role":     "agent",
                        "text":     greeting,
                        "language": self.lang,
                    })

                elif event == "media":
                    await self._process_audio_chunk(data)

                elif event == "stop":
                    print(f"[Call {self.call_id}] Call ended")
                    break

            except Exception as e:
                print(f"[Call {self.call_id}] Error in handle loop: {e}")
                import traceback
                traceback.print_exc()

        await broadcast({
            "type":    "call_ended",
            "call_id": self.call_id,
        })

    async def _process_audio_chunk(self, data: dict):
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
        if len(self.audio_chunks) < MIN_SPEECH_CHUNKS:
            self._reset_audio()
            return

        print(f"[Call {self.call_id}] Processing speech...")
        combined_mulaw = b"".join(self.audio_chunks)
        self._reset_audio()

        wav_bytes = convert_mulaw_to_wav(combined_mulaw)
        if not wav_bytes:
            print(f"[Call {self.call_id}] ffmpeg mulaw→wav failed — is ffmpeg installed?")
            return

        text, raw_lang = await transcribe(wav_bytes)
        if not text.strip():
            return

        lang_map = {
            "hindi":    "hi", "gujarati": "gu", "tamil":   "ta",
            "telugu":   "te", "english":  "en", "marathi": "mr",
        }
        self.lang = lang_map.get(raw_lang.lower(), raw_lang.lower())
        print(f"[Call {self.call_id}] User ({self.lang}): {text}")

        await log_turn(self.call_id, "user", self.lang, text)

        await broadcast({
            "type":     "turn",
            "call_id":  self.call_id,
            "role":     "user",
            "text":     text,
            "language": self.lang,
        })

        reply = await get_response(text, self.history, self.lang)
        print(f"[Call {self.call_id}] Agent ({self.lang}): {reply}")

        await log_turn(self.call_id, "agent", self.lang, reply)

        await broadcast({
            "type":     "turn",
            "call_id":  self.call_id,
            "role":     "agent",
            "text":     reply,
            "language": self.lang,
        })

        await self._speak(reply, self.lang)

        self.history.append({"role": "user",  "parts": [{"text": text}]})
        self.history.append({"role": "model", "parts": [{"text": reply}]})
        if len(self.history) > 20:
            self.history = self.history[-20:]

    async def _speak(self, text: str, lang: str):
        try:
            if not self.stream_sid:
                print(f"[Call {self.call_id}] Cannot speak — stream_sid is None")
                return

            mp3_bytes = await speak_to_bytes(text, lang)
            if not mp3_bytes:
                print(f"[Call {self.call_id}] TTS returned empty bytes")
                return

            mulaw_bytes = convert_mp3_to_mulaw(mp3_bytes)
            if not mulaw_bytes:
                print(f"[Call {self.call_id}] ffmpeg mp3→mulaw failed — is ffmpeg installed?")
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
            import traceback
            traceback.print_exc()

    def _reset_audio(self):
        self.audio_chunks   = []
        self.silent_count   = 0
        self.speech_started = False

# """
# Twilio Call Handler — with Live Dashboard Broadcasting
# -------------------------------------------------------
# Every conversation turn is broadcast to all connected
# dashboard clients via WebSocket in real time.
# """

# import asyncio
# import base64
# import json
# import os
# import sys
# import subprocess
# import numpy as np
# from pathlib import Path

# sys.path.insert(0, str(Path(__file__).parent.parent))

# from app.stt       import transcribe
# from app.llm       import get_response
# from app.tts       import speak_to_bytes
# from app.database  import log_turn
# from app.dashboard import broadcast           # ← new

# SILENCE_THRESHOLD  = 50
# SILENCE_CHUNKS     = 15
# MIN_SPEECH_CHUNKS  = 3
# CHUNK_SIZE         = 160


# def convert_mulaw_to_wav(mulaw_bytes: bytes) -> bytes:
#     proc = subprocess.run([
#         "ffmpeg", "-f", "mulaw", "-ar", "8000", "-ac", "1",
#         "-i", "pipe:0",
#         "-ar", "16000", "-ac", "1", "-f", "wav", "pipe:1",
#         "-loglevel", "quiet"
#     ], input=mulaw_bytes, capture_output=True)
#     return proc.stdout


# def convert_mp3_to_mulaw(mp3_bytes: bytes) -> bytes:
#     proc = subprocess.run([
#         "ffmpeg", "-i", "pipe:0",
#         "-ar", "8000", "-ac", "1", "-f", "mulaw", "pipe:1",
#         "-loglevel", "quiet"
#     ], input=mp3_bytes, capture_output=True)
#     return proc.stdout


# class CallHandler:

#     def __init__(self, websocket, call_id: str,
#                  name: str = "Sir/Ma'am", lang: str = "hi"):
#         self.ws             = websocket
#         self.call_id        = call_id
#         self.name           = name
#         self.lang           = lang
#         self.stream_sid     = None
#         self.history        = []
#         self.audio_chunks   = []
#         self.silent_count   = 0
#         self.speech_started = False

#     def _get_greeting(self) -> str:
#         greetings = {
#             "hi": f"नमस्ते {self.name}जी! मैं एक AI voice assistant हूँ। आपकी क्या मदद करूँ?",
#             "gu": f"નમસ્તે {self.name}જી! હું AI voice assistant છું. કઈ રીતે મદદ કરી શકું?",
#             "en": f"Hello {self.name}! I'm an AI voice assistant. How may I help you?",
#         }
#         return greetings.get(self.lang, greetings["hi"])

#     async def handle(self):
#         print(f"[Call {self.call_id}] Connected — {self.name} ({self.lang})")

#         # ── Broadcast call started to dashboard ──
#         await broadcast({
#             "type":    "call_started",
#             "call_id": self.call_id,
#             "phone":   self.name,
#             "lang":    self.lang,
#         })

#         async for message in self.ws.iter_text():
#             try:
#                 data  = json.loads(message)
#                 event = data.get("event")

#                 if event == "start":
#                     self.stream_sid = data["start"]["streamSid"]
#                     print(f"[Call {self.call_id}] Stream started")
#                     greeting = self._get_greeting()
#                     await self._speak(greeting, self.lang)

#                     # ── Broadcast agent greeting to dashboard ──
#                     await broadcast({
#                         "type":     "turn",
#                         "call_id":  self.call_id,
#                         "role":     "agent",
#                         "text":     greeting,
#                         "language": self.lang,
#                     })

#                 elif event == "media":
#                     await self._process_audio_chunk(data)

#                 elif event == "stop":
#                     print(f"[Call {self.call_id}] Call ended")
#                     break

#             except Exception as e:
#                 print(f"[Call {self.call_id}] Error: {e}")

#         # ── Broadcast call ended to dashboard ──
#         await broadcast({
#             "type":    "call_ended",
#             "call_id": self.call_id,
#         })

#     async def _process_audio_chunk(self, data: dict):
#         audio_bytes = base64.b64decode(data["media"]["payload"])
#         audio_arr   = np.frombuffer(audio_bytes, dtype=np.uint8).astype(np.float32)
#         volume      = int(np.std(audio_arr))

#         if volume > SILENCE_THRESHOLD:
#             self.speech_started = True
#             self.silent_count   = 0
#             self.audio_chunks.append(audio_bytes)
#         else:
#             if self.speech_started:
#                 self.silent_count += 1
#                 self.audio_chunks.append(audio_bytes)
#                 if self.silent_count >= SILENCE_CHUNKS:
#                     await self._process_utterance()

#     async def _process_utterance(self):
#         if len(self.audio_chunks) < MIN_SPEECH_CHUNKS:
#             self._reset_audio()
#             return

#         print(f"[Call {self.call_id}] Processing speech...")
#         combined_mulaw = b"".join(self.audio_chunks)
#         self._reset_audio()

#         wav_bytes = convert_mulaw_to_wav(combined_mulaw)
#         if not wav_bytes:
#             return

#         text, raw_lang = await transcribe(wav_bytes)
#         if not text.strip():
#             return

#         lang_map = {
#             "hindi":    "hi", "gujarati": "gu", "tamil":   "ta",
#             "telugu":   "te", "english":  "en", "marathi": "mr",
#         }
#         self.lang = lang_map.get(raw_lang.lower(), raw_lang.lower())
#         print(f"[Call {self.call_id}] User ({self.lang}): {text}")

#         await log_turn(self.call_id, "user", self.lang, text)

#         # ── Broadcast user turn to dashboard ──
#         await broadcast({
#             "type":     "turn",
#             "call_id":  self.call_id,
#             "role":     "user",
#             "text":     text,
#             "language": self.lang,
#         })

#         reply = await get_response(text, self.history, self.lang)
#         print(f"[Call {self.call_id}] Agent ({self.lang}): {reply}")

#         await log_turn(self.call_id, "agent", self.lang, reply)

#         # ── Broadcast agent turn to dashboard ──
#         await broadcast({
#             "type":     "turn",
#             "call_id":  self.call_id,
#             "role":     "agent",
#             "text":     reply,
#             "language": self.lang,
#         })

#         await self._speak(reply, self.lang)

#         self.history.append({"role": "user",  "parts": [{"text": text}]})
#         self.history.append({"role": "model", "parts": [{"text": reply}]})
#         if len(self.history) > 20:
#             self.history = self.history[-20:]

   
#     async def _speak(self, text: str, lang: str):
#     try:
#         if not self.stream_sid:
#             print(f"[Call {self.call_id}] Cannot speak — stream_sid not set yet")
#             return

#         mp3_bytes = await speak_to_bytes(text, lang)
#         if not mp3_bytes:
#             print(f"[Call {self.call_id}] TTS returned empty bytes")
#             return

#         mulaw_bytes = convert_mp3_to_mulaw(mp3_bytes)
#         if not mulaw_bytes:
#             print(f"[Call {self.call_id}] ffmpeg mulaw conversion failed — is ffmpeg installed?")
#             return

#         for i in range(0, len(mulaw_bytes), CHUNK_SIZE):
#             chunk   = mulaw_bytes[i:i + CHUNK_SIZE]
#             payload = base64.b64encode(chunk).decode("utf-8")
#             await self.ws.send_json({
#                 "event":     "media",
#                 "streamSid": self.stream_sid,
#                 "media":     {"payload": payload}
#             })
#         print(f"[Call {self.call_id}] Spoken: {text[:60]}...")

#     except Exception as e:
#         print(f"[Call {self.call_id}] Speak error: {e}")
#         import traceback
#         traceback.print_exc()
#     def _reset_audio(self):
#         self.audio_chunks   = []
#         self.silent_count   = 0
#         self.speech_started = False
# # async def _speak(self, text: str, lang: str):
# #         try:
# #             mp3_bytes = await speak_to_bytes(text, lang)
# #             if not mp3_bytes:
# #                 return

# #             mulaw_bytes = convert_mp3_to_mulaw(mp3_bytes)
# #             if not mulaw_bytes:
# #                 return

# #             for i in range(0, len(mulaw_bytes), CHUNK_SIZE):
# #                 chunk   = mulaw_bytes[i:i + CHUNK_SIZE]
# #                 payload = base64.b64encode(chunk).decode("utf-8")
# #                 await self.ws.send_json({
# #                     "event":     "media",
# #                     "streamSid": self.stream_sid,
# #                     "media":     {"payload": payload}
# #                 })
# #             print(f"[Call {self.call_id}] Spoken: {text[:60]}...")

# #         except Exception as e:
# #             print(f"[Call {self.call_id}] Speak error: {e}")

# #     def _reset_audio(self):
# #         self.audio_chunks   = []
# #         self.silent_count   = 0
# #         self.speech_started = False
