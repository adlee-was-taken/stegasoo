"""
Stegasoo - Secure Steganography Library

A Python library for hiding encrypted messages and files in images using
hybrid photo + passphrase + PIN authentication.

Basic Usage - Text Message:
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
    decoded = decode(
        stego_image=result.stego_image,
        reference_photo=ref_photo,
        day_phrase="apple forest thunder",
        pin="123456"
    )
    print(decoded.message)  # "Meet at midnight"

File Embedding:
    from stegasoo import encode_file, decode, FilePayload
    
    # Encode a file
    result = encode_file(
        filepath="secret_document.pdf",
        reference_photo=ref_photo,
        carrier_image=carrier,
        day_phrase="apple forest thunder",
        pin="123456"
    )
    
    # Decode - automatically detects file vs text
    decoded = decode(...)
    if decoded.is_file:
        with open(decoded.filename, 'wb') as f:
            f.write(decoded.file_data)
    else:
        print(decoded.message)

Capacity Pre-check (v2.2.1):
    from stegasoo import will_fit
    
    # Check if payload will fit before encoding
    result = will_fit("My secret message", carrier_image)
    if result['fits']:
        print(f"Will use {result['usage_percent']:.1f}% capacity")
    else:
        print(f"Need {-result['headroom']} more bytes")

Debugging:
    from stegasoo.debug import debug
    debug.enable(True)  # Enable debug output
    debug.enable_performance(True)  # Enable timing
"""

from .constants import __version__, DAY_NAMES, MAX_MESSAGE_SIZE, MAX_FILE_PAYLOAD_SIZE
from .models import (
    Credentials,
    EncodeInput,
    EncodeResult,
    DecodeInput,
    DecodeResult,
    EmbedStats,
    KeyInfo,
    ValidationResult,
    FilePayload,
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
    validate_payload,
    validate_file_payload,
    validate_image,
    validate_rsa_key,
    validate_security_factors,
    validate_phrase,
    validate_date_string,
    require_valid_pin,
    require_valid_message,
    require_valid_payload,
    require_valid_image,
    require_valid_rsa_key,
    require_security_factors,
)
from .crypto import (
    encrypt_message,
    decrypt_message,
    decrypt_message_text,
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
    get_image_format,
    is_lossless_format,
    LOSSLESS_FORMATS,
    # NEW in v2.2.1
    will_fit,
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
    # NEW in v2.2.1
    strip_image_metadata,
)
from .debug import debug  # Import debug utilities

# =============================================================================
# NEW IN v2.2.0 - Compression
# =============================================================================
from .compression import (
    compress,
    decompress,
    CompressionAlgorithm,
    CompressionError,
    get_compression_ratio,
    estimate_compressed_size,
    get_available_algorithms,
)

# =============================================================================
# NEW IN v2.2.0 - Batch Processing
# =============================================================================
from .batch import (
    BatchProcessor,
    BatchResult,
    BatchItem,
    BatchStatus,
    batch_capacity_check,
    # NEW in v2.2.1
    BatchCredentials,
)

# QR Code utilities (optional, depends on qrcode and pyzbar)
try:
    from .qr_utils import (
        generate_qr_code,
        read_qr_code,
        read_qr_code_from_file,
        extract_key_from_qr,
        extract_key_from_qr_file,
        compress_data,
        decompress_data,
        auto_decompress,
        normalize_pem,
        is_compressed,
        can_fit_in_qr,
        needs_compression,
        has_qr_read,
        has_qr_write,
        has_qr_support,
    )
    HAS_QR_UTILS = True
except ImportError:
    HAS_QR_UTILS = False

from datetime import date
from pathlib import Path
from typing import Optional, Union, Dict, Any


