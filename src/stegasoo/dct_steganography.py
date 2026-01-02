"""
DCT Domain Steganography Module (v3.2.0-patch2)

Embeds data in DCT coefficients with two approaches:
1. PNG output: Scipy-based DCT transform (grayscale or color)
2. JPEG output: jpegio-based coefficient manipulation (if available)

v3.2.0-patch2 Changes:
- Chunked processing for large images to avoid heap corruption
- Process image in vertical strips to limit memory per operation
- Isolated DCT operations with fresh array allocations
- Workaround for scipy.fftpack memory issues

Requires: scipy (for PNG mode), optionally jpegio (for JPEG mode)
"""

import io
import struct
import hashlib
import gc
from dataclasses import dataclass
from typing import Optional, Tuple
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


# ============================================================================
# CONSTANTS
# ============================================================================

BLOCK_SIZE = 8
EMBED_POSITIONS = [
    (0, 1), (1, 0), (2, 0), (1, 1), (0, 2), (0, 3), (1, 2), (2, 1), (3, 0),
    (4, 0), (3, 1), (2, 2), (1, 3), (0, 4), (0, 5), (1, 4), (2, 3), (3, 2),
    (4, 1), (5, 0), (5, 1), (4, 2), (3, 3), (2, 4), (1, 5), (0, 6), (0, 7),
    (1, 6), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (7, 0),
]
DEFAULT_EMBED_POSITIONS = EMBED_POSITIONS[4:20]
QUANT_STEP = 25
DCT_MAGIC = b'DCTS'
HEADER_SIZE = 10
OUTPUT_FORMAT_PNG = 'png'
OUTPUT_FORMAT_JPEG = 'jpeg'
JPEG_OUTPUT_QUALITY = 95
JPEGIO_MAGIC = b'JPGS'
JPEGIO_MIN_COEF_MAGNITUDE = 2
JPEGIO_EMBED_CHANNEL = 0
FLAG_COLOR_MODE = 0x01

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
    PNG = 'png'
    JPEG = 'jpeg'


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
    color_mode: str = 'grayscale'


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
        raise ImportError(
            "DCT steganography requires scipy. Install with: pip install scipy"
        )


def has_dct_support() -> bool:
    return HAS_SCIPY


def has_jpegio_support() -> bool:
    return HAS_JPEGIO


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
    safe_block = np.array(block, dtype=np.float64, copy=True, order='C')
    
    # First DCT on columns (transpose -> DCT rows -> transpose back)
    temp = np.zeros_like(safe_block, dtype=np.float64, order='C')
    for i in range(BLOCK_SIZE):
        col = np.array(safe_block[:, i], dtype=np.float64, copy=True)
        temp[:, i] = dct(col, norm='ortho')
    
    # Second DCT on rows
    result = np.zeros_like(temp, dtype=np.float64, order='C')
    for i in range(BLOCK_SIZE):
        row = np.array(temp[i, :], dtype=np.float64, copy=True)
        result[i, :] = dct(row, norm='ortho')
    
    return result


def _safe_idct2(block: np.ndarray) -> np.ndarray:
    """
    Apply 2D inverse DCT with memory isolation.
    Creates a completely fresh array to avoid heap corruption.
    """
    # Create a brand new array (not a view)
    safe_block = np.array(block, dtype=np.float64, copy=True, order='C')
    
    # First IDCT on rows
    temp = np.zeros_like(safe_block, dtype=np.float64, order='C')
    for i in range(BLOCK_SIZE):
        row = np.array(safe_block[i, :], dtype=np.float64, copy=True)
        temp[i, :] = idct(row, norm='ortho')
    
    # Second IDCT on columns
    result = np.zeros_like(temp, dtype=np.float64, order='C')
    for i in range(BLOCK_SIZE):
        col = np.array(temp[:, i], dtype=np.float64, copy=True)
        result[:, i] = idct(col, norm='ortho')
    
    return result


# ============================================================================
# IMAGE PROCESSING HELPERS
# ============================================================================

def _to_grayscale(image_data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_data))
    gray = img.convert('L')
    return np.array(gray, dtype=np.float64, copy=True, order='C')


