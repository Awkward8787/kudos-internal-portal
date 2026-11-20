import sqlite3
from datetime import datetime, timezone

import click
from flask import current_app, g
from werkzeug.security import generate_password_hash


DEMO_USERS = (
    ("admin", "Alex Rivera", "admin"),
    ("jordan", "Jordan Lee", "employee"),
    ("priya", "Priya Shah", "employee"),
    ("marcus", "Marcus Chen", "employee"),
    ("anthony", "Anthony Jones", "employee"),
)

DEMO_PASSWORD = "kudos-demo"

SAMPLE_KUDOS = (
    ("jordan", "priya", "Thanks for reviewing the release notes."),
    ("priya", "marcus", "Your walkthrough of the billing fix saved us a long night."),
    ("marcus", "anthony", "Appreciate you jumping on the support queue this morning."),
    ("anthony", "jordan", "The onboarding checklist you wrote is clear and complete."),
)

SCHEMA = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL DEFAULT 'employee' CHECK (role IN ('employee', 'admin')),
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kudos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_user_id INTEGER NOT NULL REFERENCES users(id),
    to_user_id INTEGER NOT NULL REFERENCES users(id),
    message TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_visible INTEGER NOT NULL DEFAULT 1 CHECK (is_visible IN (0, 1)),
    moderated_by INTEGER REFERENCES users(id),
    moderated_at TEXT,
    reason_for_moderation TEXT,
    CHECK (from_user_id != to_user_id),
    CHECK (length(message) >= 1 AND length(message) <= 500)
);

CREATE INDEX IF NOT EXISTS idx_kudos_feed
    ON kudos (is_visible, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_kudos_from_created
    ON kudos (from_user_id, created_at DESC);
"""


def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def get_db():
    if "db" not in g:
        db = sqlite3.connect(current_app.config["DATABASE"])
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys = ON")
        g.db = db
    return g.db


def close_db(_error=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA)
    now = utc_now()
    hash_method = "pbkdf2:sha256:1" if current_app.config.get("TESTING") else None
    password_hash = (
        generate_password_hash(DEMO_PASSWORD, method=hash_method)
        if hash_method
        else generate_password_hash(DEMO_PASSWORD)
    )
    for username, display_name, role in DEMO_USERS:
        db.execute(
            """
            INSERT OR IGNORE INTO users (username, display_name, password_hash, role, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (username, display_name, password_hash, role, now),
        )
    db.commit()
    if current_app.config.get("SEED_SAMPLE_KUDOS"):
        existing = db.execute("SELECT COUNT(*) AS n FROM kudos").fetchone()["n"]
        if existing == 0:
            users = {
                row["username"]: row["id"]
                for row in db.execute("SELECT id, username FROM users")
            }
            for sender, recipient, message in SAMPLE_KUDOS:
                db.execute(
                    """
                    INSERT INTO kudos (from_user_id, to_user_id, message, created_at, is_visible)
                    VALUES (?, ?, ?, ?, 1)
                    """,
                    (users[sender], users[recipient], message, now),
                )
            db.commit()


@click.command("init-db")
def init_db_command():
    """Create tables and seed the demo users."""
    init_db()
    click.echo("Initialized the Kudos database.")


def init_app(app):
    app.teardown_appcontext(close_db)
    app.cli.add_command(init_db_command)