def encode(
    message: Union[str, bytes, FilePayload],
    reference_photo: bytes,
    carrier_image: bytes,
    day_phrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    date_str: Optional[str] = None,
    output_format: Optional[str] = None,
) -> EncodeResult:
    """
    Encode a secret message or file into an image.
    
    High-level convenience function that handles validation,
    encryption, and embedding in one call.
    
    Args:
        message: Secret message (str), raw bytes, or FilePayload to hide
        reference_photo: Shared reference photo bytes
        carrier_image: Image to hide message in
        day_phrase: Today's passphrase
        pin: Static PIN (optional if using RSA key)
        rsa_key_data: RSA private key PEM bytes (optional if using PIN)
        rsa_password: Password for RSA key if encrypted
        date_str: Date string YYYY-MM-DD (defaults to today)
        output_format: Force output format ('PNG', 'BMP'). If None, preserves
                       carrier format for lossless types, defaults to PNG for lossy.
        
    Returns:
        EncodeResult with stego image and metadata
        
    Raises:
        ValidationError: If inputs are invalid
        SecurityFactorError: If no PIN or RSA key provided
        CapacityError: If carrier is too small
        EncryptionError: If encryption fails
        
    Note:
        Output format is always lossless (PNG or BMP) to preserve hidden data.
        If carrier is JPEG/GIF, output will be PNG to maintain data integrity.
    """
    # Debug logging
    debug.print(f"encode called: message type={type(message).__name__}, "
                f"day_phrase='{day_phrase[:20]}...', pin_length={len(pin)}")
    
    # Validate inputs
    require_valid_payload(message)
    require_valid_image(carrier_image, "Carrier image")
    require_security_factors(pin, rsa_key_data)
    
    if pin:
        require_valid_pin(pin)
    if rsa_key_data:
        require_valid_rsa_key(rsa_key_data, rsa_password)
    
    # Default date to today
    if date_str is None:
        date_str = date.today().isoformat()
    
    debug.print(f"Encoding for date: {date_str}")
    
    # Encrypt message/file
    encrypted = encrypt_message(
        message, reference_photo, day_phrase, date_str, pin, rsa_key_data
    )
    
    # Debug: show encrypted data size
    debug.print(f"Encrypted payload: {len(encrypted)} bytes")
    
    # Get pixel key
    pixel_key = derive_pixel_key(
        reference_photo, day_phrase, date_str, pin, rsa_key_data
    )
    
    debug.data(pixel_key, "Pixel key")
    
    # Embed in image (returns extension too)
    stego_data, stats, extension = embed_in_image(
        carrier_image, encrypted, pixel_key, output_format=output_format
    )
    
    # Generate filename with correct extension
    filename = generate_filename(date_str, extension=extension)
    
    debug.print(f"Encoding complete: {filename}, "
                f"modified {stats.pixels_modified}/{stats.total_pixels} pixels "
                f"({stats.modification_percent:.2f}%)")
    
    return EncodeResult(
        stego_image=stego_data,
        filename=filename,
        pixels_modified=stats.pixels_modified,
        total_pixels=stats.total_pixels,
        capacity_used=stats.capacity_used,
        date_used=date_str
    )


def encode_file(
    filepath: Union[str, Path],
    reference_photo: bytes,
    carrier_image: bytes,
    day_phrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    date_str: Optional[str] = None,
    output_format: Optional[str] = None,
    filename_override: Optional[str] = None,
) -> EncodeResult:
    """
    Encode a file into an image.
    
    Convenience function for embedding files. Preserves original filename.
    
    Args:
        filepath: Path to file to embed
        reference_photo: Shared reference photo bytes
        carrier_image: Image to hide file in
        day_phrase: Today's passphrase
        pin: Static PIN (optional if using RSA key)
        rsa_key_data: RSA private key PEM bytes (optional if using PIN)
        rsa_password: Password for RSA key if encrypted
        date_str: Date string YYYY-MM-DD (defaults to today)
        output_format: Force output format ('PNG', 'BMP')
        filename_override: Override the stored filename
        
    Returns:
        EncodeResult with stego image and metadata
    """
    debug.print(f"encode_file called: filepath={filepath}")
    payload = FilePayload.from_file(str(filepath), filename_override)
    
    return encode(
        message=payload,
        reference_photo=reference_photo,
        carrier_image=carrier_image,
        day_phrase=day_phrase,
        pin=pin,
        rsa_key_data=rsa_key_data,
        rsa_password=rsa_password,
        date_str=date_str,
        output_format=output_format,
    )


def encode_bytes(
    data: bytes,
    filename: str,
    reference_photo: bytes,
    carrier_image: bytes,
    day_phrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    date_str: Optional[str] = None,
    output_format: Optional[str] = None,
    mime_type: Optional[str] = None,
) -> EncodeResult:
    """
    Encode raw bytes with a filename into an image.
    
    Convenience function for embedding binary data with metadata.
    
    Args:
        data: Raw bytes to embed
        filename: Filename to associate with the data
        reference_photo: Shared reference photo bytes
        carrier_image: Image to hide data in
        day_phrase: Today's passphrase
        pin: Static PIN (optional if using RSA key)
        rsa_key_data: RSA private key PEM bytes (optional if using PIN)
        rsa_password: Password for RSA key if encrypted
        date_str: Date string YYYY-MM-DD (defaults to today)
        output_format: Force output format ('PNG', 'BMP')
        mime_type: MIME type of the data
        
    Returns:
        EncodeResult with stego image and metadata
    """
    debug.print(f"encode_bytes called: filename={filename}, data_size={len(data)}")
    payload = FilePayload(data=data, filename=filename, mime_type=mime_type)
    
    return encode(
        message=payload,
        reference_photo=reference_photo,
        carrier_image=carrier_image,
        day_phrase=day_phrase,
        pin=pin,
        rsa_key_data=rsa_key_data,
        rsa_password=rsa_password,
        date_str=date_str,
        output_format=output_format,
    )