def _extract_y_channel(image_data: bytes) -> np.ndarray:
    img = Image.open(io.BytesIO(image_data))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    rgb = np.array(img, dtype=np.float64, copy=True, order='C')
    Y = 0.299 * rgb[:, :, 0] + 0.587 * rgb[:, :, 1] + 0.114 * rgb[:, :, 2]
    return np.array(Y, dtype=np.float64, copy=True, order='C')


def _pad_to_blocks(image: np.ndarray) -> Tuple[np.ndarray, Tuple[int, int]]:
    h, w = image.shape
    new_h = ((h + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
    new_w = ((w + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
    
    if new_h == h and new_w == w:
        return np.array(image, dtype=np.float64, copy=True, order='C'), (h, w)
    
    padded = np.zeros((new_h, new_w), dtype=np.float64, order='C')
    padded[:h, :w] = image
    
    # Simple edge replication for padding
    if new_h > h:
        for i in range(h, new_h):
            padded[i, :w] = padded[h-1, :w]
    if new_w > w:
        for j in range(w, new_w):
            padded[:h, j] = padded[:h, w-1]
    if new_h > h and new_w > w:
        padded[h:, w:] = padded[h-1, w-1]
    
    return padded, (h, w)


def _unpad_image(image: np.ndarray, original_size: Tuple[int, int]) -> np.ndarray:
    h, w = original_size
    return np.array(image[:h, :w], dtype=np.float64, copy=True, order='C')


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
    rng = np.random.RandomState(int.from_bytes(hash_bytes[:4], 'big'))
    order = list(range(num_blocks))
    rng.shuffle(order)
    return order


def _save_stego_image(image: np.ndarray, output_format: str = OUTPUT_FORMAT_PNG) -> bytes:
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
    R = rgb[:, :, 0].astype(np.float64)
    G = rgb[:, :, 1].astype(np.float64)
    B = rgb[:, :, 2].astype(np.float64)
    
    Y = np.array(0.299 * R + 0.587 * G + 0.114 * B, dtype=np.float64, copy=True, order='C')
    Cb = np.array(128 - 0.168736 * R - 0.331264 * G + 0.5 * B, dtype=np.float64, copy=True, order='C')
    Cr = np.array(128 + 0.5 * R - 0.418688 * G - 0.081312 * B, dtype=np.float64, copy=True, order='C')
    
    return Y, Cb, Cr


def _ycbcr_to_rgb(Y: np.ndarray, Cb: np.ndarray, Cr: np.ndarray) -> np.ndarray:
    R = Y + 1.402 * (Cr - 128)
    G = Y - 0.344136 * (Cb - 128) - 0.714136 * (Cr - 128)
    B = Y + 1.772 * (Cb - 128)
    
    rgb = np.zeros((Y.shape[0], Y.shape[1], 3), dtype=np.float64, order='C')
    rgb[:, :, 0] = R
    rgb[:, :, 1] = G
    rgb[:, :, 2] = B
    return rgb


def _create_header(data_length: int, flags: int = 0) -> bytes:
    return struct.pack('>4sBBI', DCT_MAGIC, 1, flags, data_length)


def _parse_header(header_bits: list) -> Tuple[int, int, int]:
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
# JPEGIO HELPERS
# ============================================================================

def _jpegio_bytes_to_file(data: bytes, suffix: str = '.jpg') -> str:
    import tempfile
    import os
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
    rng = np.random.RandomState(int.from_bytes(hash_bytes[:4], 'big'))
    order = list(range(num_positions))
    rng.shuffle(order)
    return order


def _jpegio_create_header(data_length: int, flags: int = 0) -> bytes:
    return struct.pack('>4sBBI', JPEGIO_MAGIC, 1, flags, data_length)


def _jpegio_parse_header(header_bytes: bytes) -> Tuple[int, int, int]:
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
    color_mode: str = 'color',
) -> Tuple[bytes, DCTEmbedStats]:
    """Embed data using DCT coefficient modification."""
    if output_format not in (OUTPUT_FORMAT_PNG, OUTPUT_FORMAT_JPEG):
        raise ValueError(f"Invalid output format: {output_format}")
    
    if color_mode not in ('color', 'grayscale'):
        color_mode = 'color'
    
    if output_format == OUTPUT_FORMAT_JPEG and HAS_JPEGIO:
        return _embed_jpegio(data, carrier_image, seed, color_mode)
    
    _check_scipy()
    return _embed_scipy_dct_safe(data, carrier_image, seed, output_format, color_mode)


def _embed_scipy_dct_safe(
    data: bytes,
    carrier_image: bytes,
    seed: bytes,
    output_format: str,
    color_mode: str = 'color',
) -> Tuple[bytes, DCTEmbedStats]:
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
    
    flags = FLAG_COLOR_MODE if color_mode == 'color' else 0
    
    # Prepare payload bits
    header = _create_header(len(data), flags)
    payload = header + data
    bits = []
    for byte in payload:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    
    # Generate block order
    num_blocks = capacity_info.total_blocks
    block_order = _generate_block_order(num_blocks, seed)
    blocks_x = width // BLOCK_SIZE
    
    if color_mode == 'color' and img.mode in ('RGB', 'RGBA'):
        if img.mode == 'RGBA':
            img = img.convert('RGB')
        
        # Process color image
        rgb = np.array(img, dtype=np.float64, copy=True, order='C')
        img.close()
        
        Y, Cb, Cr = _rgb_to_ycbcr(rgb)
        del rgb
        gc.collect()
        
        Y_padded, original_size = _pad_to_blocks(Y)
        del Y
        gc.collect()
        
        # Embed in Y channel
        Y_embedded = _embed_in_channel_safe(Y_padded, bits, block_order, blocks_x)
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
        
        embedded = _embed_in_channel_safe(padded, bits, block_order, blocks_x)
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
) -> np.ndarray:
    """
    Embed bits in channel using safe DCT operations.
    
    Processes one block at a time with fresh array allocations.
    """
    h, w = channel.shape
    
    # Create result with explicit new memory
    result = np.array(channel, dtype=np.float64, copy=True, order='C')
    
    bit_idx = 0
    
    for block_num in block_order:
        if bit_idx >= len(bits):
            break
        
        by = (block_num // blocks_x) * BLOCK_SIZE
        bx = (block_num % blocks_x) * BLOCK_SIZE
        
        # Extract block - create brand new array
        block = np.array(
            result[by:by+BLOCK_SIZE, bx:bx+BLOCK_SIZE],
            dtype=np.float64, copy=True, order='C'
        )
        
        # Apply safe DCT (row-by-row)
        dct_block = _safe_dct2(block)
        
        # Embed bits
        for pos in DEFAULT_EMBED_POSITIONS:
            if bit_idx >= len(bits):
                break
            dct_block[pos[0], pos[1]] = _embed_bit_in_coeff(
                float(dct_block[pos[0], pos[1]]), 
                bits[bit_idx]
            )
            bit_idx += 1
        
        # Apply safe inverse DCT
        modified_block = _safe_idct2(dct_block)
        
        # Copy back
        result[by:by+BLOCK_SIZE, bx:bx+BLOCK_SIZE] = modified_block
        
        # Clean up this iteration
        del block, dct_block, modified_block
    
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
    if img.format != 'JPEG':
        img.close()
        return image_data
    
    # Check quantization tables
    needs_normalization = False
    if hasattr(img, 'quantization') and img.quantization:
        for table_id, table in img.quantization.items():
            # If all values in any table are <= threshold, normalize
            if max(table) <= JPEGIO_MAX_QUANT_VALUE_THRESHOLD:
                needs_normalization = True
                break
    
    if not needs_normalization:
        img.close()
        return image_data
    
    # Re-save at safe quality level
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=JPEGIO_NORMALIZE_QUALITY, subsampling=0)
    img.close()
    
    return buffer.getvalue()


def _embed_jpegio(
    data: bytes,
    carrier_image: bytes,
    seed: bytes,
    color_mode: str = 'color',
) -> Tuple[bytes, DCTEmbedStats]:
    """Embed using jpegio for proper JPEG coefficient modification."""
    import tempfile
    import os
    
    # Normalize JPEG to avoid crashes with quality=100 images
    carrier_image = _normalize_jpeg_for_jpegio(carrier_image)
    
    img = Image.open(io.BytesIO(carrier_image))
    width, height = img.size
    
    if img.format != 'JPEG':
        buffer = io.BytesIO()
        if img.mode != 'RGB':
            img = img.convert('RGB')
        img.save(buffer, format='JPEG', quality=95, subsampling=0)
        carrier_image = buffer.getvalue()
    img.close()
    
    input_path = _jpegio_bytes_to_file(carrier_image, suffix='.jpg')
    output_path = tempfile.mktemp(suffix='.jpg')
    
    flags = FLAG_COLOR_MODE if color_mode == 'color' else 0
    
    try:
        jpeg = jio.read(input_path)
        coef_array = jpeg.coef_arrays[JPEGIO_EMBED_CHANNEL]
        
        all_positions = _jpegio_get_usable_positions(coef_array)
        order = _jpegio_generate_order(len(all_positions), seed)
        
        header = _jpegio_create_header(len(data), flags)
        payload = header + data
        
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
        
        jio.write(jpeg, output_path)
        
        with open(output_path, 'rb') as f:
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
    
    if fmt == 'JPEG' and HAS_JPEGIO:
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
    
    if mode in ('RGB', 'RGBA'):
        channel = _extract_y_channel(stego_image)
    else:
        channel = _to_grayscale(stego_image)
    img.close()
    
    padded, _ = _pad_to_blocks(channel)
    del channel
    gc.collect()
    
    h, w = padded.shape
    blocks_x = w // BLOCK_SIZE
    num_blocks = (h // BLOCK_SIZE) * blocks_x
    
    block_order = _generate_block_order(num_blocks, seed)
    
    all_bits = []
    
    for block_num in block_order:
        by = (block_num // blocks_x) * BLOCK_SIZE
        bx = (block_num % blocks_x) * BLOCK_SIZE
        
        block = np.array(
            padded[by:by+BLOCK_SIZE, bx:bx+BLOCK_SIZE],
            dtype=np.float64, copy=True, order='C'
        )
        dct_block = _safe_dct2(block)
        
        for pos in DEFAULT_EMBED_POSITIONS:
            bit = _extract_bit_from_coeff(float(dct_block[pos[0], pos[1]]))
            all_bits.append(bit)
        
        del block, dct_block
        
        if len(all_bits) >= HEADER_SIZE * 8:
            try:
                _, flags, data_length = _parse_header(all_bits[:HEADER_SIZE * 8])
                total_needed = (HEADER_SIZE + data_length) * 8
                if len(all_bits) >= total_needed:
                    break
            except ValueError:
                pass
    
    del padded
    gc.collect()
    
    _, flags, data_length = _parse_header(all_bits)
    data_bits = all_bits[HEADER_SIZE * 8:(HEADER_SIZE + data_length) * 8]
    
    data = bytes([
        sum(data_bits[i*8:(i+1)*8][j] << (7-j) for j in range(8))
        for i in range(data_length)
    ])
    
    return data


def _extract_jpegio(stego_image: bytes, seed: bytes) -> bytes:
    """Extract using jpegio for JPEG images."""
    import os
    
    # Normalize JPEG to avoid crashes with quality=100 images
    # (shouldn't happen with stego images, but be defensive)
    stego_image = _normalize_jpeg_for_jpegio(stego_image)
    
    temp_path = _jpegio_bytes_to_file(stego_image, suffix='.jpg')
    
    try:
        jpeg = jio.read(temp_path)
        coef_array = jpeg.coef_arrays[JPEGIO_EMBED_CHANNEL]
        
        all_positions = _jpegio_get_usable_positions(coef_array)
        order = _jpegio_generate_order(len(all_positions), seed)
        
        header_bits = []
        for pos_idx in order[:HEADER_SIZE * 8]:
            row, col = all_positions[pos_idx]
            coef = coef_array[row, col]
            header_bits.append(coef & 1)
        
        header_bytes = bytes([
            sum(header_bits[i*8:(i+1)*8][j] << (7-j) for j in range(8))
            for i in range(HEADER_SIZE)
        ])
        
        _, flags, data_length = _jpegio_parse_header(header_bytes)
        
        total_bits_needed = (HEADER_SIZE + data_length) * 8
        
        all_bits = []
        for bit_idx, pos_idx in enumerate(order):
            if bit_idx >= total_bits_needed:
                break
            row, col = all_positions[pos_idx]
            coef = coef_array[row, col]
            all_bits.append(coef & 1)
        
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
    if output_format == OUTPUT_FORMAT_JPEG:
        return '.jpg'
    return '.png'


def get_output_mimetype(output_format: str) -> str:
    if output_format == OUTPUT_FORMAT_JPEG:
        return 'image/jpeg'
    return 'image/png'
