"""
Admin credential storage.

Credentials (email + hashed password) are kept in their own JSON file,
separate from the SQLite database, so they can be managed/rotated
independently and are easy to exclude from backups or version control.
"""

import json
import os
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)
CREDENTIALS_FILE = os.path.join(DATA_DIR, "admin_credentials.json")


def load_credentials():
    """Return {'email': ..., 'password_hash': ...} or None if not set up."""
    if not os.path.exists(CREDENTIALS_FILE):
        return None
    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_credentials(email, password):
    data = {
        "email": email.strip().lower(),
        "password_hash": generate_password_hash(password),
    }
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.chmod(CREDENTIALS_FILE, 0o600)
    return data


def verify_credentials(email, password):
    creds = load_credentials()
    if not creds:
        return False
    if email.strip().lower() != creds.get("email", ""):
        return False
    return check_password_hash(creds.get("password_hash", ""), password)


def ensure_credentials_exist():
    """
    On first run, set up an admin account so the app is usable immediately.

    If ADMIN_EMAIL and ADMIN_PASSWORD environment variables are set, those
    are used (handy for hosts like Render where you set env vars in a
    dashboard rather than reading server logs). Otherwise, a default
    account with a random password is created and printed once to the
    console — change it with set_admin_credentials.py.
    """
    if load_credentials() is not None:
        return

    env_email = os.environ.get("ADMIN_EMAIL")
    env_password = os.environ.get("ADMIN_PASSWORD")
    if env_email and env_password:
        save_credentials(env_email, env_password)
        print(f"Admin credentials created from ADMIN_EMAIL/ADMIN_PASSWORD for {env_email.strip().lower()}.")
        return

    default_email = "admin@example.com"
    default_password = secrets.token_urlsafe(9)
    save_credentials(default_email, default_password)

    print("=" * 64)
    print("No admin credentials found — created a default admin account:")
    print(f"  Email:    {default_email}")
    print(f"  Password: {default_password}")
    print()
    print("Change these now by running: python3 set_admin_credentials.py")
    print(f"Credentials are stored in: {CREDENTIALS_FILE}")
    print("=" * 64)
