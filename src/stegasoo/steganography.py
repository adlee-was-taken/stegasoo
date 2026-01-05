"""
Stegasoo Steganography Functions (v3.2.0)

LSB and DCT embedding modes with pseudo-random pixel/coefficient selection.

Changes in v3.0:
- DCT domain embedding mode (requires scipy)
- embed_mode parameter for encode/decode
- Auto-detection of embedding mode
- Comparison utilities

Changes in v3.0.1:
- dct_output_format parameter for DCT mode ('png' or 'jpeg')
- dct_color_mode parameter for DCT mode ('grayscale' or 'color')

Changes in v3.2.0:
- Fixed HEADER_OVERHEAD constant (65 bytes, not 104 - date field removed)
- Updated ENCRYPTION_OVERHEAD calculation
"""

import io
import struct
from typing import TYPE_CHECKING, Union

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from PIL import Image

if TYPE_CHECKING:
    from .dct_steganography import DCTEmbedStats

from .constants import (
    EMBED_MODE_AUTO,
    EMBED_MODE_DCT,
    EMBED_MODE_LSB,
    VALID_EMBED_MODES,
)
from .debug import debug
from .exceptions import CapacityError, EmbeddingError
from .models import EmbedStats, FilePayload

# Lossless formats that preserve LSB data
LOSSLESS_FORMATS = {"PNG", "BMP", "TIFF"}

# Format to extension mapping
FORMAT_TO_EXT = {
    "PNG": "png",
    "BMP": "bmp",
    "TIFF": "tiff",
}

# Extension to PIL format mapping
EXT_TO_FORMAT = {
    "png": "PNG",
    "bmp": "BMP",
    "tiff": "TIFF",
    "tif": "TIFF",
}

# =============================================================================
# OVERHEAD CONSTANTS (v4.0.0 - Updated for channel key support)
# =============================================================================
# v4.0.0 Header format (with flags byte for channel key indicator):
#   Magic:   4 bytes  (\x89ST3)
#   Version: 1 byte   (5 for v4.0.0)
#   Flags:   1 byte   (bit 0 = has channel key)
#   Salt:    32 bytes
#   IV:      12 bytes
#   Tag:     16 bytes
#   -----------------
#   Total:   66 bytes
#
# v3.2.0 had 65 bytes (no flags byte)
# v3.1.0 had date field (10 bytes + 1 byte length) = 76 bytes header

HEADER_OVERHEAD = 66  # v4.0.0: Magic + version + flags + salt + iv + tag
LENGTH_PREFIX = 4  # 4 bytes for payload length in LSB embedding
ENCRYPTION_OVERHEAD = HEADER_OVERHEAD + LENGTH_PREFIX  # 70 bytes total

# DCT output format options (v3.0.1)
DCT_OUTPUT_PNG = "png"
DCT_OUTPUT_JPEG = "jpeg"

# DCT color mode options (v3.0.1)
DCT_COLOR_GRAYSCALE = "grayscale"
DCT_COLOR_COLOR = "color"


# =============================================================================
# DCT MODULE LAZY LOADING
# =============================================================================

_dct_module = None


def _get_dct_module():
    """Lazy load DCT module to avoid scipy import if not needed."""
    global _dct_module
    if _dct_module is None:
        from . import dct_steganography

        _dct_module = dct_steganography
    return _dct_module


def has_dct_support() -> bool:
    """
    Check if DCT steganography mode is available.

    Returns:
        True if scipy is installed and DCT functions work

    Example:
        >>> if has_dct_support():
        ...     result = encode(..., embed_mode='dct')
    """
    try:
        dct_mod = _get_dct_module()
        return dct_mod.has_dct_support()
    except (ImportError, ValueError):
        # ValueError: numpy binary incompatibility (e.g., jpegio built against numpy 2.x)
        return False


# =============================================================================
# FORMAT UTILITIES
# =============================================================================


