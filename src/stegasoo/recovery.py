"""
Stegasoo Admin Recovery Module (v4.1.0)

Generates and manages recovery keys for admin password reset.

Recovery keys use the same format as channel keys (32 alphanumeric chars
with dashes) but serve a different purpose - they allow resetting the
admin password when locked out.

Security model:
- Recovery key is generated once during setup
- Only the hash is stored in the database
- The actual key is shown once and must be saved by the user
- Key can reset any admin account's password
- No recovery key = no password reset possible (most secure)

Usage:
    # During setup - generate and show to user
    key = generate_recovery_key()
    key_hash = hash_recovery_key(key)
    # Store key_hash in database, show key to user

    # During recovery - verify user's key
    if verify_recovery_key(user_input, stored_hash):
        # Allow password reset
"""

import base64
import hashlib
import secrets
from io import BytesIO

from .constants import RECOVERY_OBFUSCATION_KEY
from .debug import debug


def _xor_bytes(data: bytes, key: bytes) -> bytes:
    """XOR data with repeating key."""
    return bytes(b ^ key[i % len(key)] for i, b in enumerate(data))


def obfuscate_key(key: str) -> str:
    """
    Obfuscate a recovery key for QR encoding.

    XORs the key with magic header hash and base64 encodes.
    Result looks like random gibberish when scanned.

    Args:
        key: Plain recovery key (formatted or normalized)

    Returns:
        Obfuscated string prefixed with "STEGO:" marker
    """
    normalized = normalize_recovery_key(key)
    key_bytes = normalized.encode("utf-8")
    xored = _xor_bytes(key_bytes, RECOVERY_OBFUSCATION_KEY)
    encoded = base64.b64encode(xored).decode("ascii")
    return f"STEGO:{encoded}"


def deobfuscate_key(obfuscated: str) -> str | None:
    """
    Deobfuscate a recovery key from QR data.

    Reverses the obfuscation process.

    Args:
        obfuscated: Obfuscated string from QR scan

    Returns:
        Formatted recovery key, or None if invalid
    """
    if not obfuscated.startswith("STEGO:"):
        # Not obfuscated - try as plain key
        try:
            return format_recovery_key(obfuscated)
        except ValueError:
            return None

    try:
        encoded = obfuscated[6:]  # Strip "STEGO:" prefix
        xored = base64.b64decode(encoded)
        key_bytes = _xor_bytes(xored, RECOVERY_OBFUSCATION_KEY)
        normalized = key_bytes.decode("utf-8")
        return format_recovery_key(normalized)
    except Exception:
        return None


# =============================================================================
# STEGO BACKUP - Hide recovery key in an image using Stegasoo itself
# =============================================================================

# Fixed credentials for recovery key stego (internal, not user-facing)
# These are hardcoded - security is in the obscurity of the stego image
_RECOVERY_STEGO_PASSPHRASE = "stegasoo-recovery-v1"
_RECOVERY_STEGO_PIN = "314159"  # Pi digits - fixed, not secret

# Size limits for carrier image
STEGO_BACKUP_MIN_SIZE = 50 * 1024      # 50 KB
STEGO_BACKUP_MAX_SIZE = 2 * 1024 * 1024  # 2 MB


def create_stego_backup(
    recovery_key: str,
    carrier_image: bytes,
) -> bytes:
    """
    Hide recovery key in an image using Stegasoo steganography.

    Uses the same image as both carrier and reference for simplicity.
    Fixed internal passphrase, no PIN required - obscurity is the security.

    Args:
        recovery_key: The recovery key to hide
        carrier_image: JPEG image bytes (50KB-2MB, used as carrier AND reference)

    Returns:
        PNG image with hidden recovery key

    Raises:
        ValueError: If image size out of range or invalid format
    """
    from .encode import encode

    # Validate image size
    size = len(carrier_image)
    if size < STEGO_BACKUP_MIN_SIZE:
        raise ValueError(f"Image too small: {size // 1024}KB (min 50KB)")
    if size > STEGO_BACKUP_MAX_SIZE:
        raise ValueError(f"Image too large: {size // 1024}KB (max 2MB)")

    # Normalize key for embedding
    formatted_key = format_recovery_key(recovery_key)

    # Encode using Stegasoo - same image as carrier and reference
    result = encode(
        message=formatted_key,
        reference_photo=carrier_image,  # Same image for simplicity
        carrier_image=carrier_image,
        passphrase=_RECOVERY_STEGO_PASSPHRASE,
        pin=_RECOVERY_STEGO_PIN,
    )

    debug.print(f"Created stego backup: {len(result.stego_image)} bytes")
    return result.stego_image


