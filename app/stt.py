"""
Speech-to-Text Module — Groq Whisper API
-----------------------------------------
Transcribes audio bytes to text using Groq's hosted Whisper large-v3.
Supports auto language detection for Hindi, Gujarati, Tamil, Telugu, English.

Usage:
    text, lang = await transcribe(audio_bytes)
    text, lang = await transcribe(audio_bytes, hint_lang="hi")
"""

import os
from pathlib import Path
from groq import Groq
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

client = Groq(api_key=os.getenv("GROQ_API_KEY"))


async def transcribe(
    audio_bytes: bytes,
    hint_lang: str = "hi"
) -> tuple[str, str]:
    """
    Transcribe audio bytes using Groq Whisper large-v3.

    Args:
        audio_bytes: Raw audio bytes (WAV or MP3 format)
        hint_lang:   Language hint for better accuracy
                     "hi"=Hindi, "gu"=Gujarati, "ta"=Tamil,
                     "te"=Telugu, "en"=English

    Returns:
        Tuple of (transcribed_text, detected_language_code)
        Example: ("नमस्ते कैसे हैं", "hi")
    """
    try:
        result = client.audio.transcriptions.create(
            file=("audio.mp3", audio_bytes),
            model="whisper-large-v3",
            response_format="verbose_json",
            language=hint_lang
        )
        text = result.text.strip()
        lang = getattr(result, "language", hint_lang)
        return text, lang

    except Exception as e:
        print(f"STT error: {e}")
        return "", hint_lang  # safe fallback


# ── Test Block ───────────────────────────────────────────────
if __name__ == "__main__":
    import asyncio
    import os

    async def test():
        # Find test audio relative to project root
        base_dir    = os.path.dirname(os.path.abspath(__file__))
        project_dir = os.path.dirname(base_dir)
        root_dir    = os.path.dirname(project_dir)

        # Try common test file names
        for fname in ["test_audio.mp3", "test_audio.wav"]:
            audio_path = os.path.join(root_dir, fname)
            if os.path.exists(audio_path):
                print(f"Testing with: {audio_path}")
                with open(audio_path, "rb") as f:
                    audio = f.read()
                text, lang = await transcribe(audio)
                print(f"Detected language : {lang}")
                print(f"Transcribed text  : {text}")
                return

        print("No test audio found. Place test_audio.mp3 in project root.")

    asyncio.run(test())
