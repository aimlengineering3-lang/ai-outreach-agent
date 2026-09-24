"""
Standalone: forces (re-)authorization for one Gmail sender account.
Opens a browser window to sign in and grant access.

Safe by construction: sender.py now checks that the Google account you
actually authorized matches the email you asked for. If the browser
picks/signs into the wrong one, this will raise a clear error instead
of silently saving the wrong account's token under the right name.

Usage:
    python scripts/authorize_account.py "usman.homeads@gmail.com"
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.email.sender import _get_credentials


def main():
    if len(sys.argv) < 2:
        print('Usage: python scripts/authorize_account.py "<email>"')
        sys.exit(1)

    email = sys.argv[1]
    print(f"Opening a browser window to authorize: {email}")
    print("On Google's screen, make sure you sign in as (or select) exactly this account.\n")

    _get_credentials(email)

    print(f"\nAuthorized and saved token for {email}.")


if __name__ == "__main__":
    main()