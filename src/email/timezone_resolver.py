"""
Resolves a US city/state to an IANA timezone using a built-in
state -> timezone lookup table (no native/compiled packages, no
external geocoding service), and checks whether the current time
falls within the configured sending window there.
"""

from datetime import datetime
from typing import Optional

import pytz

# Most US states sit entirely (or almost entirely) in one timezone.
# A handful are split across two zones (TX, FL, MI, IN, KY, ND, SD,
# NE, ID, OR, ...) -- for those we use the zone the majority of the
# state's population lives in. Accepted trade-off: a few border-town
# leads may be off by one hour, in exchange for not depending on any
# compiled/native package (timezonefinder -> h3 was getting blocked
# by Windows Application Control Policy) or an external geocoding
# API call per lead.
_STATE_TIMEZONES: dict[str, str] = {
    "AL": "America/Chicago", "AK": "America/Anchorage", "AZ": "America/Phoenix",
    "AR": "America/Chicago", "CA": "America/Los_Angeles", "CO": "America/Denver",
    "CT": "America/New_York", "DE": "America/New_York", "FL": "America/New_York",
    "GA": "America/New_York", "HI": "Pacific/Honolulu", "ID": "America/Denver",
    "IL": "America/Chicago", "IN": "America/New_York", "IA": "America/Chicago",
    "KS": "America/Chicago", "KY": "America/New_York", "LA": "America/Chicago",
    "ME": "America/New_York", "MD": "America/New_York", "MA": "America/New_York",
    "MI": "America/New_York", "MN": "America/Chicago", "MS": "America/Chicago",
    "MO": "America/Chicago", "MT": "America/Denver", "NE": "America/Chicago",
    "NV": "America/Los_Angeles", "NH": "America/New_York", "NJ": "America/New_York",
    "NM": "America/Denver", "NY": "America/New_York", "NC": "America/New_York",
    "ND": "America/Chicago", "OH": "America/New_York", "OK": "America/Chicago",
    "OR": "America/Los_Angeles", "PA": "America/New_York", "RI": "America/New_York",
    "SC": "America/New_York", "SD": "America/Chicago", "TN": "America/Chicago",
    "TX": "America/Chicago", "UT": "America/Denver", "VT": "America/New_York",
    "VA": "America/New_York", "WA": "America/Los_Angeles", "WV": "America/New_York",
    "WI": "America/Chicago", "WY": "America/Denver", "DC": "America/New_York",
}


def resolve_timezone(city: str, state: str) -> Optional[str]:
    """
    Returns an IANA timezone string (e.g. 'America/Chicago') for a US
    state abbreviation. `city` is accepted for call-site compatibility
    but isn't used for the lookup (see trade-off note above).
    """
    return _STATE_TIMEZONES.get((state or "").strip().upper())


def is_within_send_window(timezone_str: str) -> bool:
    """
    Returns True if it's currently within the configured sending window
    (local time for that timezone). Window is read from
    configs/settings.yaml so it's editable from the dashboard.
    """
    import os
    from src.core.config import load_settings

    if os.getenv("IGNORE_SEND_WINDOW", "false").lower() == "true":
        return True

    settings = load_settings()
    window = settings.get("sending_window", {"start_hour": 9, "end_hour": 17})

    tz = pytz.timezone(timezone_str)
    local_now = datetime.now(tz)
    return window["start_hour"] <= local_now.hour < window["end_hour"]


if __name__ == "__main__":
    for city, state in [("Anchorage", "AK"), ("Honolulu", "HI"), ("Houston", "TX"), ("Bozeman", "MT")]:
        tz = resolve_timezone(city, state)
        print(f"{city}, {state} -> {tz}")