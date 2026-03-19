"""
LLM Module — Google Gemini Flash
----------------------------------
Generates conversational responses using Gemini.
Loads the master prompt once at startup and reuses it for every call.
Handles rate limiting with automatic retry.

Usage:
    reply = await get_response(user_text, history, detected_lang)
"""

import os
import sys
import asyncio
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

# ── Paths ────────────────────────────────────────────────────
base_dir    = os.path.dirname(os.path.abspath(__file__))
project_dir = os.path.dirname(base_dir)
prompt_path = os.path.join(project_dir, "prompts", "master_prompt.txt")

# ── Load master prompt once at startup ───────────────────────
print(f"Loading prompt from: {prompt_path}")
with open(prompt_path, "r", encoding="utf-8") as f:
    MASTER_PROMPT = f.read()
print(f"Master prompt loaded. ({len(MASTER_PROMPT.split())} words)")


def normalize_lang(lang: str) -> str:
    """Convert full language names to 2-letter codes."""
    return {
        "hindi":    "hi",
        "gujarati": "gu",
        "tamil":    "ta",
        "telugu":   "te",
        "english":  "en",
        "marathi":  "mr",
    }.get(lang.lower().strip(), lang.lower().strip())


async def get_response(
    user_text: str,
    history: list,
    detected_lang: str = "hi"
) -> str:
    """
    Generate agent response using Gemini Flash.

    Args:
        user_text:     What the user said (transcribed text)
        history:       Conversation history as list of message dicts
        detected_lang: Language code detected by Whisper

    Returns:
        Agent's response as plain speakable text (no markdown)
    """
    try:
        lang = normalize_lang(detected_lang)
        messages = list(history)

        # Add language hint to current user message
        lang_note = f"[User is speaking in language code: {lang}]"
        messages.append({
            "role":  "user",
            "parts": [{"text": f"{lang_note}\n{user_text}"}]
        })

        # Retry up to 3 times if rate limited
        for attempt in range(3):
            try:
                response = client.models.generate_content(
                    model="gemini-2.0-flash-lite",
                    contents=messages,
                    config=types.GenerateContentConfig(
                        system_instruction=MASTER_PROMPT,
                        temperature=0.7,
                        max_output_tokens=500,
                    )
                )
                reply = response.text.strip()

                if not reply or len(reply.split()) < 3:
                    return "जी हाँ, मैं आपकी मदद कर सकता हूँ। कृपया बताएं।"

                return reply

            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    wait = 30 * (attempt + 1)
                    print(f"Rate limited. Waiting {wait}s... (attempt {attempt+1}/3)")
                    await asyncio.sleep(wait)
                else:
                    raise e

        return "क्षमा करें, एक moment रुकिए।"

    except Exception as e:
        print(f"LLM error: {e}")
        return "क्षमा करें, एक moment रुकिए।"


# ── Test Block ───────────────────────────────────────────────
if __name__ == "__main__":

    async def test():
        history = []
        tests = [
            ("नमस्ते, मुझे loan चाहिए",          "hi"),
            ("હા, મને personal loan જોઈએ છે",    "gu"),
            ("ok what is the interest rate",     "en"),
        ]
        for text, lang in tests:
            print(f"\nUser ({lang})  : {text}")
            reply = await get_response(text, history, lang)
            print(f"Agent         : {reply}")
            print(f"Word count    : {len(reply.split())} words")
            ends_ok = reply[-1] in ("?", "।", "!", ".")
            print(f"Ends properly : {'YES' if ends_ok else 'CHECK'}")

            history.append({"role": "user",  "parts": [{"text": text}]})
            history.append({"role": "model", "parts": [{"text": reply}]})
            await asyncio.sleep(5)

    asyncio.run(test())
