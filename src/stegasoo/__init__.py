"""
Stegasoo - Secure Steganography Library (v3.0.1)

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

Capacity Pre-check:
    from stegasoo import will_fit
    
    # Check if payload will fit before encoding
    result = will_fit("My secret message", carrier_image)
    if result['fits']:
        print(f"Will use {result['usage_percent']:.1f}% capacity")
    else:
        print(f"Need {-result['headroom']} more bytes")

NEW in v3.0 - DCT Embedding Mode:
    from stegasoo import encode, has_dct_support, compare_modes
    
    # Check if DCT mode is available (requires scipy)
    if has_dct_support():
        # DCT mode: smaller capacity, grayscale output, frequency domain
        result = encode(
            message="Secret",
            reference_photo=ref_photo,
            carrier_image=carrier,
            day_phrase="apple forest thunder",
            pin="123456",
            embed_mode='dct',  # NEW parameter
        )
    
    # Compare mode capacities
    info = compare_modes(carrier_image)
    print(f"LSB capacity: {info['lsb']['capacity_kb']:.1f} KB")
    print(f"DCT capacity: {info['dct']['capacity_kb']:.1f} KB")

NEW in v3.0.1 - DCT Output Format:
    # DCT mode can output PNG (lossless) or JPEG (smaller, natural)
    result = encode(
        message="Secret",
        ...,
        embed_mode='dct',
        dct_output_format='jpeg',  # 'png' (default) or 'jpeg'
    )

Debugging:
    from stegasoo.debug import debug
    debug.enable(True)  # Enable debug output
    debug.enable_performance(True)  # Enable timing
"""

from .constants import (
    __version__,
    DAY_NAMES,
    MAX_MESSAGE_SIZE,
    MAX_FILE_PAYLOAD_SIZE,
    # NEW in v3.0 - Embedding modes
    EMBED_MODE_LSB,
    EMBED_MODE_DCT,
    EMBED_MODE_AUTO,
    detect_stego_mode,
)
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
    will_fit,
    # NEW in v3.0
    has_dct_support,
    calculate_capacity_by_mode,
    will_fit_by_mode,
    get_available_modes,
    compare_modes,
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
    strip_image_metadata,
)
from .debug import debug  # Import debug utilities

# =============================================================================
# Compression
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
# Batch Processing
# =============================================================================
from .batch import (
    BatchProcessor,
    BatchResult,
    BatchItem,
    BatchStatus,
    batch_capacity_check,
    BatchCredentials,
)

# =============================================================================
# NEW in v3.0 - DCT Steganography (optional, requires scipy)
# =============================================================================
try:
    from .dct_steganography import (
        embed_in_dct,
        extract_from_dct,
        calculate_dct_capacity,
        will_fit_dct,
        estimate_capacity_comparison,
        DCTEmbedStats,
        DCTCapacityInfo,
    )
    HAS_DCT = True
except ImportError:
    HAS_DCT = False
    # Provide stub functions that raise helpful errors
    def embed_in_dct(*args, **kwargs):
        raise ImportError("DCT mode requires scipy. Install: pip install scipy")
    def extract_from_dct(*args, **kwargs):
        raise ImportError("DCT mode requires scipy. Install: pip install scipy")
    def calculate_dct_capacity(*args, **kwargs):
        raise ImportError("DCT mode requires scipy. Install: pip install scipy")
    def will_fit_dct(*args, **kwargs):
        raise ImportError("DCT mode requires scipy. Install: pip install scipy")
    def estimate_capacity_comparison(*args, **kwargs):
        raise ImportError("DCT mode requires scipy. Install: pip install scipy")
    
    # Stub classes
    class DCTEmbedStats:
        pass
    class DCTCapacityInfo:
        pass

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


# =============================================================================
# ENCODE FUNCTION (v3.0.1 - with dct_output_format)
# =============================================================================

