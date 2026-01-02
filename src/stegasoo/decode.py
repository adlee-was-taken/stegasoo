"""
Stegasoo Decode Module (v4.0.0)

High-level decoding functions for extracting messages and files from images.

Changes in v4.0.0:
- Added channel_key parameter for deployment/group isolation
- Improved error messages for channel key mismatches
"""

from pathlib import Path

from .constants import EMBED_MODE_AUTO
from .crypto import decrypt_message
from .debug import debug
from .exceptions import DecryptionError, ExtractionError
from .models import DecodeResult
from .steganography import extract_from_image
from .validation import (
    require_security_factors,
    require_valid_image,
    require_valid_pin,
    require_valid_rsa_key,
)


def decode(
    stego_image: bytes,
    reference_photo: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: bytes | None = None,
    rsa_password: str | None = None,
    embed_mode: str = EMBED_MODE_AUTO,
    channel_key: str | bool | None = None,
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
        channel_key: Channel key for deployment/group isolation:
            - None or "auto": Use server's configured key
            - str: Use this specific channel key
            - "" or False: No channel key (public mode)

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

    Example with explicit channel key:
        >>> result = decode(
        ...     stego_image=stego_bytes,
        ...     reference_photo=ref_bytes,
        ...     passphrase="apple forest thunder mountain",
        ...     pin="123456",
        ...     channel_key="ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456"
        ... )
    """
    debug.print(
        f"decode: passphrase length={len(passphrase.split())} words, "
        f"mode={embed_mode}, "
        f"channel_key={'explicit' if isinstance(channel_key, str) and channel_key else 'auto' if channel_key is None else 'none'}"
    )

    # Validate inputs
    require_valid_image(stego_image, "Stego image")
    require_valid_image(reference_photo, "Reference photo")
    require_security_factors(pin, rsa_key_data)

    if pin:
        require_valid_pin(pin)
    if rsa_key_data:
        require_valid_rsa_key(rsa_key_data, rsa_password)

    # Derive pixel/coefficient selection key (with channel key)
    from .crypto import derive_pixel_key

    pixel_key = derive_pixel_key(reference_photo, passphrase, pin, rsa_key_data, channel_key)

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

    # Decrypt (with channel key)
    result = decrypt_message(encrypted, reference_photo, passphrase, pin, rsa_key_data, channel_key)

    debug.print(f"Decryption successful: {result.payload_type}")
    return result


def decode_file(
    stego_image: bytes,
    reference_photo: bytes,
    passphrase: str,
    output_path: Path | None = None,
    pin: str = "",
    rsa_key_data: bytes | None = None,
    rsa_password: str | None = None,
    embed_mode: str = EMBED_MODE_AUTO,
    channel_key: str | bool | None = None,
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
        channel_key: Channel key parameter (see decode())

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
        channel_key,
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
    rsa_key_data: bytes | None = None,
    rsa_password: str | None = None,
    embed_mode: str = EMBED_MODE_AUTO,
    channel_key: str | bool | None = None,
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
        channel_key: Channel key parameter (see decode())

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
        channel_key,
    )

    if result.is_file:
        # Try to decode as text
        if result.file_data:
            try:
                return result.file_data.decode("utf-8")
            except UnicodeDecodeError:
                raise DecryptionError(
                    f"Payload is a binary file ({result.filename or 'unnamed'}), not text"
                )
        return ""

    return result.message or ""
