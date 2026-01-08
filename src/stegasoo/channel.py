"""
Channel Key Management for Stegasoo (v4.0.0)

A channel key ties encode/decode operations to a specific deployment or group.
Messages encoded with one channel key can only be decoded by systems with the
same channel key configured.

Use cases:
- Organization deployment: IT sets a company-wide channel key
- Friend groups: Share a channel key for private communication
- Air-gapped systems: Generate unique key per installation
- Public instances: No channel key = compatible with any instance without a channel key

Storage priority:
1. Environment variable: STEGASOO_CHANNEL_KEY
2. Config file: ~/.stegasoo/channel.key or ./config/channel.key
3. None (public mode - compatible with any instance without a channel key)

INTEGRATION STATUS (v4.0.0):
- ✅ get_channel_key_hash() integrated into derive_hybrid_key() in crypto.py
- ✅ get_channel_key_hash() integrated into derive_pixel_key() in crypto.py
- ✅ channel_key parameter added to encode() and decode() functions
- ✅ Header flags indicate whether message was encoded with channel key
- ✅ Helpful error messages for channel key mismatches
"""

import hashlib
import os
import re
import secrets
from pathlib import Path

from .debug import debug

# Channel key format: 8 groups of 4 alphanumeric chars (32 chars total)
# Example: ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456
CHANNEL_KEY_PATTERN = re.compile(r"^[A-Z0-9]{4}(-[A-Z0-9]{4}){7}$")
CHANNEL_KEY_LENGTH = 32  # Characters (excluding dashes)
CHANNEL_KEY_FORMATTED_LENGTH = 39  # With dashes

# Environment variable name
CHANNEL_KEY_ENV_VAR = "STEGASOO_CHANNEL_KEY"

# Config locations (in priority order)
CONFIG_LOCATIONS = [
    Path("./config/channel.key"),  # Project config
    Path.home() / ".stegasoo" / "channel.key",  # User config
]

# Encrypted config marker
ENCRYPTED_PREFIX = "ENC:"


def _get_machine_key() -> bytes:
    """
    Get a machine-specific key for encrypting stored channel keys.

    Uses /etc/machine-id on Linux, falls back to hostname hash.
    This ties the encrypted key to this specific machine.
    """
    machine_id = None

    # Try Linux machine-id
    try:
        machine_id = Path("/etc/machine-id").read_text().strip()
    except (OSError, FileNotFoundError):
        pass

    # Fallback to hostname
    if not machine_id:
        import socket
        machine_id = socket.gethostname()

    # Hash to get consistent 32 bytes
    return hashlib.sha256(machine_id.encode()).digest()


def _encrypt_for_storage(plaintext: str) -> str:
    """
    Encrypt a channel key for storage using machine-specific key.

    Returns ENC: prefixed base64 string.
    """
    import base64

    key = _get_machine_key()
    plaintext_bytes = plaintext.encode()

    # XOR with key (cycling if needed)
    encrypted = bytes(
        pb ^ key[i % len(key)]
        for i, pb in enumerate(plaintext_bytes)
    )

    return ENCRYPTED_PREFIX + base64.b64encode(encrypted).decode()


def _decrypt_from_storage(stored: str) -> str | None:
    """
    Decrypt a stored channel key.

    Returns None if decryption fails or format is invalid.
    """
    import base64

    if not stored.startswith(ENCRYPTED_PREFIX):
        # Not encrypted, return as-is (legacy plaintext)
        return stored

    try:
        encrypted = base64.b64decode(stored[len(ENCRYPTED_PREFIX):])
        key = _get_machine_key()

        # XOR to decrypt
        decrypted = bytes(
            eb ^ key[i % len(key)]
            for i, eb in enumerate(encrypted)
        )

        return decrypted.decode()
    except Exception:
        return None


def generate_channel_key() -> str:
    """
    Generate a new random channel key.

    Returns:
        Formatted channel key (e.g., "ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456")

    Example:
        >>> key = generate_channel_key()
        >>> len(key)
        39
    """
    # Generate 32 random alphanumeric characters
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    raw_key = "".join(secrets.choice(alphabet) for _ in range(CHANNEL_KEY_LENGTH))

    formatted = format_channel_key(raw_key)
    debug.print(f"Generated channel key: {get_channel_fingerprint(formatted)}")
    return formatted


