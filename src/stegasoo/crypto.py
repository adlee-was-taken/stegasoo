"""
Stegasoo Cryptographic Functions (v3.2.0 - Date Independent)

Key derivation, encryption, and decryption using AES-256-GCM.
Supports both text messages and binary file payloads.

BREAKING CHANGES in v3.2.0:
- Removed date dependency from key derivation
- Renamed day_phrase → passphrase (no daily rotation needed)
- Messages can now be decoded without knowing encoding date
- Enables true asynchronous communication
- NOT backward compatible with v3.1.0 and earlier
"""

import io
import hashlib
import secrets
import struct
import json
from typing import Optional, Union

from PIL import Image
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from .constants import (
    MAGIC_HEADER, FORMAT_VERSION,
    SALT_SIZE, IV_SIZE, TAG_SIZE,
    ARGON2_TIME_COST, ARGON2_MEMORY_COST, ARGON2_PARALLELISM,
    PBKDF2_ITERATIONS,
    PAYLOAD_TEXT, PAYLOAD_FILE,
    MAX_FILENAME_LENGTH,
)
from .models import FilePayload, DecodeResult
from .exceptions import (
    EncryptionError, DecryptionError, KeyDerivationError, InvalidHeaderError
)

# Check for Argon2 availability
try:
    from argon2.low_level import hash_secret_raw, Type
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes


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
    img: Image.Image = Image.open(io.BytesIO(image_data)).convert('RGB')
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
    rsa_key_data: Optional[bytes] = None
) -> bytes:
    """
    Derive encryption key from multiple factors.
    
    Combines:
    - Photo hash (something you have)
    - Passphrase (something you know)
    - PIN (something you know, static)
    - RSA key (something you have)
    - Salt (random per message)
    
    Uses Argon2id if available, falls back to PBKDF2.
    
    NOTE: v3.2.0 removed date dependency and daily rotation.
    Use a strong static passphrase instead (recommend 4+ words).
    
    Args:
        photo_data: Reference photo bytes
        passphrase: Shared passphrase (recommend 4+ words)
        salt: Random salt for this message
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        
    Returns:
        32-byte derived key
        
    Raises:
        KeyDerivationError: If key derivation fails
    """
    try:
        photo_hash = hash_photo(photo_data)
        
        key_material = (
            photo_hash +
            passphrase.lower().encode() +
            pin.encode() +
            salt
        )
        
        # Add RSA key hash if provided
        if rsa_key_data:
            key_material += hashlib.sha256(rsa_key_data).digest()
        
        if HAS_ARGON2:
            key = hash_secret_raw(
                secret=key_material,
                salt=salt[:32],
                time_cost=ARGON2_TIME_COST,
                memory_cost=ARGON2_MEMORY_COST,
                parallelism=ARGON2_PARALLELISM,
                hash_len=32,
                type=Type.ID
            )
        else:
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA512(),
                length=32,
                salt=salt,
                iterations=PBKDF2_ITERATIONS,
                backend=default_backend()
            )
            key = kdf.derive(key_material)
        
        return key
        
    except Exception as e:
        raise KeyDerivationError(f"Failed to derive key: {e}") from e


def derive_pixel_key(
    photo_data: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None
) -> bytes:
    """
    Derive key for pseudo-random pixel selection.
    
    This key determines which pixels are used for embedding,
    making the message location unpredictable without the correct inputs.
    
    NOTE: v3.2.0 removed date dependency.
    
    Args:
        photo_data: Reference photo bytes
        passphrase: Shared passphrase
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        
    Returns:
        32-byte key for pixel selection
    """
    photo_hash = hash_photo(photo_data)
    
    material = (
        photo_hash +
        passphrase.lower().encode() +
        pin.encode()
    )
    
    if rsa_key_data:
        material += hashlib.sha256(rsa_key_data).digest()
    
    return hashlib.sha256(material + b"pixel_selection").digest()


