"""
Thin wrapper around the Gemini API (cloud-hosted, runs on Google's own
servers — not on this machine). Kept separate from any specific task
(like observation selection or reply classification) so the provider
can be swapped later without touching business logic elsewhere.
"""

import os
import httpx
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("LLM_API_KEY", "")
DEFAULT_MODEL = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
GEMINI_URL_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def generate(prompt: str, model: str = None, timeout: float = 60.0) -> str:
    """
    Sends a prompt to the Gemini API and returns the raw text response.
    Raises if the API key is missing or the request fails — callers
    must handle this (e.g. skip personalization, fall back to generic
    template) rather than crash the pipeline.
    """
    if not GEMINI_API_KEY:
        raise RuntimeError(
            "LLM_API_KEY is not set in .env — get a free key at https://aistudio.google.com/apikey"
        )

    url = GEMINI_URL_TEMPLATE.format(model=model or DEFAULT_MODEL)

    response = httpx.post(
        url,
        headers={"x-goog-api-key": GEMINI_API_KEY, "Content-Type": "application/json"},
        json={"contents": [{"parts": [{"text": prompt}]}]},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data["candidates"][0]["content"]["parts"][0]["text"].strip()


if __name__ == "__main__":
    reply = generate("Reply with exactly one word: OK")
    print(reply)