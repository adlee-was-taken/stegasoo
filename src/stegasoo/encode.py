"""
Stegasoo Encode Module (v3.2.0)

High-level encoding functions for hiding messages and files in images.
"""

from typing import Optional, Union
from pathlib import Path

from .models import EncodeInput, EncodeResult, FilePayload
from .crypto import encrypt_message, derive_pixel_key
from .steganography import embed_in_image
from .validation import (
    require_valid_payload,
    require_valid_image,
    require_security_factors,
    require_valid_pin,
    require_valid_rsa_key,
)
from .utils import generate_filename
from .constants import EMBED_MODE_LSB
from .debug import debug


def encode(
    message: Union[str, bytes, FilePayload],
    reference_photo: bytes,
    carrier_image: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    output_format: Optional[str] = None,
    embed_mode: str = EMBED_MODE_LSB,
    dct_output_format: str = "png",
    dct_color_mode: str = "grayscale",
) -> EncodeResult:
    """
    Encode a message or file into an image.
    
    Args:
        message: Text message, raw bytes, or FilePayload to hide
        reference_photo: Shared reference photo bytes
        carrier_image: Carrier image bytes
        passphrase: Shared passphrase (recommend 4+ words)
        pin: Optional static PIN
        rsa_key_data: Optional RSA private key PEM bytes
        rsa_password: Optional password for encrypted RSA key
        output_format: Force output format ('PNG', 'BMP') - LSB mode only
        embed_mode: 'lsb' (default) or 'dct'
        dct_output_format: For DCT mode - 'png' or 'jpeg'
        dct_color_mode: For DCT mode - 'grayscale' or 'color'
        
    Returns:
        EncodeResult with stego image and metadata
        
    Example:
        >>> result = encode(
        ...     message="Secret message",
        ...     reference_photo=ref_bytes,
        ...     carrier_image=carrier_bytes,
        ...     passphrase="apple forest thunder mountain",
        ...     pin="123456"
        ... )
        >>> with open('stego.png', 'wb') as f:
        ...     f.write(result.stego_image)
    """
    debug.print(f"encode: passphrase length={len(passphrase.split())} words, "
                f"pin={'set' if pin else 'none'}, mode={embed_mode}")
    
    # Validate inputs
    require_valid_payload(message)
    require_valid_image(reference_photo, "Reference photo")
    require_valid_image(carrier_image, "Carrier image")
    require_security_factors(pin, rsa_key_data)
    
    if pin:
        require_valid_pin(pin)
    if rsa_key_data:
        require_valid_rsa_key(rsa_key_data, rsa_password)
    
    # Encrypt message
    encrypted = encrypt_message(
        message, reference_photo, passphrase, pin, rsa_key_data
    )
    
    debug.print(f"Encrypted payload: {len(encrypted)} bytes")
    
    # Derive pixel/coefficient selection key
    pixel_key = derive_pixel_key(
        reference_photo, passphrase, pin, rsa_key_data
    )
    
    # Embed in image
    stego_data, stats, extension = embed_in_image(
        encrypted,
        carrier_image,
        pixel_key,
        output_format=output_format,
        embed_mode=embed_mode,
        dct_output_format=dct_output_format,
        dct_color_mode=dct_color_mode,
    )
    
    # Generate filename
    filename = generate_filename(extension=extension)
    
    # Create result
    if hasattr(stats, 'pixels_modified'):
        # LSB mode stats
        return EncodeResult(
            stego_image=stego_data,
            filename=filename,
            pixels_modified=stats.pixels_modified,
            total_pixels=stats.total_pixels,
            capacity_used=stats.capacity_used,
            date_used=None,  # No longer used in v3.2.0
        )
    else:
        # DCT mode stats
        return EncodeResult(
            stego_image=stego_data,
            filename=filename,
            pixels_modified=stats.blocks_used * 64,
            total_pixels=stats.blocks_available * 64,
            capacity_used=stats.usage_percent / 100.0,
            date_used=None,
        )


def encode_file(
    filepath: Union[str, Path],
    reference_photo: bytes,
    carrier_image: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    output_format: Optional[str] = None,
    filename_override: Optional[str] = None,
    embed_mode: str = EMBED_MODE_LSB,
    dct_output_format: str = "png",
    dct_color_mode: str = "grayscale",
) -> EncodeResult:
    """
    Encode a file into an image.
    
    Convenience wrapper that loads a file and encodes it.
    
    Args:
        filepath: Path to file to embed
        reference_photo: Shared reference photo bytes
        carrier_image: Carrier image bytes
        passphrase: Shared passphrase
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        rsa_password: Optional RSA key password
        output_format: Force output format - LSB only
        filename_override: Override stored filename
        embed_mode: 'lsb' or 'dct'
        dct_output_format: 'png' or 'jpeg'
        dct_color_mode: 'grayscale' or 'color'
        
    Returns:
        EncodeResult
    """
    payload = FilePayload.from_file(str(filepath), filename_override)
    
    return encode(
        message=payload,
        reference_photo=reference_photo,
        carrier_image=carrier_image,
        passphrase=passphrase,
        pin=pin,
        rsa_key_data=rsa_key_data,
        rsa_password=rsa_password,
        output_format=output_format,
        embed_mode=embed_mode,
        dct_output_format=dct_output_format,
        dct_color_mode=dct_color_mode,
    )


def encode_bytes(
    data: bytes,
    filename: str,
    reference_photo: bytes,
    carrier_image: bytes,
    passphrase: str,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None,
    rsa_password: Optional[str] = None,
    output_format: Optional[str] = None,
    mime_type: Optional[str] = None,
    embed_mode: str = EMBED_MODE_LSB,
    dct_output_format: str = "png",
    dct_color_mode: str = "grayscale",
) -> EncodeResult:
    """
    Encode raw bytes with metadata into an image.
    
    Args:
        data: Raw bytes to embed
        filename: Filename to associate with data
        reference_photo: Shared reference photo bytes
        carrier_image: Carrier image bytes
        passphrase: Shared passphrase
        pin: Optional static PIN
        rsa_key_data: Optional RSA key bytes
        rsa_password: Optional RSA key password
        output_format: Force output format - LSB only
        mime_type: MIME type of data
        embed_mode: 'lsb' or 'dct'
        dct_output_format: 'png' or 'jpeg'
        dct_color_mode: 'grayscale' or 'color'
        
    Returns:
        EncodeResult
    """
    payload = FilePayload(data=data, filename=filename, mime_type=mime_type)
    
    return encode(
        message=payload,
        reference_photo=reference_photo,
        carrier_image=carrier_image,
        passphrase=passphrase,
        pin=pin,
        rsa_key_data=rsa_key_data,
        rsa_password=rsa_password,
        output_format=output_format,
        embed_mode=embed_mode,
        dct_output_format=dct_output_format,
        dct_color_mode=dct_color_mode,
    )