def get_output_format(input_format: str | None) -> tuple[str, str]:
    """
    Determine the output format based on input format.

    Args:
        input_format: PIL format string of input image (e.g., 'JPEG', 'PNG')

    Returns:
        Tuple of (PIL format string, file extension) for output
        Falls back to PNG for lossy or unknown formats.
    """
    debug.validate(
        input_format is None or isinstance(input_format, str), "Input format must be string or None"
    )

    if input_format and input_format.upper() in LOSSLESS_FORMATS:
        fmt = input_format.upper()
        ext = FORMAT_TO_EXT.get(fmt, "png")
        debug.print(f"Using lossless format: {fmt} -> .{ext}")
        return fmt, ext

    debug.print(f"Input format {input_format} is lossy or unknown, defaulting to PNG")
    return "PNG", "png"


# =============================================================================
# CAPACITY FUNCTIONS
# =============================================================================


def will_fit(
    payload: str | bytes | FilePayload | int,
    carrier_image: bytes,
    bits_per_channel: int = 1,
    include_compression_estimate: bool = True,
) -> dict:
    """
    Check if a payload will fit in a carrier image (LSB mode).

    Args:
        payload: Message string, raw bytes, FilePayload, or size in bytes
        carrier_image: Carrier image bytes
        bits_per_channel: Bits to use per color channel (1-2)
        include_compression_estimate: Estimate compressed size

    Returns:
        Dict with fits, capacity, usage info
    """
    # Determine payload size
    if isinstance(payload, int):
        payload_size = payload
        payload_data = None
    elif isinstance(payload, str):
        payload_data = payload.encode("utf-8")
        payload_size = len(payload_data)
    elif isinstance(payload, FilePayload):
        payload_data = payload.data
        filename_overhead = len(payload.filename.encode("utf-8")) if payload.filename else 0
        mime_overhead = len(payload.mime_type.encode("utf-8")) if payload.mime_type else 0
        payload_size = len(payload.data) + filename_overhead + mime_overhead + 5
    else:
        payload_data = payload
        payload_size = len(payload)

    capacity = calculate_capacity(carrier_image, bits_per_channel)

    # Estimate encrypted size with padding
    # Padding adds 64-319 bytes, rounded up to 256-byte boundary
    # Average case: ~190 bytes padding
    estimated_padding = 190
    estimated_encrypted_size = payload_size + estimated_padding + ENCRYPTION_OVERHEAD

    compressed_estimate = None
    if include_compression_estimate and payload_data is not None and len(payload_data) >= 64:
        try:
            import zlib

            compressed = zlib.compress(payload_data, level=6)
            compressed_size = len(compressed) + 9  # Compression header
            if compressed_size < payload_size:
                compressed_estimate = compressed_size
                estimated_encrypted_size = compressed_size + estimated_padding + ENCRYPTION_OVERHEAD
        except Exception:
            pass

    headroom = capacity - estimated_encrypted_size
    fits = headroom >= 0
    usage_percent = (estimated_encrypted_size / capacity * 100) if capacity > 0 else 100.0

    return {
        "fits": fits,
        "payload_size": payload_size,
        "estimated_encrypted_size": estimated_encrypted_size,
        "capacity": capacity,
        "usage_percent": min(usage_percent, 100.0),
        "headroom": headroom,
        "compressed_estimate": compressed_estimate,
        "mode": EMBED_MODE_LSB,
    }


def calculate_capacity(image_data: bytes, bits_per_channel: int = 1) -> int:
    """
    Calculate the maximum message capacity of an image (LSB mode).

    Args:
        image_data: Image bytes
        bits_per_channel: Bits to use per color channel

    Returns:
        Maximum bytes that can be embedded (minus overhead)
    """
    debug.validate(
        bits_per_channel in (1, 2), f"bits_per_channel must be 1 or 2, got {bits_per_channel}"
    )

    img_file = Image.open(io.BytesIO(image_data))
    try:
        num_pixels = img_file.size[0] * img_file.size[1]
        bits_per_pixel = 3 * bits_per_channel
        max_bytes = (num_pixels * bits_per_pixel) // 8

        capacity = max(0, max_bytes - ENCRYPTION_OVERHEAD)
        debug.print(f"LSB capacity: {capacity} bytes at {bits_per_channel} bit(s)/channel")
        return capacity
    finally:
        img_file.close()


