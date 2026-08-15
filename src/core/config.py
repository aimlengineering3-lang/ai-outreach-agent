"""
Loads environment variables and application settings.
This file will grow in Phase 1 — for now it just proves the environment works.
"""

import os
from dotenv import load_dotenv

load_dotenv()

APP_MODE = os.getenv("APP_MODE", "TEST")

if __name__ == "__main__":
    print(f"Environment loaded successfully. APP_MODE = {APP_MODE}")