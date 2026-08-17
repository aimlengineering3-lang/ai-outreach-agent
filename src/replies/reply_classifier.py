"""
Classifies an incoming email reply into a category using the LLM.
Classification only — never decides state transitions itself (that
remains the state_machine's job, driven by this classification result).
"""

import json
import re

from src.personalization.llm_client import generate


VALID_CATEGORIES = {"interested", "question", "not_interested", "unsubscribe", "other"}

CLASSIFICATION_PROMPT = """Classify this email reply into EXACTLY ONE of these categories:
- interested: expresses interest in the offer/service
- question: asks a question, needs more info
- not_interested: politely or firmly declines
- unsubscribe: explicitly asks to stop being contacted / remove from list
- other: anything that doesn't clearly fit above

Respond with ONLY the category word, nothing else.

REPLY TEXT:
{reply_text}

Category:"""


def classify_reply(reply_text: str) -> str:
    """
    Returns one of VALID_CATEGORIES. Defaults to "other" if the LLM
    output is unusable — never guesses "unsubscribe" or "interested"
    on unclear output, since those drive compliance-relevant actions.
    """
    prompt = CLASSIFICATION_PROMPT.format(reply_text=reply_text)

    try:
        raw = generate(prompt)
    except Exception:
        return "other"

    cleaned = re.sub(r"[^a-z_]", "", raw.strip().lower())

    if cleaned in VALID_CATEGORIES:
        return cleaned
    return "other"


if __name__ == "__main__":
    print(classify_reply("Please stop emailing me, remove me from your list."))
    print(classify_reply("This looks interesting, can you tell me more about pricing?"))
    print(classify_reply("Not interested, thanks."))