def format_channel_key(raw_key: str) -> str:
    """
    Format a raw key string into the standard format.

    Args:
        raw_key: Raw key string (with or without dashes)

    Returns:
        Formatted key with dashes (XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX)

    Raises:
        ValueError: If key is invalid length or contains invalid characters

    Example:
        >>> format_channel_key("ABCD1234EFGH5678IJKL9012MNOP3456")
        "ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456"
    """
    # Remove any existing dashes, spaces, and convert to uppercase
    clean = raw_key.replace("-", "").replace(" ", "").upper()

    if len(clean) != CHANNEL_KEY_LENGTH:
        raise ValueError(f"Channel key must be {CHANNEL_KEY_LENGTH} characters (got {len(clean)})")

    # Validate characters
    if not all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789" for c in clean):
        raise ValueError("Channel key must contain only letters A-Z and digits 0-9")

    # Format with dashes every 4 characters
    return "-".join(clean[i : i + 4] for i in range(0, CHANNEL_KEY_LENGTH, 4))


def validate_channel_key(key: str) -> bool:
    """
    Validate a channel key format.

    Args:
        key: Channel key to validate

    Returns:
        True if valid format, False otherwise

    Example:
        >>> validate_channel_key("ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456")
        True
        >>> validate_channel_key("invalid")
        False
    """
    if not key:
        return False

    try:
        formatted = format_channel_key(key)
        return bool(CHANNEL_KEY_PATTERN.match(formatted))
    except ValueError:
        return False


def get_channel_key() -> str | None:
    """
    Get the current channel key from environment or config.

    Checks in order:
    1. STEGASOO_CHANNEL_KEY environment variable
    2. ./config/channel.key file
    3. ~/.stegasoo/channel.key file

    Returns:
        Channel key if configured, None if in public mode

    Example:
        >>> key = get_channel_key()
        >>> if key:
        ...     print("Private channel")
        ... else:
        ...     print("Public mode")
    """
    # 1. Check environment variable
    env_key = os.environ.get(CHANNEL_KEY_ENV_VAR, "").strip()
    if env_key:
        if validate_channel_key(env_key):
            debug.print(f"Channel key from environment: {get_channel_fingerprint(env_key)}")
            return format_channel_key(env_key)
        else:
            debug.print(f"Warning: Invalid {CHANNEL_KEY_ENV_VAR} format, ignoring")

    # 2. Check config files (may be encrypted)
    for config_path in CONFIG_LOCATIONS:
        if config_path.exists():
            try:
                stored = config_path.read_text().strip()
                # Decrypt if encrypted, otherwise use as-is (legacy)
                key = _decrypt_from_storage(stored)
                if key and validate_channel_key(key):
                    debug.print(f"Channel key from {config_path}: {get_channel_fingerprint(key)}")
                    return format_channel_key(key)
            except (OSError, PermissionError) as e:
                debug.print(f"Could not read {config_path}: {e}")
                continue

    # 3. No channel key configured (public mode)
    debug.print("No channel key configured (public mode)")
    return None


