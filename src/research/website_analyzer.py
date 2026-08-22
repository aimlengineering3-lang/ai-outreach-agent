"""
Extracts structured business facts from a website's HTML using
BeautifulSoup — deterministic parsing, no LLM involved.

This produces the clean, structured input that the LLM (Phase 5) will
later use to pick 1-2 factual observations for personalization. The LLM
never sees raw HTML — only what this file has already extracted.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

import httpx
from bs4 import BeautifulSoup


@dataclass
class WebsiteFacts:
    """
    Structured, factual data extracted from a business website.
    Every field here is something we can point to in the actual HTML —
    nothing inferred or guessed.
    """
    title: Optional[str] = None
    meta_description: Optional[str] = None
    headings: list[str] = field(default_factory=list)       # H1/H2 text, useful for services
    has_emergency_language: bool = False                     # "24/7", "emergency service" mentions
    phone_numbers: list[str] = field(default_factory=list)
    emails: list[str] = field(default_factory=list)
    facebook_url: Optional[str] = None
    instagram_url: Optional[str] = None
    cta_texts: list[str] = field(default_factory=list)       # button/link text like "Book Now", "Get a Quote"
    fetch_succeeded: bool = False


EMERGENCY_KEYWORDS = [
    "24/7", "24 hour", "emergency service", "same day service", "same-day",
]

CTA_KEYWORDS = [
    "book now", "get a quote", "request a quote", "schedule", "call now",
    "contact us", "free estimate", "book online", "get started",
]

PHONE_PATTERN = re.compile(r"\(?\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
# Domains/extensions that indicate a regex match is NOT a real email —
# either a placeholder the site's template left in, or an image
# filename (e.g. "logo@2x.png") that superficially looks email-shaped.
PLACEHOLDER_EMAIL_DOMAINS = {
    "example.com", "domain.com", "yourdomain.com", "email.com",
    "test.com", "company.com", "yoursite.com", "sentry.io",
}
NON_EMAIL_EXTENSIONS = {
    "png", "jpg", "jpeg", "gif", "svg", "webp", "ico", "css", "js", "pdf", "woff", "woff2",
}


def _is_plausible_email(email: str) -> bool:
    """
    Filters out regex false-positives: image filenames using retina
    naming conventions (logo@2x.png) and known placeholder emails left
    in website templates (you@example.com). Both match the email regex
    syntactically but are never real contact addresses.
    """
    domain_part = email.split("@")[-1].lower()

    if domain_part in PLACEHOLDER_EMAIL_DOMAINS:
        return False

    extension = domain_part.rsplit(".", 1)[-1] if "." in domain_part else ""
    if extension in NON_EMAIL_EXTENSIONS:
        return False

    return True


def analyze_website(url: str, timeout: float = 10.0) -> WebsiteFacts:
    """
    Fetches a page and extracts structured facts from it.
    Returns fetch_succeeded=False (all other fields empty/None) if the
    site is unreachable — the caller must check this before trusting
    any other field.
    """
    try:
        response = httpx.get(
            url,
            timeout=timeout,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        html = response.text
    except (httpx.RequestError, httpx.HTTPStatusError):
        return WebsiteFacts(fetch_succeeded=False)

    soup = BeautifulSoup(html, "html.parser")
    visible_text = soup.get_text(separator=" ", strip=True)

    facts = WebsiteFacts(fetch_succeeded=True)

    # --- Title & meta description ---
    if soup.title and soup.title.string:
        facts.title = soup.title.string.strip()

    meta_desc_tag = soup.find("meta", attrs={"name": "description"})
    if meta_desc_tag and meta_desc_tag.get("content"):
        facts.meta_description = meta_desc_tag["content"].strip()

    # --- Headings (H1/H2 usually describe services) ---
    for tag in soup.find_all(["h1", "h2"]):
        text = tag.get_text(strip=True)
        if text:
            facts.headings.append(text)

    # --- Emergency/24-7 language ---
    lowered_text = visible_text.lower()
    facts.has_emergency_language = any(kw in lowered_text for kw in EMERGENCY_KEYWORDS)

    # --- Phone numbers & emails (dedup while preserving order) ---
    facts.phone_numbers = list(dict.fromkeys(PHONE_PATTERN.findall(visible_text)))
    # Run the email regex against BOTH the visible text AND the raw HTML.
    # Some sites write emails wrapped in angle brackets (e.g. "<info@x.com>")
    # as a plain-text convention — BeautifulSoup's parser can mistake that
    # for an (invalid) HTML tag and silently strip it from get_text(),
    # so scanning the raw HTML too catches emails that would otherwise
    # be lost.
    emails_from_text = EMAIL_PATTERN.findall(visible_text)
    emails_from_raw_html = EMAIL_PATTERN.findall(html)
    all_candidates = list(dict.fromkeys(emails_from_text + emails_from_raw_html))
    facts.emails = [e for e in all_candidates if _is_plausible_email(e)]
    # mailto: links are a more reliable source than visible text — many
    # sites put the email only in a mailto href (behind a "Contact" icon
    # or button), not as plain visible text.
    mailto_emails = [
        link["href"].replace("mailto:", "").split("?")[0].strip()
        for link in soup.find_all("a", href=True)
        if link["href"].lower().startswith("mailto:")
    ]
    for email in mailto_emails:
        if email and email not in facts.emails:
            facts.emails.append(email)

    # --- Social links ---
    for link in soup.find_all("a", href=True):
        href = link["href"]
        if "facebook.com" in href and not facts.facebook_url:
            facts.facebook_url = href
        elif "instagram.com" in href and not facts.instagram_url:
            facts.instagram_url = href

    # --- CTA texts: buttons and links whose text matches known CTA phrasing ---
    for tag in soup.find_all(["a", "button"]):
        text = tag.get_text(strip=True).lower()
        if any(kw in text for kw in CTA_KEYWORDS):
            facts.cta_texts.append(tag.get_text(strip=True))
    facts.cta_texts = list(dict.fromkeys(facts.cta_texts))  # dedup

    return facts


if __name__ == "__main__":
    result = analyze_website("https://www.example.com")
    print(result)
    
COMMON_CONTACT_PATHS = ["/contact", "/contact-us", "/contact-us/", "/about", "/about-us"]


def analyze_website_with_contact_fallback(base_url: str, timeout: float = 10.0) -> WebsiteFacts:
    """
    Runs analyze_website on the homepage. If no email was found there,
    tries a few common contact-page paths and merges any email found —
    many businesses only list contact info on a dedicated page, not
    the homepage.
    """
    facts = analyze_website(base_url, timeout=timeout)

    if facts.emails or not facts.fetch_succeeded:
        return facts

    base_url_clean = base_url.rstrip("/")

    for path in COMMON_CONTACT_PATHS:
        try:
            sub_facts = analyze_website(base_url_clean + path, timeout=timeout)
        except Exception:
            continue

        if sub_facts.fetch_succeeded and sub_facts.emails:
            facts.emails = sub_facts.emails
            if not facts.phone_numbers:
                facts.phone_numbers = sub_facts.phone_numbers
            break

    return facts