"""
Detects Meta Pixel, Google Analytics, and Google Tag Manager presence
on a website using deterministic signature matching — no LLM involved.

Why deterministic: these tools leave fixed, predictable string patterns
in HTML/JS. Regex matching is fast, free, and reliable for this — using
an LLM here would be slower, costlier, and non-deterministic for a task
that doesn't need language understanding.
"""

import re
from dataclasses import dataclass
from typing import Optional

import httpx


# Signature patterns — each tool leaves specific, well-documented strings.
META_PIXEL_PATTERNS = [
    r"fbq\(",
    r"connect\.facebook\.net/.*?/fbevents\.js",
    r"facebook\.com/tr\?",
]

GOOGLE_ANALYTICS_PATTERNS = [
    r"gtag\(",
    r"google-analytics\.com/analytics\.js",
    r"\bG-[A-Z0-9]{6,}\b",   # GA4 measurement ID
    r"\bUA-\d{4,}-\d+\b",    # legacy Universal Analytics ID
]

GOOGLE_TAG_MANAGER_PATTERNS = [
    r"googletagmanager\.com/gtm\.js",
    r"\bGTM-[A-Z0-9]{4,}\b",
]


@dataclass
class TechDetectionResult:
    """
    Holds the outcome for one site. Each field is PRESENT/MISSING/UNKNOWN —
    never a forced boolean, per the requirement that uncertain evidence
    must not be reported as a definite absence.
    """
    meta_pixel: str
    google_analytics: str
    gtm: str
    fetch_succeeded: bool


def _search_patterns(html: str, patterns: list[str]) -> bool:
    """
    Returns True if ANY pattern matches the HTML. re.search stops at the
    first match per pattern — we don't need every occurrence, just whether
    the signature exists at all.

    Time complexity: O(n * m) where n = len(html), m = number of patterns.
    For a handful of patterns against a single page, this is negligible
    (milliseconds), so no need to optimize further (e.g. combining into
    one compiled alternation regex) unless profiling shows otherwise.
    """
    for pattern in patterns:
        if re.search(pattern, html, re.IGNORECASE):
            return True
    return False


def detect_tech_static(url: str, timeout: float = 10.0) -> TechDetectionResult:
    # If the "website" is actually a social media profile page (not the
    # business's own site), we cannot make any determination about their
    # tracking setup — the concept doesn't apply the same way, and these
    # platforms typically block/limit scraping anyway. Report UNKNOWN
    # rather than a potentially misleading MISSING.
    social_platforms = ["facebook.com", "instagram.com", "linkedin.com/company", "yelp.com", "twitter.com", "x.com"]
    if any(platform in url.lower() for platform in social_platforms):
        return TechDetectionResult(
            meta_pixel="UNKNOWN",
            google_analytics="UNKNOWN",
            gtm="UNKNOWN",
            fetch_succeeded=False,
        )

    try:
        response = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        html = response.text
    except (httpx.RequestError, httpx.HTTPStatusError):
        # Site unreachable, timed out, or returned an error status.
        # We cannot make any claim about tech presence — everything UNKNOWN.
        return TechDetectionResult(
            meta_pixel="UNKNOWN",
            google_analytics="UNKNOWN",
            gtm="UNKNOWN",
            fetch_succeeded=False,
        )

    pixel_found = _search_patterns(html, META_PIXEL_PATTERNS)
    ga_found = _search_patterns(html, GOOGLE_ANALYTICS_PATTERNS)
    gtm_found = _search_patterns(html, GOOGLE_TAG_MANAGER_PATTERNS)

    return TechDetectionResult(
        meta_pixel="PRESENT" if pixel_found else "MISSING",
        google_analytics="PRESENT" if ga_found else "MISSING",
        gtm="PRESENT" if gtm_found else "MISSING",
        fetch_succeeded=True,
    )


if __name__ == "__main__":
    # Quick manual test against a real site — replace with any URL you like.
    result = detect_tech_static("https://www.example.com")
    print(result)