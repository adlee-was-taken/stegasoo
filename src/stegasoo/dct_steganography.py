"""
DCT Domain Steganography Module (v3.0.2)

Embeds data in DCT coefficients with two approaches:
1. PNG output: Scipy-based DCT transform (grayscale or color)
2. JPEG output: jpegio-based coefficient manipulation (if available)

The JPEG approach is the "correct" way to do JPEG steganography because
it directly modifies the already-quantized coefficients without re-encoding.

New in v3.0.2:
- jpegio integration for proper JPEG coefficient embedding
- Falls back to warning if jpegio not available for JPEG output
- Maintains backward compatibility with v3.0.1

Requires: scipy (for PNG mode), optionally jpegio (for JPEG mode)
"""

import io
import struct
import hashlib
from dataclasses import dataclass
from typing import Optional, Literal, Tuple
from enum import Enum

import numpy as np
from PIL import Image

# Check for scipy availability (for PNG/DCT mode)
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


# ============================================================================
# CONSTANTS
# ============================================================================

# DCT block size (standard 8x8 like JPEG)
BLOCK_SIZE = 8

# Coefficients to use for embedding (mid-frequency, zig-zag order positions)
EMBED_POSITIONS = [
    (0, 1), (1, 0), (2, 0), (1, 1), (0, 2), (0, 3), (1, 2), (2, 1), (3, 0),
    (4, 0), (3, 1), (2, 2), (1, 3), (0, 4), (0, 5), (1, 4), (2, 3), (3, 2),
    (4, 1), (5, 0), (5, 1), (4, 2), (3, 3), (2, 4), (1, 5), (0, 6), (0, 7),
    (1, 6), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (7, 0),
]

# Use subset of mid-frequency coefficients for better robustness
DEFAULT_EMBED_POSITIONS = EMBED_POSITIONS[4:20]  # 16 coefficients per block

# Quantization step for QIM embedding (larger = more robust, more visible)
QUANT_STEP = 25

# Magic bytes for DCT stego identification
DCT_MAGIC = b'DCTS'

# Header size: magic(4) + version(1) + flags(1) + length(4) = 10 bytes
HEADER_SIZE = 10

# Output format options
OUTPUT_FORMAT_PNG = 'png'
OUTPUT_FORMAT_JPEG = 'jpeg'

# JPEG output quality (only for fallback mode, not jpegio)
JPEG_OUTPUT_QUALITY = 95

# jpegio constants for JPEG coefficient embedding
JPEGIO_MAGIC = b'JPGS'
JPEGIO_MIN_COEF_MAGNITUDE = 2
JPEGIO_EMBED_CHANNEL = 0  # Y channel


# ============================================================================
# DATA CLASSES
# ============================================================================

class DCTOutputFormat(Enum):
    """Output format for DCT stego images."""
    PNG = 'png'
    JPEG = 'jpeg'


@dataclass
class DCTEmbedStats:
    """Statistics from DCT embedding operation."""
    blocks_used: int
    blocks_available: int
    bits_embedded: int
    capacity_bits: int
    usage_percent: float
    image_width: int
    image_height: int
    output_format: str
    jpeg_native: bool = False  # True if used jpegio for proper JPEG embedding
    color_mode: str = 'grayscale'  # 'color' or 'grayscale' (v3.0.1+)


@dataclass 
class DCTCapacityInfo:
    """Capacity information for a carrier image."""
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
    """Raise ImportError if scipy is not available."""
    if not HAS_SCIPY:
        raise ImportError(
            "DCT steganography requires scipy. "
            "Install with: pip install scipy"
        )


def has_dct_support() -> bool:
    """Check if DCT steganography is available (scipy installed)."""
    return HAS_SCIPY


def has_jpegio_support() -> bool:
    """Check if jpegio is available for proper JPEG coefficient embedding."""
    return HAS_JPEGIO


# ============================================================================
# SCIPY DCT HELPERS (for PNG output)
# ============================================================================

def _dct2(block: np.ndarray) -> np.ndarray:
    """Apply 2D DCT to a block."""
    return dct(dct(block.T, norm='ortho').T, norm='ortho')


