"""
Stegasoo Decode Module (v3.2.0)

High-level decoding functions for extracting messages and files from images.
"""

from typing import Optional
from pathlib import Path

from .models import DecodeInput, DecodeResult
from .crypto import decrypt_message
from .steganography import extract_from_image
from .validation import (
    require_valid_image,
    require_security_factors,
    require_valid_pin,
    require_valid_rsa_key,
)
from .constants import EMBED_MODE_AUTO
from .exceptions import ExtractionError, DecryptionError
from .debug import debug


def decode(
    stego_image: bytes,
    reference_photo: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    embed_mode: str = EMBED_MODE_AUTO,
) -> DecodeResult:
    """
    Decode a message or file from a stego image.
    
    Args:
        stego_image: Stego image bytes
        reference_photo: Shared reference photo bytes
        passphrase: Shared passphrase used during encoding
        pin: Optional static PIN (if used during encoding)
        rsa_key_data: Optional RSA key bytes (if used during encoding)
        rsa_password: Optional RSA key password
        embed_mode: 'auto' (default), 'lsb', or 'dct'
        
    Returns:
        DecodeResult with message or file data
        
    Example:
        >>> result = decode(
        ...     stego_image=stego_bytes,
        ...     reference_photo=ref_bytes,
        ...     passphrase="apple forest thunder mountain",
        ...     pin="123456"
        ... )
        >>> if result.is_text:
        ...     print(result.message)
        ... else:
        ...     with open(result.filename, 'wb') as f:
        ...         f.write(result.file_data)
    """
    debug.print(f"decode: passphrase length={len(passphrase.split())} words, "
                f"mode={embed_mode}")
    
    # Validate inputs
    require_valid_image(stego_image, "Stego image")
    require_valid_image(reference_photo, "Reference photo")
    require_security_factors(pin, rsa_key_data)
    
    if pin:
        require_valid_pin(pin)
    if rsa_key_data:
        require_valid_rsa_key(rsa_key_data, rsa_password)
    
    # Derive pixel/coefficient selection key
    from .crypto import derive_pixel_key
    pixel_key = derive_pixel_key(
        reference_photo, passphrase, pin, rsa_key_data
    )
    
    # Extract encrypted data
    encrypted = extract_from_image(
        stego_image,
        pixel_key,
        embed_mode=embed_mode,
    )
    
    if not encrypted:
        debug.print("No data extracted from image")
        raise ExtractionError("Could not extract data. Check your credentials and image.")
    
    debug.print(f"Extracted {len(encrypted)} bytes from image")
    
    # Decrypt
    result = decrypt_message(
        encrypted, reference_photo, passphrase, pin, rsa_key_data
    )
    
    debug.print(f"Decryption successful: {result.payload_type}")
    return result


def decode_file(
    stego_image: bytes,
    reference_photo: bytes,
    passphrase: str,
    output_path: Optional[Path] = None,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    embed_mode: str = EMBED_MODE_AUTO,
) -> Path:
    """
    Decode a file from a stego image and save it.
    
    Args:
        stego_image: Stego image bytes
        reference_photo: Shared reference photo bytes
        passphrase: Shared passphrase
        output_path: Optional output path (defaults to original filename)
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        rsa_password: Optional RSA key password
        embed_mode: 'auto', 'lsb', or 'dct'
        
    Returns:
        Path where file was saved
        
    Raises:
        DecryptionError: If payload is text, not a file
    """
    result = decode(
        stego_image,
        reference_photo,
        passphrase,
        pin,
        rsa_key_data,
        rsa_password,
        embed_mode,
    )
    
    if not result.is_file:
        raise DecryptionError("Payload is a text message, not a file")
    
    if output_path is None:
        output_path = Path(result.filename or "extracted_file")
    else:
        output_path = Path(output_path)
        if output_path.is_dir():
            output_path = output_path / (result.filename or "extracted_file")
    
    # Write file
    output_path.write_bytes(result.file_data or b"")
    
    debug.print(f"File saved to: {output_path}")
    return output_path


def decode_text(
    stego_image: bytes,
    reference_photo: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    embed_mode: str = EMBED_MODE_AUTO,
) -> str:
    """
    Decode a text message from a stego image.
    
    Convenience function that returns just the message string.
    
    Args:
        stego_image: Stego image bytes
        reference_photo: Shared reference photo bytes
        passphrase: Shared passphrase
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        rsa_password: Optional RSA key password
        embed_mode: 'auto', 'lsb', or 'dct'
        
    Returns:
        Decoded message string
        
    Raises:
        DecryptionError: If payload is a file, not text
    """
    result = decode(
        stego_image,
        reference_photo,
        passphrase,
        pin,
        rsa_key_data,
        rsa_password,
        embed_mode,
    )
    
    if result.is_file:
        # Try to decode as text
        if result.file_data:
            try:
                return result.file_data.decode('utf-8')
            except UnicodeDecodeError:
                raise DecryptionError(
                    f"Payload is a binary file ({result.filename or 'unnamed'}), not text"
                )
        return ""
    
    return result.message or ""
