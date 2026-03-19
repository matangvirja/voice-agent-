"""
CRM Data Extractor — Gemini
-----------------------------
Extracts structured CRM data from call transcripts after each call ends.
Uses Gemini to parse natural language conversation into structured JSON.

Usage:
    crm_data = await extract_crm_data(transcript, language="hi")
"""

import os
import json
import asyncio
from pathlib import Path
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

EXTRACT_PROMPT = """
You are a CRM data extractor.
Read this call transcript and extract structured data.
Respond ONLY in valid JSON — no other text, no markdown, no code blocks.

JSON format:
{
  "outcome":        "interested|not_interested|callback|wrong_number|no_response",
  "interest_level": "high|medium|low|none",
  "next_action":    "callback|send_info|close|do_not_call",
  "main_objection": "price|timing|not_needed|already_have|other|none",
  "callback_time":  "specific time mentioned or none",
  "customer_name":  "name if mentioned or unknown",
  "key_facts":      ["list of important things user said"]
}
"""

FALLBACK_CRM = {
    "outcome":        "unknown",
    "interest_level": "unknown",
    "next_action":    "unknown",
    "main_objection": "none",
    "callback_time":  "none",
    "customer_name":  "unknown",
    "key_facts":      []
}


async def extract_crm_data(
    transcript: str,
    language: str = "hi"
) -> dict:
    """
    Extract structured CRM data from call transcript.
    Called once at the END of every call.

    Args:
        transcript: Full conversation as formatted text
        language:   Primary language used in the call

    Returns:
        Dictionary with structured CRM fields
    """
    try:
        prompt = f"{EXTRACT_PROMPT}\n\nTranscript:\n{transcript}"

        response = client.models.generate_content(
            model="gemini-2.0-flash-lite",
            contents=[{"role": "user", "parts": [{"text": prompt}]}],
            config=types.GenerateContentConfig(
                temperature=0.1,       # low = consistent JSON output
                max_output_tokens=400,
            )
        )
        raw = response.text.strip()

        # Remove markdown code blocks if Gemini adds them
        raw = raw.replace("```json", "").replace("```", "").strip()

        data = json.loads(raw)
        print("CRM data extracted successfully.")
        return data

    except json.JSONDecodeError:
        print(f"Could not parse JSON from extractor response.")
        return FALLBACK_CRM

    except Exception as e:
        print(f"Extractor error: {e}")
        return FALLBACK_CRM


# ── Test Block ───────────────────────────────────────────────
if __name__ == "__main__":
    async def test():
        transcript = """
USER: नमस्ते, मुझे personal loan चाहिए
AGENT: जी हाँ! आपको कितने का loan चाहिए?
USER: 1 lakh chahiye
AGENT: बिल्कुल! क्या मैं आपका नाम जान सकता हूँ?
USER: Rahul hoon main
AGENT: धन्यवाद Rahul जी! कल सुबह 10 बजे call करूँ?
USER: haan karo
        """
        result = await extract_crm_data(transcript, "hi")
        print(json.dumps(result, indent=2, ensure_ascii=False))

    asyncio.run(test())
