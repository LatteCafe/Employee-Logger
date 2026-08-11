"""
Admin credential storage — supports multiple admin accounts.

Credentials (email + hashed password, per admin) are kept in their own
JSON file, separate from the SQLite database, so they can be
managed/rotated independently and are easy to exclude from backups or
version control.

File format: a JSON list of {"email": ..., "password_hash": ...} objects.
"""

import json
import os
import secrets

from werkzeug.security import check_password_hash, generate_password_hash

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)
CREDENTIALS_FILE = os.path.join(DATA_DIR, "admin_credentials.json")


def _write(admins):
    with open(CREDENTIALS_FILE, "w", encoding="utf-8") as f:
        json.dump(admins, f, indent=2)
    os.chmod(CREDENTIALS_FILE, 0o600)


def load_admins():
    """Return a list of {'email': ..., 'password_hash': ...} dicts."""
    if not os.path.exists(CREDENTIALS_FILE):
        return []
    with open(CREDENTIALS_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    # Support upgrading from the old single-admin file format
    # ({"email": ..., "password_hash": ...}) transparently.
    if isinstance(data, dict):
        data = [data]
        _write(data)
    return data


def find_admin(email):
    email = email.strip().lower()
    for admin in load_admins():
        if admin.get("email") == email:
            return admin
    return None


def add_or_update_admin(email, password):
    """Add a new admin, or reset the password if that email already exists."""
    email = email.strip().lower()
    admins = load_admins()
    for admin in admins:
        if admin.get("email") == email:
            admin["password_hash"] = generate_password_hash(password)
            _write(admins)
            return
    admins.append({
        "email": email,
        "password_hash": generate_password_hash(password),
    })
    _write(admins)


def remove_admin(email):
    """
    Remove an admin by email. Refuses to remove the last remaining admin
    so the app can never end up with zero valid logins.
    Returns True if removed, False if not found or if it was the last one.
    """
    email = email.strip().lower()
    admins = load_admins()
    if len(admins) <= 1:
        return False
    remaining = [a for a in admins if a.get("email") != email]
    if len(remaining) == len(admins):
        return False  # email not found
    _write(remaining)
    return True


def verify_credentials(email, password):
    admin = find_admin(email)
    if not admin:
        return False
    return check_password_hash(admin.get("password_hash", ""), password)


def ensure_credentials_exist():
    """
    On first run, set up an initial admin account so the app is usable
    immediately.

    If ADMIN_EMAIL and ADMIN_PASSWORD environment variables are set, those
    seed the first account (handy for hosts like Render where you set env
    vars in a dashboard rather than reading server logs). Otherwise, a
    default account with a random password is created and printed once to
    the console. Either way, more admins can be added later from the
    admin panel's "Manage Admins" page, or with manage_admins.py.
    """
    if load_admins():
        return

    env_email = os.environ.get("ADMIN_EMAIL")
    env_password = os.environ.get("ADMIN_PASSWORD")
    if env_email and env_password:
        add_or_update_admin(env_email, env_password)
        print(f"Admin account created from ADMIN_EMAIL/ADMIN_PASSWORD for {env_email.strip().lower()}.")
        return

    default_email = "admin@example.com"
    default_password = secrets.token_urlsafe(9)
    add_or_update_admin(default_email, default_password)

    print("=" * 64)
    print("No admin credentials found — created a default admin account:")
    print(f"  Email:    {default_email}")
    print(f"  Password: {default_password}")
    print()
    print("Change this, or add more admins, by running: python3 manage_admins.py")
    print("Or use the 'Manage Admins' page in the admin panel once logged in.")
    print(f"Credentials are stored in: {CREDENTIALS_FILE}")
    print("=" * 64)