def extract_stego_backup(
    stego_image: bytes,
    reference_photo: bytes,
) -> str | None:
    """
    Extract recovery key from a stego backup image.

    Args:
        stego_image: The stego image containing hidden key
        reference_photo: Original reference photo (same as was used for carrier)

    Returns:
        Extracted recovery key (formatted), or None if extraction fails
    """
    from .decode import decode
    from .exceptions import DecryptionError

    try:
        result = decode(
            stego_image=stego_image,
            reference_photo=reference_photo,
            passphrase=_RECOVERY_STEGO_PASSPHRASE,
            pin=_RECOVERY_STEGO_PIN,
        )

        # Validate it's a proper recovery key
        extracted = result.message or ""
        formatted = format_recovery_key(extracted)
        debug.print(f"Extracted recovery key from stego: {get_recovery_fingerprint(formatted)}")
        return formatted

    except (DecryptionError, ValueError) as e:
        debug.print(f"Stego backup extraction failed: {e}")
        return None

# Recovery key format: same as channel key (32 chars, 8 groups of 4)
RECOVERY_KEY_LENGTH = 32
RECOVERY_KEY_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def generate_recovery_key() -> str:
    """
    Generate a new random recovery key.

    Format: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
    (32 alphanumeric characters with dashes)

    Returns:
        Formatted recovery key string

    Example:
        >>> key = generate_recovery_key()
        >>> len(key)
        39
        >>> key.count('-')
        7
    """
    # Generate 32 random alphanumeric characters
    raw_key = "".join(
        secrets.choice(RECOVERY_KEY_ALPHABET)
        for _ in range(RECOVERY_KEY_LENGTH)
    )

    # Format with dashes every 4 characters
    formatted = "-".join(
        raw_key[i:i + 4]
        for i in range(0, RECOVERY_KEY_LENGTH, 4)
    )

    debug.print(f"Generated recovery key: {formatted[:4]}-••••-...-{formatted[-4:]}")
    return formatted


def normalize_recovery_key(key: str) -> str:
    """
    Normalize a recovery key for validation/hashing.

    Removes dashes, spaces, converts to uppercase.

    Args:
        key: Raw key input (may have dashes, spaces, mixed case)

    Returns:
        Normalized key (32 uppercase alphanumeric chars)

    Raises:
        ValueError: If key has invalid length or characters

    Example:
        >>> normalize_recovery_key("abcd-1234-efgh-5678-ijkl-9012-mnop-3456")
        "ABCD1234EFGH5678IJKL9012MNOP3456"
    """
    # Remove dashes and spaces, uppercase
    clean = key.replace("-", "").replace(" ", "").upper()

    # Validate length
    if len(clean) != RECOVERY_KEY_LENGTH:
        raise ValueError(
            f"Recovery key must be {RECOVERY_KEY_LENGTH} characters "
            f"(got {len(clean)})"
        )

    # Validate characters
    if not all(c in RECOVERY_KEY_ALPHABET for c in clean):
        raise ValueError(
            "Recovery key must contain only letters A-Z and digits 0-9"
        )

    return clean


def format_recovery_key(key: str) -> str:
    """
    Format a recovery key with dashes for display.

    Args:
        key: Raw or normalized key

    Returns:
        Formatted key (XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX)

    Example:
        >>> format_recovery_key("ABCD1234EFGH5678IJKL9012MNOP3456")
        "ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456"
    """
    clean = normalize_recovery_key(key)
    return "-".join(clean[i:i + 4] for i in range(0, RECOVERY_KEY_LENGTH, 4))


