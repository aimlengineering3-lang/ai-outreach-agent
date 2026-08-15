"""
Uses the LLM to select 1-2 FACTUAL observations from the structured
website facts already extracted by website_analyzer.py.

Critical constraint: the LLM only ever sees the structured facts dict
below — never raw HTML, and the prompt explicitly forbids inventing
anything not present in that dict. If the LLM's output can't be
verified against the input facts, it is discarded, not trusted blindly.
"""

import json
import re
from dataclasses import asdict

from src.personalization.llm_client import generate
from src.research.website_analyzer import WebsiteFacts


SYSTEM_INSTRUCTION = """You are selecting factual observations about a business website for a cold outreach email.

STRICT RULES:
- You may ONLY use facts that appear in the JSON data below. Do not add any fact, number, or claim not present in that data.
- Select at most 2 observations.
- Each observation must be a short, natural sentence (under 15 words) suitable for inserting into an email.
- If the data contains nothing genuinely useful for personalization, return an empty list.
- Respond with ONLY a JSON array of strings. No explanation, no markdown, no extra text.

Example valid response:
["Your site highlights 24/7 emergency service.", "You offer free estimates on your homepage."]
"""


def _strip_markdown_fences(text: str) -> str:
    """
    LLMs frequently wrap JSON in ```json ... ``` even when told not to.
    Strip these before attempting to parse.
    """
    text = re.sub(r"^```(?:json)?\s*", "", text.strip())
    text = re.sub(r"\s*```$", "", text.strip())
    return text.strip()


def select_observations(facts: WebsiteFacts) -> list[str]:
    """
    Returns a list of 0-2 factual observation strings, or an empty list
    if the LLM output is unusable (fail-safe: better to send an email
    with no personalized observation than to risk a fabricated one).
    """
    if not facts.fetch_succeeded:
        return []

    # Only pass the structured facts the LLM is allowed to use —
    # explicitly exclude fetch_succeeded (irrelevant to content).
    facts_dict = {
        "title": facts.title,
        "meta_description": facts.meta_description,
        "headings": facts.headings,
        "has_emergency_language": facts.has_emergency_language,
        "cta_texts": facts.cta_texts,
    }

    prompt = f"{SYSTEM_INSTRUCTION}\n\nWEBSITE DATA:\n{json.dumps(facts_dict, indent=2)}\n\nJSON array:"

    try:
        raw_response = generate(prompt)
    except Exception:
        # LLM unavailable or errored — fail safe, no observation rather
        # than a crashed pipeline.
        return []

    cleaned = _strip_markdown_fences(raw_response)

    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        return []

    if not isinstance(parsed, list):
        return []

    # Defensive validation: only keep strings, cap at 2, per the contract.
    observations = [item for item in parsed if isinstance(item, str)][:2]
    return observations


if __name__ == "__main__":
    sample_facts = WebsiteFacts(
        fetch_succeeded=True,
        title="ABC Plumbing - Houston's Trusted Plumber",
        meta_description="24/7 emergency plumbing services in Houston, TX.",
        headings=["Emergency Plumbing Services", "Free Estimates", "Serving Houston Since 1998"],
        has_emergency_language=True,
        cta_texts=["Book Now", "Get a Free Quote"],
    )

    observations = select_observations(sample_facts)
    print("Selected observations:")
    for obs in observations:
        print(" -", obs)