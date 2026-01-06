"""
DCT Domain Steganography Module (v4.1.0)

Embeds data in DCT coefficients with two approaches:
1. PNG output: Scipy-based DCT transform (grayscale or color)
2. JPEG output: jpegio-based coefficient manipulation (if available)

v4.1.0 Changes:
- Reed-Solomon error correction protects against bit errors in problematic blocks
- Majority voting on length headers (3 copies) for additional robustness
- RS can correct up to 16 byte errors per 223-byte chunk

v3.2.0-patch2 Changes:
- Chunked processing for large images to avoid heap corruption
- Process image in vertical strips to limit memory per operation
- Isolated DCT operations with fresh array allocations
- Workaround for scipy.fftpack memory issues

Requires: scipy (for PNG mode), optionally jpegio (for JPEG mode), reedsolo (for error correction)
"""

import gc
import hashlib
import io
import struct
from dataclasses import dataclass
from enum import Enum

import numpy as np
from PIL import Image

# Check for scipy availability (for PNG/DCT mode)
# Prefer scipy.fft (newer, more stable) over scipy.fftpack
try:
    from scipy.fft import dct, idct

    HAS_SCIPY = True
except ImportError:
    try:
        from scipy.fftpack import dct, idct

        HAS_SCIPY = True
    except ImportError:
        HAS_SCIPY = False
        dct = None
        idct = None

# Check for jpegio availability (for proper JPEG mode)
try:
    import jpegio as jio

    HAS_JPEGIO = True
except ImportError:
    HAS_JPEGIO = False
    jio = None

# Import custom exceptions
from .exceptions import InvalidMagicBytesError
from .exceptions import ReedSolomonError as StegasooRSError

# Progress reporting interval (write every N blocks)
PROGRESS_INTERVAL = 50


def _write_progress(progress_file: str | None, current: int, total: int, phase: str = "embedding"):
    """Write progress to file for frontend polling."""
    if progress_file is None:
        return
    try:
        import json

        with open(progress_file, "w") as f:
            json.dump(
                {
                    "current": current,
                    "total": total,
                    "percent": round((current / total) * 100, 1) if total > 0 else 0,
                    "phase": phase,
                },
                f,
            )
    except Exception:
        pass  # Don't let progress writing break encoding


# ============================================================================
# CONSTANTS
# ============================================================================

BLOCK_SIZE = 8
EMBED_POSITIONS = [
    (0, 1),
    (1, 0),
    (2, 0),
    (1, 1),
    (0, 2),
    (0, 3),
    (1, 2),
    (2, 1),
    (3, 0),
    (4, 0),
    (3, 1),
    (2, 2),
    (1, 3),
    (0, 4),
    (0, 5),
    (1, 4),
    (2, 3),
    (3, 2),
    (4, 1),
    (5, 0),
    (5, 1),
    (4, 2),
    (3, 3),
    (2, 4),
    (1, 5),
    (0, 6),
    (0, 7),
    (1, 6),
    (2, 5),
    (3, 4),
    (4, 3),
    (5, 2),
    (6, 1),
    (7, 0),
]
DEFAULT_EMBED_POSITIONS = EMBED_POSITIONS[4:20]
QUANT_STEP = 25
DCT_MAGIC = b"DCTS"
HEADER_SIZE = 10
OUTPUT_FORMAT_PNG = "png"
OUTPUT_FORMAT_JPEG = "jpeg"
JPEG_OUTPUT_QUALITY = 95
JPEGIO_MAGIC = b"JPGS"
JPEGIO_MIN_COEF_MAGNITUDE = 2
JPEGIO_EMBED_CHANNEL = 0
FLAG_COLOR_MODE = 0x01
FLAG_RS_PROTECTED = 0x02  # Reed-Solomon error correction enabled

# Reed-Solomon settings - 32 symbols can correct up to 16 byte errors per 223-byte chunk
RS_NSYM = 32
RS_LENGTH_HEADER_SIZE = 8  # 8 bytes: 4 for raw_payload_length + 4 for rs_payload_length
RS_LENGTH_COPIES = 3  # Store length header 3 times for majority voting
RS_LENGTH_PREFIX_SIZE = RS_LENGTH_HEADER_SIZE * RS_LENGTH_COPIES  # Total: 24 bytes

# Chunking settings for large images
MAX_CHUNK_HEIGHT = 512  # Process in 512-pixel tall strips

# JPEG normalization settings
# JPEGs with quality=100 have all quantization values = 1, which crashes jpegio
JPEGIO_NORMALIZE_QUALITY = 95  # Re-save quality for problematic JPEGs
JPEGIO_MAX_QUANT_VALUE_THRESHOLD = 1  # If all quant values <= this, normalize


# ============================================================================
# DATA CLASSES
# ============================================================================


class DCTOutputFormat(Enum):
    PNG = "png"
    JPEG = "jpeg"


@dataclass
class DCTEmbedStats:
    blocks_used: int
    blocks_available: int
    bits_embedded: int
    capacity_bits: int
    usage_percent: float
    image_width: int
    image_height: int
    output_format: str
    jpeg_native: bool = False
    color_mode: str = "grayscale"


