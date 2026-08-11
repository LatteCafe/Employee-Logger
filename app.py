import os
import sqlite3
import secrets
from datetime import datetime
from functools import wraps

from flask import (
    Flask, request, render_template, redirect, url_for,
    session, g, abort, flash
)

import auth_store

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Where the database (and, in auth_store.py, the credentials file) live.
# On most hosts this can just be the project folder. On Render, set the
# DATA_DIR environment variable to the mount path of a Persistent Disk
# (e.g. /var/data) so this data survives redeploys — Render's regular
# filesystem is wiped on every deploy.
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)
os.makedirs(DATA_DIR, exist_ok=True)
DATABASE = os.path.join(DATA_DIR, "database.db")

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", secrets.token_hex(32))


# ---------------------------------------------------------------------------
# Database helpers
# ---------------------------------------------------------------------------

def get_db():
    db = getattr(g, "_database", None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
    return db


@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, "_database", None)
    if db is not None:
        db.close()


def init_db():
    with app.app_context():
        db = get_db()
        db.executescript(
            """
            CREATE TABLE IF NOT EXISTS locations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                slug TEXT NOT NULL UNIQUE,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                location_id INTEGER NOT NULL,
                employee_name TEXT NOT NULL,
                entry_type TEXT NOT NULL DEFAULT 'IN',
                services TEXT,
                logged_at TEXT NOT NULL,
                FOREIGN KEY (location_id) REFERENCES locations (id)
                    ON DELETE CASCADE
            );
            """
        )
        # Backfill columns for databases created before these features
        # existed.
        existing_columns = [
            row["name"] for row in db.execute("PRAGMA table_info(logs)")
        ]
        if "entry_type" not in existing_columns:
            db.execute(
                "ALTER TABLE logs ADD COLUMN entry_type TEXT NOT NULL DEFAULT 'IN'"
            )
        if "services" not in existing_columns:
            db.execute("ALTER TABLE logs ADD COLUMN services TEXT")
        db.commit()


def generate_slug(name):
    """Turn a location name into a unique, URL-safe slug."""
    base = "".join(
        c.lower() if c.isalnum() else "-" for c in name
    ).strip("-")
    while "--" in base:
        base = base.replace("--", "-")
    if not base:
        base = "location"

    db = get_db()
    slug = base
    suffix = 1
    while db.execute(
        "SELECT 1 FROM locations WHERE slug = ?", (slug,)
    ).fetchone():
        suffix += 1
        slug = f"{base}-{suffix}"
    return slug


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("is_admin"):
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Public routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return redirect(url_for("admin_login"))


@app.route("/log/<slug>", methods=["GET", "POST"])
def log_page(slug):
    db = get_db()
    location = db.execute(
        "SELECT * FROM locations WHERE slug = ?", (slug,)
    ).fetchone()
    if location is None:
        abort(404)

    submitted_name = None
    submitted_type = None
    new_log_id = None
    if request.method == "POST":
        employee_name = request.form.get("employee_name", "").strip()
        if not employee_name:
            flash("Please enter your name before submitting.", "error")
        else:
            # Figure out whether this is a check-in or check-out: look at
            # this employee's most recent entry at this location. No prior
            # entry (or their last one was an OUT) -> this one is IN.
            # Their last entry was an IN -> this one is OUT.
            last_entry = db.execute(
                """
                SELECT entry_type FROM logs
                WHERE location_id = ? AND employee_name = ? COLLATE NOCASE
                ORDER BY id DESC LIMIT 1
                """,
                (location["id"], employee_name),
            ).fetchone()

            entry_type = "OUT" if last_entry and last_entry["entry_type"] == "IN" else "IN"

            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor = db.execute(
                "INSERT INTO logs (location_id, employee_name, entry_type, logged_at) "
                "VALUES (?, ?, ?, ?)",
                (location["id"], employee_name, entry_type, now),
            )
            db.commit()
            submitted_name = employee_name
            submitted_type = entry_type
            new_log_id = cursor.lastrowid

    return render_template(
        "log_page.html",
        location=location,
        submitted_name=submitted_name,
        submitted_type=submitted_type,
        new_log_id=new_log_id,
    )


