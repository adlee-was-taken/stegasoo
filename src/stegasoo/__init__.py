"""
Stegasoo - Secure Steganography Library

A Python library for hiding encrypted messages in images using
hybrid photo + passphrase + PIN authentication.

Basic Usage:
    from stegasoo import encode, decode, generate_credentials
    
    # Generate credentials
    creds = generate_credentials(use_pin=True, use_rsa=False)
    print(creds.phrases['Monday'])
    print(creds.pin)
    
    # Encode a message
    with open('secret.jpg', 'rb') as f:
        ref_photo = f.read()
    with open('meme.png', 'rb') as f:
        carrier = f.read()
    
    result = encode(
        message="Meet at midnight",
        reference_photo=ref_photo,
        carrier_image=carrier,
        day_phrase="apple forest thunder",
        pin="123456"
    )
    
    with open('stego.png', 'wb') as f:
        f.write(result.stego_image)
    
    # Decode a message
    message = decode(
        stego_image=result.stego_image,
        reference_photo=ref_photo,
        day_phrase="apple forest thunder",
        pin="123456"
    )
    print(message)  # "Meet at midnight"
"""

from .constants import __version__, DAY_NAMES
from .models import (
    Credentials,
    EncodeInput,
    EncodeResult,
    DecodeInput,
    DecodeResult,
    EmbedStats,
    KeyInfo,
    ValidationResult,
)
from .exceptions import (
    StegasooError,
    ValidationError,
    PinValidationError,
    MessageValidationError,
    ImageValidationError,
    KeyValidationError,
    SecurityFactorError,
    CryptoError,
    EncryptionError,
    DecryptionError,
    KeyDerivationError,
    KeyGenerationError,
    KeyPasswordError,
    SteganographyError,
    CapacityError,
    ExtractionError,
    EmbeddingError,
    InvalidHeaderError,
)
from .keygen import (
    generate_credentials,
    generate_pin,
    generate_phrase,
    generate_day_phrases,
    generate_rsa_key,
    export_rsa_key_pem,
    load_rsa_key,
    get_key_info,
)
from .validation import (
    validate_pin,
    validate_message,
    validate_image,
    validate_rsa_key,
    validate_security_factors,
    validate_phrase,
    validate_date_string,
    require_valid_pin,
    require_valid_message,
    require_valid_image,
    require_valid_rsa_key,
    require_security_factors,
)
from .crypto import (
    encrypt_message,
    decrypt_message,
    derive_hybrid_key,
    derive_pixel_key,
    hash_photo,
    parse_header,
    get_date_from_encrypted,
    has_argon2,
)
from .steganography import (
    embed_in_image,
    extract_from_image,
    calculate_capacity,
    get_image_dimensions,
)
from .utils import (
    generate_filename,
    parse_date_from_filename,
    get_day_from_date,
    get_today_date,
    get_today_day,
    secure_delete,
    SecureDeleter,
    format_file_size,
)

from datetime import date
from typing import Optional


def encode(
    message: str,
    reference_photo: bytes,
    carrier_image: bytes,
    day_phrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    date_str: Optional[str] = None,
) -> EncodeResult:
    """
    Encode a secret message into an image.
    
    High-level convenience function that handles validation,
    encryption, and embedding in one call.
    
    Args:
        message: Secret message to hide
        reference_photo: Shared reference photo bytes
        carrier_image: Image to hide message in
        day_phrase: Today's passphrase
        pin: Static PIN (optional if using RSA key)
        rsa_key_data: RSA private key PEM bytes (optional if using PIN)
        rsa_password: Password for RSA key if encrypted
        date_str: Date string YYYY-MM-DD (defaults to today)
        
    Returns:
        EncodeResult with stego image and metadata
        
    Raises:
        ValidationError: If inputs are invalid
        SecurityFactorError: If no PIN or RSA key provided
        CapacityError: If carrier is too small
        EncryptionError: If encryption fails
    """
    # Validate inputs
    require_valid_message(message)
    require_valid_image(carrier_image, "Carrier image")
    require_security_factors(pin, rsa_key_data)
    
    if pin:
        require_valid_pin(pin)
    if rsa_key_data:
        require_valid_rsa_key(rsa_key_data, rsa_password)
    
    # Default date to today
    if date_str is None:
        date_str = date.today().isoformat()
    
    # Encrypt message
    encrypted = encrypt_message(
        message, reference_photo, day_phrase, date_str, pin, rsa_key_data
    )
    
    # Get pixel key
    pixel_key = derive_pixel_key(
        reference_photo, day_phrase, date_str, pin, rsa_key_data
    )
    
    # Embed in image
    stego_data, stats = embed_in_image(carrier_image, encrypted, pixel_key)
    
    # Generate filename
    filename = generate_filename(date_str)
    
    return EncodeResult(
        stego_image=stego_data,
        filename=filename,
        pixels_modified=stats.pixels_modified,
        total_pixels=stats.total_pixels,
        capacity_used=stats.capacity_used,
        date_used=date_str
    )