def _pack_payload(
    content: Union[str, bytes, FilePayload],
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
        data = content.encode('utf-8')
        return bytes([PAYLOAD_TEXT]) + data, PAYLOAD_TEXT
    
    elif isinstance(content, FilePayload):
        # File with metadata
        filename = content.filename[:MAX_FILENAME_LENGTH].encode('utf-8')
        mime = (content.mime_type or '')[:100].encode('utf-8')
        
        packed = (
            bytes([PAYLOAD_FILE]) +
            struct.pack('>H', len(filename)) +
            filename +
            struct.pack('>H', len(mime)) +
            mime +
            content.data
        )
        return packed, PAYLOAD_FILE
    
    else:
        # Raw bytes - treat as file with no name
        packed = (
            bytes([PAYLOAD_FILE]) +
            struct.pack('>H', 0) +  # No filename
            struct.pack('>H', 0) +  # No mime
            content
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
        text = data[1:].decode('utf-8')
        return DecodeResult(payload_type='text', message=text)
    
    elif payload_type == PAYLOAD_FILE:
        # File with metadata
        offset = 1
        
        # Read filename
        filename_len = struct.unpack('>H', data[offset:offset+2])[0]
        offset += 2
        filename = data[offset:offset+filename_len].decode('utf-8') if filename_len else None
        offset += filename_len
        
        # Read mime type
        mime_len = struct.unpack('>H', data[offset:offset+2])[0]
        offset += 2
        mime_type = data[offset:offset+mime_len].decode('utf-8') if mime_len else None
        offset += mime_len
        
        # Rest is file data
        file_data = data[offset:]
        
        return DecodeResult(
            payload_type='file',
            file_data=file_data,
            filename=filename,
            mime_type=mime_type
        )
    
    else:
        # Unknown type - try to decode as text (backward compatibility)
        try:
            text = data.decode('utf-8')
            return DecodeResult(payload_type='text', message=text)
        except UnicodeDecodeError:
            return DecodeResult(payload_type='file', file_data=data)


def encrypt_message(
    message: Union[str, bytes, FilePayload],
    photo_data: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None
) -> bytes:
    """
    Encrypt message or file using AES-256-GCM with hybrid key derivation.
    
    Message format (v3.2.0 - no date):
    - Magic header (4 bytes)
    - Version (1 byte) = 4
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
        
    Returns:
        Encrypted message bytes
        
    Raises:
        EncryptionError: If encryption fails
    """
    try:
        salt = secrets.token_bytes(SALT_SIZE)
        key = derive_hybrid_key(photo_data, passphrase, salt, pin, rsa_key_data)
        iv = secrets.token_bytes(IV_SIZE)
        
        # Pack payload with type marker
        packed_payload, _ = _pack_payload(message)
        
        # Random padding to hide message length
        padding_len = secrets.randbelow(256) + 64
        padded_len = ((len(packed_payload) + padding_len + 255) // 256) * 256
        padding_needed = padded_len - len(packed_payload)
        padding = secrets.token_bytes(padding_needed - 4) + struct.pack('>I', len(packed_payload))
        padded_message = packed_payload + padding
        
        # Encrypt with AES-256-GCM
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encryptor.authenticate_additional_data(MAGIC_HEADER + bytes([FORMAT_VERSION]))
        ciphertext = encryptor.update(padded_message) + encryptor.finalize()
        
        # v3.2.0: Simplified header without date
        return (
            MAGIC_HEADER +
            bytes([FORMAT_VERSION]) +
            salt +
            iv +
            encryptor.tag +
            ciphertext
        )
        
    except Exception as e:
        raise EncryptionError(f"Encryption failed: {e}") from e


def parse_header(encrypted_data: bytes) -> Optional[dict]:
    """
    Parse the header from encrypted data.
    
    v3.2.0: No date field in header.
    
    Args:
        encrypted_data: Raw encrypted bytes
        
    Returns:
        Dict with salt, iv, tag, ciphertext or None if invalid
    """
    # Min size: Magic(4) + Version(1) + Salt(32) + IV(12) + Tag(16) = 65 bytes
    if len(encrypted_data) < 65 or encrypted_data[:4] != MAGIC_HEADER:
        return None
    
    try:
        version = encrypted_data[4]
        if version != FORMAT_VERSION:
            return None
        
        offset = 5
        salt = encrypted_data[offset:offset + SALT_SIZE]
        offset += SALT_SIZE
        iv = encrypted_data[offset:offset + IV_SIZE]
        offset += IV_SIZE
        tag = encrypted_data[offset:offset + TAG_SIZE]
        offset += TAG_SIZE
        ciphertext = encrypted_data[offset:]
        
        return {
            'salt': salt,
            'iv': iv,
            'tag': tag,
            'ciphertext': ciphertext
        }
    except Exception:
        return None


def decrypt_message(
    encrypted_data: bytes,
    photo_data: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None
) -> DecodeResult:
    """
    Decrypt message (v3.2.0 - no date needed).
    
    Args:
        encrypted_data: Encrypted message bytes
        photo_data: Reference photo bytes
        passphrase: Shared passphrase
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        
    Returns:
        DecodeResult with decrypted content
        
    Raises:
        InvalidHeaderError: If data doesn't have valid Stegasoo header
        DecryptionError: If decryption fails (wrong credentials)
    """
    header = parse_header(encrypted_data)
    if not header:
        raise InvalidHeaderError("Invalid or missing Stegasoo header")
    
    try:
        key = derive_hybrid_key(
            photo_data, passphrase, header['salt'], pin, rsa_key_data
        )
        
        cipher = Cipher(
            algorithms.AES(key),
            modes.GCM(header['iv'], header['tag']),
            backend=default_backend()
        )
        decryptor = cipher.decryptor()
        decryptor.authenticate_additional_data(MAGIC_HEADER + bytes([FORMAT_VERSION]))
        
        padded_plaintext = decryptor.update(header['ciphertext']) + decryptor.finalize()
        original_length = struct.unpack('>I', padded_plaintext[-4:])[0]
        
        payload_data = padded_plaintext[:original_length]
        result = _unpack_payload(payload_data)
        
        # Note: No date_encoded field in v3.2.0
        
        return result
        
    except Exception as e:
        raise DecryptionError(
            "Decryption failed. Check your passphrase, PIN, RSA key, and reference photo."
        ) from e


def decrypt_message_text(
    encrypted_data: bytes,
    photo_data: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None
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
        
    Returns:
        Decrypted message string
        
    Raises:
        DecryptionError: If decryption fails or content is a file
    """
    result = decrypt_message(encrypted_data, photo_data, passphrase, pin, rsa_key_data)
    
    if result.is_file:
        if result.file_data:
            # Try to decode as text
            try:
                return result.file_data.decode('utf-8')
            except UnicodeDecodeError:
                raise DecryptionError(
                    f"Content is a binary file ({result.filename or 'unnamed'}), not text"
                )
        return ""
    
    return result.message or ""


def has_argon2() -> bool:
    """Check if Argon2 is available."""
    return HAS_ARGON2
