"""
Stegasoo QR Code Utilities

Functions for generating and reading QR codes containing RSA keys.
Supports automatic compression for large keys.

IMPROVEMENTS IN THIS VERSION:
- Much more robust PEM normalization
- Better handling of QR code extraction edge cases
- Improved error messages
"""

import base64
import io
import zlib

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
    from pyzbar.pyzbar import ZBarSymbol
    from pyzbar.pyzbar import decode as pyzbar_decode

    HAS_QRCODE_READ = True
except ImportError:
    HAS_QRCODE_READ = False


from .constants import (
    QR_CROP_MIN_PADDING_PX,
    QR_CROP_PADDING_PERCENT,
    QR_MAX_BINARY,
)

# Constants
COMPRESSION_PREFIX = "STEGASOO-Z:"


def compress_data(data: str) -> str:
    """
    Compress string data for QR code storage.

    Args:
        data: String to compress

    Returns:
        Compressed string with STEGASOO-Z: prefix
    """
    compressed = zlib.compress(data.encode("utf-8"), level=9)
    encoded = base64.b64encode(compressed).decode("ascii")
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

    encoded = data[len(COMPRESSION_PREFIX) :]
    compressed = base64.b64decode(encoded)
    return zlib.decompress(compressed).decode("utf-8")


def normalize_pem(pem_data: str) -> str:
    """
    Normalize PEM data to ensure proper formatting for cryptography library.

    The cryptography library is very particular about PEM formatting.
    This function handles all common issues from QR code extraction:
    - Inconsistent line endings (CRLF, LF, CR)
    - Missing newlines after header/before footer
    - Extra whitespace, tabs, multiple spaces
    - Non-ASCII characters
    - Incorrect base64 padding
    - Malformed headers/footers

    Args:
        pem_data: Raw PEM string from QR code

    Returns:
        Properly formatted PEM string that cryptography library will accept
    """
    import re

    # Step 1: Normalize ALL line endings to \n
    pem_data = pem_data.replace("\r\n", "\n").replace("\r", "\n")

    # Step 2: Remove leading/trailing whitespace
    pem_data = pem_data.strip()

    # Step 3: Remove any non-ASCII characters (QR artifacts)
    pem_data = "".join(char for char in pem_data if ord(char) < 128)

    # Step 4: Extract header, content, and footer with flexible regex
    # This handles variations like:
    # - "PRIVATE KEY" vs "RSA PRIVATE KEY"
    # - Extra spaces in headers
    # - Missing spaces
    pattern = r"(-----BEGIN[^-]*-----)(.*?)(-----END[^-]*-----)"
    match = re.search(pattern, pem_data, re.DOTALL | re.IGNORECASE)

    if not match:
        # Fallback: try even more permissive pattern
        pattern = r"(-+BEGIN[^-]+-+)(.*?)(-+END[^-]+-+)"
        match = re.search(pattern, pem_data, re.DOTALL | re.IGNORECASE)

        if not match:
            # Last resort: return original if can't parse
            return pem_data

    header_raw = match.group(1).strip()
    content_raw = match.group(2)
    footer_raw = match.group(3).strip()

    # Step 5: Normalize header and footer
    # Standardize spacing and ensure proper format
    header = re.sub(r"\s+", " ", header_raw)
    footer = re.sub(r"\s+", " ", footer_raw)

    # Ensure exactly 5 dashes on each side
    header = re.sub(r"^-+", "-----", header)
    header = re.sub(r"-+$", "-----", header)
    footer = re.sub(r"^-+", "-----", footer)
    footer = re.sub(r"-+$", "-----", footer)

    # Step 6: Clean the base64 content THOROUGHLY
    # Remove ALL whitespace: spaces, tabs, newlines
    # Keep only valid base64 characters: A-Z, a-z, 0-9, +, /, =
    content_clean = "".join(char for char in content_raw if char.isalnum() or char in "+/=")

    # Double-check: remove any remaining invalid characters
    content_clean = re.sub(r"[^A-Za-z0-9+/=]", "", content_clean)

    # Step 7: Fix base64 padding
    # Base64 strings must be divisible by 4
    remainder = len(content_clean) % 4
    if remainder:
        content_clean += "=" * (4 - remainder)

    # Step 8: Split into 64-character lines (PEM standard)
    lines = [content_clean[i : i + 64] for i in range(0, len(content_clean), 64)]

    # Step 9: Reconstruct with EXACT PEM formatting
    # Format: header\ncontent_line1\ncontent_line2\n...\nfooter\n
    return header + "\n" + "\n".join(lines) + "\n" + footer + "\n"


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
        size = len(data.encode("utf-8"))
    return size <= QR_MAX_BINARY


