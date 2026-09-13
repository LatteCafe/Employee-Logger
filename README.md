## Disclaimer

AI tools were heavily used in the creation of this tool, it is not representative of my skills or abilities and should not be used as a reference point of such
While I almost always have AI write the **README** files for my projects AI was used for everything in this project except SQLite databases, excel exports and the basic logging itself.

# Employee Check-In System

A check-in / check-out logging system: employees log their name at a
location-specific page (alternating automatically between check-in and
check-out), and an admin panel manages locations and views logs. Labels
throughout the UI are shown in English, Simplified Chinese, and Traditional
Chinese.

## What's included

- **Python/Flask backend** (`app.py`)
- **SQLite database** (created automatically on first run as `database.db`)
- **HTML front end** (Jinja templates in `templates/`, styling in `static/style.css`)
- **Separate credentials file** (`admin_credentials.json`, created on first run — kept apart from the database)

## Setup

1. Install dependencies (Python 3.9+ recommended):

   ```
   pip install -r requirements.txt
   ```

2. Run the app:

   ```
   python3 app.py
   ```

   On first run this creates:
   - `database.db` — the SQLite database
   - `admin_credentials.json` — a default admin account, with a randomly
     generated password printed once to your terminal. **Copy that
     password down before it scrolls away**, or just set your own
     credentials right away (see below).

3. Open your browser to:

   ```
   http://localhost:5000/admin/login
   ```

## Admin login (email + password)

Credentials are stored in `admin_credentials.json`, separate from
`database.db`, with the password hashed (never stored in plain text).

You can have **multiple admin accounts**. Manage them two ways:

- **From the web UI:** log in, then click "Manage Admins" on the
  dashboard to add or remove admin accounts (typed there, no shell
  access needed — this is the easiest option on a host like Render).
- **From the command line:**
  ```
  python3 manage_admins.py list      # see all admin accounts
  python3 manage_admins.py add       # add a new admin, or reset an existing one's password
  python3 manage_admins.py remove    # remove an admin
  ```

There's always a safeguard: the app refuses to remove the last remaining
admin account, so you can never lock yourself out entirely.

`admin_credentials.json` and `database.db` are listed in `.gitignore` so
they won't accidentally get committed if you put this project in git.

## How it works

### Admin panel (`/admin`)

- Log in with your email + password at `/admin/login`.
- Add a new location by typing its name and clicking **Add Location**. This
  automatically creates a unique check-in URL for that location, e.g.:

  ```
  http://your-server/log/warehouse-3
  ```

- Each location card shows its check-in link (click to open/copy) and a
  running count of logged entries.
- Click **Rename** under a location's link to change its display name.
  The check-in URL (slug) stays the same, so existing printed links/QR
  codes keep working.
- Click **View Log** on any location to see every employee entry, tagged
  as **Check-In** or **Check-Out**, with a timestamp — most recent first.
  Each row has its own **Delete** button to remove just that entry.
- Click **Export** (on the dashboard or the log page) to download that
  location's full log as an Excel (`.xlsx`) file — employee, type,
  time, and services in one sheet.
- Click **Delete** on a location card to remove the whole location and
  all of its log entries (asks for confirmation first).

### Check-in page (`/log/<slug>`)

- Each location gets its own page with a unique URL slug based on its name
  (e.g. "Front Desk" → `/log/front-desk`).
- Post this link at the physical location (QR code, sticker, tablet
  bookmark, etc.).
- An employee types their name and submits. The system automatically
  alternates between **Check-In** and **Check-Out** for that employee at
  that location:
  - Their first entry (or first after a check-out) is recorded as a
    **Check-In**.
  - Their next entry is recorded as a **Check-Out**.
  - The pattern repeats from there.
  - Name matching for this purpose is case-insensitive ("Alice" and
    "alice" are treated as the same person), so make sure employees enter
    their name consistently.
- After submitting, they see a confirmation of which one it was. On a
  check-out, they're also shown an optional text box to describe what
  services were done during that visit — this gets saved onto that same
  log entry. They can leave it blank to skip.
- After that (or right away for a check-in), they see the final
  confirmation and can log another employee from the same device.