@debug.time
def decode(
    stego_image: bytes,
    reference_photo: bytes,
    day_phrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    date_str: Optional[str] = None,
) -> DecodeResult:
    """
    Decode a secret message or file from a stego image.
    
    High-level convenience function that handles extraction
    and decryption in one call.
    
    Args:
        stego_image: Image containing hidden message/file
        reference_photo: Shared reference photo bytes
        day_phrase: Passphrase for the day message was encoded
        pin: Static PIN (if used during encoding)
        rsa_key_data: RSA private key PEM bytes (if used during encoding)
        rsa_password: Password for RSA key if encrypted
        
    Returns:
        DecodeResult with:
        - .payload_type: 'text' or 'file'
        - .message: Decoded text (if text)
        - .file_data: Decoded bytes (if file)
        - .filename: Original filename (if file)
        - .is_text / .is_file: Convenience properties
        
    Raises:
        ValidationError: If inputs are invalid
        SecurityFactorError: If no PIN or RSA key provided
        ExtractionError: If data cannot be extracted
        DecryptionError: If decryption fails
    """
    debug.print(f"decode called: stego_image_size={len(stego_image)}, "
                f"day_phrase='{day_phrase[:20]}...'")
    
    # Validate inputs
    require_security_factors(pin, rsa_key_data)
    
    if pin:
        require_valid_pin(pin)
    if rsa_key_data:
        require_valid_rsa_key(rsa_key_data, rsa_password)
    
    # Try to extract with today's date first
    # Use provided date or fall back to today
    if date_str is None:
        date_str = date.today().isoformat()
    pixel_key = derive_pixel_key(
        reference_photo, day_phrase, date_str, pin, rsa_key_data
    )
    
    debug.data(pixel_key, "Pixel key for extraction")
    
    encrypted = extract_from_image(stego_image, pixel_key)
    
    # If we got data, check if it's from a different date
    if encrypted:
        header = parse_header(encrypted)
        if header and header['date'] != date_str:
            debug.print(f"Found different date in header: {header['date']} (expected {date_str})")
            # Re-extract with correct date
            pixel_key = derive_pixel_key(
                reference_photo, day_phrase, header['date'], pin, rsa_key_data
            )
            encrypted = extract_from_image(stego_image, pixel_key)
    
    if not encrypted:
        debug.print("No data extracted from image")
        raise ExtractionError("Could not extract data. Check your inputs.")
    
    debug.print(f"Extracted {len(encrypted)} bytes from image")
    debug.data(encrypted[:64], "First 64 bytes of extracted data")
    
    # Decrypt and return full result
    return decrypt_message(encrypted, reference_photo, day_phrase, pin, rsa_key_data)


def decode_text(
    stego_image: bytes,
    reference_photo: bytes,
    day_phrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    date_str: Optional[str] = None,
) -> str:
    """
    Decode a text message from a stego image.
    
    Convenience function that returns just the text string.
    Raises an error if the content is a binary file.
    
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
        DecryptionError: If content is a binary file, not text
    """
    debug.print("decode_text called")
    result = decode(stego_image, reference_photo, day_phrase, pin, rsa_key_data, rsa_password)
    
    if result.is_file:
        # Try to decode file as text
        if result.file_data:
            try:
                return result.file_data.decode('utf-8')
            except UnicodeDecodeError:
                debug.print(f"File is binary: {result.filename or 'unnamed'}")
                raise DecryptionError(
                    f"Content is a binary file ({result.filename or 'unnamed'}), not text. "
                    "Use decode() instead and check result.is_file."
                )
        return ""
    
    debug.print(f"Decoded text: {result.message[:100] if result.message else 'empty'}...")
    message: str = result.message if result.message is not None else ""
    return message


__all__ = [
    # Version
    '__version__',
    
    # High-level API
    'encode',
    'encode_file',
    'encode_bytes',
    'decode',
    'decode_text',
    'generate_credentials',
    
    # Constants
    'DAY_NAMES',
    'LOSSLESS_FORMATS',
    'MAX_MESSAGE_SIZE',
    'MAX_FILE_PAYLOAD_SIZE',
    
    # Models
    'Credentials',
    'EncodeInput',
    'EncodeResult',
    'DecodeInput',
    'DecodeResult',
    'EmbedStats',
    'KeyInfo',
    'ValidationResult',
    'FilePayload',
    
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
    'validate_payload',
    'validate_file_payload',
    'validate_image',
    'validate_rsa_key',
    'validate_security_factors',
    'validate_phrase',
    'validate_date_string',
    'require_valid_pin',
    'require_valid_message',
    'require_valid_payload',
    'require_valid_image',
    'require_valid_rsa_key',
    'require_security_factors',
    
    # Crypto
    'encrypt_message',
    'decrypt_message',
    'decrypt_message_text',
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
    'get_image_format',
    'is_lossless_format',
    'will_fit',  # NEW in v2.2.1
    
    # Utilities
    'generate_filename',
    'parse_date_from_filename',
    'get_day_from_date',
    'get_today_date',
    'get_today_day',
    'secure_delete',
    'SecureDeleter',
    'format_file_size',
    'strip_image_metadata',  # NEW in v2.2.1
    
    # Debugging
    'debug',
    
    # Compression (v2.2.0)
    'compress',
    'decompress',
    'CompressionAlgorithm',
    'CompressionError',
    'get_compression_ratio',
    'estimate_compressed_size',
    'get_available_algorithms',
    
    # Batch processing (v2.2.0)
    'BatchProcessor',
    'BatchResult',
    'BatchItem',
    'BatchStatus',
    'batch_capacity_check',
    'BatchCredentials',  # NEW in v2.2.1
]
