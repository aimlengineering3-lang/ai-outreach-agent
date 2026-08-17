"""
Generates a SAFE acknowledgement-only reply for use during unattended
(night) hours. Strictly forbidden from inventing pricing, results,
guarantees, or claiming to be a specific person — this is enforced by
using a fixed template, NOT free LLM generation, because free generation
is exactly how fabricated claims slip in.
"""

from dataclasses import dataclass


# Deliberately NOT LLM-generated. A safe acknowledgement has no need for
# language creativity, and fixed text guarantees zero fabrication risk —
# the one place in this whole system where "just use a template" is
# strictly safer than involving the LLM at all.
SAFE_ACKNOWLEDGEMENT_TEMPLATE = (
    "Hi {first_name_or_fallback},\n\n"
    "Thanks for your reply! I've received your message and will get back "
    "to you as soon as I'm available.\n\n"
    "Best,\n"
    "{sender_name}"
)


@dataclass
class NightResponse:
    body: str
    is_safe_acknowledgement: bool = True


def generate_night_response(
    first_name: str | None,
    sender_name: str,
    fallback_greeting: str = "there",
) -> NightResponse:
    """
    Returns a fixed, safe acknowledgement. Never claims a specific
    response time, never invents context about the reply's content,
    never pretends the sender has already reviewed anything specific.
    """
    greeting = first_name if first_name else fallback_greeting
    body = SAFE_ACKNOWLEDGEMENT_TEMPLATE.format(
        first_name_or_fallback=greeting, sender_name=sender_name
    )
    return NightResponse(body=body)


if __name__ == "__main__":
    response = generate_night_response(first_name="John", sender_name="Usman")
    print(response.body)
    print("---")
    response2 = generate_night_response(first_name=None, sender_name="Usman")
    print(response2.body)