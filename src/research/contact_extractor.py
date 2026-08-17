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


NAME_CONTEXT_PATTERNS = [
    r"(?:owner|founder|president)[:\s]+([A-Z][a-z]+ [A-Z][a-z]+)",
    r"([A-Z][a-z]+ [A-Z][a-z]+),?\s+(?:owner|founder|president)",
]

# Words that indicate a matched "name" is actually a business/service
# term, not a person — rejecting these prevents fabricated-looking
# greetings like "Hi Plumbing Guide,".
NON_NAME_WORDS = {
    "plumbing", "hvac", "roofing", "electrical", "guide", "services",
    "company", "team", "group", "solutions", "systems", "customer",
    "home", "commercial", "emergency", "repair", "install", "install",
}


def _looks_like_a_person_name(candidate: str) -> bool:
    words = candidate.lower().split()
    if len(words) != 2:
        return False
    return not any(word in NON_NAME_WORDS for word in words)


def extract_contact_name(html: str) -> Optional[str]:
    soup = BeautifulSoup(html, "html.parser")
    visible_text = soup.get_text(separator=" ", strip=True)

    for pattern in NAME_CONTEXT_PATTERNS:
        match = re.search(pattern, visible_text)
        if match:
            candidate = match.group(1).strip()
            if _looks_like_a_person_name(candidate):
                return candidate

    return None


if __name__ == "__main__":
    print(extract_contact_name("<p>Founded by owner: John Smith in 2005.</p>"))       # John Smith
    print(extract_contact_name("<p>Best Plumbing Guide, owner recommended.</p>"))     # None (rejected)
    print(extract_contact_name("<p>Family business since 1998.</p>"))                  # None