def calculate_capacity_by_mode(
    image_data: bytes,
    embed_mode: str = EMBED_MODE_LSB,
    bits_per_channel: int = 1,
) -> dict:
    """
    Calculate capacity for specified embedding mode.

    Args:
        image_data: Carrier image bytes
        embed_mode: 'lsb' or 'dct'
        bits_per_channel: Bits per channel for LSB mode

    Returns:
        Dict with capacity information
    """
    if embed_mode == EMBED_MODE_DCT:
        if not has_dct_support():
            raise ImportError("scipy required for DCT mode. Install: pip install scipy")

        dct_mod = _get_dct_module()
        dct_info = dct_mod.calculate_dct_capacity(image_data)

        return {
            "mode": EMBED_MODE_DCT,
            "capacity_bytes": dct_info.usable_capacity_bytes,
            "capacity_bits": dct_info.total_capacity_bits,
            "width": dct_info.width,
            "height": dct_info.height,
            "total_blocks": dct_info.total_blocks,
        }
    else:
        capacity = calculate_capacity(image_data, bits_per_channel)
        img = Image.open(io.BytesIO(image_data))
        try:
            width, height = img.size
        finally:
            img.close()

        return {
            "mode": EMBED_MODE_LSB,
            "capacity_bytes": capacity,
            "capacity_bits": capacity * 8,
            "width": width,
            "height": height,
            "bits_per_channel": bits_per_channel,
        }


def will_fit_by_mode(
    payload: str | bytes | FilePayload | int,
    carrier_image: bytes,
    embed_mode: str = EMBED_MODE_LSB,
    bits_per_channel: int = 1,
) -> dict:
    """
    Check if payload fits in specified mode.

    Args:
        payload: Message, bytes, FilePayload, or size in bytes
        carrier_image: Carrier image bytes
        embed_mode: 'lsb' or 'dct'
        bits_per_channel: For LSB mode

    Returns:
        Dict with fits, capacity, usage info
    """
    if embed_mode == EMBED_MODE_DCT:
        if not has_dct_support():
            return {"fits": False, "error": "scipy not available", "mode": EMBED_MODE_DCT}

        if isinstance(payload, int):
            payload_size = payload
        elif isinstance(payload, str):
            payload_size = len(payload.encode("utf-8"))
        elif hasattr(payload, "data"):
            payload_size = len(payload.data)
        else:
            payload_size = len(payload)

        estimated_size = payload_size + ENCRYPTION_OVERHEAD + 190  # padding estimate

        dct_mod = _get_dct_module()
        fits = dct_mod.will_fit_dct(estimated_size, carrier_image)
        capacity_info = dct_mod.calculate_dct_capacity(carrier_image)
        capacity = capacity_info.usable_capacity_bytes

        usage_percent = (estimated_size / capacity * 100) if capacity > 0 else 100.0

        return {
            "fits": fits,
            "payload_size": payload_size,
            "capacity": capacity,
            "usage_percent": min(usage_percent, 100.0),
            "headroom": capacity - estimated_size,
            "mode": EMBED_MODE_DCT,
        }
    else:
        return will_fit(payload, carrier_image, bits_per_channel)


def get_available_modes() -> dict:
    """
    Get available embedding modes and their status.

    Returns:
        Dict mapping mode name to availability info
    """
    return {
        EMBED_MODE_LSB: {
            "available": True,
            "name": "Spatial LSB",
            "description": "Embed in pixel LSBs, outputs PNG/BMP",
            "output_format": "PNG (color)",
        },
        EMBED_MODE_DCT: {
            "available": has_dct_support(),
            "name": "DCT Domain",
            "description": "Embed in DCT coefficients, outputs grayscale PNG or JPEG",
            "output_formats": ["PNG (grayscale)", "JPEG (grayscale)"],
            "requires": "scipy",
        },
    }


