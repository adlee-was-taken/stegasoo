"""
Stegasoo Authentication Module (v4.1.0)

Multi-user authentication with role-based access control.
- Admin user created at first-run setup
- Admin can create up to 16 additional users
- Uses Argon2id password hashing
- Flask sessions for authentication state
- SQLite3 for user storage
"""

import functools
import secrets
import sqlite3
import string
from dataclasses import dataclass
from pathlib import Path

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from flask import current_app, flash, g, redirect, session, url_for

# Argon2 password hasher (lighter than stegasoo's 256MB for faster login)
ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,  # 64MB
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Constants
MAX_USERS = 16  # Plus 1 admin = 17 total
ROLE_ADMIN = "admin"
ROLE_USER = "user"


@dataclass
class User:
    """User data class."""

    id: int
    username: str
    role: str
    created_at: str

    @property
    def is_admin(self) -> bool:
        return self.role == ROLE_ADMIN


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
    """Initialize database schema with migration support."""
    db = get_db()

    # Check if we need to migrate from old single-user schema
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='admin_user'"
    )
    has_old_table = cursor.fetchone() is not None

    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
    )
    has_new_table = cursor.fetchone() is not None

    if has_old_table and not has_new_table:
        # Migrate from old schema
        _migrate_from_single_user(db)
    elif not has_new_table:
        # Fresh install - create new schema
        _create_schema(db)


