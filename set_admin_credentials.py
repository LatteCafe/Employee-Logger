"""
Run this to set or change the admin email/password:

    python3 set_admin_credentials.py
"""

import getpass

from auth_store import save_credentials


def main():
    print("Set admin login credentials")
    print("-" * 30)
    email = input("Admin email: ").strip()
    if not email:
        print("Email cannot be empty. Aborted.")
        return

    password = getpass.getpass("Admin password: ")
    confirm = getpass.getpass("Confirm password: ")

    if not password:
        print("Password cannot be empty. Aborted.")
        return
    if password != confirm:
        print("Passwords do not match. Aborted.")
        return

    save_credentials(email, password)
    print(f"\nSaved. You can now log in at /admin/login as {email}.")


if __name__ == "__main__":
    main()
