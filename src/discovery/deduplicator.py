"""
Detects whether two lead records likely represent the same business,
using fuzzy matching on business name + website domain.

Why fuzzy matching: the same business often appears with slightly
different name spellings ("ABC Plumbing" vs "ABC Plumbing LLC") or
URL formats ("abcplumbing.com" vs "www.abcplumbing.com/") across
different discovery sources (search vs Maps). Exact string equality
would miss these and create duplicate database rows -> duplicate emails
to the same business, which damages sender reputation and looks
unprofessional.
"""

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Optional
from urllib.parse import urlparse


NAME_SIMILARITY_THRESHOLD = 0.85  # 0.0-1.0; tuned conservative (few false merges)


def normalize_domain(url: Optional[str]) -> Optional[str]:
    """
    Strips protocol, 'www.', and trailing slashes so different URL
    formats of the same site compare equal.

    Examples:
        "https://www.abcplumbing.com/" -> "abcplumbing.com"
        "http://abcplumbing.com"       -> "abcplumbing.com"
        "abcplumbing.com/contact"      -> "abcplumbing.com"
    """
    if not url:
        return None

    # urlparse expects a scheme to correctly split netloc from path;
    # if missing, prepend one so parsing works consistently.
    if not re.match(r"^https?://", url):
        url = "http://" + url

    parsed = urlparse(url)
    domain = parsed.netloc.lower()

    if domain.startswith("www."):
        domain = domain[4:]

    return domain or None


def normalize_business_name(name: str) -> str:
    """
    Lowercases and strips common business suffixes (LLC, Inc, Co, etc.)
    and punctuation, so "ABC Plumbing LLC" and "ABC Plumbing, Inc."
    compare more fairly.
    """
    name = name.lower().strip()
    name = re.sub(r"[.,]", "", name)
    suffixes = [r"\bllc\b", r"\binc\b", r"\bco\b", r"\bcorp\b", r"\bltd\b"]
    for suffix in suffixes:
        name = re.sub(suffix, "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def name_similarity(name_a: str, name_b: str) -> float:
    """
    Returns a 0.0-1.0 similarity ratio between two business names,
    after normalization. Uses Python's built-in difflib rather than a
    third-party fuzzy-matching library — no extra dependency needed for
    a task this well-served by the standard library.

    Time complexity: SequenceMatcher.ratio() is roughly O(n*m) in the
    length of the two strings in the worst case — negligible for short
    business names (a few dozen characters).
    """
    a = normalize_business_name(name_a)
    b = normalize_business_name(name_b)
    return SequenceMatcher(None, a, b).ratio()


@dataclass
class DuplicateCheckResult:
    is_duplicate: bool
    reason: str          # "domain_match" / "name_match" / "no_match"
    confidence: float    # 0.0-1.0, informational


def is_likely_duplicate(
    name_a: str,
    website_a: Optional[str],
    city_a: Optional[str],
    name_b: str,
    website_b: Optional[str],
    city_b: Optional[str],
) -> DuplicateCheckResult:
    """
    Decides whether two lead records likely represent the same business.

    Order of checks matters: domain match is checked first because it's
    the strongest signal (two businesses essentially never share a
    website domain). Name similarity is the fallback, and requires the
    city to also match — otherwise "ABC Plumbing" in Houston and
    "ABC Plumbing" in Dallas (a real, common occurrence with franchises
    and common business names) would incorrectly merge.
    """
    domain_a = normalize_domain(website_a)
    domain_b = normalize_domain(website_b)

    if domain_a and domain_b and domain_a == domain_b:
        return DuplicateCheckResult(is_duplicate=True, reason="domain_match", confidence=1.0)

    similarity = name_similarity(name_a, name_b)
    same_city = (
        city_a is not None
        and city_b is not None
        and city_a.strip().lower() == city_b.strip().lower()
    )

    if similarity >= NAME_SIMILARITY_THRESHOLD and same_city:
        return DuplicateCheckResult(is_duplicate=True, reason="name_match", confidence=similarity)

    return DuplicateCheckResult(is_duplicate=False, reason="no_match", confidence=similarity)


if __name__ == "__main__":
    # Same business, different sources with slightly different formatting
    result1 = is_likely_duplicate(
        "ABC Plumbing LLC", "https://www.abcplumbing.com/", "Houston",
        "ABC Plumbing", "http://abcplumbing.com", "Houston",
    )
    print("Same business, different URL format:", result1)

    # Same name, different city — should NOT be flagged as duplicate
    result2 = is_likely_duplicate(
        "ABC Plumbing", None, "Houston",
        "ABC Plumbing", None, "Dallas",
    )
    print("Same name, different city:", result2)

    # Clearly different businesses
    result3 = is_likely_duplicate(
        "ABC Plumbing", "https://abcplumbing.com", "Houston",
        "Elite HVAC Services", "https://elitehvac.com", "Houston",
    )
    print("Different businesses:", result3)