## Timezone

Servers often run on UTC regardless of where you or your employees
actually are. By default, this app stores timestamps in UTC. To make
logged times match your local clock, set a `TIMEZONE` environment
variable to an IANA timezone name, for example:

```
TIMEZONE=America/Edmonton
```

Other examples: `America/New_York`, `America/Los_Angeles`, `Europe/London`,
`Asia/Shanghai`. If `TIMEZONE` is unset or isn't a recognized name, the app
falls back to UTC rather than erroring.

## Notes on the database

Two tables are created automatically:

- `locations` — id, name, slug (used in the URL), created_at
- `logs` — id, location_id (foreign key), employee_name, entry_type
  (`IN` or `OUT`), services (free text, only set on some check-outs),
  logged_at

You can inspect the database directly with any SQLite browser, or via the
command line:

```
sqlite3 database.db "SELECT * FROM logs;"
```

## Deployment notes

This ships with Flask's built-in development server, which is fine for
trying it out on a local network but isn't meant for production. For
real/ongoing use:

- Run it behind a production WSGI server (e.g. `gunicorn app:app`) and a
  reverse proxy (e.g. nginx), ideally over HTTPS.
- Set a fixed `SECRET_KEY` environment variable (otherwise a new random key
  is generated each restart, which will log out all active admin sessions).
- Set your own admin credentials with `manage_admins.py`, or the "Manage
  Admins" page in the app, instead of using the auto-generated default.
- Back up `database.db` periodically. Keep `admin_credentials.json` private
  — treat it like any other password file.

## Deploying to Render

The app already includes a `Procfile` and uses `gunicorn` as its production
server, so Render can run it as-is. The one thing to get right is storage:
**Render's regular filesystem is wiped on every deploy**, so the SQLite
database and the credentials file need to live on a Render **Persistent
Disk** instead of the default project folder.

1. **Push this project to a GitHub repo** (Render deploys from git).

2. **Create a new Web Service on Render:**
   - Connect your repo.
   - Runtime: Python 3.
   - Build command: `pip install -r requirements.txt`
   - Start command: `gunicorn app:app --bind 0.0.0.0:$PORT` (this is also
     in the `Procfile`, so Render should pick it up automatically).

3. **Add a Persistent Disk** (Render dashboard → your service → Disks):
   - Mount path: `/var/data` (or any path you like).
   - Size: 1 GB is plenty for this app.
   - Note: Persistent Disks require a paid instance type — Render's free
     tier doesn't support them. Without one, your locations and logs will
     disappear every time the service redeploys or restarts.

4. **Set environment variables** (Render dashboard → your service →
   Environment):
   - `DATA_DIR` = `/var/data` (must match the disk's mount path — this is
     what tells the app to store `database.db` and
     `admin_credentials.json` on the persistent disk instead of the
     ephemeral project folder).
   - `SECRET_KEY` = any long random string (so admin sessions survive
     restarts instead of getting logged out).
   - `ADMIN_EMAIL` and `ADMIN_PASSWORD` = your desired admin login. If you
     skip these, the app will generate a random password on first boot and
     print it once to the Render service logs — easy to miss, so setting
     these explicitly is the more reliable option.

5. **Deploy.** Render will build and start the service. Visit
   `https://your-service-name.onrender.com/admin/login` and log in with
   the `ADMIN_EMAIL`/`ADMIN_PASSWORD` you set.

6. **Generate check-in links using your Render URL**, e.g.:

   ```
   https://your-service-name.onrender.com/log/warehouse-3
   ```

   These are the links you'd post/QR-code at each physical location.

A couple of things worth knowing about Render specifically:
- On paid plans the service stays running; on lower tiers it may spin down
  after inactivity and take a few seconds to wake up on the next request —
  not a data problem, just a brief delay.
- If you ever change `ADMIN_EMAIL`/`ADMIN_PASSWORD` env vars after the
  first deploy, they won't do anything on their own — those are only read
  once, when no credentials file exists yet. To change the login later,
  just log in with the existing account and use the "Manage Admins" page
  to add a new admin or reset a password — no shell access needed.
