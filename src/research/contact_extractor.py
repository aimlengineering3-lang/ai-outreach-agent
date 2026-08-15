"""
Attempts to find an owner/contact NAME on a business website.

Critical rule (per architecture requirement): NEVER fabricate a name.
If no clear signal exists, this returns None — the caller must then use
a configured fallback greeting (e.g. "Hi {business_name} team,") instead
of inventing a person.
"""

import re
from typing import Optional

from bs4 import BeautifulSoup


# Patterns that typically precede a real name on "About Us" / "Team" pages.
# Intentionally narrow — a false positive here means fabricating a name,
# which is the one thing we're required never to do.
NAME_CONTEXT_PATTERNS = [
    r"(?:owner|founder|president)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)",
    r"([A-Z][a-z]+ [A-Z][a-z]+),?\s+(?:owner|founder|president)",
]


def extract_contact_name(html: str) -> Optional[str]:
    """
    Looks for a name near owner/founder-style context words.

    Design choice: this is intentionally conservative. A regex that's too
    eager to match "Firstname Lastname" patterns will produce false
    positives constantly (e.g. matching a customer testimonial's name,
    or a random capitalized phrase). We accept a high MISS rate here in
    exchange for near-zero fabrication risk — the fallback greeting exists
    precisely so a miss is not a failure.
    """
    soup = BeautifulSoup(html, "html.parser")
    visible_text = soup.get_text(separator=" ", strip=True)

    for pattern in NAME_CONTEXT_PATTERNS:
        match = re.search(pattern, visible_text)
        if match:
            return match.group(1).strip()

    return None


if __name__ == "__main__":
    sample_html = "<p>Founded by owner: John Smith in 2005.</p>"
    print(extract_contact_name(sample_html))  # Expect: John Smith

    sample_html_2 = "<p>We are a family business serving Houston since 1998.</p>"
    print(extract_contact_name(sample_html_2))  # Expect: None