def encode(
    message,  # Union[str, bytes, FilePayload]
    reference_photo: bytes,
    carrier_image: bytes,
    day_phrase: str,
    pin: str = "",
    rsa_key_data = None,  # Optional[bytes]
    rsa_password = None,  # Optional[str]
    date_str = None,  # Optional[str]
    output_format = None,  # Optional[str]
    embed_mode: str = EMBED_MODE_LSB,
    dct_output_format: str = "png",  # NEW in v3.0.1: 'png' or 'jpeg'
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
        output_format: Force output format ('PNG', 'BMP') - LSB mode only
        embed_mode: Embedding mode - 'lsb' (default) or 'dct' (v3.0+)
        dct_output_format: For DCT mode - 'png' (lossless) or 'jpeg' (smaller)
        
    Returns:
        EncodeResult with stego image and metadata
        
    Raises:
        ValidationError: If inputs are invalid
        SecurityFactorError: If no PIN or RSA key provided
        CapacityError: If carrier is too small
        EncryptionError: If encryption fails
        ImportError: If DCT mode requested but scipy unavailable
        
    Example:
        # Default LSB mode
        >>> result = encode(message="Secret", ...)
        
        # DCT mode with PNG output (lossless)
        >>> result = encode(message="Secret", ..., embed_mode='dct')
        
        # DCT mode with JPEG output (smaller, natural)
        >>> result = encode(message="Secret", ..., embed_mode='dct', dct_output_format='jpeg')
    """
    # Debug logging
    debug.print(f"encode called: message type={type(message).__name__}, "
                f"day_phrase='{day_phrase[:20]}...', pin_length={len(pin)}, "
                f"embed_mode={embed_mode}, dct_output_format={dct_output_format}")
    
    # Validate embed_mode
    if embed_mode not in (EMBED_MODE_LSB, EMBED_MODE_DCT):
        raise ValidationError(f"Invalid embed_mode: {embed_mode}. Use 'lsb' or 'dct'")
    
    if embed_mode == EMBED_MODE_DCT and not has_dct_support():
        raise ImportError(
            "DCT embedding mode requires scipy. "
            "Install with: pip install scipy"
        )
    
    # Validate dct_output_format
    if dct_output_format not in ('png', 'jpeg'):
        debug.print(f"Invalid dct_output_format '{dct_output_format}', defaulting to 'png'")
        dct_output_format = 'png'
    
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
    # CRITICAL: Pass dct_output_format to embed_in_image
    stego_data, stats, extension = embed_in_image(
        encrypted,
        carrier_image,
        pixel_key,
        output_format=output_format,
        embed_mode=embed_mode,
        dct_output_format=dct_output_format,  # NEW in v3.0.1
    )
    
    # Generate filename with correct extension
    filename = generate_filename(date_str, extension=extension)
    
    # Handle stats from either LSB or DCT mode
    if hasattr(stats, 'pixels_modified'):
        # LSB mode stats
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
    else:
        # DCT mode stats
        debug.print(f"Encoding complete (DCT): {filename}, "
                    f"embedded {stats.bits_embedded // 8} bytes "
                    f"({stats.usage_percent:.2f}% capacity)")
        
        return EncodeResult(
            stego_image=stego_data,
            filename=filename,
            pixels_modified=stats.blocks_used * 64,  # Approximate
            total_pixels=stats.blocks_available * 64,
            capacity_used=stats.usage_percent / 100.0,
            date_used=date_str
        )


# =============================================================================
# ENCODE_FILE FUNCTION (v3.0.1 - with dct_output_format)
# =============================================================================

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
    embed_mode: str = EMBED_MODE_LSB,
    dct_output_format: str = "png",  # NEW in v3.0.1
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
        output_format: Force output format ('PNG', 'BMP') - LSB mode only
        filename_override: Override the stored filename
        embed_mode: 'lsb' (default) or 'dct' (v3.0+)
        dct_output_format: For DCT mode - 'png' or 'jpeg' (v3.0.1+)
        
    Returns:
        EncodeResult with stego image and metadata
    """
    debug.print(f"encode_file called: filepath={filepath}, embed_mode={embed_mode}, "
                f"dct_output_format={dct_output_format}")
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
        embed_mode=embed_mode,
        dct_output_format=dct_output_format,  # NEW in v3.0.1
    )