@dataclass
class DCTCapacityInfo:
    width: int
    height: int
    blocks_x: int
    blocks_y: int
    total_blocks: int
    bits_per_block: int
    total_capacity_bits: int
    total_capacity_bytes: int
    usable_capacity_bytes: int


# ============================================================================
# AVAILABILITY CHECKS
# ============================================================================


def _check_scipy():
    if not HAS_SCIPY:
        raise ImportError("DCT steganography requires scipy. Install with: pip install scipy")


def has_dct_support() -> bool:
    return HAS_SCIPY


def has_jpegio_support() -> bool:
    return HAS_JPEGIO


# ============================================================================
# REED-SOLOMON ERROR CORRECTION
# Protects against bit errors in problematic image blocks
# ============================================================================

# Check for reedsolo availability
try:
    from reedsolo import ReedSolomonError, RSCodec

    HAS_REEDSOLO = True
except ImportError:
    HAS_REEDSOLO = False
    RSCodec = None
    ReedSolomonError = None


def _rs_encode(data: bytes) -> bytes:
    """Add Reed-Solomon error correction symbols to data."""
    if not HAS_REEDSOLO:
        return data  # No protection if reedsolo not available
    rs = RSCodec(RS_NSYM)
    return bytes(rs.encode(data))


def _rs_decode(data: bytes) -> bytes:
    """Decode Reed-Solomon protected data, correcting errors if possible."""
    if not HAS_REEDSOLO:
        return data  # No decoding if reedsolo not available
    rs = RSCodec(RS_NSYM)
    try:
        decoded, _, errata_pos = rs.decode(data)
        if errata_pos:
            pass  # Errors were corrected
        return bytes(decoded)
    except ReedSolomonError as e:
        raise StegasooRSError(f"Image corrupted beyond repair: {e}") from e


# ============================================================================
# SAFE DCT FUNCTIONS
# These create fresh arrays to avoid scipy memory corruption issues
# ============================================================================


def _safe_dct2(block: np.ndarray) -> np.ndarray:
    """
    Apply 2D DCT with memory isolation.
    Creates a completely fresh array to avoid heap corruption.
    """
    # Create a brand new array (not a view)
    safe_block = np.array(block, dtype=np.float64, copy=True, order="C")

    # First DCT on columns (transpose -> DCT rows -> transpose back)
    temp = np.zeros_like(safe_block, dtype=np.float64, order="C")
    for i in range(BLOCK_SIZE):
        col = np.array(safe_block[:, i], dtype=np.float64, copy=True)
        temp[:, i] = dct(col, norm="ortho")

    # Second DCT on rows
    result = np.zeros_like(temp, dtype=np.float64, order="C")
    for i in range(BLOCK_SIZE):
        row = np.array(temp[i, :], dtype=np.float64, copy=True)
        result[i, :] = dct(row, norm="ortho")

    return result


def _safe_idct2(block: np.ndarray) -> np.ndarray:
    """
    Apply 2D inverse DCT with memory isolation.
    Creates a completely fresh array to avoid heap corruption.
    """
    # Create a brand new array (not a view)
    safe_block = np.array(block, dtype=np.float64, copy=True, order="C")

    # First IDCT on rows
    temp = np.zeros_like(safe_block, dtype=np.float64, order="C")
    for i in range(BLOCK_SIZE):
        row = np.array(safe_block[i, :], dtype=np.float64, copy=True)
        temp[i, :] = idct(row, norm="ortho")

    # Second IDCT on columns
    result = np.zeros_like(temp, dtype=np.float64, order="C")
    for i in range(BLOCK_SIZE):
        col = np.array(temp[:, i], dtype=np.float64, copy=True)
        result[:, i] = idct(col, norm="ortho")

    return result


# ============================================================================
# IMAGE PROCESSING HELPERS
# ============================================================================


def _to_grayscale(image_data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_data))
    gray = img.convert("L")
    return np.array(gray, dtype=np.float64, copy=True, order="C")


def _extract_y_channel(image_data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_data))
    if img.mode != "RGB":
        img = img.convert("RGB")

    rgb = np.array(img, dtype=np.float64, copy=True, order="C")
    Y = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    return np.array(Y, dtype=np.float64, copy=True, order="C")


