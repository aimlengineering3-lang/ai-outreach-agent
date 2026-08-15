"""
Thin wrapper around the local Ollama API. Kept separate from any specific
task (like observation selection) so the LLM provider can be swapped later
(e.g. to a hosted API) without touching business logic elsewhere.
"""

import json
import httpx


OLLAMA_URL = "http://localhost:11434/api/generate"
DEFAULT_MODEL = "llama3.1:8b"


def generate(prompt: str, model: str = DEFAULT_MODEL, timeout: float = 60.0) -> str:
    """
    Sends a prompt to the local Ollama server and returns the raw text
    response. Raises if Ollama isn't running or the request fails —
    callers must handle this (e.g. skip personalization, fall back to
    generic template) rather than crash the pipeline.
    """
    response = httpx.post(
        OLLAMA_URL,
        json={"model": model, "prompt": prompt, "stream": False},
        timeout=timeout,
    )
    response.raise_for_status()
    data = response.json()
    return data.get("response", "").strip()


if __name__ == "__main__":
    reply = generate("Reply with exactly one word: OK")
    print(reply)