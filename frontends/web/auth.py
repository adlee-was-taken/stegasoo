"""
Stegasoo Authentication Module

Single-admin authentication with Argon2 password hashing.
Uses Flask sessions for authentication state and SQLite3 for storage.
"""

import functools
import sqlite3
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import current_app, g, redirect, session, url_for

# Argon2 password hasher (lighter than stegasoo's 256MB for faster login)
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)


def get_db_path() -> Path:
    """Get database path in Flask instance folder."""
    instance_path = Path(current_app.instance_path)
    instance_path.mkdir(parents=True, exist_ok=True)
    return instance_path / "stegasoo.db"


def get_db() -> sqlite3.Connection:
    """Get database connection, cached on Flask g object."""
    if "db" not in g:
        g.db = sqlite3.connect(get_db_path())
        g.db.row_factory = sqlite3.Row
    return g.db


def close_db(e=None):
    """Close database connection at end of request."""
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    """Initialize database schema."""
    db = get_db()
    db.executescript("""
        CREATE TABLE IF NOT EXISTS admin_user (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            username TEXT NOT NULL DEFAULT 'admin',
            password_hash TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
    """)
    db.commit()


def user_exists() -> bool:
    """Check if admin user has been created."""
    db = get_db()
    result = db.execute("SELECT 1 FROM admin_user WHERE id = 1").fetchone()
    return result is not None


def create_user(username: str, password: str):
    """Create admin user (first-run setup)."""
    if user_exists():
        raise ValueError("Admin user already exists")

    password_hash = ph.hash(password)
    db = get_db()
    db.execute(
        "INSERT INTO admin_user (id, username, password_hash) VALUES (1, ?, ?)",
        (username, password_hash),
    )
    db.commit()


def get_username() -> str:
    """Get the admin username."""
    db = get_db()
    row = db.execute("SELECT username FROM admin_user WHERE id = 1").fetchone()
    return row["username"] if row else "admin"


def verify_password(password: str) -> bool:
    """Verify password against stored hash."""
    db = get_db()
    row = db.execute("SELECT password_hash FROM admin_user WHERE id = 1").fetchone()
    if not row:
        return False
    try:
        ph.verify(row["password_hash"], password)
        # Rehash if parameters changed
        if ph.check_needs_rehash(row["password_hash"]):
            new_hash = ph.hash(password)
            db.execute(
                "UPDATE admin_user SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
                (new_hash,),
            )
            db.commit()
        return True
    except VerifyMismatchError:
        return False


def change_password(current_password: str, new_password: str) -> tuple[bool, str]:
    """Change admin password. Returns (success, message)."""
    if not verify_password(current_password):
        return False, "Current password is incorrect"

    if len(new_password) < 8:
        return False, "New password must be at least 8 characters"

    new_hash = ph.hash(new_password)
    db = get_db()
    db.execute(
        "UPDATE admin_user SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = 1",
        (new_hash,),
    )
    db.commit()
    return True, "Password changed successfully"


def is_authenticated() -> bool:
    """Check if current session is authenticated."""
    return session.get("authenticated", False)


def login_required(f):
    """Decorator to require login for a route."""

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if auth is enabled
        if not current_app.config.get("AUTH_ENABLED", True):
            return f(*args, **kwargs)

        # Check for first-run setup
        if not user_exists():
            return redirect(url_for("setup"))

        # Check authentication
        if not is_authenticated():
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


def init_app(app):
    """Initialize auth module with Flask app."""
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()
