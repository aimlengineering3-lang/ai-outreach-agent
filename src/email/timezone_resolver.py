"""
Resolves ANY US city/state to an IANA timezone using free geocoding
(no API key, no per-city hardcoding needed) and checks whether the
current time falls within the configured sending window there.
"""

import httpx
from datetime import datetime
from typing import Optional

import pytz
from timezonefinder import TimezoneFinder

_tf = TimezoneFinder()

# Simple in-memory cache so we don't re-geocode the same city every call.
_geocode_cache: dict[str, tuple[float, float]] = {}


def _geocode_city(city: str, state: str) -> Optional[tuple[float, float]]:
    """
    Uses the free OpenStreetMap Nominatim geocoding service to turn any
    "City, State" into latitude/longitude — works for every US city,
    not just a hardcoded list.
    """
    cache_key = f"{city.lower()},{state.lower()}"
    if cache_key in _geocode_cache:
        return _geocode_cache[cache_key]

    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={"q": f"{city}, {state}, USA", "format": "json", "limit": 1},
            headers={"User-Agent": "AI-Outreach-Agent/1.0"},
            timeout=10.0,
        )
        results = response.json()
        if not results:
            return None
        lat = float(results[0]["lat"])
        lng = float(results[0]["lon"])
        _geocode_cache[cache_key] = (lat, lng)
        return (lat, lng)
    except Exception:
        return None


def resolve_timezone(city: str, state: str) -> Optional[str]:
    """
    Returns an IANA timezone string (e.g. 'America/Anchorage') for ANY
    US city, by geocoding it first and then looking up the timezone
    for those coordinates. Works nationwide — Alaska, Hawaii, small
    towns, everywhere — with no manual city list to maintain.
    """
    coords = _geocode_city(city, state)
    if not coords:
        return None

    lat, lng = coords
    return _tf.timezone_at(lat=lat, lng=lng)


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