def _create_schema(db: sqlite3.Connection):
    """Create the multi-user schema."""
    db.executescript("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL UNIQUE,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
        CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
    """)
    db.commit()


def _migrate_from_single_user(db: sqlite3.Connection):
    """Migrate from old single-user admin_user table to multi-user users table."""
    # Create new table
    _create_schema(db)

    # Copy admin user from old table
    old_user = db.execute(
        "SELECT username, password_hash, created_at FROM admin_user WHERE id = 1"
    ).fetchone()

    if old_user:
        db.execute(
            """
            INSERT INTO users (username, password_hash, role, created_at)
            VALUES (?, ?, 'admin', ?)
            """,
            (old_user["username"], old_user["password_hash"], old_user["created_at"]),
        )
        db.commit()

    # Drop old table
    db.execute("DROP TABLE admin_user")
    db.commit()


# =============================================================================
# User Queries
# =============================================================================


def any_users_exist() -> bool:
    """Check if any users have been created (for first-run detection)."""
    db = get_db()
    result = db.execute("SELECT 1 FROM users LIMIT 1").fetchone()
    return result is not None


def user_exists() -> bool:
    """Alias for any_users_exist() for backwards compatibility."""
    return any_users_exist()


def get_user_count() -> int:
    """Get total number of users."""
    db = get_db()
    result = db.execute("SELECT COUNT(*) FROM users").fetchone()
    return result[0] if result else 0


def get_non_admin_count() -> int:
    """Get number of non-admin users."""
    db = get_db()
    result = db.execute("SELECT COUNT(*) FROM users WHERE role != 'admin'").fetchone()
    return result[0] if result else 0


def can_create_user() -> bool:
    """Check if we can create more users (within limit)."""
    return get_non_admin_count() < MAX_USERS


def get_user_by_id(user_id: int) -> User | None:
    """Get user by ID."""
    db = get_db()
    row = db.execute(
        "SELECT id, username, role, created_at FROM users WHERE id = ?", (user_id,)
    ).fetchone()
    if row:
        return User(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            created_at=row["created_at"],
        )
    return None


def get_user_by_username(username: str) -> User | None:
    """Get user by username."""
    db = get_db()
    row = db.execute(
        "SELECT id, username, role, created_at FROM users WHERE username = ?",
        (username,),
    ).fetchone()
    if row:
        return User(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            created_at=row["created_at"],
        )
    return None


def get_all_users() -> list[User]:
    """Get all users, admins first, then by creation date."""
    db = get_db()
    rows = db.execute(
        """
        SELECT id, username, role, created_at FROM users
        ORDER BY role = 'admin' DESC, created_at ASC
        """
    ).fetchall()
    return [
        User(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            created_at=row["created_at"],
        )
        for row in rows
    ]


def get_current_user() -> User | None:
    """Get the currently logged-in user from session."""
    user_id = session.get("user_id")
    if user_id:
        return get_user_by_id(user_id)
    return None


def get_username() -> str:
    """Get current user's username (backwards compatibility)."""
    user = get_current_user()
    return user.username if user else "unknown"


# =============================================================================
# Authentication
# =============================================================================


def verify_user_password(username: str, password: str) -> User | None:
    """
    Verify password for a user.

    Returns User if valid, None if invalid.
    Also rehashes password if needed.
    """
    db = get_db()
    row = db.execute(
        "SELECT id, username, role, created_at, password_hash FROM users WHERE username = ?",
        (username,),
    ).fetchone()

    if not row:
        return None

    try:
        ph.verify(row["password_hash"], password)

        # Rehash if parameters changed
        if ph.check_needs_rehash(row["password_hash"]):
            new_hash = ph.hash(password)
            db.execute(
                "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_hash, row["id"]),
            )
            db.commit()

        return User(
            id=row["id"],
            username=row["username"],
            role=row["role"],
            created_at=row["created_at"],
        )
    except VerifyMismatchError:
        return None


def verify_password(password: str) -> bool:
    """Verify password for current user (backwards compatibility)."""
    user = get_current_user()
    if not user:
        return False
    result = verify_user_password(user.username, password)
    return result is not None


def is_authenticated() -> bool:
    """Check if current session is authenticated."""
    return session.get("user_id") is not None


def is_admin() -> bool:
    """Check if current user is an admin."""
    user = get_current_user()
    return user.is_admin if user else False


def login_user(user: User):
    """Set up session for logged-in user."""
    session["user_id"] = user.id
    session["username"] = user.username
    session["role"] = user.role
    # Legacy compatibility
    session["authenticated"] = True


def logout_user():
    """Clear session for logout."""
    session.clear()


# =============================================================================
# User Management
# =============================================================================


def generate_temp_password(length: int = 8) -> str:
    """Generate a random temporary password."""
    alphabet = string.ascii_letters + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


def validate_username(username: str) -> tuple[bool, str]:
    """
    Validate username format.

    Rules: 3-80 chars, alphanumeric + underscore/hyphen + @/. for email-style
    """
    if not username:
        return False, "Username is required"

    if len(username) < 3:
        return False, "Username must be at least 3 characters"

    if len(username) > 80:
        return False, "Username must be at most 80 characters"

    # Allow: alphanumeric, underscore, hyphen, @, . (for email-style)
    allowed = set(string.ascii_letters + string.digits + "_-@.")
    if not all(c in allowed for c in username):
        return False, "Username can only contain letters, numbers, underscore, hyphen, @ and ."

    # Must start with letter or number
    if username[0] not in string.ascii_letters + string.digits:
        return False, "Username must start with a letter or number"

    return True, ""


def validate_password(password: str) -> tuple[bool, str]:
    """Validate password requirements."""
    if not password:
        return False, "Password is required"

    if len(password) < 8:
        return False, "Password must be at least 8 characters"

    return True, ""


def create_user(
    username: str, password: str, role: str = ROLE_USER
) -> tuple[bool, str, User | None]:
    """
    Create a new user.

    Returns (success, message, user).
    """
    # Validate username
    valid, msg = validate_username(username)
    if not valid:
        return False, msg, None

    # Validate password
    valid, msg = validate_password(password)
    if not valid:
        return False, msg, None

    # Check if username already exists
    if get_user_by_username(username):
        return False, "Username already exists", None

    # Check user limit (only for non-admin users)
    if role != ROLE_ADMIN and not can_create_user():
        return False, f"Maximum of {MAX_USERS} users reached", None

    # Create user
    password_hash = ph.hash(password)
    db = get_db()

    try:
        cursor = db.execute(
            """
            INSERT INTO users (username, password_hash, role)
            VALUES (?, ?, ?)
            """,
            (username, password_hash, role),
        )
        db.commit()

        user = get_user_by_id(cursor.lastrowid)
        return True, "User created successfully", user
    except sqlite3.IntegrityError:
        return False, "Username already exists", None


def create_admin_user(username: str, password: str) -> tuple[bool, str]:
    """Create the initial admin user (first-run setup)."""
    if any_users_exist():
        return False, "Admin user already exists"

    success, msg, _ = create_user(username, password, ROLE_ADMIN)
    return success, msg


def change_password(
    user_id: int, current_password: str, new_password: str
) -> tuple[bool, str]:
    """Change a user's password (requires current password)."""
    user = get_user_by_id(user_id)
    if not user:
        return False, "User not found"

    # Verify current password
    if not verify_user_password(user.username, current_password):
        return False, "Current password is incorrect"

    # Validate new password
    valid, msg = validate_password(new_password)
    if not valid:
        return False, msg

    # Update password
    new_hash = ph.hash(new_password)
    db = get_db()
    db.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_hash, user_id),
    )
    db.commit()

    return True, "Password changed successfully"


