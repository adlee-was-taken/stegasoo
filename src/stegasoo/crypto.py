"""
Stegasoo Cryptographic Functions

Key derivation, encryption, and decryption using AES-256-GCM.
"""

import io
import hashlib
import secrets
import struct
from typing import Optional

from PIL import Image
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from .constants import (
    MAGIC_HEADER, FORMAT_VERSION,
    SALT_SIZE, IV_SIZE, TAG_SIZE,
    ARGON2_TIME_COST, ARGON2_MEMORY_COST, ARGON2_PARALLELISM,
    PBKDF2_ITERATIONS,
)
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
    img = Image.open(io.BytesIO(image_data))
    img = img.convert('RGB')
    pixels = img.tobytes()
    
    # Double-hash with prefix for additional mixing
    h = hashlib.sha256(pixels).digest()
    h = hashlib.sha256(h + pixels[:1024]).digest()
    return h


def derive_hybrid_key(
    photo_data: bytes,
    day_phrase: str,
    date_str: str,
    salt: bytes,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None
) -> bytes:
    """
    Derive encryption key from multiple factors.
    
    Combines:
    - Photo hash (something you have)
    - Day phrase (something you know, rotates daily)
    - PIN (something you know, static)
    - RSA key (something you have)
    - Date (automatic rotation)
    - Salt (random per message)
    
    Uses Argon2id if available, falls back to PBKDF2.
    
    Args:
        photo_data: Reference photo bytes
        day_phrase: The day's phrase
        date_str: Date string (YYYY-MM-DD)
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
            day_phrase.lower().encode() +
            pin.encode() +
            date_str.encode() +
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
    day_phrase: str,
    date_str: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None
) -> bytes:
    """
    Derive key for pseudo-random pixel selection.
    
    This key determines which pixels are used for embedding,
    making the message location unpredictable without the correct inputs.
    
    Args:
        photo_data: Reference photo bytes
        day_phrase: The day's phrase
        date_str: Date string (YYYY-MM-DD)
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        
    Returns:
        32-byte key for pixel selection
    """
    photo_hash = hash_photo(photo_data)
    
    material = (
        photo_hash +
        day_phrase.lower().encode() +
        pin.encode() +
        date_str.encode()
    )
    
    if rsa_key_data:
        material += hashlib.sha256(rsa_key_data).digest()
    
    return hashlib.sha256(material + b"pixel_selection").digest()


def encrypt_message(
    message: str | bytes,
    photo_data: bytes,
    day_phrase: str,
    date_str: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None
) -> bytes:
    """
    Encrypt message using AES-256-GCM with hybrid key derivation.
    
    Message format:
    - Magic header (4 bytes)
    - Version (1 byte)
    - Date length (1 byte)
    - Date string (variable)
    - Salt (32 bytes)
    - IV (12 bytes)
    - Auth tag (16 bytes)
    - Ciphertext (variable, padded)
    
    Args:
        message: Message to encrypt
        photo_data: Reference photo bytes
        day_phrase: The day's phrase
        date_str: Date string (YYYY-MM-DD)
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        
    Returns:
        Encrypted message bytes
        
    Raises:
        EncryptionError: If encryption fails
    """
    try:
        salt = secrets.token_bytes(SALT_SIZE)
        key = derive_hybrid_key(photo_data, day_phrase, date_str, salt, pin, rsa_key_data)
        iv = secrets.token_bytes(IV_SIZE)
        
        if isinstance(message, str):
            message = message.encode('utf-8')
        
        # Random padding to hide message length
        padding_len = secrets.randbelow(256) + 64
        padded_len = ((len(message) + padding_len + 255) // 256) * 256
        padding_needed = padded_len - len(message)
        padding = secrets.token_bytes(padding_needed - 4) + struct.pack('>I', len(message))
        padded_message = message + padding
        
        # Encrypt with AES-256-GCM
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
        encryptor = cipher.encryptor()
        encryptor.authenticate_additional_data(MAGIC_HEADER + bytes([FORMAT_VERSION]))
        ciphertext = encryptor.update(padded_message) + encryptor.finalize()
        
        date_bytes = date_str.encode()
        
        return (
            MAGIC_HEADER +
            bytes([FORMAT_VERSION]) +
            bytes([len(date_bytes)]) +
            date_bytes +
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
    
    Args:
        encrypted_data: Raw encrypted bytes
        
    Returns:
        Dict with date, salt, iv, tag, ciphertext or None if invalid
    """
    if len(encrypted_data) < 10 or encrypted_data[:4] != MAGIC_HEADER:
        return None
    
    try:
        version = encrypted_data[4]
        if version != FORMAT_VERSION:
            return None
        
        date_len = encrypted_data[5]
        date_str = encrypted_data[6:6 + date_len].decode()
        
        offset = 6 + date_len
        salt = encrypted_data[offset:offset + SALT_SIZE]
        offset += SALT_SIZE
        iv = encrypted_data[offset:offset + IV_SIZE]
        offset += IV_SIZE
        tag = encrypted_data[offset:offset + TAG_SIZE]
        offset += TAG_SIZE
        ciphertext = encrypted_data[offset:]
        
        return {
            'date': date_str,
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
    day_phrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None
) -> str:
    """
    Decrypt message using the embedded date from the header.
    
    Args:
        encrypted_data: Encrypted message bytes
        photo_data: Reference photo bytes
        day_phrase: The day's phrase (must match encoding day)
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        
    Returns:
        Decrypted message string
        
    Raises:
        InvalidHeaderError: If data doesn't have valid Stegasoo header
        DecryptionError: If decryption fails (wrong credentials)
    """
    header = parse_header(encrypted_data)
    if not header:
        raise InvalidHeaderError("Invalid or missing Stegasoo header")
    
    try:
        key = derive_hybrid_key(
            photo_data, day_phrase, header['date'], header['salt'], pin, rsa_key_data
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
        
        return padded_plaintext[:original_length].decode('utf-8')
        
    except Exception as e:
        raise DecryptionError(
            "Decryption failed. Check your phrase, PIN, RSA key, and reference photo."
        ) from e


def get_date_from_encrypted(encrypted_data: bytes) -> Optional[str]:
    """
    Extract the date string from encrypted data without decrypting.
    
    Useful for determining which day's phrase to use.
    
    Args:
        encrypted_data: Encrypted message bytes
        
    Returns:
        Date string (YYYY-MM-DD) or None if invalid
    """
    header = parse_header(encrypted_data)
    return header['date'] if header else None


def has_argon2() -> bool:
    """Check if Argon2 is available."""
    return HAS_ARGON2
