"""
Stegasoo Cryptographic Functions (v4.0.0 - Channel Key Support)

Key derivation, encryption, and decryption using AES-256-GCM.
Supports both text messages and binary file payloads.

BREAKING CHANGES in v4.0.0:
- Added channel key support for deployment/group isolation
- Messages encoded with a channel key require the same key to decode
- Channel key can be configured via environment, config file, or explicit parameter
- FORMAT_VERSION bumped to 5

BREAKING CHANGES in v3.2.0:
- Removed date dependency from key derivation
- Renamed day_phrase → passphrase (no daily rotation needed)
"""

import hashlib
import io
import secrets
import struct

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from PIL import Image

from .constants import (
    ARGON2_MEMORY_COST,
    ARGON2_PARALLELISM,
    ARGON2_TIME_COST,
    FORMAT_VERSION,
    IV_SIZE,
    MAGIC_HEADER,
    MAX_FILENAME_LENGTH,
    PAYLOAD_FILE,
    PAYLOAD_TEXT,
    PBKDF2_ITERATIONS,
    SALT_SIZE,
    TAG_SIZE,
)
from .exceptions import DecryptionError, EncryptionError, InvalidHeaderError, KeyDerivationError
from .models import DecodeResult, FilePayload

# Check for Argon2 availability
try:
    from argon2.low_level import Type, hash_secret_raw

    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


# =============================================================================
# CHANNEL KEY RESOLUTION
# =============================================================================

# Sentinel value for "use auto-detected channel key"
CHANNEL_KEY_AUTO = "auto"


def _resolve_channel_key(channel_key: str | bool | None) -> bytes | None:
    """
    Resolve channel key parameter to actual key hash.

    Args:
        channel_key: Channel key parameter with these behaviors:
            - None or "auto": Use server's configured key (from env/config)
            - str (valid key): Use this specific key
            - "" or False: Explicitly use NO channel key (public mode)

    Returns:
        32-byte channel key hash, or None for public mode
    """
    # Explicit public mode
    if channel_key == "" or channel_key is False:
        return None

    # Auto-detect from environment/config
    if channel_key is None or channel_key == CHANNEL_KEY_AUTO:
        from .channel import get_channel_key_hash

        return get_channel_key_hash()

    # Explicit key provided - validate and hash it
    if isinstance(channel_key, str):
        from .channel import format_channel_key, validate_channel_key

        if not validate_channel_key(channel_key):
            raise ValueError(f"Invalid channel key format: {channel_key}")
        formatted = format_channel_key(channel_key)
        return hashlib.sha256(formatted.encode("utf-8")).digest()

    raise ValueError(f"Invalid channel_key type: {type(channel_key)}")


# =============================================================================
# CORE CRYPTO FUNCTIONS
# =============================================================================


def hash_photo(image_data: bytes) -> bytes:
    """
    Compute deterministic hash of photo pixel content.

    This normalizes the image to RGB and hashes the raw pixel data,
    making it resistant to metadata changes.

    Args:
        image_data: Raw image file bytes

    Returns:
        32-byte SHA-256 hash
    """
    img: Image.Image = Image.open(io.BytesIO(image_data)).convert("RGB")
    pixels = img.tobytes()

    # Double-hash with prefix for additional mixing
    h = hashlib.sha256(pixels).digest()
    h = hashlib.sha256(h + pixels[:1024]).digest()
    return h