def compare_modes(image_data: bytes) -> dict:
    """
    Compare embedding modes for a carrier image.

    Args:
        image_data: Carrier image bytes

    Returns:
        Dict with comparison of LSB vs DCT modes
    """
    img = Image.open(io.BytesIO(image_data))
    try:
        width, height = img.size
    finally:
        img.close()

    lsb_bytes = calculate_capacity(image_data, 1)

    if has_dct_support():
        dct_mod = _get_dct_module()
        dct_info = dct_mod.calculate_dct_capacity(image_data)
        dct_bytes = dct_info.usable_capacity_bytes
        dct_available = True
    else:
        safe_blocks = (height // 8) * (width // 8)
        dct_bytes = (safe_blocks * 16) // 8  # Estimated
        dct_available = False

    return {
        "width": width,
        "height": height,
        "lsb": {
            "capacity_bytes": lsb_bytes,
            "capacity_kb": lsb_bytes / 1024,
            "available": True,
            "output": "PNG (color)",
        },
        "dct": {
            "capacity_bytes": dct_bytes,
            "capacity_kb": dct_bytes / 1024,
            "available": dct_available,
            "output": "PNG or JPEG (grayscale)",
            "ratio_vs_lsb": (dct_bytes / lsb_bytes * 100) if lsb_bytes > 0 else 0,
        },
    }


# =============================================================================
# PIXEL INDEX GENERATION
# =============================================================================


@debug.time
def generate_pixel_indices(key: bytes, num_pixels: int, num_needed: int) -> list[int]:
    """
    Generate pseudo-random pixel indices for embedding.

    Uses ChaCha20 as a CSPRNG seeded by the key to deterministically
    select which pixels will hold hidden data.
    """
    debug.validate(len(key) == 32, f"Pixel key must be 32 bytes, got {len(key)}")
    debug.validate(num_pixels > 0, f"Number of pixels must be positive, got {num_pixels}")
    debug.validate(num_needed > 0, f"Number needed must be positive, got {num_needed}")
    debug.validate(
        num_needed <= num_pixels, f"Cannot select {num_needed} pixels from {num_pixels} available"
    )

    debug.print(f"Generating {num_needed} pixel indices from {num_pixels} total pixels")

    if num_needed >= num_pixels // 2:
        debug.print(f"Using full shuffle (needed {num_needed}/{num_pixels} pixels)")
        nonce = b"\x00" * 16
        cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None, backend=default_backend())
        encryptor = cipher.encryptor()

        indices = list(range(num_pixels))
        random_bytes = encryptor.update(b"\x00" * (num_pixels * 4))

        for i in range(num_pixels - 1, 0, -1):
            j_bytes = random_bytes[(num_pixels - 1 - i) * 4 : (num_pixels - i) * 4]
            j = int.from_bytes(j_bytes, "big") % (i + 1)
            indices[i], indices[j] = indices[j], indices[i]

        selected = indices[:num_needed]
        debug.print(f"Generated {len(selected)} indices via shuffle")
        return selected

    debug.print(f"Using optimized selection (needed {num_needed}/{num_pixels} pixels)")
    selected = []
    used = set()

    nonce = b"\x00" * 16
    cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None, backend=default_backend())
    encryptor = cipher.encryptor()

    bytes_needed = (num_needed * 2) * 4
    random_bytes = encryptor.update(b"\x00" * bytes_needed)

    byte_offset = 0
    collisions = 0
    while len(selected) < num_needed and byte_offset < len(random_bytes) - 4:
        idx = int.from_bytes(random_bytes[byte_offset : byte_offset + 4], "big") % num_pixels
        byte_offset += 4

        if idx not in used:
            used.add(idx)
            selected.append(idx)
        else:
            collisions += 1

    if len(selected) < num_needed:
        debug.print(f"Need {num_needed - len(selected)} more indices, generating...")
        extra_needed = num_needed - len(selected)
        for _ in range(extra_needed * 2):
            extra_bytes = encryptor.update(b"\x00" * 4)
            idx = int.from_bytes(extra_bytes, "big") % num_pixels
            if idx not in used:
                used.add(idx)
                selected.append(idx)
                if len(selected) == num_needed:
                    break

    debug.print(f"Generated {len(selected)} indices with {collisions} collisions")
    debug.validate(
        len(selected) == num_needed,
        f"Failed to generate enough indices: {len(selected)}/{num_needed}",
    )
    return selected


# =============================================================================
# EMBEDDING FUNCTIONS
# =============================================================================


