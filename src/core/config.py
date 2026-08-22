"""
Loads environment variables and application settings (YAML-based, so
sending window / target cities are editable from the dashboard without
touching Python code).
"""

import os
import yaml
from pathlib import Path
from dotenv import load_dotenv, set_key

load_dotenv()

ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"
SETTINGS_PATH = Path(__file__).resolve().parent.parent.parent / "configs" / "settings.yaml"

DEFAULT_SETTINGS = {
    "sending_window": {"start_hour": 9, "end_hour": 17},
    "target_cities": [{"city": "Austin", "state": "TX"}],
}


def load_settings() -> dict:
    if not SETTINGS_PATH.exists():
        return DEFAULT_SETTINGS
    with open(SETTINGS_PATH, "r") as f:
        data = yaml.safe_load(f)
    return data or DEFAULT_SETTINGS


def save_settings(settings: dict) -> None:
    SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_PATH, "w") as f:
        yaml.safe_dump(settings, f)


def get_app_mode() -> str:
    load_dotenv(override=True)
    return os.getenv("APP_MODE", "TEST")


def set_app_mode(mode: str) -> None:
    """Writes APP_MODE directly into the .env file on disk."""
    set_key(str(ENV_PATH), "APP_MODE", mode)


if __name__ == "__main__":
    print(f"APP_MODE = {get_app_mode()}")
    print("Settings:", load_settings())