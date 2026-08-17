"""
Resolves a US city/state to an IANA timezone and checks whether the
current time falls within the configured sending window there.
"""

from datetime import datetime
from typing import Optional

import pytz
from timezonefinder import TimezoneFinder

_tf = TimezoneFinder()

# Free geocoding cache for common US cities (avoids repeated Nominatim
# calls, which are rate-limited). Extend as needed.
CITY_COORDS = {
    "houston": (29.7604, -95.3698),
    "austin": (30.2672, -97.7431),
    "dallas": (32.7767, -96.7970),
    "new york": (40.7128, -74.0060),
    "los angeles": (34.0522, -118.2437),
    "chicago": (41.8781, -87.6298),
    "phoenix": (33.4484, -112.0740),
    "denver": (39.7392, -104.9903),
}


def resolve_timezone(city: str, state: str) -> Optional[str]:
    """
    Returns an IANA timezone string (e.g. 'America/Chicago') for a city,
    or None if unresolvable. Falls back to state-level defaults for US
    states not in the coordinate cache.
    """
    key = city.strip().lower()
    if key in CITY_COORDS:
        lat, lng = CITY_COORDS[key]
        tz = _tf.timezone_at(lat=lat, lng=lng)
        if tz:
            return tz

    # State-level fallback (approximate but reasonable default)
    state_tz_map = {
        "TX": "America/Chicago", "CA": "America/Los_Angeles",
        "NY": "America/New_York", "FL": "America/New_York",
        "IL": "America/Chicago", "AZ": "America/Phoenix",
        "CO": "America/Denver", "WA": "America/Los_Angeles",
    }
    return state_tz_map.get(state.strip().upper())


def is_within_send_window(
    timezone_str: str,
    window_start_hour: int = 9,
    window_end_hour: int = 17,
) -> bool:
    """
    Returns True if it's currently within the sending window (local time
    for that timezone). Window is in 24h format, e.g. 9-17 = 9am-5pm.
    """
    tz = pytz.timezone(timezone_str)
    local_now = datetime.now(tz)
    return window_start_hour <= local_now.hour < window_end_hour


if __name__ == "__main__":
    tz = resolve_timezone("Houston", "TX")
    print("Houston timezone:", tz)
    print("Within send window:", is_within_send_window(tz))

    tz2 = resolve_timezone("Los Angeles", "CA")
    print("LA timezone:", tz2)
    print("Within send window:", is_within_send_window(tz2))