def hash_recovery_key(key: str) -> str:
    """
    Hash a recovery key for secure storage.

    Uses SHA-256 with a fixed salt prefix. The hash is stored in the
    database; the original key is never stored.

    Args:
        key: Recovery key (formatted or raw)

    Returns:
        Hex-encoded hash string (64 chars)

    Example:
        >>> key = "ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456"
        >>> len(hash_recovery_key(key))
        64
    """
    clean = normalize_recovery_key(key)

    # Use a fixed salt prefix for recovery keys
    # This differentiates from other hashes in the system
    salted = f"stegasoo-recovery-v1:{clean}"

    hash_bytes = hashlib.sha256(salted.encode("utf-8")).digest()
    hash_hex = hash_bytes.hex()

    debug.print(f"Hashed recovery key: {hash_hex[:8]}...")
    return hash_hex


def verify_recovery_key(key: str, stored_hash: str) -> bool:
    """
    Verify a recovery key against a stored hash.

    Args:
        key: User-provided recovery key
        stored_hash: Hash from database

    Returns:
        True if key matches, False otherwise

    Example:
        >>> key = generate_recovery_key()
        >>> h = hash_recovery_key(key)
        >>> verify_recovery_key(key, h)
        True
        >>> verify_recovery_key("WRONG-KEY!", h)
        False
    """
    try:
        computed_hash = hash_recovery_key(key)
        # Use constant-time comparison to prevent timing attacks
        matches = secrets.compare_digest(computed_hash, stored_hash)
        debug.print(f"Recovery key verification: {'success' if matches else 'failed'}")
        return matches
    except ValueError:
        # Invalid key format
        debug.print("Recovery key verification: invalid format")
        return False


def get_recovery_fingerprint(key: str) -> str:
    """
    Get a short fingerprint for display (first and last 4 chars).

    Args:
        key: Recovery key

    Returns:
        Fingerprint like "ABCD-••••-...-3456"

    Example:
        >>> get_recovery_fingerprint("ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456")
        "ABCD-••••-••••-••••-••••-••••-••••-3456"
    """
    formatted = format_recovery_key(key)
    parts = formatted.split("-")
    masked = [parts[0]] + ["••••"] * 6 + [parts[-1]]
    return "-".join(masked)


def generate_recovery_qr(key: str) -> bytes:
    """
    Generate a QR code image for the recovery key.

    The key is obfuscated using XOR with Stegasoo's magic headers,
    so scanning the QR shows gibberish instead of the actual key.

    Args:
        key: Recovery key

    Returns:
        PNG image bytes

    Raises:
        ImportError: If qrcode library not available

    Example:
        >>> key = generate_recovery_key()
        >>> png_bytes = generate_recovery_qr(key)
        >>> len(png_bytes) > 0
        True
    """
    try:
        import qrcode
    except ImportError:
        raise ImportError("qrcode library required: pip install qrcode[pil]")

    # Obfuscate so scanning shows gibberish, not the actual key
    obfuscated = obfuscate_key(key)

    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(obfuscated)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    img.save(buffer, format="PNG")
    buffer.seek(0)

    debug.print(f"Generated recovery QR (obfuscated): {len(buffer.getvalue())} bytes")
    return buffer.getvalue()


def extract_key_from_qr(image_data: bytes) -> str | None:
    """
    Extract recovery key from a QR code image.

    Handles both obfuscated (STEGO:...) and plain key formats.

    Args:
        image_data: PNG/JPEG image bytes containing QR code

    Returns:
        Extracted and validated recovery key, or None if not found/invalid

    Example:
        >>> key = generate_recovery_key()
        >>> qr = generate_recovery_qr(key)
        >>> extract_key_from_qr(qr) == format_recovery_key(key)
        True
    """
    try:
        from PIL import Image
        from pyzbar import pyzbar
    except ImportError:
        debug.print("pyzbar/PIL not available for QR reading")
        return None

    try:
        img = Image.open(BytesIO(image_data))
        decoded = pyzbar.decode(img)

        for obj in decoded:
            data = obj.data.decode("utf-8").strip()

            # Try deobfuscation first (handles both obfuscated and plain)
            result = deobfuscate_key(data)
            if result:
                debug.print(f"Extracted recovery key from QR: {get_recovery_fingerprint(result)}")
                return result

        debug.print("No valid recovery key found in QR")
        return None

    except Exception as e:
        debug.print(f"QR extraction error: {e}")
        return None