@debug.time
def embed_in_image(
    data: bytes,
    image_data: bytes,
    pixel_key: bytes,
    bits_per_channel: int = 1,
    output_format: str | None = None,
    embed_mode: str = EMBED_MODE_LSB,
    dct_output_format: str = DCT_OUTPUT_PNG,
    dct_color_mode: str = "color",
) -> tuple[bytes, Union[EmbedStats, "DCTEmbedStats"], str]:
    """
    Embed data into an image using specified mode.

    Args:
        data: Data to embed (encrypted payload)
        image_data: Carrier image bytes
        pixel_key: Key for pixel/coefficient selection
        bits_per_channel: Bits per channel (LSB mode only)
        output_format: Force output format (LSB mode only)
        embed_mode: 'lsb' (default) or 'dct'
        dct_output_format: For DCT mode - 'png' (lossless) or 'jpeg' (smaller)
        dct_color_mode: For DCT mode - 'grayscale' (default) or 'color' (preserves colors)

    Returns:
        Tuple of (stego image bytes, stats, file extension)

    Raises:
        CapacityError: If data won't fit
        EmbeddingError: If embedding fails
        ImportError: If DCT mode requested but scipy unavailable
    """
    debug.print(f"embed_in_image: mode={embed_mode}, data={len(data)} bytes")
    debug.validate(
        embed_mode in VALID_EMBED_MODES, f"Invalid embed_mode: {embed_mode}. Use 'lsb' or 'dct'"
    )

    # DCT MODE
    if embed_mode == EMBED_MODE_DCT:
        if not has_dct_support():
            raise ImportError(
                "scipy is required for DCT embedding mode. " "Install with: pip install scipy"
            )

        # Validate DCT output format
        if dct_output_format not in (DCT_OUTPUT_PNG, DCT_OUTPUT_JPEG):
            debug.print(f"Invalid dct_output_format '{dct_output_format}', defaulting to PNG")
            dct_output_format = DCT_OUTPUT_PNG

        # Validate DCT color mode (v3.0.1)
        if dct_color_mode not in ("grayscale", "color"):
            debug.print(f"Invalid dct_color_mode '{dct_color_mode}', defaulting to color")
            dct_color_mode = "color"

        dct_mod = _get_dct_module()

        # Pass output_format and color_mode to DCT module (v3.0.1)
        stego_bytes, dct_stats = dct_mod.embed_in_dct(
            data,
            image_data,
            pixel_key,
            output_format=dct_output_format,
            color_mode=dct_color_mode,
        )

        # Determine extension based on output format
        if dct_output_format == DCT_OUTPUT_JPEG:
            ext = "jpg"
        else:
            ext = "png"

        debug.print(
            f"DCT embedding complete: {dct_output_format.upper()} output, "
            f"color_mode={dct_color_mode}, ext={ext}"
        )
        return stego_bytes, dct_stats, ext

    # LSB MODE
    return _embed_lsb(data, image_data, pixel_key, bits_per_channel, output_format)