def derive_hybrid_key(
    photo_data: bytes,
    passphrase: str,
    salt: bytes,
    pin: str = "",
    rsa_key_data: bytes | None = None,
    channel_key: str | bool | None = None,
) -> bytes:
    """
    Derive encryption key from multiple factors.

    Combines:
    - Photo hash (something you have)
    - Passphrase (something you know)
    - PIN (something you know, static)
    - RSA key (something you have)
    - Channel key (deployment/group binding)
    - Salt (random per message)

    Uses Argon2id if available, falls back to PBKDF2.

    Args:
        photo_data: Reference photo bytes
        passphrase: Shared passphrase (recommend 4+ words)
        salt: Random salt for this message
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        channel_key: Channel key parameter:
            - None or "auto": Use configured key
            - str: Use this specific key
            - "" or False: No channel key (public mode)

    Returns:
        32-byte derived key

    Raises:
        KeyDerivationError: If key derivation fails
    """
    try:
        photo_hash = hash_photo(photo_data)

        # Resolve channel key
        channel_hash = _resolve_channel_key(channel_key)

        # Build key material
        key_material = photo_hash + passphrase.lower().encode() + pin.encode() + salt

        # Add RSA key hash if provided
        if rsa_key_data:
            key_material += hashlib.sha256(rsa_key_data).digest()

        # Add channel key hash if configured (v4.0.0)
        if channel_hash:
            key_material += channel_hash

        if HAS_ARGON2:
            key = hash_secret_raw(
                secret=key_material,
                salt=salt[:32],
                time_cost=ARGON2_TIME_COST,
                memory_cost=ARGON2_MEMORY_COST,
                parallelism=ARGON2_PARALLELISM,
                hash_len=32,
                type=Type.ID,
            )
        else:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA512(),
                length=32,
                salt=salt,
                iterations=PBKDF2_ITERATIONS,
                backend=default_backend(),
            )
            key = kdf.derive(key_material)

        return key

    except Exception as e:
        raise KeyDerivationError(f"Failed to derive key: {e}") from e


def derive_pixel_key(
    photo_data: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: bytes | None = None,
    channel_key: str | bool | None = None,
) -> bytes:
    """
    Derive key for pseudo-random pixel selection.

    This key determines which pixels are used for embedding,
    making the message location unpredictable without the correct inputs.

    Args:
        photo_data: Reference photo bytes
        passphrase: Shared passphrase
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        channel_key: Channel key parameter (see derive_hybrid_key)

    Returns:
        32-byte key for pixel selection
    """
    photo_hash = hash_photo(photo_data)

    # Resolve channel key
    channel_hash = _resolve_channel_key(channel_key)

    material = photo_hash + passphrase.lower().encode() + pin.encode()

    if rsa_key_data:
        material += hashlib.sha256(rsa_key_data).digest()

    # Add channel key hash if configured (v4.0.0)
    if channel_hash:
        material += channel_hash

    return hashlib.sha256(material + b"pixel_selection").digest()


def _pack_payload(
    content: str | bytes | FilePayload,
) -> tuple[bytes, int]:
    """
    Pack payload with type marker and metadata.

    Format for text:
        [type:1][data]

    Format for file:
        [type:1][filename_len:2][filename][mime_len:2][mime][data]

    Args:
        content: Text string, raw bytes, or FilePayload

    Returns:
        Tuple of (packed bytes, payload type)
    """
    if isinstance(content, str):
        # Text message
        data = content.encode("utf-8")
        return bytes([PAYLOAD_TEXT]) + data, PAYLOAD_TEXT

    elif isinstance(content, FilePayload):
        # File with metadata
        filename = content.filename[:MAX_FILENAME_LENGTH].encode("utf-8")
        mime = (content.mime_type or "")[:100].encode("utf-8")

        packed = (
            bytes([PAYLOAD_FILE])
            + struct.pack(">H", len(filename))
            + filename
            + struct.pack(">H", len(mime))
            + mime
            + content.data
        )
        return packed, PAYLOAD_FILE

    else:
        # Raw bytes - treat as file with no name
        packed = (
            bytes([PAYLOAD_FILE])
            + struct.pack(">H", 0)  # No filename
            + struct.pack(">H", 0)  # No mime
            + content
        )
        return packed, PAYLOAD_FILE


def _unpack_payload(data: bytes) -> DecodeResult:
    """
    Unpack payload and extract content with metadata.

    Args:
        data: Packed payload bytes

    Returns:
        DecodeResult with appropriate content
    """
    if len(data) < 1:
        raise DecryptionError("Empty payload")

    payload_type = data[0]

    if payload_type == PAYLOAD_TEXT:
        # Text message
        text = data[1:].decode("utf-8")
        return DecodeResult(payload_type="text", message=text)

    elif payload_type == PAYLOAD_FILE:
        # File with metadata
        offset = 1

        # Read filename
        filename_len = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        filename = data[offset : offset + filename_len].decode("utf-8") if filename_len else None
        offset += filename_len

        # Read mime type
        mime_len = struct.unpack(">H", data[offset : offset + 2])[0]
        offset += 2
        mime_type = data[offset : offset + mime_len].decode("utf-8") if mime_len else None
        offset += mime_len

        # Rest is file data
        file_data = data[offset:]

        return DecodeResult(
            payload_type="file", file_data=file_data, filename=filename, mime_type=mime_type
        )

    else:
        # Unknown type - try to decode as text (backward compatibility)
        try:
            text = data.decode("utf-8")
            return DecodeResult(payload_type="text", message=text)
        except UnicodeDecodeError:
            return DecodeResult(payload_type="file", file_data=data)