def set_channel_key(key: str, location: str = "project") -> Path:
    """
    Save a channel key to config file.

    Args:
        key: Channel key to save (will be formatted)
        location: 'project' for ./config/ or 'user' for ~/.stegasoo/

    Returns:
        Path where key was saved

    Raises:
        ValueError: If key format is invalid

    Example:
        >>> path = set_channel_key("ABCD1234EFGH5678IJKL9012MNOP3456")
        >>> print(path)
        ./config/channel.key
    """
    formatted = format_channel_key(key)

    if location == "user":
        config_path = Path.home() / ".stegasoo" / "channel.key"
    else:
        config_path = Path("./config/channel.key")

    # Create directory if needed
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Encrypt and write (tied to this machine's identity)
    encrypted = _encrypt_for_storage(formatted)
    config_path.write_text(encrypted + "\n")

    # Set restrictive permissions (owner read/write only)
    try:
        config_path.chmod(0o600)
    except (OSError, AttributeError):
        pass  # Windows doesn't support chmod the same way

    debug.print(f"Channel key saved to {config_path}")
    return config_path


def clear_channel_key(location: str = "all") -> list[Path]:
    """
    Remove channel key configuration.

    Args:
        location: 'project', 'user', or 'all'

    Returns:
        List of paths that were deleted

    Example:
        >>> deleted = clear_channel_key('all')
        >>> print(f"Removed {len(deleted)} files")
    """
    deleted = []

    paths_to_check = []
    if location in ("project", "all"):
        paths_to_check.append(Path("./config/channel.key"))
    if location in ("user", "all"):
        paths_to_check.append(Path.home() / ".stegasoo" / "channel.key")

    for path in paths_to_check:
        if path.exists():
            try:
                path.unlink()
                deleted.append(path)
                debug.print(f"Removed channel key: {path}")
            except (OSError, PermissionError) as e:
                debug.print(f"Could not remove {path}: {e}")

    return deleted


def get_channel_key_hash(key: str | None = None) -> bytes | None:
    """
    Get the channel key as a 32-byte hash suitable for key derivation.

    This hash is mixed into the Argon2 key derivation to bind
    encryption to a specific channel.

    Args:
        key: Channel key (if None, reads from config)

    Returns:
        32-byte SHA-256 hash of channel key, or None if no channel key

    Example:
        >>> hash_bytes = get_channel_key_hash()
        >>> if hash_bytes:
        ...     print(f"Hash: {len(hash_bytes)} bytes")
    """
    if key is None:
        key = get_channel_key()

    if not key:
        return None

    # Hash the formatted key to get consistent 32 bytes
    formatted = format_channel_key(key)
    return hashlib.sha256(formatted.encode("utf-8")).digest()


def get_channel_fingerprint(key: str | None = None) -> str | None:
    """
    Get a short fingerprint for display purposes.
    Shows first and last 4 chars with masked middle.

    Args:
        key: Channel key (if None, reads from config)

    Returns:
        Fingerprint like "ABCD-••••-••••-••••-••••-••••-••••-3456" or None

    Example:
        >>> print(get_channel_fingerprint())
        ABCD-••••-••••-••••-••••-••••-••••-3456
    """
    if key is None:
        key = get_channel_key()

    if not key:
        return None

    formatted = format_channel_key(key)
    parts = formatted.split("-")

    # Show first and last group, mask the rest
    masked = [parts[0]] + ["••••"] * 6 + [parts[-1]]
    return "-".join(masked)


def get_channel_status() -> dict:
    """
    Get comprehensive channel key status.

    Returns:
        Dictionary with:
        - mode: 'private' or 'public'
        - configured: bool
        - fingerprint: masked key or None
        - source: where key came from or None
        - key: full key (for export) or None

    Example:
        >>> status = get_channel_status()
        >>> print(f"Mode: {status['mode']}")
        Mode: private
    """
    key = get_channel_key()

    if key:
        # Find which source provided the key
        source = "unknown"
        env_key = os.environ.get(CHANNEL_KEY_ENV_VAR, "").strip()
        if env_key and validate_channel_key(env_key):
            source = "environment"
        else:
            for config_path in CONFIG_LOCATIONS:
                if config_path.exists():
                    try:
                        stored = config_path.read_text().strip()
                        file_key = _decrypt_from_storage(stored)
                        if file_key and validate_channel_key(file_key) and format_channel_key(file_key) == key:
                            source = str(config_path)
                            break
                    except (OSError, PermissionError, ValueError):
                        continue

        return {
            "mode": "private",
            "configured": True,
            "fingerprint": get_channel_fingerprint(key),
            "source": source,
            "key": key,
        }
    else:
        return {
            "mode": "public",
            "configured": False,
            "fingerprint": None,
            "source": None,
            "key": None,
        }


def has_channel_key() -> bool:
    """
    Quick check if a channel key is configured.

    Returns:
        True if channel key is set, False for public mode

    Example:
        >>> if has_channel_key():
        ...     print("Private channel active")
    """
    return get_channel_key() is not None


def resolve_channel_key(
    value: str | None = None,
    *,
    file_path: str | Path | None = None,
    no_channel: bool = False,
) -> str | None:
    """
    Resolve a channel key from user input (unified for all frontends).

    This consolidates channel key resolution logic used by CLI, API, and WebUI.

    Args:
        value: Input value:
            - 'auto' or None: Use server-configured key
            - 'none' or '': Public mode (no channel key)
            - explicit key: Validate and use
        file_path: Path to file containing channel key
        no_channel: If True, return "" for public mode (overrides value)

    Returns:
        None: Use server-configured key (auto mode)
        "": Public mode (no channel key)
        str: Explicit valid channel key

    Raises:
        ValueError: If key format is invalid
        FileNotFoundError: If file_path doesn't exist

    Example:
        >>> resolve_channel_key("auto")  # -> None
        >>> resolve_channel_key("none")  # -> ""
        >>> resolve_channel_key(no_channel=True)  # -> ""
        >>> resolve_channel_key("ABCD-1234-...")  # -> "ABCD-1234-..."
        >>> resolve_channel_key(file_path="key.txt")  # reads from file
    """
    debug.print(f"resolve_channel_key: value={value}, file_path={file_path}, no_channel={no_channel}")

    # no_channel flag takes precedence
    if no_channel:
        debug.print("resolve_channel_key: public mode (no_channel=True)")
        return ""

    # Read from file if provided
    if file_path:
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"Channel key file not found: {file_path}")
        key = path.read_text().strip()
        if not validate_channel_key(key):
            raise ValueError(f"Invalid channel key format in file: {file_path}")
        debug.print(f"resolve_channel_key: from file -> {get_channel_fingerprint(key)}")
        return format_channel_key(key)

    # Handle value string
    if value is None or value.lower() == "auto":
        debug.print("resolve_channel_key: auto mode (server config)")
        return None

    if value == "" or value.lower() == "none":
        debug.print("resolve_channel_key: public mode (explicit none)")
        return ""

    # Explicit key - validate
    if validate_channel_key(value):
        formatted = format_channel_key(value)
        debug.print(f"resolve_channel_key: explicit key -> {get_channel_fingerprint(formatted)}")
        return formatted

    raise ValueError(
        "Invalid channel key format. Expected: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX\n"
        "Generate a new key with: stegasoo channel generate"
    )


