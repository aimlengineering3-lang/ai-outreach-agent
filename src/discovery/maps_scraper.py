"""
Scrapes business listings from Google Maps search results using Playwright.

Note: Google Maps' DOM structure changes periodically — selectors here
may need updates over time. This is expected and documented behavior
for any scraper against a site not offering a public API for this data.
"""

from dataclasses import dataclass
from typing import Callable, Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


@dataclass
class MapsListing:
    business_name: str
    address: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None


@dataclass
class ScrapeResult:
    listings: list[MapsListing]
    # True if the scroll loop stopped because it hit max_results, not
    # because Maps ran out of new listings — i.e. more businesses
    # likely still exist and re-running with a higher cap (or running
    # again later) could surface them. False means the loop stopped on
    # its own (repeated no-change scrolls), which means this is
    # genuinely everything Maps was willing to show for this query.
    reached_max_results: bool


def scrape_maps_listings(
    query: str,
    max_results: int = 10,
    headless: bool = True,
    should_visit: Optional[Callable[[str], bool]] = None,
) -> ScrapeResult:
    """
    Searches Google Maps for `query` (e.g. "plumbers in Houston, TX")
    and returns up to max_results business listings, plus whether the
    cap was actually reached (see ScrapeResult).

    should_visit: optional callback(business_name) -> bool, checked
    against the name Maps already shows in the list view — BEFORE
    opening that business's own page. Returning False skips visiting
    it entirely (used by callers to avoid revisiting businesses they
    already know about). This is only a name-based prefilter: a
    business that passes it can still turn out to be a duplicate once
    its website is known, so callers should still run their normal
    duplicate check on the returned listings too.
    """
    results: list[MapsListing] = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()

        search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        page.goto(search_url, timeout=60000)

        try:
            page.wait_for_selector('div[role="feed"]', timeout=10000)
        except PlaywrightTimeoutError:
            # Feed didn't load — could be a CAPTCHA, no results, or layout change.
            browser.close()
            return ScrapeResult(listings=results, reached_max_results=False)

        # Scroll the results feed to load more listings (Maps lazy-loads).
        feed = page.locator('div[role="feed"]')
        card_locator = page.locator('div[role="feed"] > div a[href*="/maps/place/"]')

        def collect_unique_candidates() -> list[tuple[str, str]]:
            # Each place's Maps URL is a stable, unique identifier — far
            # more reliable than counting DOM elements, since Maps can
            # render the same business more than once (e.g. an organic
            # + a "sponsored" slot). The list view's aria-label already
            # carries the business name, so callers can prefilter by
            # name before we ever open a page. dict preserves order
            # while deduping by href.
            raw_pairs = card_locator.evaluate_all(
                "els => els.map(el => [el.href, el.getAttribute('aria-label') || ''])"
            )
            seen: dict[str, str] = {}
            for href, name in raw_pairs:
                if href not in seen:
                    seen[href] = name
            return list(seen.items())

        # The feed container can appear before its listing cards render,
        # so give it a moment and retry once before concluding there are
        # genuinely zero results — otherwise a slow first render (e.g. a
        # city being scraped for the first time) gets misread as "no
        # businesses" and the whole scroll loop is skipped.
        candidates = collect_unique_candidates()
        if not candidates:
            page.wait_for_timeout(3000)
            candidates = collect_unique_candidates()

        if not candidates:
            # Still nothing after the retry — genuinely no results.
            browser.close()
            return ScrapeResult(listings=results, reached_max_results=False)

        previous_count = len(candidates)
        no_change_streak = 0

        for _ in range(60):
            if len(candidates) >= max_results:
                break

            feed.evaluate("el => el.scrollTop = el.scrollHeight")
            page.wait_for_timeout(1500)
            candidates = collect_unique_candidates()

            if len(candidates) > previous_count:
                previous_count = len(candidates)
                no_change_streak = 0
                continue

            page.wait_for_timeout(3000)
            candidates = collect_unique_candidates()

            if len(candidates) > previous_count:
                previous_count = len(candidates)
                no_change_streak = 0
                continue

            no_change_streak += 1

            # Stop only after repeated stalls, so temporary Maps
            # buffering does not cause businesses to be missed.
            if no_change_streak >= 5:
                break

        # Whether more listings likely exist beyond this scrape is about
        # how much Maps actually had to offer, independent of how many
        # we go on to visit below — so this is measured before any
        # should_visit filtering.
        reached_max_results = len(candidates) >= max_results
        candidates = candidates[:max_results]

        # Visit each place directly by its own URL rather than clicking
        # cards by index. Clicking a card can cause Maps to reorder or
        # re-render the feed underneath (e.g. re-centering the list on
        # the selected item), which was making later index-based clicks
        # land on a business already scraped — the same few businesses
        # got scraped over and over instead of moving through the list.
        # Navigating straight to each unique URL sidesteps that entirely.
        skipped_known = 0
        skipped_timeout = 0
        for href, name in candidates:
            if should_visit is not None and name and not should_visit(name):
                # Caller already knows this one (by name) — skip the
                # expensive page visit entirely.
                skipped_known += 1
                continue

            try:
                page.goto(href, timeout=15000)
                page.wait_for_selector('h1.DUwDvf', timeout=5000)
                page_name = page.locator("h1.DUwDvf").first.text_content(timeout=5000) or ""

                # The business name renders first; the website/phone/
                # address buttons in the same panel can still be
                # loading a moment after that — checking them too soon
                # (right after the name appears) was reading them as
                # "not present" when they just hadn't rendered yet.
                # This settle pause gives them a chance to show up
                # before we check.
                page.wait_for_timeout(1200)

                address = None
                address_el = page.locator('button[data-item-id="address"]')
                if address_el.count() > 0:
                    raw = address_el.first.get_attribute("aria-label")
                    address = raw.replace("Address: ", "").strip() if raw else None

                website = None
                website_el = page.locator('a[data-item-id="authority"]')
                if website_el.count() > 0:
                    website = website_el.first.get_attribute("href")

                phone = None
                phone_el = page.locator('button[data-item-id^="phone"]')
                if phone_el.count() > 0:
                    raw = phone_el.first.get_attribute("aria-label")
                    phone = raw.replace("Phone: ", "").strip() if raw else None

                if page_name.strip():
                    results.append(
                        MapsListing(
                            business_name=page_name.strip(),
                            address=address,
                            website=website,
                            phone=phone,
                        )
                    )
            except PlaywrightTimeoutError:
                skipped_timeout += 1
                continue

        browser.close()

    return ScrapeResult(listings=results, reached_max_results=reached_max_results)


if __name__ == "__main__":
    result = scrape_maps_listings("plumbers in Austin, TX", max_results=5, headless=False)
    for listing in result.listings:
        print(listing)
    print(f"Reached max_results cap: {result.reached_max_results}")