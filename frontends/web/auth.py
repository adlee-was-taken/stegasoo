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
MAX_CHANNEL_KEYS = 10  # Per user
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
    else:
        # Existing install - check for new tables (migrations)
        _ensure_channel_keys_table(db)
        _ensure_app_settings_table(db)


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

        CREATE TABLE IF NOT EXISTS user_channel_keys (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            channel_key TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_used_at TEXT,
            FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
            UNIQUE(user_id, channel_key)
        );

        CREATE INDEX IF NOT EXISTS idx_channel_keys_user ON user_channel_keys(user_id);

        -- App-level settings (v4.1.0)
        -- Stores recovery key hash and other instance-wide settings
        CREATE TABLE IF NOT EXISTS app_settings (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
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


def _ensure_channel_keys_table(db: sqlite3.Connection):
    """Ensure user_channel_keys table exists (migration for existing installs)."""
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='user_channel_keys'"
    )
    if cursor.fetchone() is None:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS user_channel_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                channel_key TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                last_used_at TEXT,
                FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
                UNIQUE(user_id, channel_key)
            );

            CREATE INDEX IF NOT EXISTS idx_channel_keys_user ON user_channel_keys(user_id);
        """)
        db.commit()


def _ensure_app_settings_table(db: sqlite3.Connection):
    """Ensure app_settings table exists (v4.1.0 migration)."""
    cursor = db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='app_settings'"
    )
    if cursor.fetchone() is None:
        db.executescript("""
            CREATE TABLE IF NOT EXISTS app_settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            );
        """)
        db.commit()


# =============================================================================
# App Settings (v4.1.0)
# =============================================================================


def get_app_setting(key: str) -> str | None:
    """Get an app-level setting value."""
    db = get_db()
    row = db.execute(
        "SELECT value FROM app_settings WHERE key = ?", (key,)
    ).fetchone()
    return row["value"] if row else None


def set_app_setting(key: str, value: str) -> None:
    """Set an app-level setting value."""
    db = get_db()
    db.execute(
        """
        INSERT INTO app_settings (key, value)
        VALUES (?, ?)
        ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = CURRENT_TIMESTAMP
        """,
        (key, value, value),
    )
    db.commit()


def delete_app_setting(key: str) -> bool:
    """Delete an app-level setting. Returns True if deleted."""
    db = get_db()
    cursor = db.execute("DELETE FROM app_settings WHERE key = ?", (key,))
    db.commit()
    return cursor.rowcount > 0


# =============================================================================
# Recovery Key Management (v4.1.0)
# =============================================================================


# Setting key for recovery hash
RECOVERY_KEY_SETTING = "recovery_key_hash"


def has_recovery_key() -> bool:
    """Check if a recovery key has been configured."""
    return get_app_setting(RECOVERY_KEY_SETTING) is not None


def get_recovery_key_hash() -> str | None:
    """Get the stored recovery key hash."""
    return get_app_setting(RECOVERY_KEY_SETTING)


def set_recovery_key_hash(key_hash: str) -> None:
    """Store a recovery key hash."""
    set_app_setting(RECOVERY_KEY_SETTING, key_hash)


def clear_recovery_key() -> bool:
    """Remove the recovery key. Returns True if removed."""
    return delete_app_setting(RECOVERY_KEY_SETTING)


def verify_and_reset_admin_password(recovery_key: str, new_password: str) -> tuple[bool, str]:
    """
    Verify recovery key and reset the first admin's password.

    Args:
        recovery_key: User-provided recovery key
        new_password: New password to set

    Returns:
        (success, message) tuple
    """
    from stegasoo.recovery import verify_recovery_key

    stored_hash = get_recovery_key_hash()
    if not stored_hash:
        return False, "No recovery key configured for this instance"

    if not verify_recovery_key(recovery_key, stored_hash):
        return False, "Invalid recovery key"

    # Find first admin user
    db = get_db()
    admin = db.execute(
        "SELECT id, username FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
    ).fetchone()

    if not admin:
        return False, "No admin user found"

    # Reset password
    new_hash = ph.hash(new_password)
    db.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_hash, admin["id"]),
    )
    db.commit()

    # Invalidate all sessions for this user
    invalidate_user_sessions(admin["id"])

    return True, f"Password reset for '{admin['username']}'"


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
# Channel Keys
# =============================================================================


@dataclass
class ChannelKey:
    """Saved channel key data class."""

    id: int
    user_id: int
    name: str
    channel_key: str
    created_at: str
    last_used_at: str | None


def get_user_channel_keys(user_id: int) -> list[ChannelKey]:
    """Get all saved channel keys for a user, most recently used first."""
    db = get_db()
    rows = db.execute(
        """
        SELECT id, user_id, name, channel_key, created_at, last_used_at
        FROM user_channel_keys
        WHERE user_id = ?
        ORDER BY last_used_at DESC NULLS LAST, created_at DESC
        """,
        (user_id,),
    ).fetchall()
    return [
        ChannelKey(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            channel_key=row["channel_key"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
        )
        for row in rows
    ]


def get_channel_key_by_id(key_id: int, user_id: int) -> ChannelKey | None:
    """Get a specific channel key (ensures user owns it)."""
    db = get_db()
    row = db.execute(
        """
        SELECT id, user_id, name, channel_key, created_at, last_used_at
        FROM user_channel_keys
        WHERE id = ? AND user_id = ?
        """,
        (key_id, user_id),
    ).fetchone()
    if row:
        return ChannelKey(
            id=row["id"],
            user_id=row["user_id"],
            name=row["name"],
            channel_key=row["channel_key"],
            created_at=row["created_at"],
            last_used_at=row["last_used_at"],
        )
    return None


def get_channel_key_count(user_id: int) -> int:
    """Get count of saved channel keys for a user."""
    db = get_db()
    result = db.execute(
        "SELECT COUNT(*) FROM user_channel_keys WHERE user_id = ?", (user_id,)
    ).fetchone()
    return result[0] if result else 0


def can_save_channel_key(user_id: int) -> bool:
    """Check if user can save more channel keys (within limit)."""
    return get_channel_key_count(user_id) < MAX_CHANNEL_KEYS


def save_channel_key(
    user_id: int, name: str, channel_key: str
) -> tuple[bool, str, ChannelKey | None]:
    """
    Save a channel key for a user.

    Returns (success, message, key).
    """
    # Validate name
    name = name.strip()
    if not name:
        return False, "Key name is required", None
    if len(name) > 50:
        return False, "Key name must be at most 50 characters", None

    # Validate channel key format (hex string)
    channel_key = channel_key.strip().lower()
    if not channel_key:
        return False, "Channel key is required", None
    if not all(c in "0123456789abcdef" for c in channel_key):
        return False, "Invalid channel key format", None

    # Check limit
    if not can_save_channel_key(user_id):
        return False, f"Maximum of {MAX_CHANNEL_KEYS} saved keys reached", None

    db = get_db()
    try:
        cursor = db.execute(
            """
            INSERT INTO user_channel_keys (user_id, name, channel_key)
            VALUES (?, ?, ?)
            """,
            (user_id, name, channel_key),
        )
        db.commit()

        key = get_channel_key_by_id(cursor.lastrowid, user_id)
        return True, "Channel key saved", key
    except sqlite3.IntegrityError:
        return False, "This channel key is already saved", None


def update_channel_key_name(
    key_id: int, user_id: int, new_name: str
) -> tuple[bool, str]:
    """Update the name of a saved channel key."""
    new_name = new_name.strip()
    if not new_name:
        return False, "Key name is required"
    if len(new_name) > 50:
        return False, "Key name must be at most 50 characters"

    key = get_channel_key_by_id(key_id, user_id)
    if not key:
        return False, "Channel key not found"

    db = get_db()
    db.execute(
        "UPDATE user_channel_keys SET name = ? WHERE id = ? AND user_id = ?",
        (new_name, key_id, user_id),
    )
    db.commit()
    return True, "Key name updated"


def update_channel_key_last_used(key_id: int, user_id: int):
    """Update the last_used_at timestamp for a channel key."""
    db = get_db()
    db.execute(
        """
        UPDATE user_channel_keys
        SET last_used_at = CURRENT_TIMESTAMP
        WHERE id = ? AND user_id = ?
        """,
        (key_id, user_id),
    )
    db.commit()


def delete_channel_key(key_id: int, user_id: int) -> tuple[bool, str]:
    """Delete a saved channel key."""
    key = get_channel_key_by_id(key_id, user_id)
    if not key:
        return False, "Channel key not found"

    db = get_db()
    db.execute(
        "DELETE FROM user_channel_keys WHERE id = ? AND user_id = ?",
        (key_id, user_id),
    )
    db.commit()
    return True, f"Key '{key.name}' deleted"


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
