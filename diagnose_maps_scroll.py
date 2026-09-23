"""
DIAGNOSTIC ONLY — does not touch maps_scraper.py or the database.

Mirrors the real scroll loop step-by-step but prints what's happening at
every stage, and saves a screenshot + the feed's raw HTML so we can see
exactly what Google served. Use this on a city you KNOW should return
many businesses (one that used to work).

Place this file in your project root (same folder as app/, src/) and run:
    python diagnose_maps_scroll.py "plumbing" "Fairbanks" "AK"

Optional 4th arg = max_results to aim for (default 150).
Always runs with a visible browser window (headless=False) so you can
watch what happens too.

Outputs (in a new diagnostics/ folder next to this script):
    diagnostics/screenshot.png   - what the page looked like at the end
    diagnostics/feed.html        - raw HTML of the results feed container
    (plus everything printed to the console)

After running, paste me the FULL console output (and the screenshot if
possible) and I'll pinpoint the exact cause.
"""

import os
import sys
import time

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError


def main():
    if len(sys.argv) < 4:
        print('Usage: python diagnose_maps_scroll.py "<niche>" "<city>" "<state>" [max_results]')
        sys.exit(1)

    niche, city, state = sys.argv[1], sys.argv[2], sys.argv[3]
    max_results = int(sys.argv[4]) if len(sys.argv) > 4 else 150
    query = f"{niche} in {city}, {state}"

    out_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "diagnostics")
    os.makedirs(out_dir, exist_ok=True)

    print(f"Query: '{query}'  (target max_results={max_results})")
    print("Launching browser (visible)...\n")

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()

        search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
        print(f"Navigating to: {search_url}")
        page.goto(search_url, timeout=60000)

        print(f"Landed on URL : {page.url}")
        print(f"Page title    : {page.title()}\n")

        # Flag anything that looks like a consent wall / CAPTCHA / block page
        # BEFORE we even look for the feed.
        body_text = ""
        try:
            body_text = page.locator("body").inner_text(timeout=5000)
        except Exception:
            pass
        lowered = body_text.lower()
        for flag in ["before you continue", "unusual traffic", "captcha", "consent.google", "i'm not a robot"]:
            if flag in lowered or flag in page.url.lower():
                print(f"!!! POSSIBLE BLOCK/CONSENT PAGE DETECTED (matched: '{flag}') !!!")
                print("This alone could explain a collapse to a handful of results.\n")

        try:
            page.wait_for_selector('div[role="feed"]', timeout=10000)
            print("Feed container found.\n")
        except PlaywrightTimeoutError:
            print("Feed container NEVER appeared within 10s.")
            page.screenshot(path=os.path.join(out_dir, "screenshot.png"), full_page=True)
            print(f"Saved screenshot to {out_dir}/screenshot.png — open it and look.")
            browser.close()
            return

        feed = page.locator('div[role="feed"]')
        card_locator = page.locator('div[role="feed"] > div a[href*="/maps/place/"]')

        def collect():
            raw_pairs = card_locator.evaluate_all(
                "els => els.map(el => [el.href, el.getAttribute('aria-label') || ''])"
            )
            seen = {}
            for href, name in raw_pairs:
                if href not in seen:
                    seen[href] = name
            return list(seen.items())

        def scroll_metrics():
            return feed.evaluate("el => ({scrollTop: el.scrollTop, scrollHeight: el.scrollHeight, clientHeight: el.clientHeight})")

        candidates = collect()
        print(f"[t=0] Initial candidates found: {len(candidates)}")
        m = scroll_metrics()
        print(f"      feed scrollTop={m['scrollTop']} scrollHeight={m['scrollHeight']} clientHeight={m['clientHeight']}")
        if m['scrollHeight'] <= m['clientHeight']:
            print("      !!! scrollHeight <= clientHeight -> this element has NOTHING to scroll.")
            print("      !!! This means div[role=\"feed\"] is no longer the actual scrollable list container.\n")

        previous_count = len(candidates)
        no_change_streak = 0

        for i in range(1, 31):
            before = scroll_metrics()
            feed.evaluate("el => el.scrollTop = el.scrollHeight")
            page.wait_for_timeout(1500)
            after = scroll_metrics()
            candidates = collect()

            scrolled = after['scrollTop'] != before['scrollTop']
            grew = after['scrollHeight'] != before['scrollHeight']
            print(
                f"[scroll {i}] candidates={len(candidates)}  "
                f"scrollTop {before['scrollTop']}->{after['scrollTop']} (moved={scrolled})  "
                f"scrollHeight {before['scrollHeight']}->{after['scrollHeight']} (grew={grew})"
            )

            if len(candidates) > previous_count:
                previous_count = len(candidates)
                no_change_streak = 0
                continue

            no_change_streak += 1
            print(f"           no new candidates this round (no_change_streak={no_change_streak})")
            if no_change_streak >= 5:
                print("\nStopping: 5 consecutive scrolls with no new candidates.")
                break

            if len(candidates) >= max_results:
                print("\nStopping: reached max_results.")
                break

        print(f"\nFINAL candidate count: {len(candidates)}")

        page.screenshot(path=os.path.join(out_dir, "screenshot.png"), full_page=True)
        try:
            feed_html = feed.evaluate("el => el.outerHTML")
            with open(os.path.join(out_dir, "feed.html"), "w", encoding="utf-8") as f:
                f.write(feed_html)
            print(f"Saved feed HTML to {out_dir}/feed.html")
        except Exception as e:
            print(f"Could not dump feed HTML: {e}")
        print(f"Saved screenshot to {out_dir}/screenshot.png")

        browser.close()


if __name__ == "__main__":
    main()