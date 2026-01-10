"""
DCT Domain Steganography Module (v4.1.0)

The fancy pants mode. Instead of hiding bits in pixel values (LSB mode),
we hide them in the *frequency domain* - specifically in the Discrete Cosine
Transform coefficients that JPEG compression uses internally.

Why is this cool?
- Survives some image processing that would destroy LSB data
- Works with JPEG without the usual "save destroys everything" problem
- Uses the same math that JPEG itself uses - we're hiding in plain sight

Two approaches depending on what you want:
1. PNG output: We do our own DCT math via scipy (works on any image)
2. JPEG output: We use jpegio to directly tweak the coefficients (chef's kiss)

v4.1.0 - The "please stop corrupting my data" release:
- Reed-Solomon error correction (can fix up to 16 byte errors per chunk)
- Majority voting on headers (store 3 copies, take the winner)
- Because some image regions are just... problematic

v3.2.0-patch2 - The "scipy why are you like this" release:
- Chunked processing because scipy's FFT was corrupting memory on big images
- Process blocks one at a time with fresh arrays
- Yes, it's slower. No, I don't care. Correctness > speed.

Requires: scipy (PNG mode), optionally jpegio (JPEG mode), reedsolo (error correction)
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
    from scipy.fft import dct, idct, dctn, idctn

    HAS_SCIPY = True
except ImportError:
    try:
        from scipy.fftpack import dct, idct, dctn, idctn

        HAS_SCIPY = True
    except ImportError:
        HAS_SCIPY = False
        dct = None
        idct = None
        dctn = None
        idctn = None

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

# JPEG uses 8x8 blocks for DCT - this is baked into the standard
BLOCK_SIZE = 8

# The zig-zag order of DCT coefficients. JPEG stores them this way because
# the human eye is more sensitive to low frequencies (top-left corner)
# than high frequencies (bottom-right). After quantization, most high-freq
# coefficients become zero, so zig-zag gives great compression.
#
# Visual of an 8x8 DCT block with zig-zag numbering:
#
#   DC  1   5   6  14  15  27  28     <- Low frequency (smooth gradients)
#    2  4   7  13  16  26  29  42
#    3  8  12  17  25  30  41  43
#    9 11  18  24  31  40  44  53
#   10 19  23  32  39  45  52  54
#   20 22  33  38  46  51  55  60
#   21 34  37  47  50  56  59  61
#   35 36  48  49  57  58  62  63     <- High frequency (fine detail/noise)
#
# Position (0,0) is the DC coefficient - the average brightness of the block.
# We NEVER touch DC because changing it causes visible brightness shifts.
EMBED_POSITIONS = [
    (0, 1),   # 1st AC coefficient
    (1, 0),   # 2nd AC coefficient
    (2, 0),   # ... and so on in zig-zag order
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

# We use positions 4-20 (mid-frequency range). Here's the reasoning:
# - Positions 0-3: Too low frequency, changes are visible as color shifts
# - Positions 4-20: Sweet spot - carries enough energy to survive, not visible
# - Positions 21+: High frequency, often quantized to zero, unreliable
DEFAULT_EMBED_POSITIONS = EMBED_POSITIONS[4:20]

# Quantization step for QIM (Quantization Index Modulation).
# This is how we actually embed bits: we round the coefficient to a grid
# and then nudge it based on whether we want a 0 or 1.
# Bigger step = more robust to noise, but more visible. 25 is a good balance.
QUANT_STEP = 25

# Magic bytes so we can identify our own images
DCT_MAGIC = b"DCTS"      # scipy DCT mode marker
JPEGIO_MAGIC = b"JPGS"   # jpegio native JPEG mode marker
HEADER_SIZE = 10         # Magic (4) + version (1) + flags (1) + length (4)

OUTPUT_FORMAT_PNG = "png"
OUTPUT_FORMAT_JPEG = "jpeg"
JPEG_OUTPUT_QUALITY = 95  # High quality but not 100 (100 causes issues, see below)

# For jpegio mode: we only embed in coefficients with magnitude >= 2
# Coefficients of 0 or 1 are usually quantized noise - unreliable
JPEGIO_MIN_COEF_MAGNITUDE = 2

# We embed in the Y (luminance) channel only - it has the most capacity
# Cb/Cr are often subsampled 4:2:0 anyway
JPEGIO_EMBED_CHANNEL = 0

# Header flags
FLAG_COLOR_MODE = 0x01      # Set if we preserved color (YCbCr mode)
FLAG_RS_PROTECTED = 0x02    # Set if Reed-Solomon protected (v4.1.0+)

# Reed-Solomon settings - the "please don't lose my data" system
# 32 parity symbols per chunk means we can correct up to 16 byte errors
# Math: RS(255, 223) where 255-223=32 parity bytes, corrects floor(32/2)=16
RS_NSYM = 32

# We store the payload length 3 times and take majority vote
# Because if the length is wrong, everything is wrong
RS_LENGTH_HEADER_SIZE = 8   # 4 bytes raw length + 4 bytes RS-encoded length
RS_LENGTH_COPIES = 3        # Store 3 copies, need 2 to agree
RS_LENGTH_PREFIX_SIZE = RS_LENGTH_HEADER_SIZE * RS_LENGTH_COPIES  # 24 bytes total

# Chunking for large images - scipy's FFT gets memory-corrupty on huge arrays
MAX_CHUNK_HEIGHT = 512  # Process in strips to keep memory sane

# Fun bug: JPEGs saved with quality=100 have quantization tables full of 1s
# This makes the DCT coefficients HUGE and jpegio crashes spectacularly
# Solution: detect and re-save at quality 95 first
JPEGIO_NORMALIZE_QUALITY = 95
JPEGIO_MAX_QUANT_VALUE_THRESHOLD = 1  # All 1s in quant table = bad news


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
# ============================================================================
#
# Why do we need this? DCT embedding isn't perfect. Some image regions are
# problematic - flat areas, high compression, edge cases. Bits can flip.
#
# Reed-Solomon is the same error correction used in CDs, DVDs, QR codes, and
# deep space communications. If it's good enough for Voyager, it's good enough
# for hiding cat pictures in other cat pictures.
#
# How it works (simplified):
# 1. Take your data bytes
# 2. Add extra "parity" bytes calculated from the data
# 3. If some bytes get corrupted, the math lets you reconstruct them
# 4. RS(255, 223) means: 255 byte blocks, 223 data + 32 parity
# 5. Can correct up to 16 corrupted bytes per block (floor(32/2))
#
# The tradeoff: ~14% overhead (32/223). Worth it for reliability.

try:
    from reedsolo import ReedSolomonError, RSCodec
    HAS_REEDSOLO = True
except ImportError:
    HAS_REEDSOLO = False
    RSCodec = None
    ReedSolomonError = None


def _rs_encode(data: bytes) -> bytes:
    """
    Wrap data in Reed-Solomon error correction.

    Takes your precious payload and adds parity bytes so we can
    recover from the inevitable bit-rot of DCT embedding.
    """
    if not HAS_REEDSOLO:
        return data  # YOLO mode - no protection, good luck
    rs = RSCodec(RS_NSYM)
    return bytes(rs.encode(data))


def _rs_decode(data: bytes) -> bytes:
    """
    Decode Reed-Solomon protected data, fixing errors along the way.

    This is where the magic happens. If bits got flipped during
    extraction, RS will quietly fix them. If too many flipped...
    well, we tried.
    """
    if not HAS_REEDSOLO:
        return data
    rs = RSCodec(RS_NSYM)
    try:
        decoded, _, errata_pos = rs.decode(data)
        if errata_pos:
            # Errors were found and corrected - RS earned its keep today
            pass
        return bytes(decoded)
    except ReedSolomonError as e:
        # Too many errors - the image got mangled beyond repair
        raise StegasooRSError(f"Image corrupted beyond repair: {e}") from e


# ============================================================================
# SAFE DCT FUNCTIONS
# ============================================================================
#
# Story time: scipy's fftpack (the old DCT implementation) has memory issues
# when you process large images. We'd get random garbage in our output, or
# worse, segfaults. Turns out it was reusing internal buffers in unsafe ways.
#
# The fix? Be paranoid. Every single array operation creates a fresh copy.
# Is it slower? Yes. Does it work? Also yes. I'll take correct over fast.
#
# The newer scipy.fft module is better, but we still play it safe because
# not everyone has the latest scipy and I don't want debugging nightmares.


def _safe_dct2(block: np.ndarray) -> np.ndarray:
    """
    Apply 2D DCT (Discrete Cosine Transform) to an 8x8 block.

    The DCT converts spatial data (pixel values) into frequency data
    (how much of each frequency component is present). It's the heart
    of JPEG compression.

    We do it row-by-row and column-by-column with fresh arrays each time
    because scipy's built-in dct2 can corrupt memory on large batches.
    Paranoid? Yes. Necessary? Also yes.
    """
    # Create a brand new array (not a view) - paranoia level: maximum
    safe_block = np.array(block, dtype=np.float64, copy=True, order="C")

    # 2D DCT = 1D DCT on rows, then 1D DCT on columns (separable transform)
    # First pass: DCT each column
    temp = np.zeros_like(safe_block, dtype=np.float64, order="C")
    for i in range(BLOCK_SIZE):
        col = np.array(safe_block[:, i], dtype=np.float64, copy=True)
        temp[:, i] = dct(col, norm="ortho")  # ortho normalization for symmetry

    # Second pass: DCT each row of the result
    result = np.zeros_like(temp, dtype=np.float64, order="C")
    for i in range(BLOCK_SIZE):
        row = np.array(temp[i, :], dtype=np.float64, copy=True)
        result[i, :] = dct(row, norm="ortho")

    return result


def _safe_idct2(block: np.ndarray) -> np.ndarray:
    """
    Apply 2D inverse DCT - convert frequency data back to pixels.

    After we've embedded our secret bits in the DCT coefficients,
    we need to convert back to pixel values. This is the reverse
    of _safe_dct2.

    Same paranoid memory handling because same paranoid developer.
    """
    safe_block = np.array(block, dtype=np.float64, copy=True, order="C")

    # Inverse is the same idea: IDCT rows, then IDCT columns
    temp = np.zeros_like(safe_block, dtype=np.float64, order="C")
    for i in range(BLOCK_SIZE):
        row = np.array(safe_block[i, :], dtype=np.float64, copy=True)
        temp[i, :] = idct(row, norm="ortho")

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
    """
    Embed a single bit into a DCT coefficient using QIM.

    QIM (Quantization Index Modulation) is smarter than simple LSB flipping.
    Instead of just changing the last bit, we round to a quantization grid
    and use odd/even to encode 0/1.

    Why is this better?
    - More robust to noise (small changes don't flip the bit)
    - Works naturally with JPEG's own quantization
    - The change is spread across the coefficient's magnitude

    Visual example (quant_step=25):
    - Coef = 73, want bit=0 -> round to 75 (75/25=3, 3%2=1) -> nudge to 50 (50/25=2, 2%2=0)
    - Coef = 73, want bit=1 -> round to 75 (75/25=3, 3%2=1) -> already odd, keep at 75
    """
    quantized = round(coef / quant_step)
    if (quantized % 2) != bit:
        # Need to flip even<->odd. Nudge in the direction that's closest.
        if quantized % 2 == 0 and bit == 1:
            quantized += 1 if coef >= quantized * quant_step else -1
        elif quantized % 2 == 1 and bit == 0:
            quantized += 1 if coef >= quantized * quant_step else -1
    return float(quantized * quant_step)


def _extract_bit_from_coeff(coef: float, quant_step: int = QUANT_STEP) -> int:
    """
    Extract a bit from a DCT coefficient.

    The inverse of _embed_bit_in_coeff. We round to the quantization grid
    and check if it's odd (1) or even (0).

    This is why QIM is robust: small noise in the coefficient usually
    doesn't change which grid point we round to.
    """
    quantized = round(coef / quant_step)
    return int(quantized % 2)


def _generate_block_order(num_blocks: int, seed: bytes) -> list:
    """
    Generate a pseudo-random order for processing blocks.

    This is crucial for security - if we just went left-to-right, top-to-bottom,
    anyone could find the message by checking blocks in order. Instead, we
    use a keyed shuffle so only someone with the same seed can find the data.

    The seed comes from the crypto layer (derived from passphrase + photo + pin),
    so the block order is effectively part of the encryption.
    """
    # Use SHA-256 to expand the seed into randomness
    hash_bytes = hashlib.sha256(seed).digest()
    # Seed numpy's RNG (we use RandomState for reproducibility across versions)
    rng = np.random.RandomState(int.from_bytes(hash_bytes[:4], "big"))
    # Fisher-Yates shuffle
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
    """
    Convert RGB to YCbCr color space.

    YCbCr separates brightness (Y) from color (Cb=blue-ish, Cr=red-ish).
    This is what JPEG uses internally, and it's great for us because:
    - Human eyes are WAY more sensitive to brightness than color
    - We can hide data in Y without it being as visible
    - Cb/Cr are often subsampled (4:2:0) so Y has more capacity anyway

    The coefficients here are from ITU-R BT.601 - the standard for video.
    """
    R = rgb[:, :, 0].astype(np.float64)
    G = rgb[:, :, 1].astype(np.float64)
    B = rgb[:, :, 2].astype(np.float64)

    # Y = luminance (brightness). Green contributes most because eyes are most sensitive to it.
    Y = np.array(0.299 * R + 0.587 * G + 0.114 * B, dtype=np.float64, copy=True, order="C")
    # Cb = blue-difference chroma (centered at 128)
    Cb = np.array(
        128 - 0.168736 * R - 0.331264 * G + 0.5 * B, dtype=np.float64, copy=True, order="C"
    )
    # Cr = red-difference chroma (centered at 128)
    Cr = np.array(
        128 + 0.5 * R - 0.418688 * G - 0.081312 * B, dtype=np.float64, copy=True, order="C"
    )

    return Y, Cb, Cr


def _ycbcr_to_rgb(Y: np.ndarray, Cb: np.ndarray, Cr: np.ndarray) -> np.ndarray:
    """
    Convert YCbCr back to RGB.

    After embedding in the Y channel, we need to reconstruct RGB for display.
    The Cb/Cr channels are unchanged - we only touched luminance.
    """
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
    Embed bits in channel using vectorized DCT operations.

    Processes blocks in batches for ~10x speedup over sequential processing.
    """
    h, w = channel.shape

    # Create result with explicit new memory
    result = np.array(channel, dtype=np.float64, copy=True, order="C")

    # Pre-compute embed positions as numpy indices
    embed_rows = np.array([pos[0] for pos in DEFAULT_EMBED_POSITIONS])
    embed_cols = np.array([pos[1] for pos in DEFAULT_EMBED_POSITIONS])
    bits_per_block = len(DEFAULT_EMBED_POSITIONS)

    # Calculate how many blocks we need
    total_bits = len(bits)
    blocks_needed = (total_bits + bits_per_block - 1) // bits_per_block
    blocks_to_process = min(blocks_needed, len(block_order))

    # Vectorized embedding: process blocks in batches
    BATCH_SIZE = 500
    bit_idx = 0
    block_idx = 0

    while block_idx < blocks_to_process and bit_idx < total_bits:
        # Determine batch size
        batch_end = min(block_idx + BATCH_SIZE, blocks_to_process)
        batch_order = block_order[block_idx:batch_end]
        batch_count = len(batch_order)

        # Extract blocks into 3D array
        blocks = np.zeros((batch_count, BLOCK_SIZE, BLOCK_SIZE), dtype=np.float64)
        block_positions = []
        for i, block_num in enumerate(batch_order):
            by = (block_num // blocks_x) * BLOCK_SIZE
            bx = (block_num % blocks_x) * BLOCK_SIZE
            blocks[i] = result[by : by + BLOCK_SIZE, bx : bx + BLOCK_SIZE]
            block_positions.append((by, bx))

        # Vectorized 2D DCT on all blocks at once
        dct_blocks = dctn(blocks, axes=(1, 2), norm="ortho")

        # Embed bits in each block (vectorized where possible)
        for i in range(batch_count):
            if bit_idx >= total_bits:
                break

            # Get bits for this block
            block_bits = bits[bit_idx : bit_idx + bits_per_block]
            num_bits = len(block_bits)

            if num_bits == bits_per_block:
                # Full block - vectorized embedding
                coeffs = dct_blocks[i, embed_rows, embed_cols]
                bit_array = np.array(block_bits)
                # QIM embedding: round to grid, adjust for bit
                quantized = np.round(coeffs / QUANT_STEP).astype(int)
                # If quantized % 2 != bit, nudge coefficient
                needs_adjust = (quantized % 2) != bit_array
                # Determine direction to nudge
                dct_blocks[i, embed_rows[needs_adjust], embed_cols[needs_adjust]] = (
                    (quantized[needs_adjust] + (1 - 2 * (quantized[needs_adjust] % 2 == 1))) * QUANT_STEP
                ).astype(np.float64)
                # For bits that already match, just quantize
                dct_blocks[i, embed_rows[~needs_adjust], embed_cols[~needs_adjust]] = (
                    quantized[~needs_adjust] * QUANT_STEP
                ).astype(np.float64)
            else:
                # Partial block - process remaining bits individually
                for j, bit in enumerate(block_bits):
                    row, col = embed_rows[j], embed_cols[j]
                    dct_blocks[i, row, col] = _embed_bit_in_coeff(
                        float(dct_blocks[i, row, col]), bit
                    )

            bit_idx += num_bits

        # Vectorized inverse DCT
        modified_blocks = idctn(dct_blocks, axes=(1, 2), norm="ortho")

        # Copy modified blocks back to result
        for i, (by, bx) in enumerate(block_positions):
            result[by : by + BLOCK_SIZE, bx : bx + BLOCK_SIZE] = modified_blocks[i]

        # Cleanup
        del blocks, dct_blocks, modified_blocks
        block_idx = batch_end

        # Report progress periodically
        if progress_file and block_idx % PROGRESS_INTERVAL == 0:
            _write_progress(progress_file, block_idx, blocks_to_process, "embedding")

    # Final progress update
    if progress_file:
        _write_progress(progress_file, blocks_to_process, blocks_to_process, "finalizing")

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


def extract_from_dct(
    stego_image: bytes,
    seed: bytes,
    progress_file: str | None = None,
) -> bytes:
    """Extract data from DCT stego image."""
    img = Image.open(io.BytesIO(stego_image))
    fmt = img.format
    img.close()

    if fmt == "JPEG" and HAS_JPEGIO:
        try:
            return _extract_jpegio(stego_image, seed, progress_file)
        except ValueError:
            pass

    _check_scipy()
    return _extract_scipy_dct_safe(stego_image, seed, progress_file)


def _extract_scipy_dct_safe(
    stego_image: bytes,
    seed: bytes,
    progress_file: str | None = None,
) -> bytes:
    """Extract using safe DCT operations with vectorized processing."""
    _write_progress(progress_file, 0, 100, "loading")

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

    # Vectorized extraction: process blocks in batches for ~10x speedup
    # Batch size balances memory usage vs. parallelization benefit
    BATCH_SIZE = 500
    all_bits = []

    # Pre-compute embed positions as numpy indices for vectorized access
    embed_rows = np.array([pos[0] for pos in DEFAULT_EMBED_POSITIONS])
    embed_cols = np.array([pos[1] for pos in DEFAULT_EMBED_POSITIONS])

    # Progress reporting interval
    PROGRESS_INTERVAL = 2000  # Report every N blocks

    block_idx = 0
    while block_idx < len(block_order):
        # Determine batch size (may be smaller at end)
        batch_end = min(block_idx + BATCH_SIZE, len(block_order))
        batch_order = block_order[block_idx:batch_end]
        batch_count = len(batch_order)

        # Extract blocks into 3D array (batch_count, 8, 8)
        blocks = np.zeros((batch_count, BLOCK_SIZE, BLOCK_SIZE), dtype=np.float64)
        for i, block_num in enumerate(batch_order):
            by = (block_num // blocks_x) * BLOCK_SIZE
            bx = (block_num % blocks_x) * BLOCK_SIZE
            blocks[i] = padded[by : by + BLOCK_SIZE, bx : bx + BLOCK_SIZE]

        # Vectorized 2D DCT on all blocks at once (~10-15x faster than sequential)
        dct_blocks = dctn(blocks, axes=(1, 2), norm="ortho")

        # Extract bits from embed positions (vectorized)
        # Shape: (batch_count, num_positions)
        coeffs = dct_blocks[:, embed_rows, embed_cols]

        # Quantize and extract bits (vectorized)
        quantized = np.round(coeffs / QUANT_STEP).astype(int)
        bits = (quantized % 2).flatten().tolist()
        all_bits.extend(bits)

        del blocks, dct_blocks, coeffs, quantized
        block_idx = batch_end

        # Report progress
        if progress_file and block_idx % PROGRESS_INTERVAL < BATCH_SIZE:
            _write_progress(progress_file, block_idx, num_blocks, "extracting")

        # Check if we have enough bits (early exit)
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

    _write_progress(progress_file, 80, 100, "decoding")

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
                    _write_progress(progress_file, 100, 100, "complete")
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

    _write_progress(progress_file, 100, 100, "complete")
    return data


def _extract_jpegio(
    stego_image: bytes,
    seed: bytes,
    progress_file: str | None = None,
) -> bytes:
    """Extract using jpegio for JPEG images."""
    import os

    _write_progress(progress_file, 0, 100, "loading")

    # Normalize JPEG to avoid crashes with quality=100 images
    # (shouldn't happen with stego images, but be defensive)
    stego_image = _normalize_jpeg_for_jpegio(stego_image)

    temp_path = _jpegio_bytes_to_file(stego_image, suffix=".jpg")

    try:
        jpeg = jio.read(temp_path)
        coef_array = jpeg.coef_arrays[JPEGIO_EMBED_CHANNEL]

        all_positions = _jpegio_get_usable_positions(coef_array)
        order = _jpegio_generate_order(len(all_positions), seed)

        _write_progress(progress_file, 20, 100, "extracting")

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
                        _write_progress(progress_file, 70, 100, "decoding")
                        raw_payload = _rs_decode(rs_encoded)
                        _, flags, data_length = _jpegio_parse_header(raw_payload[:HEADER_SIZE])
                        data = raw_payload[HEADER_SIZE : HEADER_SIZE + data_length]
                        _write_progress(progress_file, 100, 100, "complete")
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

        _write_progress(progress_file, 100, 100, "complete")
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
