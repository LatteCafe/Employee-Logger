"""
Manage admin accounts from the command line.

Usage:
    python3 manage_admins.py list
    python3 manage_admins.py add
    python3 manage_admins.py remove
"""

import getpass
import sys

import auth_store


def cmd_list():
    admins = auth_store.load_admins()
    if not admins:
        print("No admin accounts exist yet.")
        return
    print(f"{len(admins)} admin account(s):")
    for admin in admins:
        print(f"  - {admin['email']}")


def cmd_add():
    email = input("Admin email: ").strip()
    if not email:
        print("Email cannot be empty. Aborted.")
        return

    password = getpass.getpass("Password: ")
    confirm = getpass.getpass("Confirm password: ")
    if not password:
        print("Password cannot be empty. Aborted.")
        return
    if password != confirm:
        print("Passwords do not match. Aborted.")
        return

    existed = auth_store.find_admin(email) is not None
    auth_store.add_or_update_admin(email, password)
    if existed:
        print(f"\nUpdated password for existing admin: {email.strip().lower()}")
    else:
        print(f"\nAdded new admin: {email.strip().lower()}")


def cmd_remove():
    cmd_list()
    email = input("\nEmail to remove: ").strip()
    if not email:
        print("Aborted.")
        return
    ok = auth_store.remove_admin(email)
    if ok:
        print(f"Removed admin: {email.strip().lower()}")
    else:
        print(
            "Could not remove that admin — either the email wasn't found, "
            "or it's the last remaining admin (at least one must stay)."
        )


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in ("list", "add", "remove"):
        print(__doc__)
        return

    command = sys.argv[1]
    if command == "list":
        cmd_list()
    elif command == "add":
        cmd_add()
    elif command == "remove":
        cmd_remove()


if __name__ == "__main__":
    main()