def decode(
    stego_image: bytes,
    reference_photo: bytes,
    day_phrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
) -> str:
    """
    Decode a secret message from a stego image.
    
    High-level convenience function that handles extraction
    and decryption in one call.
    
    Args:
        stego_image: Image containing hidden message
        reference_photo: Shared reference photo bytes
        day_phrase: Passphrase for the day message was encoded
        pin: Static PIN (if used during encoding)
        rsa_key_data: RSA private key PEM bytes (if used during encoding)
        rsa_password: Password for RSA key if encrypted
        
    Returns:
        Decrypted message string
        
    Raises:
        ValidationError: If inputs are invalid
        SecurityFactorError: If no PIN or RSA key provided
        ExtractionError: If data cannot be extracted
        DecryptionError: If decryption fails
    """
    # Validate inputs
    require_security_factors(pin, rsa_key_data)
    
    if pin:
        require_valid_pin(pin)
    if rsa_key_data:
        require_valid_rsa_key(rsa_key_data, rsa_password)
    
    # Try to extract with today's date first
    date_str = date.today().isoformat()
    pixel_key = derive_pixel_key(
        reference_photo, day_phrase, date_str, pin, rsa_key_data
    )
    
    encrypted = extract_from_image(stego_image, pixel_key)
    
    # If we got data, check if it's from a different date
    if encrypted:
        header = parse_header(encrypted)
        if header and header['date'] != date_str:
            # Re-extract with correct date
            pixel_key = derive_pixel_key(
                reference_photo, day_phrase, header['date'], pin, rsa_key_data
            )
            encrypted = extract_from_image(stego_image, pixel_key)
    
    if not encrypted:
        raise ExtractionError("Could not extract data. Check your inputs.")
    
    # Decrypt
    return decrypt_message(encrypted, reference_photo, day_phrase, pin, rsa_key_data)


__all__ = [
    # Version
    '__version__',
    
    # High-level API
    'encode',
    'decode',
    'generate_credentials',
    
    # Constants
    'DAY_NAMES',
    
    # Models
    'Credentials',
    'EncodeInput',
    'EncodeResult',
    'DecodeInput',
    'DecodeResult',
    'EmbedStats',
    'KeyInfo',
    'ValidationResult',
    
    # Exceptions
    'StegasooError',
    'ValidationError',
    'PinValidationError',
    'MessageValidationError',
    'ImageValidationError',
    'KeyValidationError',
    'SecurityFactorError',
    'CryptoError',
    'EncryptionError',
    'DecryptionError',
    'KeyDerivationError',
    'KeyGenerationError',
    'KeyPasswordError',
    'SteganographyError',
    'CapacityError',
    'ExtractionError',
    'EmbeddingError',
    'InvalidHeaderError',
    
    # Key generation
    'generate_pin',
    'generate_phrase',
    'generate_day_phrases',
    'generate_rsa_key',
    'export_rsa_key_pem',
    'load_rsa_key',
    'get_key_info',
    
    # Validation
    'validate_pin',
    'validate_message',
    'validate_image',
    'validate_rsa_key',
    'validate_security_factors',
    'validate_phrase',
    'validate_date_string',
    'require_valid_pin',
    'require_valid_message',
    'require_valid_image',
    'require_valid_rsa_key',
    'require_security_factors',
    
    # Crypto
    'encrypt_message',
    'decrypt_message',
    'derive_hybrid_key',
    'derive_pixel_key',
    'hash_photo',
    'parse_header',
    'get_date_from_encrypted',
    'has_argon2',
    
    # Steganography
    'embed_in_image',
    'extract_from_image',
    'calculate_capacity',
    'get_image_dimensions',
    
    # Utilities
    'generate_filename',
    'parse_date_from_filename',
    'get_day_from_date',
    'get_today_date',
    'get_today_day',
    'secure_delete',
    'SecureDeleter',
    'format_file_size',
]