# =============================================================================
# HEADER FLAGS (v4.0.0)
# =============================================================================

# Header flag bits
FLAG_CHANNEL_KEY = 0x01  # Set if encoded with a channel key


def encrypt_message(
    message: str | bytes | FilePayload,
    photo_data: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: bytes | None = None,
    channel_key: str | bool | None = None,
) -> bytes:
    """
    Encrypt message or file using AES-256-GCM with hybrid key derivation.

    Message format (v4.0.0 - with channel key support):
    - Magic header (4 bytes)
    - Version (1 byte) = 5
    - Flags (1 byte) - indicates if channel key was used
    - Salt (32 bytes)
    - IV (12 bytes)
    - Auth tag (16 bytes)
    - Ciphertext (variable, padded)

    Args:
        message: Message string, raw bytes, or FilePayload to encrypt
        photo_data: Reference photo bytes
        passphrase: Shared passphrase (recommend 4+ words for good entropy)
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        channel_key: Channel key parameter:
            - None or "auto": Use configured key
            - str: Use this specific key
            - "" or False: No channel key (public mode)

    Returns:
        Encrypted message bytes

    Raises:
        EncryptionError: If encryption fails
    """
    try:
        salt = secrets.token_bytes(SALT_SIZE)
        key = derive_hybrid_key(photo_data, passphrase, salt, pin, rsa_key_data, channel_key)
        iv = secrets.token_bytes(IV_SIZE)

        # Determine flags
        flags = 0
        channel_hash = _resolve_channel_key(channel_key)
        if channel_hash:
            flags |= FLAG_CHANNEL_KEY

        # Pack payload with type marker
        packed_payload, _ = _pack_payload(message)

        # Random padding to hide message length
        padding_len = secrets.randbelow(256) + 64
        padded_len = ((len(packed_payload) + padding_len + 255) // 256) * 256
        padding_needed = padded_len - len(packed_payload)
        padding = secrets.token_bytes(padding_needed - 4) + struct.pack(">I", len(packed_payload))
        padded_message = packed_payload + padding

        # Build header for AAD
        header = MAGIC_HEADER + bytes([FORMAT_VERSION, flags])

        # Encrypt with AES-256-GCM
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encryptor.authenticate_additional_data(header)
        ciphertext = encryptor.update(padded_message) + encryptor.finalize()

        # v4.0.0: Header with flags byte
        return header + salt + iv + encryptor.tag + ciphertext

    except Exception as e:
        raise EncryptionError(f"Encryption failed: {e}") from e


def parse_header(encrypted_data: bytes) -> dict | None:
    """
    Parse the header from encrypted data.

    v4.0.0: Includes flags byte for channel key indicator.

    Args:
        encrypted_data: Raw encrypted bytes

    Returns:
        Dict with salt, iv, tag, ciphertext, flags or None if invalid
    """
    # Min size: Magic(4) + Version(1) + Flags(1) + Salt(32) + IV(12) + Tag(16) = 66 bytes
    if len(encrypted_data) < 66 or encrypted_data[:4] != MAGIC_HEADER:
        return None

    try:
        version = encrypted_data[4]
        if version != FORMAT_VERSION:
            return None

        flags = encrypted_data[5]

        offset = 6
        salt = encrypted_data[offset : offset + SALT_SIZE]
        offset += SALT_SIZE
        iv = encrypted_data[offset : offset + IV_SIZE]
        offset += IV_SIZE
        tag = encrypted_data[offset : offset + TAG_SIZE]
        offset += TAG_SIZE
        ciphertext = encrypted_data[offset:]

        return {
            "version": version,
            "flags": flags,
            "has_channel_key": bool(flags & FLAG_CHANNEL_KEY),
            "salt": salt,
            "iv": iv,
            "tag": tag,
            "ciphertext": ciphertext,
        }
    except Exception:
        return None


def decrypt_message(
    encrypted_data: bytes,
    photo_data: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: bytes | None = None,
    channel_key: str | bool | None = None,
) -> DecodeResult:
    """
    Decrypt message (v4.0.0 - with channel key support).

    Args:
        encrypted_data: Encrypted message bytes
        photo_data: Reference photo bytes
        passphrase: Shared passphrase
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        channel_key: Channel key parameter (see encrypt_message)

    Returns:
        DecodeResult with decrypted content

    Raises:
        InvalidHeaderError: If data doesn't have valid Stegasoo header
        DecryptionError: If decryption fails (wrong credentials)
    """
    header = parse_header(encrypted_data)
    if not header:
        raise InvalidHeaderError("Invalid or missing Stegasoo header")

    # Check for channel key mismatch and provide helpful error
    channel_hash = _resolve_channel_key(channel_key)
    has_configured_key = channel_hash is not None
    message_has_key = header["has_channel_key"]

    try:
        key = derive_hybrid_key(
            photo_data, passphrase, header["salt"], pin, rsa_key_data, channel_key
        )

        # Reconstruct header for AAD verification
        aad_header = MAGIC_HEADER + bytes([FORMAT_VERSION, header["flags"]])

        cipher = Cipher(
            algorithms.AES(key), modes.GCM(header["iv"], header["tag"]), backend=default_backend()
        )
        decryptor = cipher.decryptor()
        decryptor.authenticate_additional_data(aad_header)

        padded_plaintext = decryptor.update(header["ciphertext"]) + decryptor.finalize()
        original_length = struct.unpack(">I", padded_plaintext[-4:])[0]

        payload_data = padded_plaintext[:original_length]
        result = _unpack_payload(payload_data)

        return result

    except Exception as e:
        # Provide more helpful error message for channel key issues
        if message_has_key and not has_configured_key:
            raise DecryptionError(
                "Decryption failed. This message was encoded with a channel key, "
                "but no channel key is configured. Provide the correct channel key."
            ) from e
        elif not message_has_key and has_configured_key:
            raise DecryptionError(
                "Decryption failed. This message was encoded without a channel key, "
                "but you have one configured. Try with channel_key='' for public mode."
            ) from e
        else:
            raise DecryptionError(
                "Decryption failed. Check your passphrase, PIN, RSA key, "
                "reference photo, and channel key."
            ) from e


def decrypt_message_text(
    encrypted_data: bytes,
    photo_data: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: bytes | None = None,
    channel_key: str | bool | None = None,
) -> str:
    """
    Decrypt message and return as text string.

    For backward compatibility - returns text content or raises error for files.

    Args:
        encrypted_data: Encrypted message bytes
        photo_data: Reference photo bytes
        passphrase: Shared passphrase
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        channel_key: Channel key parameter

    Returns:
        Decrypted message string

    Raises:
        DecryptionError: If decryption fails or content is a file
    """
    result = decrypt_message(encrypted_data, photo_data, passphrase, pin, rsa_key_data, channel_key)

    if result.is_file:
        if result.file_data:
            # Try to decode as text
            try:
                return result.file_data.decode("utf-8")
            except UnicodeDecodeError:
                raise DecryptionError(
                    f"Content is a binary file ({result.filename or 'unnamed'}), not text"
                )
        return ""

    return result.message or ""


def has_argon2() -> bool:
    """Check if Argon2 is available."""
    return HAS_ARGON2


# =============================================================================
# CHANNEL KEY UTILITIES (exposed for convenience)
# =============================================================================


def get_active_channel_key() -> str | None:
    """
    Get the currently configured channel key (if any).

    Returns:
        Formatted channel key string, or None if not configured
    """
    from .channel import get_channel_key

    return get_channel_key()


def get_channel_fingerprint(key: str | None = None) -> str | None:
    """
    Get a display-safe fingerprint of a channel key.

    Args:
        key: Channel key (if None, uses configured key)

    Returns:
        Masked key like "ABCD-••••-••••-••••-••••-••••-••••-3456" or None
    """
    from .channel import get_channel_fingerprint as _get_fingerprint

    return _get_fingerprint(key)