def get_channel_response_info(channel_key: str | None) -> dict:
    """
    Get channel info for API/WebUI responses.

    Args:
        channel_key: Resolved channel key (None=auto, ""=public, str=explicit)

    Returns:
        Dict with mode, fingerprint, and display info

    Example:
        >>> info = get_channel_response_info("ABCD-1234-...")
        >>> info['mode']
        'explicit'
    """
    if channel_key is None:
        # Auto mode - check server config
        server_key = get_channel_key()
        if server_key:
            return {
                "mode": "private",
                "fingerprint": get_channel_fingerprint(server_key),
                "source": "server",
            }
        return {
            "mode": "public",
            "fingerprint": None,
            "source": "server",
        }

    if channel_key == "":
        return {
            "mode": "public",
            "fingerprint": None,
            "source": "explicit",
        }

    return {
        "mode": "private",
        "fingerprint": get_channel_fingerprint(channel_key),
        "source": "explicit",
    }


# =============================================================================
# CLI SUPPORT
# =============================================================================

if __name__ == "__main__":
    import sys

    def print_status():
        """Print current channel status."""
        status = get_channel_status()
        print(f"Mode: {status['mode'].upper()}")
        if status["configured"]:
            print(f"Fingerprint: {status['fingerprint']}")
            print(f"Source: {status['source']}")
        else:
            print("No channel key configured (public mode)")

    if len(sys.argv) < 2:
        print("Channel Key Manager")
        print("=" * 40)
        print_status()
        print()
        print("Commands:")
        print("  python -m stegasoo.channel generate  - Generate new key")
        print("  python -m stegasoo.channel set <KEY> - Set channel key")
        print("  python -m stegasoo.channel show      - Show full key")
        print("  python -m stegasoo.channel clear     - Remove channel key")
        print("  python -m stegasoo.channel status    - Show status")
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == "generate":
        key = generate_channel_key()
        print("Generated channel key:")
        print(f"  {key}")
        print()
        save = input("Save to config? [y/N]: ").strip().lower()
        if save == "y":
            path = set_channel_key(key)
            print(f"Saved to: {path}")

    elif cmd == "set":
        if len(sys.argv) < 3:
            print("Usage: python -m stegasoo.channel set <KEY>")
            sys.exit(1)

        try:
            key = sys.argv[2]
            formatted = format_channel_key(key)
            path = set_channel_key(formatted)
            print(f"Channel key set: {get_channel_fingerprint(formatted)}")
            print(f"Saved to: {path}")
        except ValueError as e:
            print(f"Error: {e}")
            sys.exit(1)

    elif cmd == "show":
        status = get_channel_status()
        if status["configured"]:
            print(f"Channel key: {status['key']}")
            print(f"Source: {status['source']}")
        else:
            print("No channel key configured")

    elif cmd == "clear":
        deleted = clear_channel_key("all")
        if deleted:
            print(f"Removed channel key from: {', '.join(str(p) for p in deleted)}")
        else:
            print("No channel key files found")

    elif cmd == "status":
        print_status()

    else:
        print(f"Unknown command: {cmd}")
        sys.exit(1)