def reset_user_password(user_id: int, new_password: str) -> tuple[bool, str]:
    """Reset a user's password (admin function, no current password required)."""
    user = get_user_by_id(user_id)
    if not user:
        return False, "User not found"

    # Validate new password
    valid, msg = validate_password(new_password)
    if not valid:
        return False, msg

    # Update password
    new_hash = ph.hash(new_password)
    db = get_db()
    db.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_hash, user_id),
    )
    db.commit()

    # Invalidate user's sessions
    invalidate_user_sessions(user_id)

    return True, "Password reset successfully"


def delete_user(user_id: int, current_user_id: int) -> tuple[bool, str]:
    """
    Delete a user.

    Cannot delete yourself or the last admin.
    """
    if user_id == current_user_id:
        return False, "Cannot delete yourself"

    user = get_user_by_id(user_id)
    if not user:
        return False, "User not found"

    # Check if this is the last admin
    if user.role == ROLE_ADMIN:
        db = get_db()
        admin_count = db.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin'"
        ).fetchone()[0]
        if admin_count <= 1:
            return False, "Cannot delete the last admin"

    # Invalidate user's sessions before deletion
    invalidate_user_sessions(user_id)

    # Delete user
    db = get_db()
    db.execute("DELETE FROM users WHERE id = ?", (user_id,))
    db.commit()

    return True, f"User '{user.username}' deleted"


def invalidate_user_sessions(user_id: int):
    """
    Invalidate all sessions for a user.

    This is called when a user is deleted or their password is reset.
    Since we use server-side sessions, we increment a "session version"
    that's checked on each request.
    """
    # For Flask's default session (client-side), we can't truly invalidate.
    # But we can add a check - store a "valid_from" timestamp in the DB
    # and compare against session creation time.
    #
    # For now, we'll use a simpler approach: store invalidated user IDs
    # in app config (memory) which gets checked by login_required.
    #
    # This works for single-process deployments (like RPi).
    # For multi-process, would need Redis or DB-backed sessions.

    if "invalidated_users" not in current_app.config:
        current_app.config["invalidated_users"] = set()

    current_app.config["invalidated_users"].add(user_id)


def is_session_valid() -> bool:
    """Check if current session is still valid (user not deleted/invalidated)."""
    user_id = session.get("user_id")
    if not user_id:
        return False

    # Check if user was invalidated
    invalidated = current_app.config.get("invalidated_users", set())
    if user_id in invalidated:
        return False

    # Check if user still exists
    if not get_user_by_id(user_id):
        return False

    return True


# =============================================================================
# Decorators
# =============================================================================


def login_required(f):
    """Decorator to require login for a route."""

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if auth is enabled
        if not current_app.config.get("AUTH_ENABLED", True):
            return f(*args, **kwargs)

        # Check for first-run setup
        if not any_users_exist():
            return redirect(url_for("setup"))

        # Check authentication
        if not is_authenticated():
            return redirect(url_for("login"))

        # Check if session is still valid (user not deleted)
        if not is_session_valid():
            logout_user()
            flash("Your session has expired. Please log in again.", "warning")
            return redirect(url_for("login"))

        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """Decorator to require admin role for a route."""

    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        # Check if auth is enabled
        if not current_app.config.get("AUTH_ENABLED", True):
            return f(*args, **kwargs)

        # Check for first-run setup
        if not any_users_exist():
            return redirect(url_for("setup"))

        # Check authentication
        if not is_authenticated():
            return redirect(url_for("login"))

        # Check if session is still valid
        if not is_session_valid():
            logout_user()
            flash("Your session has expired. Please log in again.", "warning")
            return redirect(url_for("login"))

        # Check admin role
        if not is_admin():
            flash("Admin access required", "error")
            return redirect(url_for("index"))

        return f(*args, **kwargs)

    return decorated_function


# =============================================================================
# App Initialization
# =============================================================================


def init_app(app):
    """Initialize auth module with Flask app."""
    app.teardown_appcontext(close_db)

    with app.app_context():
        init_db()