@app.route("/log/<slug>/services/<int:log_id>", methods=["POST"])
def log_services(slug, log_id):
    """
    After a check-out, the employee is offered a text box to describe what
    services were done. This saves that text onto the log entry that was
    just created. Submitting blank simply skips it.
    """
    db = get_db()
    location = db.execute(
        "SELECT * FROM locations WHERE slug = ?", (slug,)
    ).fetchone()
    if location is None:
        abort(404)

    # Make sure this log entry actually belongs to this location and is a
    # check-out, so the endpoint can't be used to edit arbitrary rows.
    log_entry = db.execute(
        "SELECT * FROM logs WHERE id = ? AND location_id = ? AND entry_type = 'OUT'",
        (log_id, location["id"]),
    ).fetchone()

    if log_entry is not None:
        services = request.form.get("services", "").strip()
        if services:
            db.execute(
                "UPDATE logs SET services = ? WHERE id = ?",
                (services, log_id),
            )
            db.commit()

    return render_template(
        "log_page.html",
        location=location,
        submitted_name=log_entry["employee_name"] if log_entry else None,
        submitted_type="OUT" if log_entry else None,
        new_log_id=None,
        services_saved=True,
    )


# ---------------------------------------------------------------------------
# Admin routes
# ---------------------------------------------------------------------------

@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        if auth_store.verify_credentials(email, password):
            session["is_admin"] = True
            session["admin_email"] = email.strip().lower()
            next_url = request.args.get("next") or url_for("admin_dashboard")
            return redirect(next_url)
        flash("Incorrect email or password. Please try again.", "error")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("is_admin", None)
    session.pop("admin_email", None)
    return redirect(url_for("admin_login"))


@app.route("/admin", methods=["GET", "POST"])
@admin_required
def admin_dashboard():
    db = get_db()

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if not name:
            flash("Please enter a location name.", "error")
        else:
            slug = generate_slug(name)
            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            db.execute(
                "INSERT INTO locations (name, slug, created_at) "
                "VALUES (?, ?, ?)",
                (name, slug, now),
            )
            db.commit()
            flash(f'Location "{name}" was added.', "success")
        return redirect(url_for("admin_dashboard"))

    locations = db.execute(
        """
        SELECT l.*, COUNT(g.id) AS log_count
        FROM locations l
        LEFT JOIN logs g ON g.location_id = l.id
        GROUP BY l.id
        ORDER BY l.created_at DESC
        """
    ).fetchall()

    return render_template("admin_dashboard.html", locations=locations)


@app.route("/admin/location/<int:location_id>")
@admin_required
def admin_location_log(location_id):
    db = get_db()
    location = db.execute(
        "SELECT * FROM locations WHERE id = ?", (location_id,)
    ).fetchone()
    if location is None:
        abort(404)

    logs = db.execute(
        "SELECT * FROM logs WHERE location_id = ? ORDER BY logged_at DESC",
        (location_id,),
    ).fetchall()

    return render_template(
        "admin_location_log.html", location=location, logs=logs
    )


@app.route("/admin/location/<int:location_id>/delete", methods=["POST"])
@admin_required
def admin_delete_location(location_id):
    db = get_db()
    db.execute("DELETE FROM logs WHERE location_id = ?", (location_id,))
    db.execute("DELETE FROM locations WHERE id = ?", (location_id,))
    db.commit()
    flash("Location and its logs were deleted.", "success")
    return redirect(url_for("admin_dashboard"))


@app.route("/admin/admins", methods=["GET", "POST"])
@admin_required
def admin_manage_admins():
    if request.method == "POST":
        action = request.form.get("action")

        if action == "add":
            email = request.form.get("email", "").strip()
            password = request.form.get("password", "")
            confirm = request.form.get("confirm_password", "")
            if not email or not password:
                flash("Please provide both an email and a password.", "error")
            elif password != confirm:
                flash("Passwords do not match.", "error")
            elif len(password) < 8:
                flash("Password must be at least 8 characters.", "error")
            else:
                existed = auth_store.find_admin(email) is not None
                auth_store.add_or_update_admin(email, password)
                if existed:
                    flash(f"Updated password for {email.strip().lower()}.", "success")
                else:
                    flash(f"Added new admin: {email.strip().lower()}.", "success")

        elif action == "remove":
            email = request.form.get("email", "")
            if email.strip().lower() == session.get("admin_email"):
                flash("You can't remove the account you're currently logged in as.", "error")
            elif auth_store.remove_admin(email):
                flash(f"Removed admin: {email.strip().lower()}.", "success")
            else:
                flash("Couldn't remove that admin (at least one admin must remain).", "error")

        return redirect(url_for("admin_manage_admins"))

    admins = auth_store.load_admins()
    return render_template("admin_manage_admins.html", admins=admins)


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


# ---------------------------------------------------------------------------
# Startup: make sure the database and admin credentials exist. This runs at
# import time so it happens whether the app is started with
# `python3 app.py` (dev) or `gunicorn app:app` (production/Render).
# ---------------------------------------------------------------------------

auth_store.ensure_credentials_exist()
init_db()


# ---------------------------------------------------------------------------
# Entry point (local development only — Render/production uses gunicorn)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, host="0.0.0.0", port=port)
