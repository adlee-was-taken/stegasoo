"""
Stegasoo QR Code Utilities

Functions for generating and reading QR codes containing RSA keys.
Supports automatic compression for large keys.
"""

import io
import zlib
import base64
from typing import Optional, Tuple

from PIL import Image

# QR code generation
try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M
    HAS_QRCODE_WRITE = True
except ImportError:
    HAS_QRCODE_WRITE = False

# QR code reading
try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    from pyzbar.pyzbar import ZBarSymbol
    HAS_QRCODE_READ = True
except ImportError:
    HAS_QRCODE_READ = False


# Constants
COMPRESSION_PREFIX = "STEGASOO-Z:"
QR_MAX_BINARY = 2900  # Safe limit for binary data in QR


def compress_data(data: str) -> str:
    """
    Compress string data for QR code storage.
    
    Args:
        data: String to compress
        
    Returns:
        Compressed string with STEGASOO-Z: prefix
    """
    compressed = zlib.compress(data.encode('utf-8'), level=9)
    encoded = base64.b64encode(compressed).decode('ascii')
    return COMPRESSION_PREFIX + encoded


def decompress_data(data: str) -> str:
    """
    Decompress data from QR code.
    
    Args:
        data: Compressed string with STEGASOO-Z: prefix
        
    Returns:
        Original uncompressed string
        
    Raises:
        ValueError: If data is not valid compressed format
    """
    if not data.startswith(COMPRESSION_PREFIX):
        raise ValueError("Data is not in compressed format")
    
    encoded = data[len(COMPRESSION_PREFIX):]
    compressed = base64.b64decode(encoded)
    return zlib.decompress(compressed).decode('utf-8')


def normalize_pem(pem_data: str) -> str:
    """
    Normalize PEM data to ensure proper formatting.
    
    Fixes common issues:
    - Inconsistent line endings
    - Missing newlines after header/before footer
    - Extra whitespace
    
    Args:
        pem_data: Raw PEM string
        
    Returns:
        Properly formatted PEM string
    """
    import re
    
    # Normalize line endings
    pem_data = pem_data.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove any leading/trailing whitespace
    pem_data = pem_data.strip()
    
    # Extract header, content, and footer using regex
    # Match patterns like -----BEGIN RSA PRIVATE KEY----- or -----BEGIN PRIVATE KEY-----
    pattern = r'(-----BEGIN [^-]+-----)(.*?)(-----END [^-]+-----)'
    match = re.search(pattern, pem_data, re.DOTALL)
    
    if not match:
        return pem_data  # Return as-is if not recognized
    
    header = match.group(1)
    content = match.group(2)
    footer = match.group(3)
    
    # Clean up the base64 content
    # Remove all whitespace and rejoin with proper 64-char lines
    content_clean = ''.join(content.split())
    
    # Split into 64-character lines (PEM standard)
    lines = [content_clean[i:i+64] for i in range(0, len(content_clean), 64)]
    
    # Reconstruct PEM
    return header + '\n' + '\n'.join(lines) + '\n' + footer + '\n'


def is_compressed(data: str) -> bool:
    """Check if data has compression prefix."""
    return data.startswith(COMPRESSION_PREFIX)


def auto_decompress(data: str) -> str:
    """
    Automatically decompress data if compressed, otherwise return as-is.
    
    Args:
        data: Possibly compressed string
        
    Returns:
        Decompressed string
    """
    if is_compressed(data):
        return decompress_data(data)
    return data


def get_compressed_size(data: str) -> int:
    """Get size of data after compression (including prefix)."""
    return len(compress_data(data))


def can_fit_in_qr(data: str, compress: bool = False) -> bool:
    """
    Check if data can fit in a QR code.
    
    Args:
        data: String data
        compress: Whether compression will be used
        
    Returns:
        True if data fits
    """
    if compress:
        size = get_compressed_size(data)
    else:
        size = len(data.encode('utf-8'))
    return size <= QR_MAX_BINARY


def needs_compression(data: str) -> bool:
    """Check if data needs compression to fit in QR code."""
    return not can_fit_in_qr(data, compress=False) and can_fit_in_qr(data, compress=True)