# =============================================================================
# ENCODE_BYTES FUNCTION (v3.0.1 - with dct_output_format)
# =============================================================================

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
    embed_mode: str = EMBED_MODE_LSB,
    dct_output_format: str = "png",  # NEW in v3.0.1
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
        output_format: Force output format ('PNG', 'BMP') - LSB mode only
        mime_type: MIME type of the data
        embed_mode: 'lsb' (default) or 'dct' (v3.0+)
        dct_output_format: For DCT mode - 'png' or 'jpeg' (v3.0.1+)
        
    Returns:
        EncodeResult with stego image and metadata
    """
    debug.print(f"encode_bytes called: filename={filename}, data_size={len(data)}, "
                f"embed_mode={embed_mode}, dct_output_format={dct_output_format}")
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
        embed_mode=embed_mode,
        dct_output_format=dct_output_format,  # NEW in v3.0.1
    )


# =============================================================================
# DECODE FUNCTION
# =============================================================================

@debug.time
def decode(
    stego_image: bytes,
    reference_photo: bytes,
    day_phrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    date_str: Optional[str] = None,
    embed_mode: str = EMBED_MODE_AUTO,
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
        date_str: Date override (defaults to today, then checks header)
        embed_mode: 'auto' (default), 'lsb', or 'dct' (v3.0+)
                    - 'auto': Try LSB first, then DCT if available
                    - 'lsb': Only try LSB extraction
                    - 'dct': Only try DCT extraction (requires scipy)
        
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
        ImportError: If DCT mode explicitly requested but scipy unavailable
        
    Note:
        With embed_mode='auto' (default), tries LSB first then DCT.
        For best performance, specify the mode if you know it.
    """
    debug.print(f"decode called: stego_image_size={len(stego_image)}, "
                f"day_phrase='{day_phrase[:20]}...', embed_mode={embed_mode}")
    
    # Validate embed_mode
    if embed_mode not in (EMBED_MODE_AUTO, EMBED_MODE_LSB, EMBED_MODE_DCT):
        raise ValidationError(f"Invalid embed_mode: {embed_mode}. Use 'auto', 'lsb', or 'dct'")
    
    if embed_mode == EMBED_MODE_DCT and not has_dct_support():
        raise ImportError(
            "DCT extraction mode requires scipy. "
            "Install with: pip install scipy"
        )
    
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
    
    # Extract with specified mode
    encrypted = extract_from_image(
        stego_image,
        pixel_key,
        embed_mode=embed_mode,
    )
    
    # If we got data, check if it's from a different date
    if encrypted:
        header = parse_header(encrypted)
        if header and header['date'] != date_str:
            debug.print(f"Found different date in header: {header['date']} (expected {date_str})")
            # Re-extract with correct date
            pixel_key = derive_pixel_key(
                reference_photo, day_phrase, header['date'], pin, rsa_key_data
            )
            encrypted = extract_from_image(
                stego_image,
                pixel_key,
                embed_mode=embed_mode,
            )
    
    if not encrypted:
        debug.print("No data extracted from image")
        raise ExtractionError("Could not extract data. Check your inputs.")
    
    debug.print(f"Extracted {len(encrypted)} bytes from image")
    debug.data(encrypted[:64], "First 64 bytes of extracted data")
    
    # Decrypt and return full result
    return decrypt_message(encrypted, reference_photo, day_phrase, pin, rsa_key_data)


# =============================================================================
# DECODE_TEXT FUNCTION
# =============================================================================

def decode_text(
    stego_image: bytes,
    reference_photo: bytes,
    day_phrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    date_str: Optional[str] = None,
    embed_mode: str = EMBED_MODE_AUTO,
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
        date_str: Date override
        embed_mode: 'auto' (default), 'lsb', or 'dct' (v3.0+)
        
    Returns:
        Decrypted message string
        
    Raises:
        DecryptionError: If content is a binary file, not text
    """
    debug.print(f"decode_text called, embed_mode={embed_mode}")
    result = decode(
        stego_image,
        reference_photo,
        day_phrase,
        pin,
        rsa_key_data,
        rsa_password,
        date_str,
        embed_mode,
    )
    
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


# =============================================================================
# EXPORTS
# =============================================================================

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
    
    # NEW in v3.0 - Embedding modes
    'EMBED_MODE_LSB',
    'EMBED_MODE_DCT',
    'EMBED_MODE_AUTO',
    'has_dct_support',
    'compare_modes',
    'get_available_modes',
    'calculate_capacity_by_mode',
    'will_fit_by_mode',
    'detect_stego_mode',
    'HAS_DCT',
    
    # NEW in v3.0 - DCT functions (available if scipy installed)
    'embed_in_dct',
    'extract_from_dct',
    'calculate_dct_capacity',
    'will_fit_dct',
    'estimate_capacity_comparison',
    'DCTEmbedStats',
    'DCTCapacityInfo',
    
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
    'will_fit',
    
    # Utilities
    'generate_filename',
    'parse_date_from_filename',
    'get_day_from_date',
    'get_today_date',
    'get_today_day',
    'secure_delete',
    'SecureDeleter',
    'format_file_size',
    'strip_image_metadata',
    
    # Debugging
    'debug',
    
    # Compression
    'compress',
    'decompress',
    'CompressionAlgorithm',
    'CompressionError',
    'get_compression_ratio',
    'estimate_compressed_size',
    'get_available_algorithms',
    
    # Batch processing
    'BatchProcessor',
    'BatchResult',
    'BatchItem',
    'BatchStatus',
    'batch_capacity_check',
    'BatchCredentials',
]