def needs_compression(data: str) -> bool:
    """Check if data needs compression to fit in QR code."""
    return not can_fit_in_qr(data, compress=False) and can_fit_in_qr(data, compress=True)


def generate_qr_code(data: str, compress: bool = False, error_correction=None) -> bytes:
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
    if len(qr_data.encode("utf-8")) > QR_MAX_BINARY:
        raise ValueError(
            f"Data too large for QR code ({len(qr_data)} bytes). " f"Maximum: {QR_MAX_BINARY} bytes"
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
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.getvalue()


def read_qr_code(image_data: bytes) -> str | None:
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
        img: Image.Image = Image.open(io.BytesIO(image_data))

        # Convert to RGB if necessary (pyzbar works best with RGB/grayscale)
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")

        # Decode QR codes
        decoded = pyzbar_decode(img, symbols=[ZBarSymbol.QRCODE])

        if not decoded:
            return None

        # Return first QR code found
        result: str = decoded[0].data.decode("utf-8")
        return result

    except Exception:
        return None


def read_qr_code_from_file(filepath: str) -> str | None:
    """
    Read QR code from image file.

    Args:
        filepath: Path to image file

    Returns:
        Decoded string, or None if no QR code found
    """
    with open(filepath, "rb") as f:
        return read_qr_code(f.read())


def extract_key_from_qr(image_data: bytes) -> str | None:
    """
    Extract RSA key from QR code image, auto-decompressing if needed.

    This function is more robust than the original, with better error handling
    and PEM normalization.

    Args:
        image_data: Image bytes containing QR code

    Returns:
        PEM-encoded RSA key string, or None if not found/invalid
    """
    # Step 1: Read QR code
    qr_data = read_qr_code(image_data)

    if not qr_data:
        return None

    # Step 2: Auto-decompress if needed
    try:
        if is_compressed(qr_data):
            key_pem = decompress_data(qr_data)
        else:
            key_pem = qr_data
    except Exception:
        # If decompression fails, try using data as-is
        key_pem = qr_data

    # Step 3: Validate it looks like a PEM key
    if "-----BEGIN" not in key_pem or "-----END" not in key_pem:
        return None

    # Step 4: Aggressively normalize PEM format
    # This is crucial - QR codes can introduce subtle formatting issues
    try:
        key_pem = normalize_pem(key_pem)
    except Exception:
        # If normalization fails, return None rather than broken PEM
        return None

    # Step 5: Final validation - ensure it still looks like PEM
    if "-----BEGIN" in key_pem and "-----END" in key_pem:
        return key_pem

    return None


def extract_key_from_qr_file(filepath: str) -> str | None:
    """
    Extract RSA key from QR code image file.

    Args:
        filepath: Path to image file containing QR code

    Returns:
        PEM-encoded RSA key string, or None if not found/invalid
    """
    with open(filepath, "rb") as f:
        return extract_key_from_qr(f.read())


def detect_and_crop_qr(
    image_data: bytes,
    padding_percent: float = QR_CROP_PADDING_PERCENT,
    min_padding_px: int = QR_CROP_MIN_PADDING_PX,
) -> bytes | None:
    """
    Detect QR code in image and crop to it, handling rotation.

    Uses the QR code's corner coordinates to compute an axis-aligned
    bounding box, then adds padding to ensure rotated QR codes aren't clipped.

    Args:
        image_data: Input image bytes (PNG, JPG, etc.)
        padding_percent: Padding as fraction of QR size (default 10%)
        min_padding_px: Minimum padding in pixels (default 10)

    Returns:
        Cropped PNG image bytes, or None if no QR code found

    Raises:
        RuntimeError: If pyzbar library not available
    """
    if not HAS_QRCODE_READ:
        raise RuntimeError(
            "pyzbar library not installed. Run: pip install pyzbar\n"
            "Also requires system library: sudo apt-get install libzbar0"
        )

    try:
        img: Image.Image = Image.open(io.BytesIO(image_data))
        original_mode = img.mode

        # Convert for pyzbar detection
        if img.mode not in ("RGB", "L"):
            detect_img = img.convert("RGB")
        else:
            detect_img = img

        # Decode QR codes to get corner positions
        decoded = pyzbar_decode(detect_img, symbols=[ZBarSymbol.QRCODE])

        if not decoded:
            return None

        # Get the polygon corners of the first QR code
        # pyzbar returns a Polygon with Point objects (x, y attributes)
        polygon = decoded[0].polygon

        if len(polygon) < 4:
            # Fallback to rect if polygon not available
            rect = decoded[0].rect
            min_x, min_y = rect.left, rect.top
            max_x, max_y = rect.left + rect.width, rect.top + rect.height
        else:
            # Extract corner coordinates - handles any rotation
            xs = [p.x for p in polygon]
            ys = [p.y for p in polygon]
            min_x, max_x = min(xs), max(xs)
            min_y, max_y = min(ys), max(ys)

        # Calculate QR dimensions and padding
        qr_width = max_x - min_x
        qr_height = max_y - min_y

        # Use larger dimension for padding calculation (handles rotation)
        qr_size = max(qr_width, qr_height)
        padding = max(int(qr_size * padding_percent), min_padding_px)

        # Calculate crop box with padding, clamped to image bounds
        img_width, img_height = img.size
        crop_left = max(0, min_x - padding)
        crop_top = max(0, min_y - padding)
        crop_right = min(img_width, max_x + padding)
        crop_bottom = min(img_height, max_y + padding)

        # Crop the original image (preserves original mode/quality)
        cropped = img.crop((crop_left, crop_top, crop_right, crop_bottom))

        # Convert to PNG bytes
        buf = io.BytesIO()
        # Preserve transparency if present
        if original_mode in ("RGBA", "LA", "P"):
            cropped.save(buf, format="PNG")
        else:
            cropped.save(buf, format="PNG")
        buf.seek(0)
        return buf.getvalue()

    except Exception as e:
        # Log for debugging but return None for clean API
        import sys

        print(f"QR crop error: {e}", file=sys.stderr)
        return None


def detect_and_crop_qr_file(
    filepath: str,
    padding_percent: float = QR_CROP_PADDING_PERCENT,
    min_padding_px: int = QR_CROP_MIN_PADDING_PX,
) -> bytes | None:
    """
    Detect QR code in image file and crop to it.

    Args:
        filepath: Path to image file
        padding_percent: Padding as fraction of QR size (default 10%)
        min_padding_px: Minimum padding in pixels (default 10)

    Returns:
        Cropped PNG image bytes, or None if no QR code found
    """
    with open(filepath, "rb") as f:
        return detect_and_crop_qr(f.read(), padding_percent, min_padding_px)


def has_qr_write() -> bool:
    """Check if QR code writing is available."""
    return HAS_QRCODE_WRITE


def has_qr_read() -> bool:
    """Check if QR code reading is available."""
    return HAS_QRCODE_READ


def has_qr_support() -> bool:
    """Check if full QR code support is available."""
    return HAS_QRCODE_WRITE and HAS_QRCODE_READ