def generate_qr_code(
    data: str,
    compress: bool = False,
    error_correction=None
) -> bytes:
    """
    Generate a QR code PNG from string data.
    
    Args:
        data: String data to encode
        compress: Whether to compress data first
        error_correction: QR error correction level (default: auto)
        
    Returns:
        PNG image bytes
        
    Raises:
        RuntimeError: If qrcode library not available
        ValueError: If data too large for QR code
    """
    if not HAS_QRCODE_WRITE:
        raise RuntimeError("qrcode library not installed. Run: pip install qrcode[pil]")
    
    qr_data = data
    
    # Compress if requested
    if compress:
        qr_data = compress_data(data)
    
    # Check size
    if len(qr_data.encode('utf-8')) > QR_MAX_BINARY:
        raise ValueError(
            f"Data too large for QR code ({len(qr_data)} bytes). "
            f"Maximum: {QR_MAX_BINARY} bytes"
        )
    
    # Use lower error correction for larger data
    if error_correction is None:
        error_correction = ERROR_CORRECT_L if len(qr_data) > 1000 else ERROR_CORRECT_M
    
    qr = qrcode.QRCode(
        version=None,
        error_correction=error_correction,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()


def read_qr_code(image_data: bytes) -> Optional[str]:
    """
    Read QR code from image data.
    
    Args:
        image_data: Image bytes (PNG, JPG, etc.)
        
    Returns:
        Decoded string, or None if no QR code found
        
    Raises:
        RuntimeError: If pyzbar library not available
    """
    if not HAS_QRCODE_READ:
        raise RuntimeError(
            "pyzbar library not installed. Run: pip install pyzbar\n"
            "Also requires system library: sudo apt-get install libzbar0"
        )
    
    try:
        img = Image.open(io.BytesIO(image_data))
        
        # Convert to RGB if necessary (pyzbar works best with RGB/grayscale)
        if img.mode not in ('RGB', 'L'):
            img = img.convert('RGB')
        
        # Decode QR codes
        decoded = pyzbar_decode(img, symbols=[ZBarSymbol.QRCODE])
        
        if not decoded:
            return None
        
        # Return first QR code found
        return decoded[0].data.decode('utf-8')
        
    except Exception:
        return None


def read_qr_code_from_file(filepath: str) -> Optional[str]:
    """
    Read QR code from image file.
    
    Args:
        filepath: Path to image file
        
    Returns:
        Decoded string, or None if no QR code found
    """
    with open(filepath, 'rb') as f:
        return read_qr_code(f.read())


def extract_key_from_qr(image_data: bytes) -> Optional[str]:
    """
    Extract RSA key from QR code image, auto-decompressing if needed.
    
    Args:
        image_data: Image bytes containing QR code
        
    Returns:
        PEM-encoded RSA key string, or None if not found/invalid
    """
    qr_data = read_qr_code(image_data)
    
    if not qr_data:
        return None
    
    # Auto-decompress if needed
    try:
        if is_compressed(qr_data):
            key_pem = decompress_data(qr_data)
        else:
            key_pem = qr_data
    except Exception:
        key_pem = qr_data
    
    # Validate it looks like a PEM key
    if '-----BEGIN' in key_pem and '-----END' in key_pem:
        # Normalize PEM format to fix potential line ending issues
        key_pem = normalize_pem(key_pem)
        return key_pem
    
    return None


def extract_key_from_qr_file(filepath: str) -> Optional[str]:
    """
    Extract RSA key from QR code image file.
    
    Args:
        filepath: Path to image file containing QR code
        
    Returns:
        PEM-encoded RSA key string, or None if not found/invalid
    """
    with open(filepath, 'rb') as f:
        return extract_key_from_qr(f.read())


def has_qr_write() -> bool:
    """Check if QR code writing is available."""
    return HAS_QRCODE_WRITE


def has_qr_read() -> bool:
    """Check if QR code reading is available."""
    return HAS_QRCODE_READ


def has_qr_support() -> bool:
    """Check if full QR code support is available."""
    return HAS_QRCODE_WRITE and HAS_QRCODE_READ
