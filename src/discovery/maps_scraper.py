"""
Scrapes business listings from Google Maps search results using Playwright.

Note: Google Maps' DOM structure changes periodically — selectors here
may need updates over time. This is expected and documented behavior
for any scraper against a site not offering a public API for this data.
"""

import time
from dataclasses import dataclass
from typing import Optional

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


@dataclass
class MapsListing:
    business_name: str
    address: Optional[str] = None
    website: Optional[str] = None
    phone: Optional[str] = None


def scrape_maps_listings(
    query: str,
    max_results: int = 10,
    headless: bool = True,
) -> list[MapsListing]:
    """
    Searches Google Maps for `query` (e.g. "plumbers in Houston, TX")
    and returns up to max_results business listings.
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
            return results

        # Scroll the results feed to load more listings (Maps lazy-loads).
        feed = page.locator('div[role="feed"]')
        for _ in range(5):
            feed.evaluate("el => el.scrollTop = el.scrollHeight")
            time.sleep(1.5)

        cards = page.locator('div[role="feed"] > div a[href*="/maps/place/"]')
        count = min(cards.count(), max_results)

        for i in range(count):
            card = cards.nth(i)
            try:
                card.click()
                page.wait_for_timeout(2000)

                page.wait_for_selector('h1.DUwDvf', timeout=5000)
                name = page.locator("h1.DUwDvf").first.text_content(timeout=5000) or ""

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

                if name.strip():
                    results.append(
                        MapsListing(
                            business_name=name.strip(),
                            address=address,
                            website=website,
                            phone=phone,
                        )
                    )
            except PlaywrightTimeoutError:
                continue

        browser.close()

    return results


if __name__ == "__main__":
    listings = scrape_maps_listings("plumbers in Austin, TX", max_results=5, headless=False)
    for listing in listings:
        print(listing)