def _idct2(block: np.ndarray) -> np.ndarray:
    """Apply 2D inverse DCT to a block."""
    return idct(idct(block.T, norm='ortho').T, norm='ortho')


def _to_grayscale(image_data: bytes) -> np.ndarray:
    """Convert image bytes to grayscale numpy array."""
    img = Image.open(io.BytesIO(image_data))
    gray = img.convert('L')
    return np.array(gray, dtype=np.float64)


def _pad_to_blocks(image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
    """Pad image dimensions to be divisible by block size."""
    h, w = image.shape
    new_h = ((h + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
    new_w = ((w + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
    
    if new_h == h and new_w == w:
        return image, (h, w)
    
    padded = np.zeros((new_h, new_w), dtype=image.dtype)
    padded[:h, :w] = image
    
    if new_h > h:
        padded[h:, :w] = image[h-(new_h-h):h, :w][::-1, :]
    if new_w > w:
        padded[:h, w:] = image[:h, w-(new_w-w):w][:, ::-1]
    if new_h > h and new_w > w:
        padded[h:, w:] = image[h-(new_h-h):h, w-(new_w-w):w][::-1, ::-1]
    
    return padded, (h, w)


def _unpad_image(image: np.ndarray, original_size: Tuple[int, int]) -> np.ndarray:
    """Remove padding from image."""
    h, w = original_size
    return image[:h, :w]


def _embed_bit_in_coeff(coef: float, bit: int, quant_step: int = QUANT_STEP) -> float:
    """Embed a single bit into a DCT coefficient using QIM."""
    quantized = round(coef / quant_step)
    if (quantized % 2) != bit:
        if quantized % 2 == 0 and bit == 1:
            quantized += 1 if coef >= quantized * quant_step else -1
        elif quantized % 2 == 1 and bit == 0:
            quantized += 1 if coef >= quantized * quant_step else -1
    return quantized * quant_step


def _extract_bit_from_coeff(coef: float, quant_step: int = QUANT_STEP) -> int:
    """Extract a single bit from a DCT coefficient."""
    quantized = round(coef / quant_step)
    return quantized % 2


def _generate_block_order(num_blocks: int, seed: bytes) -> list:
    """Generate pseudo-random block order from seed."""
    hash_bytes = hashlib.sha256(seed).digest()
    rng = np.random.RandomState(int.from_bytes(hash_bytes[:4], 'big'))
    order = list(range(num_blocks))
    rng.shuffle(order)
    return order


def _save_stego_image(image: np.ndarray, output_format: str = OUTPUT_FORMAT_PNG) -> bytes:
    """Save stego image in specified format (grayscale)."""
    clipped = np.clip(image, 0, 255).astype(np.uint8)
    img = Image.fromarray(clipped, mode='L')
    
    buffer = io.BytesIO()
    
    if output_format == OUTPUT_FORMAT_JPEG:
        img.save(buffer, format='JPEG', quality=JPEG_OUTPUT_QUALITY, 
                 subsampling=0, optimize=True)
    else:
        img.save(buffer, format='PNG', optimize=True)
    
    return buffer.getvalue()


def _save_color_image(rgb_array: np.ndarray, output_format: str = OUTPUT_FORMAT_PNG) -> bytes:
    """Save color RGB image in specified format."""
    clipped = np.clip(rgb_array, 0, 255).astype(np.uint8)
    img = Image.fromarray(clipped, mode='RGB')
    
    buffer = io.BytesIO()
    
    if output_format == OUTPUT_FORMAT_JPEG:
        img.save(buffer, format='JPEG', quality=JPEG_OUTPUT_QUALITY,
                 subsampling=0, optimize=True)
    else:
        img.save(buffer, format='PNG', optimize=True)
    
    return buffer.getvalue()


def _rgb_to_ycbcr(rgb: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
    """
    Convert RGB array to YCbCr components.
    
    Uses ITU-R BT.601 conversion (standard for JPEG).
    
    Args:
        rgb: RGB image array (H, W, 3), float64
        
    Returns:
        Tuple of (Y, Cb, Cr) arrays
    """
    R = rgb[:, :, 0]
    G = rgb[:, :, 1]
    B = rgb[:, :, 2]
    
    # ITU-R BT.601 conversion
    Y = 0.299 * R + 0.587 * G + 0.114 * B
    Cb = 128 - 0.168736 * R - 0.331264 * G + 0.5 * B
    Cr = 128 + 0.5 * R - 0.418688 * G - 0.081312 * B
    
    return Y, Cb, Cr


def _ycbcr_to_rgb(Y: np.ndarray, Cb: np.ndarray, Cr: np.ndarray) -> np.ndarray:
    """
    Convert YCbCr components back to RGB array.
    
    Args:
        Y: Luminance channel
        Cb: Blue-difference chroma
        Cr: Red-difference chroma
        
    Returns:
        RGB array (H, W, 3)
    """
    R = Y + 1.402 * (Cr - 128)
    G = Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128)
    B = Y + 1.772 * (Cb - 128)
    
    rgb = np.stack([R, G, B], axis=-1)
    return rgb


def _create_header(data_length: int, flags: int = 0) -> bytes:
    """Create DCT stego header."""
    version = 1
    return struct.pack('>4sBBI', DCT_MAGIC, version, flags, data_length)


def _parse_header(header_bits: list) -> Tuple[int, int, int]:
    """Parse header from extracted bits. Returns (version, flags, data_length)."""
    if len(header_bits) < HEADER_SIZE * 8:
        raise ValueError("Insufficient header data")
    
    header_bytes = bytes([
        sum(header_bits[i*8:(i+1)*8][j] << (7-j) for j in range(8))
        for i in range(HEADER_SIZE)
    ])
    
    magic, version, flags, length = struct.unpack('>4sBBI', header_bytes)
    
    if magic != DCT_MAGIC:
        raise ValueError("Invalid DCT stego magic bytes")
    
    return version, flags, length


# ============================================================================
# JPEGIO HELPERS (for proper JPEG output)
# ============================================================================

def _jpegio_bytes_to_file(data: bytes, suffix: str = '.jpg') -> str:
    """Write bytes to temp file for jpegio."""
    import tempfile
    import os
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        os.write(fd, data)
    finally:
        os.close(fd)
    return path


def _jpegio_file_to_bytes(path: str) -> bytes:
    """Read file to bytes and delete it."""
    import os
    try:
        with open(path, 'rb') as f:
            return f.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _jpegio_get_usable_positions(coef_array: np.ndarray) -> list:
    """Get usable coefficient positions for jpegio embedding."""
    positions = []
    h, w = coef_array.shape
    
    for row in range(h):
        for col in range(w):
            # Skip DC coefficients
            if (row % BLOCK_SIZE == 0) and (col % BLOCK_SIZE == 0):
                continue
            # Check magnitude
            if abs(coef_array[row, col]) >= JPEGIO_MIN_COEF_MAGNITUDE:
                positions.append((row, col))
    
    return positions


def _jpegio_generate_order(num_positions: int, seed: bytes) -> list:
    """Generate pseudo-random order for jpegio embedding."""
    hash_bytes = hashlib.sha256(seed + b"jpeg_coef_order").digest()
    rng = np.random.RandomState(int.from_bytes(hash_bytes[:4], 'big'))
    order = list(range(num_positions))
    rng.shuffle(order)
    return order


def _jpegio_create_header(data_length: int) -> bytes:
    """Create header for jpegio embedding."""
    return struct.pack('>4sBBI', JPEGIO_MAGIC, 1, 0, data_length)


def _jpegio_parse_header(header_bytes: bytes) -> Tuple[int, int, int]:
    """Parse jpegio header."""
    if len(header_bytes) < HEADER_SIZE:
        raise ValueError("Insufficient header data")
    
    magic, version, flags, length = struct.unpack('>4sBBI', header_bytes[:HEADER_SIZE])
    
    if magic != JPEGIO_MAGIC:
        raise ValueError(f"Invalid JPEG stego magic: {magic}")
    
    return version, flags, length


# ============================================================================
# PUBLIC API
# ============================================================================

def calculate_dct_capacity(image_data: bytes) -> DCTCapacityInfo:
    """
    Calculate the DCT embedding capacity of an image.
    
    Args:
        image_data: Image file bytes
        
    Returns:
        DCTCapacityInfo with capacity details
    """
    _check_scipy()
    
    img = Image.open(io.BytesIO(image_data))
    width, height = img.size
    
    blocks_x = width // BLOCK_SIZE
    blocks_y = height // BLOCK_SIZE
    total_blocks = blocks_x * blocks_y
    
    bits_per_block = len(DEFAULT_EMBED_POSITIONS)
    total_bits = total_blocks * bits_per_block
    total_bytes = total_bits // 8
    usable_bytes = max(0, total_bytes - HEADER_SIZE)
    
    return DCTCapacityInfo(
        width=width,
        height=height,
        blocks_x=blocks_x,
        blocks_y=blocks_y,
        total_blocks=total_blocks,
        bits_per_block=bits_per_block,
        total_capacity_bits=total_bits,
        total_capacity_bytes=total_bytes,
        usable_capacity_bytes=usable_bytes
    )


def will_fit_dct(data_length: int, image_data: bytes) -> bool:
    """Check if data will fit in the image using DCT embedding."""
    capacity = calculate_dct_capacity(image_data)
    return data_length <= capacity.usable_capacity_bytes


def estimate_capacity_comparison(image_data: bytes) -> dict:
    """Compare LSB and DCT capacity for an image."""
    img = Image.open(io.BytesIO(image_data))
    width, height = img.size
    pixels = width * height
    
    lsb_bytes = (pixels * 3) // 8
    
    if HAS_SCIPY:
        dct_info = calculate_dct_capacity(image_data)
        dct_bytes = dct_info.usable_capacity_bytes
    else:
        blocks = (width // 8) * (height // 8)
        dct_bytes = (blocks * 16) // 8 - HEADER_SIZE
    
    return {
        'width': width,
        'height': height,
        'lsb': {
            'capacity_bytes': lsb_bytes,
            'capacity_kb': lsb_bytes / 1024,
            'output': 'PNG/BMP (color)',
        },
        'dct': {
            'capacity_bytes': dct_bytes,
            'capacity_kb': dct_bytes / 1024,
            'output': 'PNG or JPEG (grayscale)',
            'ratio_vs_lsb': (dct_bytes / lsb_bytes * 100) if lsb_bytes > 0 else 0,
            'available': HAS_SCIPY,
        },
        'jpeg_native': {
            'available': HAS_JPEGIO,
            'note': 'Uses jpegio for proper JPEG coefficient embedding',
        }
    }


def embed_in_dct(
    data: bytes,
    carrier_image: bytes,
    seed: bytes,
    output_format: str = OUTPUT_FORMAT_PNG,
    color_mode: str = 'color',  # v3.0.1: 'color' or 'grayscale'
) -> Tuple[bytes, DCTEmbedStats]:
    """
    Embed data into image using DCT coefficient modification.
    
    For PNG output: Uses scipy DCT transform
    For JPEG output: Uses jpegio if available for proper coefficient embedding
    
    Args:
        data: Data to embed
        carrier_image: Carrier image bytes
        seed: Seed for pseudo-random selection
        output_format: 'png' (default, lossless) or 'jpeg'
        color_mode: 'color' (preserve colors) or 'grayscale' (v3.0.1+)
        
    Returns:
        Tuple of (stego_image_bytes, stats)
    """
    # Validate output format
    if output_format not in (OUTPUT_FORMAT_PNG, OUTPUT_FORMAT_JPEG):
        raise ValueError(f"Invalid output format: {output_format}")
    
    # Validate color mode
    if color_mode not in ('color', 'grayscale'):
        color_mode = 'color'  # Default to color
    
    # For JPEG output, try to use jpegio for proper coefficient embedding
    # Note: jpegio naturally preserves color (works in YCbCr space)
    if output_format == OUTPUT_FORMAT_JPEG:
        if HAS_JPEGIO:
            return _embed_jpegio(data, carrier_image, seed, color_mode)
        else:
            # Fall back to scipy + PIL JPEG (WARNING: may not decode properly)
            import warnings
            warnings.warn(
                "jpegio not available. JPEG output may not decode correctly. "
                "Install jpegio for proper JPEG steganography support.",
                RuntimeWarning
            )
            # Continue with scipy method but output as JPEG
    
    # PNG output or JPEG fallback: use scipy DCT method
    _check_scipy()
    return _embed_scipy_dct(data, carrier_image, seed, output_format, color_mode)


def _embed_scipy_dct(
    data: bytes,
    carrier_image: bytes,
    seed: bytes,
    output_format: str,
    color_mode: str = 'color',
) -> Tuple[bytes, DCTEmbedStats]:
    """Embed using scipy DCT (for PNG output), with color preservation option."""
    capacity_info = calculate_dct_capacity(carrier_image)
    
    if len(data) > capacity_info.usable_capacity_bytes:
        raise ValueError(
            f"Data too large ({len(data)} bytes) for carrier "
            f"(capacity: {capacity_info.usable_capacity_bytes} bytes)"
        )
    
    # Load image
    img = Image.open(io.BytesIO(carrier_image))
    width, height = img.size
    
    if color_mode == 'color' and img.mode in ('RGB', 'RGBA'):
        # Color mode: convert to YCbCr, embed in Y only, preserve Cb/Cr
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        rgb_array = np.array(img, dtype=np.float64)
        Y, Cb, Cr = _rgb_to_ycbcr(rgb_array)
        
        # Pad Y channel
        Y_padded, original_size = _pad_to_blocks(Y)
        
        # Embed in Y channel
        Y_embedded = _embed_in_channel(Y_padded, data, seed, capacity_info)
        
        # Unpad
        Y_result = _unpad_image(Y_embedded, original_size)
        
        # Convert back to RGB
        result_rgb = _ycbcr_to_rgb(Y_result, Cb, Cr)
        
        # Save as color image
        stego_bytes = _save_color_image(result_rgb, output_format)
    else:
        # Grayscale mode: original behavior
        image = _to_grayscale(carrier_image)
        padded, original_size = _pad_to_blocks(image)
        
        embedded = _embed_in_channel(padded, data, seed, capacity_info)
        
        result = _unpad_image(embedded, original_size)
        stego_bytes = _save_stego_image(result, output_format)
    
    # Calculate stats
    header = _create_header(len(data))
    payload = header + data
    bits = len(payload) * 8
    
    stats = DCTEmbedStats(
        blocks_used=(bits + len(DEFAULT_EMBED_POSITIONS) - 1) // len(DEFAULT_EMBED_POSITIONS),
        blocks_available=capacity_info.total_blocks,
        bits_embedded=bits,
        capacity_bits=capacity_info.total_capacity_bits,
        usage_percent=(bits / capacity_info.total_capacity_bits) * 100,
        image_width=width,
        image_height=height,
        output_format=output_format,
        jpeg_native=False,
        color_mode=color_mode,
    )
    
    return stego_bytes, stats


def _embed_in_channel(
    channel: np.ndarray,
    data: bytes,
    seed: bytes,
    capacity_info: DCTCapacityInfo,
) -> np.ndarray:
    """Embed data in a single channel using DCT."""
    header = _create_header(len(data))
    payload = header + data
    
    bits = []
    for byte in payload:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    
    num_blocks = capacity_info.total_blocks
    block_order = _generate_block_order(num_blocks, seed)
    
    h, w = channel.shape
    result = channel.copy()
    
    bit_idx = 0
    for block_num in block_order:
        if bit_idx >= len(bits):
            break
        
        by = (block_num // (w // BLOCK_SIZE)) * BLOCK_SIZE
        bx = (block_num % (w // BLOCK_SIZE)) * BLOCK_SIZE
        
        block = result[by:by+BLOCK_SIZE, bx:bx+BLOCK_SIZE].copy()
        dct_block = _dct2(block)
        
        for pos in DEFAULT_EMBED_POSITIONS:
            if bit_idx >= len(bits):
                break
            dct_block[pos] = _embed_bit_in_coeff(dct_block[pos], bits[bit_idx])
            bit_idx += 1
        
        modified_block = _idct2(dct_block)
        result[by:by+BLOCK_SIZE, bx:bx+BLOCK_SIZE] = modified_block
    
    return result


def _embed_jpegio(
    data: bytes,
    carrier_image: bytes,
    seed: bytes,
    color_mode: str = 'color',
) -> Tuple[bytes, DCTEmbedStats]:
    """
    Embed using jpegio for proper JPEG coefficient modification.
    
    Note: jpegio naturally preserves color since JPEG stores YCbCr
    and we only modify Y channel coefficients.
    """
    import tempfile
    import os
    
    # Check if carrier is JPEG - if not, convert it
    img = Image.open(io.BytesIO(carrier_image))
    width, height = img.size
    
    if img.format != 'JPEG':
        # Convert to JPEG first
        buffer = io.BytesIO()
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(buffer, format='JPEG', quality=95, subsampling=0)
        carrier_image = buffer.getvalue()
    
    # Write carrier to temp file
    input_path = _jpegio_bytes_to_file(carrier_image, suffix='.jpg')
    output_path = tempfile.mktemp(suffix='.jpg')
    
    try:
        # Read JPEG with jpegio
        jpeg = jio.read(input_path)
        
        # Get Y channel coefficients (channel 0)
        # For grayscale mode, we could convert to grayscale, but jpegio
        # works with the original JPEG which already has color info.
        # The color_mode primarily affects the output interpretation.
        coef_array = jpeg.coef_arrays[JPEGIO_EMBED_CHANNEL]
        
        # Find usable positions
        all_positions = _jpegio_get_usable_positions(coef_array)
        
        # Generate pseudo-random order
        order = _jpegio_generate_order(len(all_positions), seed)
        
        # Create payload
        header = _jpegio_create_header(len(data))
        payload = header + data
        
        # Convert to bits
        bits = []
        for byte in payload:
            for i in range(7, -1, -1):
                bits.append((byte >> i) & 1)
        
        if len(bits) > len(all_positions):
            raise ValueError(
                f"Payload too large: {len(bits)} bits, "
                f"only {len(all_positions)} usable coefficients"
            )
        
        # Embed using LSB
        coefs_used = 0
        for bit_idx, pos_idx in enumerate(order):
            if bit_idx >= len(bits):
                break
            
            row, col = all_positions[pos_idx]
            coef = coef_array[row, col]
            
            # Embed bit in LSB
            if (coef & 1) != bits[bit_idx]:
                if coef > 0:
                    coef_array[row, col] = coef - 1 if (coef & 1) else coef + 1
                else:
                    coef_array[row, col] = coef + 1 if (coef & 1) else coef - 1
            
            coefs_used += 1
        
        # Write modified JPEG
        jio.write(jpeg, output_path)
        
        # Read back as bytes
        with open(output_path, 'rb') as f:
            stego_bytes = f.read()
        
        stats = DCTEmbedStats(
            blocks_used=coefs_used // 63,  # Approximate blocks
            blocks_available=len(all_positions) // 63,
            bits_embedded=len(bits),
            capacity_bits=len(all_positions),
            usage_percent=(len(bits) / len(all_positions)) * 100 if all_positions else 0,
            image_width=width,
            image_height=height,
            output_format=OUTPUT_FORMAT_JPEG,
            jpeg_native=True,
            color_mode=color_mode,  # JPEG naturally preserves color
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
) -> bytes:
    """
    Extract data from DCT stego image.
    
    Automatically detects whether image uses scipy DCT or jpegio embedding.
    
    Args:
        stego_image: Stego image bytes
        seed: Same seed used for embedding
        
    Returns:
        Extracted data bytes
    """
    # Check image format
    img = Image.open(io.BytesIO(stego_image))
    
    if img.format == 'JPEG' and HAS_JPEGIO:
        # Try jpegio extraction first
        try:
            return _extract_jpegio(stego_image, seed)
        except ValueError:
            # If jpegio magic not found, fall back to scipy method
            pass
    
    # PNG or fallback: use scipy DCT method
    _check_scipy()
    return _extract_scipy_dct(stego_image, seed)


def _extract_scipy_dct(stego_image: bytes, seed: bytes) -> bytes:
    """Extract using scipy DCT (for PNG images)."""
    image = _to_grayscale(stego_image)
    padded, original_size = _pad_to_blocks(image)
    
    h, w = padded.shape
    blocks_x = w // BLOCK_SIZE
    blocks_y = h // BLOCK_SIZE
    num_blocks = blocks_x * blocks_y
    
    block_order = _generate_block_order(num_blocks, seed)
    
    all_bits = []
    
    for block_num in block_order:
        by = (block_num // blocks_x) * BLOCK_SIZE
        bx = (block_num % blocks_x) * BLOCK_SIZE
        
        block = padded[by:by+BLOCK_SIZE, bx:bx+BLOCK_SIZE]
        dct_block = _dct2(block)
        
        for pos in DEFAULT_EMBED_POSITIONS:
            bit = _extract_bit_from_coeff(dct_block[pos])
            all_bits.append(bit)
        
        if len(all_bits) >= HEADER_SIZE * 8:
            try:
                _, _, data_length = _parse_header(all_bits[:HEADER_SIZE * 8])
                total_needed = (HEADER_SIZE + data_length) * 8
                if len(all_bits) >= total_needed:
                    break
            except ValueError:
                pass
    
    version, flags, data_length = _parse_header(all_bits)
    
    data_bits = all_bits[HEADER_SIZE * 8:(HEADER_SIZE + data_length) * 8]
    
    data = bytes([
        sum(data_bits[i*8:(i+1)*8][j] << (7-j) for j in range(8))
        for i in range(data_length)
    ])
    
    return data


def _extract_jpegio(stego_image: bytes, seed: bytes) -> bytes:
    """Extract using jpegio for JPEG images."""
    import os
    
    temp_path = _jpegio_bytes_to_file(stego_image, suffix='.jpg')
    
    try:
        jpeg = jio.read(temp_path)
        coef_array = jpeg.coef_arrays[JPEGIO_EMBED_CHANNEL]
        
        all_positions = _jpegio_get_usable_positions(coef_array)
        order = _jpegio_generate_order(len(all_positions), seed)
        
        # Extract header bits
        header_bits = []
        for pos_idx in order[:HEADER_SIZE * 8]:
            row, col = all_positions[pos_idx]
            coef = coef_array[row, col]
            header_bits.append(coef & 1)
        
        header_bytes = bytes([
            sum(header_bits[i*8:(i+1)*8][j] << (7-j) for j in range(8))
            for i in range(HEADER_SIZE)
        ])
        
        version, flags, data_length = _jpegio_parse_header(header_bytes)
        
        # Extract all needed bits
        total_bits_needed = (HEADER_SIZE + data_length) * 8
        
        all_bits = []
        for bit_idx, pos_idx in enumerate(order):
            if bit_idx >= total_bits_needed:
                break
            row, col = all_positions[pos_idx]
            coef = coef_array[row, col]
            all_bits.append(coef & 1)
        
        # Extract data
        data_bits = all_bits[HEADER_SIZE * 8:]
        
        data = bytes([
            sum(data_bits[i*8:(i+1)*8][j] << (7-j) for j in range(8))
            for i in range(data_length)
        ])
        
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
    """Get file extension for output format."""
    if output_format == OUTPUT_FORMAT_JPEG:
        return '.jpg'
    return '.png'


def get_output_mimetype(output_format: str) -> str:
    """Get MIME type for output format."""
    if output_format == OUTPUT_FORMAT_JPEG:
        return 'image/jpeg'
    return 'image/png'
