"""
Text-to-Speech Module — Microsoft Edge TTS
-------------------------------------------
Converts text to speech using Edge-TTS neural voices.
Completely free — no API key required.
Supports Hindi, Gujarati, Tamil, Telugu, Marathi, English.

Usage:
    await speak_to_file("नमस्ते!", "hi", "output.mp3")
    audio_bytes = await speak_to_bytes("Hello!", "en")
"""

import edge_tts
import asyncio

# Indian neural voices — all free, no API key needed
VOICES = {
    "hi": "hi-IN-SwaraNeural",    # Hindi female
    "gu": "gu-IN-DhwaniNeural",   # Gujarati female
    "ta": "ta-IN-PallaviNeural",  # Tamil female
    "te": "te-IN-MoazamNeural",   # Telugu male
    "mr": "mr-IN-AarohiNeural",   # Marathi female
    "en": "en-IN-NeerjaNeural",   # Indian English female
}
DEFAULT_VOICE = VOICES["hi"]


async def speak_to_file(
    text: str,
    lang: str = "hi",
    output_path: str = "output.mp3"
) -> str:
    """
    Convert text to speech and save as MP3 file.

    Args:
        text:        Text to speak
        lang:        Language code ("hi", "gu", "ta", "te", "mr", "en")
        output_path: Path to save the MP3 file

    Returns:
        Path to the saved audio file
    """
    voice = VOICES.get(lang, DEFAULT_VOICE)
    tts   = edge_tts.Communicate(text, voice)
    await tts.save(output_path)
    return output_path


async def speak_to_bytes(
    text: str,
    lang: str = "hi"
) -> bytes:
    """
    Convert text to speech and return as bytes.
    Used for streaming audio over phone calls.

    Args:
        text: Text to speak
        lang: Language code

    Returns:
        MP3 audio as bytes
    """
    voice       = VOICES.get(lang, DEFAULT_VOICE)
    tts         = edge_tts.Communicate(text, voice)
    audio_chunks = []

    async for chunk in tts.stream():
        if chunk["type"] == "audio":
            audio_chunks.append(chunk["data"])

    return b"".join(audio_chunks)


# ── Test Block ───────────────────────────────────────────────
if __name__ == "__main__":
    async def test():
        tests = [
            ("नमस्ते! मैं एक AI voice assistant हूँ। आपकी क्या मदद करूँ?", "hi"),
            ("નમસ્તે! હું AI voice assistant છું. કઈ રીતે મદદ કરી શકું?",   "gu"),
        ]
        for text, lang in tests:
            path = f"test_{lang}.mp3"
            await speak_to_file(text, lang, path)
            print(f"Saved: {path} — open and play this file!")

    asyncio.run(test())
