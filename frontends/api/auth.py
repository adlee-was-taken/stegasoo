"""
API Key Authentication for Stegasoo REST API.

Provides simple API key authentication with hashed key storage.
Keys can be stored in user config (~/.stegasoo/) or project config (./config/).

Usage:
    from .auth import require_api_key, get_api_key_status

    @app.get("/protected")
    async def protected_endpoint(api_key: str = Depends(require_api_key)):
        return {"status": "authenticated"}
"""

import hashlib
import json
import os
import secrets
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, Security
from fastapi.security import APIKeyHeader

# API key header name
API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)

# Config locations
USER_CONFIG_DIR = Path.home() / ".stegasoo"
PROJECT_CONFIG_DIR = Path("./config")

# Key file name
API_KEYS_FILE = "api_keys.json"

# Environment variable for API key (alternative to file)
API_KEY_ENV_VAR = "STEGASOO_API_KEY"


def _hash_key(key: str) -> str:
    """Hash an API key for storage."""
    return hashlib.sha256(key.encode()).hexdigest()


def _get_keys_file(location: str = "user") -> Path:
    """Get path to API keys file."""
    if location == "project":
        return PROJECT_CONFIG_DIR / API_KEYS_FILE
    return USER_CONFIG_DIR / API_KEYS_FILE


def _load_keys(location: str = "user") -> dict:
    """Load API keys from config file."""
    keys_file = _get_keys_file(location)
    if keys_file.exists():
        try:
            with open(keys_file) as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"keys": [], "enabled": True}
    return {"keys": [], "enabled": True}


def _save_keys(data: dict, location: str = "user") -> None:
    """Save API keys to config file."""
    keys_file = _get_keys_file(location)
    keys_file.parent.mkdir(parents=True, exist_ok=True)

    with open(keys_file, "w") as f:
        json.dump(data, f, indent=2)

    # Secure permissions (owner read/write only)
    os.chmod(keys_file, 0o600)


def generate_api_key() -> str:
    """Generate a new API key."""
    # Format: stegasoo_XXXX_XXXXXXXXXXXXXXXXXXXXXXXXXXXX
    # 32 bytes = 256 bits of entropy
    random_part = secrets.token_hex(16)
    return f"stegasoo_{random_part[:4]}_{random_part[4:]}"


def add_api_key(name: str, location: str = "user") -> str:
    """
    Generate and store a new API key.

    Args:
        name: Descriptive name for the key (e.g., "laptop", "automation")
        location: "user" or "project"

    Returns:
        The generated API key (only shown once!)
    """
    key = generate_api_key()
    key_hash = _hash_key(key)

    data = _load_keys(location)

    # Check for duplicate name
    for existing in data["keys"]:
        if existing["name"] == name:
            raise ValueError(f"Key with name '{name}' already exists")

    data["keys"].append({
        "name": name,
        "hash": key_hash,
        "created": __import__("datetime").datetime.now().isoformat(),
    })

    _save_keys(data, location)

    return key


def remove_api_key(name: str, location: str = "user") -> bool:
    """
    Remove an API key by name.

    Returns:
        True if key was found and removed, False otherwise
    """
    data = _load_keys(location)
    original_count = len(data["keys"])

    data["keys"] = [k for k in data["keys"] if k["name"] != name]

    if len(data["keys"]) < original_count:
        _save_keys(data, location)
        return True
    return False


def list_api_keys(location: str = "user") -> list[dict]:
    """
    List all API keys (names and creation dates, not actual keys).
    """
    data = _load_keys(location)
    return [{"name": k["name"], "created": k.get("created", "unknown")} for k in data["keys"]]


def set_auth_enabled(enabled: bool, location: str = "user") -> None:
    """Enable or disable API key authentication."""
    data = _load_keys(location)
    data["enabled"] = enabled
    _save_keys(data, location)


def is_auth_enabled() -> bool:
    """Check if API key authentication is enabled."""
    # Check project config first, then user config
    for location in ["project", "user"]:
        data = _load_keys(location)
        if "enabled" in data:
            return data["enabled"]

    # Default: enabled if any keys exist
    return bool(get_all_key_hashes())


def get_all_key_hashes() -> set[str]:
    """Get all valid API key hashes from all sources."""
    hashes = set()

    # Check environment variable first
    env_key = os.environ.get(API_KEY_ENV_VAR)
    if env_key:
        hashes.add(_hash_key(env_key))

    # Check project and user configs
    for location in ["project", "user"]:
        data = _load_keys(location)
        for key_entry in data.get("keys", []):
            if "hash" in key_entry:
                hashes.add(key_entry["hash"])

    return hashes


def validate_api_key(key: str) -> bool:
    """Validate an API key against stored hashes."""
    if not key:
        return False

    key_hash = _hash_key(key)
    valid_hashes = get_all_key_hashes()

    return key_hash in valid_hashes


def get_api_key_status() -> dict:
    """Get current API key authentication status."""
    user_keys = list_api_keys("user")
    project_keys = list_api_keys("project")
    env_configured = bool(os.environ.get(API_KEY_ENV_VAR))

    total_keys = len(user_keys) + len(project_keys) + (1 if env_configured else 0)

    return {
        "enabled": is_auth_enabled(),
        "total_keys": total_keys,
        "user_keys": len(user_keys),
        "project_keys": len(project_keys),
        "env_configured": env_configured,
        "keys": {
            "user": user_keys,
            "project": project_keys,
        }
    }


# FastAPI dependency for API key authentication
async def require_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)) -> str:
    """
    FastAPI dependency that requires a valid API key.

    Usage:
        @app.get("/protected")
        async def endpoint(key: str = Depends(require_api_key)):
            ...
    """
    # Check if auth is enabled
    if not is_auth_enabled():
        return "auth_disabled"

    # No keys configured = auth disabled
    if not get_all_key_hashes():
        return "no_keys_configured"

    # Validate the provided key
    if not api_key:
        raise HTTPException(
            status_code=401,
            detail="API key required. Provide X-API-Key header.",
            headers={"WWW-Authenticate": "ApiKey"},
        )

    if not validate_api_key(api_key):
        raise HTTPException(
            status_code=403,
            detail="Invalid API key.",
        )

    return api_key


async def optional_api_key(api_key: Optional[str] = Security(API_KEY_HEADER)) -> Optional[str]:
    """
    FastAPI dependency that optionally validates API key.

    Returns the key if valid, None if not provided or invalid.
    Doesn't raise exceptions - useful for endpoints that work
    with or without auth.
    """
    if api_key and validate_api_key(api_key):
        return api_key
    return None