def _embed_lsb(
    data: bytes,
    image_data: bytes,
    pixel_key: bytes,
    bits_per_channel: int = 1,
    output_format: str | None = None,
) -> tuple[bytes, EmbedStats, str]:
    """
    Embed data using LSB steganography (internal implementation).
    """
    debug.print(f"LSB embedding {len(data)} bytes into image")
    debug.data(pixel_key, "Pixel key for embedding")
    debug.validate(
        bits_per_channel in (1, 2), f"bits_per_channel must be 1 or 2, got {bits_per_channel}"
    )
    debug.validate(len(pixel_key) == 32, f"Pixel key must be 32 bytes, got {len(pixel_key)}")

    img_file = None
    img = None
    stego_img = None

    try:
        img_file = Image.open(io.BytesIO(image_data))
        input_format = img_file.format

        debug.print(f"Carrier image: {img_file.size[0]}x{img_file.size[1]}, format: {input_format}")

        img = img_file.convert("RGB") if img_file.mode != "RGB" else img_file.copy()
        if img_file.mode != "RGB":
            debug.print(f"Converting image from {img_file.mode} to RGB")

        pixels = list(img.getdata())
        num_pixels = len(pixels)

        bits_per_pixel = 3 * bits_per_channel
        max_bytes = (num_pixels * bits_per_pixel) // 8

        debug.print(f"Image capacity: {max_bytes} bytes at {bits_per_channel} bit(s)/channel")

        data_with_len = struct.pack(">I", len(data)) + data

        if len(data_with_len) > max_bytes:
            debug.print(f"Capacity error: need {len(data_with_len)}, have {max_bytes}")
            raise CapacityError(len(data_with_len), max_bytes)

        debug.print(
            f"Total data to embed: {len(data_with_len)} bytes "
            f"({len(data_with_len)/max_bytes*100:.1f}% of capacity)"
        )

        binary_data = "".join(format(b, "08b") for b in data_with_len)
        pixels_needed = (len(binary_data) + bits_per_pixel - 1) // bits_per_pixel

        debug.print(f"Need {pixels_needed} pixels to embed {len(binary_data)} bits")

        selected_indices = generate_pixel_indices(pixel_key, num_pixels, pixels_needed)

        new_pixels = list(pixels)
        clear_mask = 0xFF ^ ((1 << bits_per_channel) - 1)

        bit_idx = 0
        modified_pixels = 0

        for pixel_idx in selected_indices:
            if bit_idx >= len(binary_data):
                break

            r, g, b = new_pixels[pixel_idx]
            modified = False

            for channel_idx, channel_val in enumerate([r, g, b]):
                if bit_idx >= len(binary_data):
                    break
                bits = binary_data[bit_idx : bit_idx + bits_per_channel].ljust(
                    bits_per_channel, "0"
                )
                new_val = (channel_val & clear_mask) | int(bits, 2)

                if channel_val != new_val:
                    modified = True
                    if channel_idx == 0:
                        r = new_val
                    elif channel_idx == 1:
                        g = new_val
                    else:
                        b = new_val

                bit_idx += bits_per_channel

            if modified:
                new_pixels[pixel_idx] = (r, g, b)
                modified_pixels += 1

        debug.print(f"Modified {modified_pixels} pixels (out of {len(selected_indices)} selected)")

        stego_img = Image.new("RGB", img.size)
        stego_img.putdata(new_pixels)

        if output_format:
            out_fmt = output_format.upper()
            out_ext = FORMAT_TO_EXT.get(out_fmt, "png")
            debug.print(f"Using forced output format: {out_fmt}")
        else:
            out_fmt, out_ext = get_output_format(input_format)
            debug.print(f"Auto-selected output format: {out_fmt}")

        output = io.BytesIO()
        stego_img.save(output, out_fmt)
        output.seek(0)

        stats = EmbedStats(
            pixels_modified=modified_pixels,
            total_pixels=num_pixels,
            capacity_used=len(data_with_len) / max_bytes,
            bytes_embedded=len(data_with_len),
        )

        debug.print(f"LSB embedding complete: {out_fmt} image, {len(output.getvalue())} bytes")
        return output.getvalue(), stats, out_ext

    except CapacityError:
        raise
    except Exception as e:
        debug.exception(e, "embed_lsb")
        raise EmbeddingError(f"Failed to embed data: {e}") from e
    finally:
        # Properly close all PIL Images to prevent memory leaks
        if stego_img is not None:
            stego_img.close()
        if img is not None and img is not img_file:
            img.close()
        if img_file is not None:
            img_file.close()


# =============================================================================
# EXTRACTION FUNCTIONS
# =============================================================================


