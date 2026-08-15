"""
Renders email templates by substituting ONLY approved {variable}
placeholders. This file NEVER calls an LLM and NEVER rewrites the
template body — it is pure, deterministic string substitution.

This is the enforcement point for the "AI must not change the offer/
pitch/CTA" requirement: this function physically cannot alter anything
outside the {variable} placeholders the template author put there.
"""

import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


# The only variables personalization is allowed to fill.
# Adding a new variable means adding it here explicitly — nothing is
# available by default, which is the whole point of "controlled"
# personalization.
APPROVED_VARIABLES = {
    "first_name",
    "business_name",
    "city",
    "state",
    "niche",
    "meta_pixel_status",
    "website_observation",
}

PLACEHOLDER_PATTERN = re.compile(r"\{([a-zA-Z_][a-zA-Z0-9_]*)\}")


@dataclass
class RenderResult:
    rendered_body: str
    used_fallback_greeting: bool
    missing_variables: list[str] = field(default_factory=list)
    modification_log: Optional[dict] = None  # populated only if a minimal modification occurred


def render_template(
    template_body: str,
    variables: dict[str, Optional[str]],
    fallback_greeting: str = "Hi there,",
) -> RenderResult:
    """
    Substitutes {variable} placeholders in template_body with values
    from `variables`. Any placeholder not in APPROVED_VARIABLES is left
    untouched (fails loudly via missing_variables, never silently guessed).

    Special handling for {first_name}: if missing/empty, it is NOT left
    as a blank or invented name — the caller must have already placed
    a fallback-greeting-compatible template, OR this function substitutes
    the configured fallback_greeting as a documented minimal modification.
    """
    missing_variables: list[str] = []
    used_fallback_greeting = False
    modification_log = None

    def replace(match: re.Match) -> str:
        nonlocal used_fallback_greeting, modification_log
        var_name = match.group(1)

        if var_name not in APPROVED_VARIABLES:
            # Unapproved variable: leave the placeholder exactly as-is.
            # This makes the failure visible to the human operator instead
            # of silently blank or fabricated.
            missing_variables.append(var_name)
            return match.group(0)

        value = variables.get(var_name)

        if var_name == "first_name" and not value:
            # Missing owner name: never fabricate. Log this as a
            # documented minimal modification, not a silent rewrite.
            used_fallback_greeting = True
            modification_log = {
                "reason": "missing_owner_name",
                "original_placeholder": "{first_name}",
                "substituted_with": fallback_greeting,
                "timestamp": datetime.utcnow().isoformat(),
            }
            return fallback_greeting

        if value is None:
            missing_variables.append(var_name)
            return match.group(0)

        return str(value)

    rendered = PLACEHOLDER_PATTERN.sub(replace, template_body)

    return RenderResult(
        rendered_body=rendered,
        used_fallback_greeting=used_fallback_greeting,
        missing_variables=missing_variables,
        modification_log=modification_log,
    )


if __name__ == "__main__":
    template = (
        "{first_name}\n\n"
        "I noticed {business_name} in {city}, {state} might be missing "
        "the Meta Pixel on your website. {website_observation}\n\n"
        "Want a free trial? Just reply."
    )

    # Case 1: full data available
    result1 = render_template(
        template,
        {
            "first_name": "Hi John,",
            "business_name": "ABC Plumbing",
            "city": "Houston",
            "state": "TX",
            "meta_pixel_status": "MISSING",
            "website_observation": "Your site mentions 24/7 emergency service.",
        },
    )
    print("--- Case 1 (full data) ---")
    print(result1.rendered_body)
    print("Missing vars:", result1.missing_variables)

    # Case 2: owner name unknown -> fallback greeting
    result2 = render_template(
        template,
        {
            "first_name": None,
            "business_name": "Beyond Wow Plumbing",
            "city": "Austin",
            "state": "TX",
            "website_observation": "",
        },
        fallback_greeting="Hi Beyond Wow Plumbing team,",
    )
    print("\n--- Case 2 (no owner name) ---")
    print(result2.rendered_body)
    print("Used fallback:", result2.used_fallback_greeting)
    print("Modification log:", result2.modification_log)