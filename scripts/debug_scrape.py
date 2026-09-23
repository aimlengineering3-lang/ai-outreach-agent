"""
Standalone debug tool for the Maps discovery step. Run this whenever a
city/niche combination isn't finding as many leads as expected.

READ-ONLY: this never inserts, updates, or deletes anything in the
database. It only scrapes Maps and compares against what's already
there, then prints what it would have done.

Usage (PowerShell, from the project root, with the venv active):
    python debug_scrape.py "plumbing" "Fairbanks" "AK"

Optional: add a 4th argument for max_results (default 150), and a 5th
argument "show" to run the browser visibly instead of headless:
    python debug_scrape.py "plumbing" "Fairbanks" "AK" 150 show
"""

import os
import sys

# This file lives in scripts/, but "src" is a package at the project
# root — add the root to Python's search path so the import below
# works no matter which folder the script is run from.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.db.session import SessionLocal
from src.db.models import Lead
from src.discovery.maps_scraper import scrape_maps_listings
from src.discovery.deduplicator import is_likely_duplicate
from app.run_agent import _is_in_niche, NICHE_KEYWORDS, EXCLUDE_KEYWORDS


def main():
    if len(sys.argv) < 4:
        print('Usage: python debug_scrape.py "<niche>" "<city>" "<state>" [max_results] [show]')
        sys.exit(1)

    niche = sys.argv[1]
    city = sys.argv[2]
    state = sys.argv[3]
    max_results = int(sys.argv[4]) if len(sys.argv) > 4 else 150
    headless = not (len(sys.argv) > 5 and sys.argv[5].lower() == "show")

    query = f"{niche} in {city}, {state}"
    print(f"Scraping: '{query}' (max_results={max_results}, headless={headless})\n")

    scrape_result = scrape_maps_listings(query, max_results=max_results, headless=headless)
    listings = scrape_result.listings
    print(f"Maps returned {len(listings)} unique listing(s).")
    if scrape_result.reached_max_results:
        print("(Hit the max_results cap — more businesses likely exist. Try a higher max_results.)\n")
    else:
        print("(Stopped on its own — this is likely everything Maps has for this query.)\n")

    session = SessionLocal()
    try:
        existing_leads = session.query(Lead).filter(Lead.niche == niche).all()
        print(f"{len(existing_leads)} existing '{niche}' lead(s) already in the database (any city).\n")

        new_count = 0
        niche_rejected = 0
        dup_rejected = 0
        for listing in listings:
            # Mirrors discover_and_save()'s ORDER of checks exactly: niche
            # filter first, then duplicate check — so this print-out is a
            # faithful preview of what the real pipeline would do.
            if not _is_in_niche(listing.business_name, niche):
                name_lower = listing.business_name.lower()
                matched_exclude = next((kw for kw in EXCLUDE_KEYWORDS if kw in name_lower), None)
                if matched_exclude:
                    reason = f"excluded keyword: '{matched_exclude}'"
                else:
                    reason = f"no niche keyword match (needs one of: {NICHE_KEYWORDS.get(niche)})"
                print(f"  SKIP  '{listing.business_name}'  (not in niche: {reason})")
                niche_rejected += 1
                continue

            dup = next(
                (
                    is_likely_duplicate(
                        listing.business_name, listing.website, city,
                        existing.business_name, existing.website, existing.city,
                    )
                    for existing in existing_leads
                    if is_likely_duplicate(
                        listing.business_name, listing.website, city,
                        existing.business_name, existing.website, existing.city,
                    ).is_duplicate
                ),
                None,
            )
            if dup:
                print(f"  SKIP  '{listing.business_name}'  (duplicate: {dup.reason})")
                dup_rejected += 1
            else:
                print(f"  NEW   '{listing.business_name}'  website={listing.website or '-'}  phone={listing.phone or '-'}")
                new_count += 1

        print(
            f"\n{new_count} of {len(listings)} would be inserted as genuinely new leads. "
            f"({niche_rejected} rejected as off-niche, {dup_rejected} rejected as duplicates)"
        )
        print(
            "\nNOTE: this count is still based on listings the scraper actually VISITED. "
            "Production's should_visit prefilter also rejects candidates by name BEFORE "
            "visiting them — so if the raw Maps count above looks low to begin with, that's "
            "a scraping/search issue, not a filtering issue."
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()