def _pad_to_blocks(image: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
    h, w = image.shape
    new_h = ((h + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
    new_w = ((w + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE

    if new_h == h and new_w == w:
        return np.array(image, dtype=np.float64, copy=True, order="C"), (h, w)

    padded = np.zeros((new_h, new_w), dtype=np.float64, order="C")
    padded[:h, :w] = image

    # Simple edge replication for padding
    if new_h > h:
        for i in range(h, new_h):
            padded[i, :w] = padded[h - 1, :w]
    if new_w > w:
        for j in range(w, new_w):
            padded[:h, j] = padded[:h, w - 1]
    if new_h > h and new_w > w:
        padded[h:, w:] = padded[h - 1, w - 1]

    return padded, (h, w)


def _unpad_image(image: np.ndarray, original_size: tuple[int, int]) -> np.ndarray:
    h, w = original_size
    return np.array(image[:h, :w], dtype=np.float64, copy=True, order="C")


def _embed_bit_in_coeff(coef: float, bit: int, quant_step: int = QUANT_STEP) -> float:
    quantized = round(coef / quant_step)
    if (quantized % 2) != bit:
        if quantized % 2 == 0 and bit == 1:
            quantized += 1 if coef >= quantized * quant_step else -1
        elif quantized % 2 == 1 and bit == 0:
            quantized += 1 if coef >= quantized * quant_step else -1
    return float(quantized * quant_step)


def _extract_bit_from_coeff(coef: float, quant_step: int = QUANT_STEP) -> int:
    quantized = round(coef / quant_step)
    return int(quantized % 2)


def _generate_block_order(num_blocks: int, seed: bytes) -> list:
    hash_bytes = hashlib.sha256(seed).digest()
    rng = np.random.RandomState(int.from_bytes(hash_bytes[:4], "big"))
    order = list(range(num_blocks))
    rng.shuffle(order)
    return order


def _save_stego_image(image: np.ndarray, output_format: str = OUTPUT_FORMAT_PNG) -> bytes:
    clipped = np.clip(image, 0, 255).astype(np.uint8)
    img = Image.fromarray(clipped, mode="L")
    buffer = io.BytesIO()
    if output_format == OUTPUT_FORMAT_JPEG:
        img.save(buffer, format="JPEG", quality=JPEG_OUTPUT_QUALITY, subsampling=0, optimize=True)
    else:
        img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _save_color_image(rgb_array: np.ndarray, output_format: str = OUTPUT_FORMAT_PNG) -> bytes:
    clipped = np.clip(rgb_array, 0, 255).astype(np.uint8)
    img = Image.fromarray(clipped, mode="RGB")
    buffer = io.BytesIO()
    if output_format == OUTPUT_FORMAT_JPEG:
        img.save(buffer, format="JPEG", quality=JPEG_OUTPUT_QUALITY, subsampling=0, optimize=True)
    else:
        img.save(buffer, format="PNG", optimize=True)
    return buffer.getvalue()


def _rgb_to_ycbcr(rgb: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    R = rgb[:, :, 0].astype(np.float64)
    G = rgb[:, :, 1].astype(np.float64)
    B = rgb[:, :, 2].astype(np.float64)

    Y = np.array(0.299 * R + 0.587 * G + 0.114 * B, dtype=np.float64, copy=True, order="C")
    Cb = np.array(
        128 - 0.168736 * R - 0.331264 * G + 0.5 * B, dtype=np.float64, copy=True, order="C"
    )
    Cr = np.array(
        128 + 0.5 * R - 0.418688 * G - 0.081312 * B, dtype=np.float64, copy=True, order="C"
    )

    return Y, Cb, Cr


def _ycbcr_to_rgb(Y: np.ndarray, Cb: np.ndarray, Cr: np.ndarray) -> np.ndarray:
    R = Y + 1.402 * (Cr - 128)
    G = Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128)
    B = Y + 1.772 * (Cb - 128)

    rgb = np.zeros((Y.shape[0], Y.shape[1], 3), dtype=np.float64, order="C")
    rgb[:, :, 0] = R
    rgb[:, :, 1] = G
    rgb[:, :, 2] = B
    return rgb


def _create_header(data_length: int, flags: int = 0) -> bytes:
    return struct.pack(">4sBBI", DCT_MAGIC, 1, flags, data_length)


def _parse_header(header_bits: list) -> tuple[int, int, int]:
    if len(header_bits) < HEADER_SIZE * 8:
        raise ValueError("Insufficient header data")

    header_bytes = bytes(
        [
            sum(header_bits[i * 8 : (i + 1) * 8][j] << (7 - j) for j in range(8))
            for i in range(HEADER_SIZE)
        ]
    )

    magic, version, flags, length = struct.unpack(">4sBBI", header_bytes)

    if magic != DCT_MAGIC:
        raise InvalidMagicBytesError("Not a Stegasoo image or wrong mode (try LSB instead of DCT)")

    return version, flags, length


# ============================================================================
# JPEGIO HELPERS
# ============================================================================


def _jpegio_bytes_to_file(data: bytes, suffix: str = ".jpg") -> str:
    import os
    import tempfile

    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return path


def _jpegio_get_usable_positions(coef_array: np.ndarray) -> list:
    positions = []
    h, w = coef_array.shape
    for row in range(h):
        for col in range(w):
            if (row % BLOCK_SIZE == 0) and (col % BLOCK_SIZE == 0):
                continue
            if abs(coef_array[row, col]) >= JPEGIO_MIN_COEF_MAGNITUDE:
                positions.append((row, col))
    return positions


def _jpegio_generate_order(num_positions: int, seed: bytes) -> list:
    hash_bytes = hashlib.sha256(seed + b"jpeg_coef_order").digest()
    rng = np.random.RandomState(int.from_bytes(hash_bytes[:4], "big"))
    order = list(range(num_positions))
    rng.shuffle(order)
    return order


def _jpegio_create_header(data_length: int, flags: int = 0) -> bytes:
    return struct.pack(">4sBBI", JPEGIO_MAGIC, 1, flags, data_length)


def _jpegio_parse_header(header_bytes: bytes) -> tuple[int, int, int]:
    if len(header_bytes) < HEADER_SIZE:
        raise ValueError("Insufficient header data")
    magic, version, flags, length = struct.unpack(">4sBBI", header_bytes[:HEADER_SIZE])
    if magic != JPEGIO_MAGIC:
        raise InvalidMagicBytesError("Not a Stegasoo JPEG or wrong mode")
    return version, flags, length


# ============================================================================
# PUBLIC API
# ============================================================================


def calculate_dct_capacity(image_data: bytes) -> DCTCapacityInfo:
    """Calculate DCT embedding capacity of an image."""
    _check_scipy()

    # Just get dimensions, don't process anything
    img = Image.open(io.BytesIO(image_data))
    width, height = img.size
    img.close()  # Explicitly close

    blocks_x = width // BLOCK_SIZE
    blocks_y = height // BLOCK_SIZE
    total_blocks = blocks_x * blocks_y

    bits_per_block = len(DEFAULT_EMBED_POSITIONS)
    total_bits = total_blocks * bits_per_block
    total_bytes = total_bits // 8
    # Account for header and RS overhead
    # RS format: [24-byte length prefix (3 copies)] + RS(header + data)
    # RS adds RS_NSYM bytes per 223-byte chunk (255 - RS_NSYM = 223)
    # Conservatively estimate RS overhead as ~15% + one chunk minimum
    if HAS_REEDSOLO:
        # Overhead = 24 (prefix) + 10 (header) + RS overhead
        # Simplify: base overhead = 24 + 10 + 32 + 15% margin for larger data
        overhead = RS_LENGTH_PREFIX_SIZE + HEADER_SIZE + RS_NSYM + 20
    else:
        overhead = HEADER_SIZE
    usable_bytes = max(0, total_bytes - overhead)

    return DCTCapacityInfo(
        width=width,
        height=height,
        blocks_x=blocks_x,
        blocks_y=blocks_y,
        total_blocks=total_blocks,
        bits_per_block=bits_per_block,
        total_capacity_bits=total_bits,
        total_capacity_bytes=total_bytes,
        usable_capacity_bytes=usable_bytes,
    )


def will_fit_dct(data_length: int, image_data: bytes) -> bool:
    capacity = calculate_dct_capacity(image_data)
    return data_length <= capacity.usable_capacity_bytes


def estimate_capacity_comparison(image_data: bytes) -> dict:
    """Compare LSB and DCT capacity (no actual DCT operations)."""
    img = Image.open(io.BytesIO(image_data))
    width, height = img.size
    img.close()

    pixels = width * height
    lsb_bytes = (pixels * 3) // 8

    blocks = (width // 8) * (height // 8)
    dct_bytes = (blocks * 16) // 8 - HEADER_SIZE

    return {
        "width": width,
        "height": height,
        "lsb": {
            "capacity_bytes": lsb_bytes,
            "capacity_kb": lsb_bytes / 1024,
            "output": "PNG/BMP (color)",
        },
        "dct": {
            "capacity_bytes": dct_bytes,
            "capacity_kb": dct_bytes / 1024,
            "output": "PNG or JPEG (grayscale)",
            "ratio_vs_lsb": (dct_bytes / lsb_bytes * 100) if lsb_bytes > 0 else 0,
            "available": HAS_SCIPY,
        },
        "jpeg_native": {
            "available": HAS_JPEGIO,
            "note": "Uses jpegio for proper JPEG coefficient embedding",
        },
    }


def embed_in_dct(
    data: bytes,
    carrier_image: bytes,
    seed: bytes,
    output_format: str = OUTPUT_FORMAT_PNG,
    color_mode: str = "color",
    progress_file: str | None = None,
) -> tuple[bytes, DCTEmbedStats]:
    """Embed data using DCT coefficient modification."""
    if output_format not in (OUTPUT_FORMAT_PNG, OUTPUT_FORMAT_JPEG):
        raise ValueError(f"Invalid output format: {output_format}")

    if color_mode not in ("color", "grayscale"):
        color_mode = "color"

    if output_format == OUTPUT_FORMAT_JPEG and HAS_JPEGIO:
        return _embed_jpegio(data, carrier_image, seed, color_mode, progress_file)

    _check_scipy()
    return _embed_scipy_dct_safe(
        data, carrier_image, seed, output_format, color_mode, progress_file
    )


def _embed_scipy_dct_safe(
    data: bytes,
    carrier_image: bytes,
    seed: bytes,
    output_format: str,
    color_mode: str = "color",
    progress_file: str | None = None,
) -> tuple[bytes, DCTEmbedStats]:
    """
    Embed using scipy DCT with safe memory handling.

    Uses row-by-row 1D DCT operations instead of 2D arrays to avoid
    scipy memory corruption issues with large images.
    """
    capacity_info = calculate_dct_capacity(carrier_image)

    if len(data) > capacity_info.usable_capacity_bytes:
        raise ValueError(
            f"Data too large ({len(data)} bytes) for carrier "
            f"(capacity: {capacity_info.usable_capacity_bytes} bytes)"
        )

    # Load image
    img = Image.open(io.BytesIO(carrier_image))
    width, height = img.size

    flags = FLAG_COLOR_MODE if color_mode == "color" else 0

    # Build raw payload (header + data)
    header = _create_header(len(data), flags)
    raw_payload = header + data

    # Apply Reed-Solomon error correction to entire payload if available
    if HAS_REEDSOLO:
        rs_payload = _rs_encode(raw_payload)
        # Format: [length_header x 3 for majority voting] + [RS-encoded payload]
        # Each length_header is 8 bytes: 4 for raw_payload_length + 4 for rs_payload_length
        length_header = struct.pack(">II", len(raw_payload), len(rs_payload))
        length_prefix = length_header * RS_LENGTH_COPIES  # Repeat 3 times
        payload = length_prefix + rs_payload
    else:
        payload = raw_payload
    bits = []
    for byte in payload:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)

    # Generate block order
    num_blocks = capacity_info.total_blocks
    block_order = _generate_block_order(num_blocks, seed)
    blocks_x = width // BLOCK_SIZE

    if color_mode == "color" and img.mode in ("RGB", "RGBA"):
        if img.mode == "RGBA":
            img = img.convert("RGB")

        # Process color image
        rgb = np.array(img, dtype=np.float64, copy=True, order="C")
        img.close()

        Y, Cb, Cr = _rgb_to_ycbcr(rgb)
        del rgb
        gc.collect()

        Y_padded, original_size = _pad_to_blocks(Y)
        del Y
        gc.collect()

        # Embed in Y channel
        Y_embedded = _embed_in_channel_safe(Y_padded, bits, block_order, blocks_x, progress_file)
        del Y_padded
        gc.collect()

        Y_result = _unpad_image(Y_embedded, original_size)
        del Y_embedded
        gc.collect()

        result_rgb = _ycbcr_to_rgb(Y_result, Cb, Cr)
        del Y_result, Cb, Cr
        gc.collect()

        stego_bytes = _save_color_image(result_rgb, output_format)
        del result_rgb
        gc.collect()
    else:
        # Grayscale mode
        image = _to_grayscale(carrier_image)
        img.close()

        padded, original_size = _pad_to_blocks(image)
        del image
        gc.collect()

        embedded = _embed_in_channel_safe(padded, bits, block_order, blocks_x, progress_file)
        del padded
        gc.collect()

        result = _unpad_image(embedded, original_size)
        del embedded
        gc.collect()

        stego_bytes = _save_stego_image(result, output_format)
        del result
        gc.collect()

    stats = DCTEmbedStats(
        blocks_used=(len(bits) + len(DEFAULT_EMBED_POSITIONS) - 1) // len(DEFAULT_EMBED_POSITIONS),
        blocks_available=capacity_info.total_blocks,
        bits_embedded=len(bits),
        capacity_bits=capacity_info.total_capacity_bits,
        usage_percent=(len(bits) / capacity_info.total_capacity_bits) * 100,
        image_width=width,
        image_height=height,
        output_format=output_format,
        jpeg_native=False,
        color_mode=color_mode,
    )

    return stego_bytes, stats


def _embed_in_channel_safe(
    channel: np.ndarray,
    bits: list,
    block_order: list,
    blocks_x: int,
    progress_file: str | None = None,
) -> np.ndarray:
    """
    Embed bits in channel using safe DCT operations.

    Processes one block at a time with fresh array allocations.
    """
    h, w = channel.shape

    # Create result with explicit new memory
    result = np.array(channel, dtype=np.float64, copy=True, order="C")

    bit_idx = 0
    total_blocks = len(block_order)

    for block_idx, block_num in enumerate(block_order):
        if bit_idx >= len(bits):
            break

        by = (block_num // blocks_x) * BLOCK_SIZE
        bx = (block_num % blocks_x) * BLOCK_SIZE

        # Extract block - create brand new array
        block = np.array(
            result[by : by + BLOCK_SIZE, bx : bx + BLOCK_SIZE],
            dtype=np.float64,
            copy=True,
            order="C",
        )

        # Apply safe DCT (row-by-row)
        dct_block = _safe_dct2(block)

        # Embed bits
        for pos in DEFAULT_EMBED_POSITIONS:
            if bit_idx >= len(bits):
                break
            dct_block[pos[0], pos[1]] = _embed_bit_in_coeff(
                float(dct_block[pos[0], pos[1]]), bits[bit_idx]
            )
            bit_idx += 1

        # Apply safe inverse DCT
        modified_block = _safe_idct2(dct_block)

        # Copy back
        result[by : by + BLOCK_SIZE, bx : bx + BLOCK_SIZE] = modified_block

        # Clean up this iteration
        del block, dct_block, modified_block

        # Report progress periodically
        if progress_file and block_idx % PROGRESS_INTERVAL == 0:
            _write_progress(progress_file, block_idx, total_blocks, "embedding")

    # Final progress update
    if progress_file:
        _write_progress(progress_file, total_blocks, total_blocks, "finalizing")

    # Force garbage collection
    gc.collect()

    return result


def _normalize_jpeg_for_jpegio(image_data: bytes) -> bytes:
    """
    Normalize a JPEG image to ensure jpegio can process it safely.

    JPEGs saved with quality=100 have quantization tables with all values = 1,
    which causes jpegio to crash due to huge coefficient magnitudes.
    This function detects such images and re-saves them at a safe quality level.

    Args:
        image_data: Raw JPEG bytes

    Returns:
        Normalized JPEG bytes (may be unchanged if already safe)
    """
    img = Image.open(io.BytesIO(image_data))

    # Only process JPEGs
    if img.format != "JPEG":
        img.close()
        return image_data

    # Check quantization tables
    needs_normalization = False
    if hasattr(img, "quantization") and img.quantization:
        for table_id, table in img.quantization.items():
            # If all values in any table are <= threshold, normalize
            if max(table) <= JPEGIO_MAX_QUANT_VALUE_THRESHOLD:
                needs_normalization = True
                break

    if not needs_normalization:
        img.close()
        return image_data

    # Re-save at safe quality level
    if img.mode != "RGB":
        img = img.convert("RGB")

    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=JPEGIO_NORMALIZE_QUALITY, subsampling=0)
    img.close()

    return buffer.getvalue()


def _embed_jpegio(
    data: bytes,
    carrier_image: bytes,
    seed: bytes,
    color_mode: str = "color",
    progress_file: str | None = None,
) -> tuple[bytes, DCTEmbedStats]:
    """Embed using jpegio for proper JPEG coefficient modification."""
    import os
    import tempfile

    # Normalize JPEG to avoid crashes with quality=100 images
    carrier_image = _normalize_jpeg_for_jpegio(carrier_image)

    img = Image.open(io.BytesIO(carrier_image))
    width, height = img.size

    if img.format != "JPEG":
        buffer = io.BytesIO()
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(buffer, format="JPEG", quality=95, subsampling=0)
        carrier_image = buffer.getvalue()
    img.close()

    input_path = _jpegio_bytes_to_file(carrier_image, suffix=".jpg")
    output_path = tempfile.mktemp(suffix=".jpg")

    flags = FLAG_COLOR_MODE if color_mode == "color" else 0

    try:
        jpeg = jio.read(input_path)
        coef_array = jpeg.coef_arrays[JPEGIO_EMBED_CHANNEL]

        all_positions = _jpegio_get_usable_positions(coef_array)
        order = _jpegio_generate_order(len(all_positions), seed)

        # Build raw payload (header + data)
        header = _jpegio_create_header(len(data), flags)
        raw_payload = header + data

        # Apply Reed-Solomon error correction to entire payload if available
        if HAS_REEDSOLO:
            rs_payload = _rs_encode(raw_payload)
            # Format: [length_header x 3 for majority voting] + [RS-encoded payload]
            length_header = struct.pack(">II", len(raw_payload), len(rs_payload))
            length_prefix = length_header * RS_LENGTH_COPIES
            payload = length_prefix + rs_payload
        else:
            payload = raw_payload

        bits = []
        for byte in payload:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)

        if len(bits) > len(all_positions):
            raise ValueError(
                f"Payload too large: {len(bits)} bits, "
                f"only {len(all_positions)} usable coefficients"
            )

        coefs_used = 0
        total_bits = len(bits)
        progress_interval = max(total_bits // 20, 100)  # Report ~20 times or every 100 bits

        for bit_idx, pos_idx in enumerate(order):
            if bit_idx >= len(bits):
                break

            row, col = all_positions[pos_idx]
            coef = coef_array[row, col]

            if (coef & 1) != bits[bit_idx]:
                if coef > 0:
                    coef_array[row, col] = coef - 1 if (coef & 1) else coef + 1
                else:
                    coef_array[row, col] = coef + 1 if (coef & 1) else coef - 1

            coefs_used += 1

            # Report progress periodically
            if progress_file and bit_idx % progress_interval == 0:
                _write_progress(progress_file, bit_idx, total_bits, "embedding")

        # Final progress before save
        if progress_file:
            _write_progress(progress_file, total_bits, total_bits, "saving")

        jio.write(jpeg, output_path)

        with open(output_path, "rb") as f:
            stego_bytes = f.read()

        stats = DCTEmbedStats(
            blocks_used=coefs_used // 63,
            blocks_available=len(all_positions) // 63,
            bits_embedded=len(bits),
            capacity_bits=len(all_positions),
            usage_percent=(len(bits) / len(all_positions)) * 100 if all_positions else 0,
            image_width=width,
            image_height=height,
            output_format=OUTPUT_FORMAT_JPEG,
            jpeg_native=True,
            color_mode=color_mode,
        )

        return stego_bytes, stats

    finally:
        for path in [input_path, output_path]:
            try:
                os.unlink(path)
            except OSError:
                pass


def extract_from_dct(stego_image: bytes, seed: bytes) -> bytes:
    """Extract data from DCT stego image."""
    img = Image.open(io.BytesIO(stego_image))
    fmt = img.format
    img.close()

    if fmt == "JPEG" and HAS_JPEGIO:
        try:
            return _extract_jpegio(stego_image, seed)
        except ValueError:
            pass

    _check_scipy()
    return _extract_scipy_dct_safe(stego_image, seed)


def _extract_scipy_dct_safe(stego_image: bytes, seed: bytes) -> bytes:
    """Extract using safe DCT operations."""
    img = Image.open(io.BytesIO(stego_image))
    width, height = img.size
    mode = img.mode

    if mode in ("RGB", "RGBA"):
        channel = _extract_y_channel(stego_image)
    else:
        channel = _to_grayscale(stego_image)
    img.close()

    padded, _ = _pad_to_blocks(channel)
    del channel
    gc.collect()

    # Use ORIGINAL image dimensions for block calculations (must match embed)
    # Embed uses width // BLOCK_SIZE, not padded width
    h, w = padded.shape  # Padded dimensions for bounds checking
    blocks_x = width // BLOCK_SIZE
    blocks_y = height // BLOCK_SIZE
    num_blocks = blocks_y * blocks_x

    block_order = _generate_block_order(num_blocks, seed)

    all_bits = []

    for block_num in block_order:
        by = (block_num // blocks_x) * BLOCK_SIZE
        bx = (block_num % blocks_x) * BLOCK_SIZE

        block = np.array(
            padded[by : by + BLOCK_SIZE, bx : bx + BLOCK_SIZE],
            dtype=np.float64,
            copy=True,
            order="C",
        )
        dct_block = _safe_dct2(block)

        for pos in DEFAULT_EMBED_POSITIONS:
            bit = _extract_bit_from_coeff(float(dct_block[pos[0], pos[1]]))
            all_bits.append(bit)

        del block, dct_block

        if len(all_bits) >= HEADER_SIZE * 8:
            try:
                _, flags, data_length = _parse_header(all_bits[: HEADER_SIZE * 8])
                total_needed = (HEADER_SIZE + data_length) * 8
                if len(all_bits) >= total_needed:
                    break
            except (ValueError, InvalidMagicBytesError):
                pass  # RS-protected format has length prefix first, not magic bytes

    del padded
    gc.collect()

    # Try RS-protected format first (has 24-byte length prefix: 3 copies of 8-byte header)
    if HAS_REEDSOLO and len(all_bits) >= RS_LENGTH_PREFIX_SIZE * 8:
        # Extract length prefix (24 bytes: 3 copies of 8-byte header for majority voting)
        length_prefix_bits = all_bits[: RS_LENGTH_PREFIX_SIZE * 8]
        length_prefix_bytes = bytes(
            [
                sum(length_prefix_bits[i * 8 : (i + 1) * 8][j] << (7 - j) for j in range(8))
                for i in range(RS_LENGTH_PREFIX_SIZE)
            ]
        )

        # Extract 3 copies and use majority voting
        copies = []
        for i in range(RS_LENGTH_COPIES):
            start = i * RS_LENGTH_HEADER_SIZE
            end = start + RS_LENGTH_HEADER_SIZE
            copies.append(length_prefix_bytes[start:end])

        # Count occurrences of each unique copy
        from collections import Counter

        counter = Counter(copies)
        best_header, count = counter.most_common(1)[0]

        # Only proceed if we have at least 2 matching copies (majority)
        if count >= 2:
            raw_payload_length, rs_encoded_length = struct.unpack(">II", best_header)
        else:
            # No majority - try first copy as fallback
            raw_payload_length, rs_encoded_length = struct.unpack(">II", copies[0])

        # Sanity check: both lengths should be reasonable
        max_reasonable = (len(all_bits) // 8) - RS_LENGTH_PREFIX_SIZE
        if (
            raw_payload_length > 0
            and raw_payload_length <= max_reasonable
            and rs_encoded_length > 0
            and rs_encoded_length <= max_reasonable
            and rs_encoded_length >= raw_payload_length
        ):
            # This looks like RS-protected format
            total_bits_needed = (RS_LENGTH_PREFIX_SIZE + rs_encoded_length) * 8

            if len(all_bits) >= total_bits_needed:
                rs_bits = all_bits[RS_LENGTH_PREFIX_SIZE * 8 : total_bits_needed]
                rs_encoded = bytes(
                    [
                        sum(rs_bits[i * 8 : (i + 1) * 8][j] << (7 - j) for j in range(8))
                        for i in range(rs_encoded_length)
                    ]
                )

                try:
                    # RS decode to get header + data
                    raw_payload = _rs_decode(rs_encoded)

                    # Parse header from decoded payload
                    _, flags, data_length = _parse_header(
                        [((raw_payload[i // 8] >> (7 - i % 8)) & 1) for i in range(HEADER_SIZE * 8)]
                    )

                    # Extract data
                    data = raw_payload[HEADER_SIZE : HEADER_SIZE + data_length]
                    return data
                except (ValueError, struct.error):
                    pass  # Fall through to legacy format

    # Legacy format: header not protected by RS
    _, flags, data_length = _parse_header(all_bits)
    data_bits = all_bits[HEADER_SIZE * 8 : (HEADER_SIZE + data_length) * 8]

    data = bytes(
        [
            sum(data_bits[i * 8 : (i + 1) * 8][j] << (7 - j) for j in range(8))
            for i in range(data_length)
        ]
    )

    return data


def _extract_jpegio(stego_image: bytes, seed: bytes) -> bytes:
    """Extract using jpegio for JPEG images."""
    import os

    # Normalize JPEG to avoid crashes with quality=100 images
    # (shouldn't happen with stego images, but be defensive)
    stego_image = _normalize_jpeg_for_jpegio(stego_image)

    temp_path = _jpegio_bytes_to_file(stego_image, suffix=".jpg")

    try:
        jpeg = jio.read(temp_path)
        coef_array = jpeg.coef_arrays[JPEGIO_EMBED_CHANNEL]

        all_positions = _jpegio_get_usable_positions(coef_array)
        order = _jpegio_generate_order(len(all_positions), seed)

        # Try RS-protected format first (has 24-byte length prefix: 3 copies for majority voting)
        if HAS_REEDSOLO and len(all_positions) >= RS_LENGTH_PREFIX_SIZE * 8:
            # Extract length prefix (24 bytes: 3 copies of 8-byte header)
            length_prefix_bits = []
            for pos_idx in order[: RS_LENGTH_PREFIX_SIZE * 8]:
                row, col = all_positions[pos_idx]
                coef = coef_array[row, col]
                length_prefix_bits.append(coef & 1)

            length_prefix_bytes = bytes(
                [
                    sum(length_prefix_bits[i * 8 : (i + 1) * 8][j] << (7 - j) for j in range(8))
                    for i in range(RS_LENGTH_PREFIX_SIZE)
                ]
            )

            # Extract 3 copies and use majority voting
            from collections import Counter

            copies = []
            for i in range(RS_LENGTH_COPIES):
                start = i * RS_LENGTH_HEADER_SIZE
                end = start + RS_LENGTH_HEADER_SIZE
                copies.append(length_prefix_bytes[start:end])

            counter = Counter(copies)
            best_header, count = counter.most_common(1)[0]

            if count >= 2:
                raw_payload_length, rs_encoded_length = struct.unpack(">II", best_header)
            else:
                raw_payload_length, rs_encoded_length = struct.unpack(">II", copies[0])

            # Sanity check
            max_reasonable = (len(all_positions) // 8) - RS_LENGTH_PREFIX_SIZE
            if (
                raw_payload_length > 0
                and raw_payload_length <= max_reasonable
                and rs_encoded_length > 0
                and rs_encoded_length <= max_reasonable
                and rs_encoded_length >= raw_payload_length
            ):
                total_bits_needed = (RS_LENGTH_PREFIX_SIZE + rs_encoded_length) * 8

                if len(all_positions) >= total_bits_needed:
                    # Extract RS-encoded data
                    all_bits = []
                    for bit_idx, pos_idx in enumerate(order):
                        if bit_idx >= total_bits_needed:
                            break
                        row, col = all_positions[pos_idx]
                        coef = coef_array[row, col]
                        all_bits.append(coef & 1)

                    rs_bits = all_bits[RS_LENGTH_PREFIX_SIZE * 8 :]
                    rs_encoded = bytes(
                        [
                            sum(rs_bits[i * 8 : (i + 1) * 8][j] << (7 - j) for j in range(8))
                            for i in range(rs_encoded_length)
                        ]
                    )

                    try:
                        raw_payload = _rs_decode(rs_encoded)
                        _, flags, data_length = _jpegio_parse_header(raw_payload[:HEADER_SIZE])
                        data = raw_payload[HEADER_SIZE : HEADER_SIZE + data_length]
                        return data
                    except (ValueError, struct.error):
                        pass  # Fall through to legacy format

        # Legacy format: header not protected by RS
        header_bits = []
        for pos_idx in order[: HEADER_SIZE * 8]:
            row, col = all_positions[pos_idx]
            coef = coef_array[row, col]
            header_bits.append(coef & 1)

        header_bytes = bytes(
            [
                sum(header_bits[i * 8 : (i + 1) * 8][j] << (7 - j) for j in range(8))
                for i in range(HEADER_SIZE)
            ]
        )

        _, flags, data_length = _jpegio_parse_header(header_bytes)
        total_bits_needed = (HEADER_SIZE + data_length) * 8

        all_bits = []
        for bit_idx, pos_idx in enumerate(order):
            if bit_idx >= total_bits_needed:
                break
            row, col = all_positions[pos_idx]
            coef = coef_array[row, col]
            all_bits.append(coef & 1)

        data_bits = all_bits[HEADER_SIZE * 8 :]
        data = bytes(
            [
                sum(data_bits[i * 8 : (i + 1) * 8][j] << (7 - j) for j in range(8))
                for i in range(data_length)
            ]
        )

        return data

    finally:
        try:
            os.unlink(temp_path)
        except OSError:
            pass


# ============================================================================
# CONVENIENCE FUNCTIONS
# ============================================================================


def get_output_extension(output_format: str) -> str:
    if output_format == OUTPUT_FORMAT_JPEG:
        return ".jpg"
    return ".png"


def get_output_mimetype(output_format: str) -> str:
    if output_format == OUTPUT_FORMAT_JPEG:
        return "image/jpeg"
    return "image/png"