@debug.time
def extract_from_image(
    image_data: bytes,
    pixel_key: bytes,
    bits_per_channel: int = 1,
    embed_mode: str = EMBED_MODE_AUTO,
) -> bytes | None:
    """
    Extract hidden data from a stego image.

    Args:
        image_data: Stego image bytes
        pixel_key: Key for pixel/coefficient selection (must match encoding)
        bits_per_channel: Bits per channel (LSB mode only)
        embed_mode: 'auto' (try both), 'lsb', or 'dct'

    Returns:
        Extracted data bytes, or None if extraction fails
    """
    debug.print(f"extract_from_image: mode={embed_mode}")

    # AUTO MODE: Try LSB first, then DCT
    if embed_mode == EMBED_MODE_AUTO:
        result = _extract_lsb(image_data, pixel_key, bits_per_channel)
        if result is not None:
            debug.print("Auto-detect: LSB extraction succeeded")
            return result

        if has_dct_support():
            debug.print("Auto-detect: LSB failed, trying DCT")
            result = _extract_dct(image_data, pixel_key)
            if result is not None:
                debug.print("Auto-detect: DCT extraction succeeded")
                return result

        debug.print("Auto-detect: All modes failed")
        return None

    # EXPLICIT DCT MODE
    elif embed_mode == EMBED_MODE_DCT:
        if not has_dct_support():
            raise ImportError("scipy required for DCT mode")
        return _extract_dct(image_data, pixel_key)

    # EXPLICIT LSB MODE
    else:
        return _extract_lsb(image_data, pixel_key, bits_per_channel)


def _extract_dct(image_data: bytes, pixel_key: bytes) -> bytes | None:
    """Extract using DCT mode."""
    try:
        dct_mod = _get_dct_module()
        return dct_mod.extract_from_dct(image_data, pixel_key)
    except Exception as e:
        debug.print(f"DCT extraction failed: {e}")
        return None


def _extract_lsb(image_data: bytes, pixel_key: bytes, bits_per_channel: int = 1) -> bytes | None:
    """
    Extract using LSB mode (internal implementation).
    """
    debug.print(f"LSB extracting from {len(image_data)} byte image")
    debug.data(pixel_key, "Pixel key for extraction")
    debug.validate(
        bits_per_channel in (1, 2), f"bits_per_channel must be 1 or 2, got {bits_per_channel}"
    )

    img_file = None
    img = None

    try:
        img_file = Image.open(io.BytesIO(image_data))
        debug.print(f"Image: {img_file.size[0]}x{img_file.size[1]}, format: {img_file.format}")

        img = img_file.convert("RGB") if img_file.mode != "RGB" else img_file.copy()
        if img_file.mode != "RGB":
            debug.print(f"Converting image from {img_file.mode} to RGB")

        pixels = list(img.getdata())
        num_pixels = len(pixels)
        bits_per_pixel = 3 * bits_per_channel

        debug.print(f"Image has {num_pixels} pixels, {bits_per_pixel} bits/pixel")

        initial_pixels = (32 + bits_per_pixel - 1) // bits_per_pixel + 10
        debug.print(f"Extracting initial {initial_pixels} pixels to find length")

        initial_indices = generate_pixel_indices(pixel_key, num_pixels, initial_pixels)

        binary_data = ""
        for pixel_idx in initial_indices:
            r, g, b = pixels[pixel_idx]
            for channel in [r, g, b]:
                for bit_pos in range(bits_per_channel - 1, -1, -1):
                    binary_data += str((channel >> bit_pos) & 1)

        try:
            length_bits = binary_data[:32]
            if len(length_bits) < 32:
                debug.print(f"Not enough bits for length: {len(length_bits)}/32")
                return None

            data_length = struct.unpack(">I", int(length_bits, 2).to_bytes(4, "big"))[0]
            debug.print(f"Extracted length: {data_length} bytes")
        except Exception as e:
            debug.print(f"Failed to parse length: {e}")
            return None

        max_possible = (num_pixels * bits_per_pixel) // 8 - 4
        if data_length > max_possible or data_length < 10:
            debug.print(f"Invalid data length: {data_length} (max possible: {max_possible})")
            return None

        total_bits = (4 + data_length) * 8
        pixels_needed = (total_bits + bits_per_pixel - 1) // bits_per_pixel

        debug.print(f"Need {pixels_needed} pixels to extract {data_length} bytes")

        selected_indices = generate_pixel_indices(pixel_key, num_pixels, pixels_needed)

        binary_data = ""
        for pixel_idx in selected_indices:
            r, g, b = pixels[pixel_idx]
            for channel in [r, g, b]:
                for bit_pos in range(bits_per_channel - 1, -1, -1):
                    binary_data += str((channel >> bit_pos) & 1)

        data_bits = binary_data[32 : 32 + (data_length * 8)]

        if len(data_bits) < data_length * 8:
            debug.print(f"Insufficient bits: {len(data_bits)} < {data_length * 8}")
            return None

        data_bytes = bytearray()
        for i in range(0, len(data_bits), 8):
            byte_bits = data_bits[i : i + 8]
            if len(byte_bits) == 8:
                data_bytes.append(int(byte_bits, 2))

        debug.print(f"LSB successfully extracted {len(data_bytes)} bytes")
        return bytes(data_bytes)

    except Exception as e:
        debug.exception(e, "extract_lsb")
        return None
    finally:
        # Properly close all PIL Images to prevent memory leaks
        if img is not None and img is not img_file:
            img.close()
        if img_file is not None:
            img_file.close()


# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================


def get_image_dimensions(image_data: bytes) -> tuple[int, int]:
    """Get image dimensions without loading full image."""
    debug.validate(len(image_data) > 0, "Image data cannot be empty")
    img = Image.open(io.BytesIO(image_data))
    try:
        dimensions = img.size
        debug.print(f"Image dimensions: {dimensions[0]}x{dimensions[1]}")
        return dimensions
    finally:
        img.close()


def get_image_format(image_data: bytes) -> str | None:
    """Get image format (PIL format string like 'PNG', 'JPEG')."""
    try:
        img = Image.open(io.BytesIO(image_data))
        try:
            format_str = img.format
            debug.print(f"Image format: {format_str}")
            return format_str
        finally:
            img.close()
    except Exception as e:
        debug.print(f"Failed to get image format: {e}")
        return None


def is_lossless_format(image_data: bytes) -> bool:
    """Check if image is in a lossless format suitable for steganography."""
    fmt = get_image_format(image_data)
    is_lossless = fmt is not None and fmt.upper() in LOSSLESS_FORMATS
    debug.print(f"Image is lossless: {is_lossless} (format: {fmt})")
    return is_lossless


def peek_image(image_data: bytes) -> dict:
    """
    Check if an image contains Stegasoo hidden data without decrypting.

    Attempts to detect LSB and DCT headers by extracting the first few bytes
    and looking for Stegasoo magic markers.

    Args:
        image_data: Raw image bytes

    Returns:
        dict with:
            - has_stegasoo: bool - True if header detected
            - mode: str or None - 'lsb', 'dct', or None
            - confidence: str - 'high', 'low', or None

    Example:
        >>> result = peek_image(suspicious_image_bytes)
        >>> if result['has_stegasoo']:
        ...     print(f"Found {result['mode']} data!")
    """
    from .constants import EMBED_MODE_DCT, EMBED_MODE_LSB

    result = {"has_stegasoo": False, "mode": None, "confidence": None}

    # Try LSB extraction (look for header bytes)
    try:
        img = Image.open(io.BytesIO(image_data))
        pixels = list(img.getdata())
        img.close()

        # Extract first 32 bits (4 bytes) from LSB
        extracted = []
        for i in range(32):
            if i < len(pixels):
                pixel = pixels[i]
                if isinstance(pixel, tuple):
                    extracted.append(pixel[0] & 1)
                else:
                    extracted.append(pixel & 1)

        # Convert bits to bytes
        header_bytes = bytearray()
        for i in range(0, len(extracted), 8):
            byte = 0
            for j in range(8):
                if i + j < len(extracted):
                    byte = (byte << 1) | extracted[i + j]
            header_bytes.append(byte)

        # Check for LSB magic: \x89ST3
        if bytes(header_bytes[:4]) == b"\x89ST3":
            result["has_stegasoo"] = True
            result["mode"] = EMBED_MODE_LSB
            result["confidence"] = "high"
            return result
    except Exception:
        pass

    # Try DCT extraction (requires scipy/jpegio)
    try:
        from .dct_steganography import HAS_JPEGIO, HAS_SCIPY

        if HAS_SCIPY or HAS_JPEGIO:
            from .dct_steganography import extract_from_dct

            # Extract first few bytes to check header
            extracted = extract_from_dct(image_data, seed=b"\x00" * 32, length=4)
            if extracted == b"\x89DCT":
                result["has_stegasoo"] = True
                result["mode"] = EMBED_MODE_DCT
                result["confidence"] = "high"
                return result
    except Exception:
        pass

    return result
