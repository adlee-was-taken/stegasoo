"""
DCT Domain Steganography Module (v3.0.1)

Embeds data in DCT coefficients of grayscale images.
Supports PNG (lossless) or JPEG (natural, smaller) output.

This provides an alternative to LSB embedding with different trade-offs:
- More resistant to visual inspection
- Survives some image processing
- Lower capacity (~20% of LSB)
- Works in frequency domain

Requires: scipy (for DCT transforms)
"""

import io
import struct
import hashlib
from dataclasses import dataclass
from typing import Optional, Literal
from enum import Enum

import numpy as np
from PIL import Image

# Check for scipy availability
try:
    from scipy.fftpack import dct, idct
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    dct = None
    idct = None


# ============================================================================
# CONSTANTS
# ============================================================================

# DCT block size (standard 8x8 like JPEG)
BLOCK_SIZE = 8

# Coefficients to use for embedding (mid-frequency, zig-zag order positions)
# Avoiding DC (0,0) and high-frequency edges
# These positions are relatively stable across JPEG compression
EMBED_POSITIONS = [
    (0, 1), (1, 0), (2, 0), (1, 1), (0, 2), (0, 3), (1, 2), (2, 1), (3, 0),
    (4, 0), (3, 1), (2, 2), (1, 3), (0, 4), (0, 5), (1, 4), (2, 3), (3, 2),
    (4, 1), (5, 0), (5, 1), (4, 2), (3, 3), (2, 4), (1, 5), (0, 6), (0, 7),
    (1, 6), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (7, 0),
]

# Use subset of mid-frequency coefficients for better robustness
# Positions 4-20 in zig-zag order (skip very low and very high frequencies)
DEFAULT_EMBED_POSITIONS = EMBED_POSITIONS[4:20]  # 16 coefficients per block

# Quantization step for embedding (larger = more robust, more visible)
QUANT_STEP = 25

# Magic bytes for DCT stego identification
DCT_MAGIC = b'DCTS'

# Header: magic(4) + version(1) + flags(1) + length(4) = 10 bytes
HEADER_SIZE = 10

# Output format options
OUTPUT_FORMAT_PNG = 'png'
OUTPUT_FORMAT_JPEG = 'jpeg'

# JPEG quality for output (high to preserve coefficients)
JPEG_OUTPUT_QUALITY = 95


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
    output_format: str  # 'png' or 'jpeg'


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
    usable_capacity_bytes: int  # After header overhead


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _check_scipy():
    """Raise ImportError if scipy is not available."""
    if not HAS_SCIPY:
        raise ImportError(
            "DCT steganography requires scipy. "
            "Install with: pip install scipy"
        )


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


def _pad_to_blocks(image: np.ndarray) -> tuple[np.ndarray, tuple[int, int]]:
    """Pad image dimensions to be divisible by block size."""
    h, w = image.shape
    new_h = ((h + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
    new_w = ((w + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
    
    if new_h == h and new_w == w:
        return image, (h, w)
    
    padded = np.zeros((new_h, new_w), dtype=image.dtype)
    padded[:h, :w] = image
    
    # Mirror padding for smoother edges
    if new_h > h:
        padded[h:, :w] = image[h-(new_h-h):h, :w][::-1, :]
    if new_w > w:
        padded[:h, w:] = image[:h, w-(new_w-w):w][:, ::-1]
    if new_h > h and new_w > w:
        padded[h:, w:] = image[h-(new_h-h):h, w-(new_w-w):w][::-1, ::-1]
    
    return padded, (h, w)


def _unpad_image(image: np.ndarray, original_size: tuple[int, int]) -> np.ndarray:
    """Remove padding from image."""
    h, w = original_size
    return image[:h, :w]


def _embed_bit_in_coeff(coeff: float, bit: int, quant_step: int = QUANT_STEP) -> float:
    """Embed a single bit into a DCT coefficient using QIM."""
    # Quantization Index Modulation
    quantized = round(coeff / quant_step)
    if (quantized % 2) != bit:
        # Adjust to embed the bit
        if quantized % 2 == 0 and bit == 1:
            quantized += 1 if coeff >= quantized * quant_step else -1
        elif quantized % 2 == 1 and bit == 0:
            quantized += 1 if coeff >= quantized * quant_step else -1
    return quantized * quant_step


def _extract_bit_from_coeff(coeff: float, quant_step: int = QUANT_STEP) -> int:
    """Extract a single bit from a DCT coefficient."""
    quantized = round(coeff / quant_step)
    return quantized % 2


def _generate_block_order(num_blocks: int, seed: bytes) -> list[int]:
    """Generate pseudo-random block order from seed."""
    # Create deterministic RNG from seed
    hash_bytes = hashlib.sha256(seed).digest()
    rng = np.random.RandomState(int.from_bytes(hash_bytes[:4], 'big'))
    
    order = list(range(num_blocks))
    rng.shuffle(order)
    return order


def _save_stego_image(
    image: np.ndarray, 
    output_format: str = OUTPUT_FORMAT_PNG
) -> bytes:
    """Save stego image in specified format."""
    # Clip to valid range and convert to uint8
    clipped = np.clip(image, 0, 255).astype(np.uint8)
    img = Image.fromarray(clipped, mode='L')
    
    buffer = io.BytesIO()
    
    if output_format == OUTPUT_FORMAT_JPEG:
        # High-quality JPEG with no chroma subsampling
        img.save(
            buffer, 
            format='JPEG', 
            quality=JPEG_OUTPUT_QUALITY, 
            subsampling=0,  # 4:4:4 - no subsampling
            optimize=True
        )
    else:
        # PNG (lossless, default)
        img.save(buffer, format='PNG', optimize=True)
    
    return buffer.getvalue()


def _create_header(data_length: int, flags: int = 0) -> bytes:
    """Create DCT stego header."""
    # Header format: MAGIC(4) + VERSION(1) + FLAGS(1) + LENGTH(4)
    version = 1
    return struct.pack('>4sBBI', DCT_MAGIC, version, flags, data_length)


def _parse_header(header_bits: list[int]) -> tuple[int, int, int]:
    """Parse header from extracted bits. Returns (version, flags, data_length)."""
    if len(header_bits) < HEADER_SIZE * 8:
        raise ValueError("Insufficient header data")
    
    # Convert bits to bytes
    header_bytes = bytes([
        sum(header_bits[i*8:(i+1)*8][j] << (7-j) for j in range(8))
        for i in range(HEADER_SIZE)
    ])
    
    magic, version, flags, length = struct.unpack('>4sBBI', header_bytes)
    
    if magic != DCT_MAGIC:
        raise ValueError("Invalid DCT stego magic bytes - not a DCT stego image")
    
    return version, flags, length


# ============================================================================
# PUBLIC API
# ============================================================================

def has_dct_support() -> bool:
    """Check if DCT steganography is available."""
    return HAS_SCIPY


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
    
    # Calculate blocks
    blocks_x = width // BLOCK_SIZE
    blocks_y = height // BLOCK_SIZE
    total_blocks = blocks_x * blocks_y
    
    # Bits per block (using selected coefficient positions)
    bits_per_block = len(DEFAULT_EMBED_POSITIONS)
    
    # Total capacity
    total_bits = total_blocks * bits_per_block
    total_bytes = total_bits // 8
    
    # Usable capacity (minus header)
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
    """
    Check if data will fit in the image using DCT embedding.
    
    Args:
        data_length: Length of data in bytes
        image_data: Carrier image bytes
        
    Returns:
        True if data fits, False otherwise
    """
    capacity = calculate_dct_capacity(image_data)
    return data_length <= capacity.usable_capacity_bytes


def estimate_capacity_comparison(image_data: bytes) -> dict:
    """
    Compare LSB and DCT capacity for an image.
    
    Args:
        image_data: Image file bytes
        
    Returns:
        Dict with 'lsb' and 'dct' capacity info
    """
    img = Image.open(io.BytesIO(image_data))
    width, height = img.size
    pixels = width * height
    
    # LSB capacity (3 bits per pixel for RGB, simplified)
    lsb_bytes = (pixels * 3) // 8
    
    # DCT capacity
    if HAS_SCIPY:
        dct_info = calculate_dct_capacity(image_data)
        dct_bytes = dct_info.usable_capacity_bytes
    else:
        # Estimate without scipy
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
        }
    }


def embed_in_dct(
    data: bytes,
    carrier_image: bytes,
    seed: bytes,
    output_format: str = OUTPUT_FORMAT_PNG,
) -> tuple[bytes, DCTEmbedStats]:
    """
    Embed data into image using DCT coefficient modification.
    
    Args:
        data: Data to embed
        carrier_image: Carrier image bytes
        seed: Seed for pseudo-random block selection
        output_format: Output format - 'png' (default, lossless) or 'jpeg' (smaller)
        
    Returns:
        Tuple of (stego_image_bytes, stats)
        
    Raises:
        ImportError: If scipy is not available
        ValueError: If data is too large for carrier
    """
    _check_scipy()
    
    # Validate output format
    if output_format not in (OUTPUT_FORMAT_PNG, OUTPUT_FORMAT_JPEG):
        raise ValueError(f"Invalid output format: {output_format}. Use 'png' or 'jpeg'")
    
    # Calculate capacity
    capacity_info = calculate_dct_capacity(carrier_image)
    
    if len(data) > capacity_info.usable_capacity_bytes:
        raise ValueError(
            f"Data too large ({len(data)} bytes) for carrier "
            f"(capacity: {capacity_info.usable_capacity_bytes} bytes)"
        )
    
    # Prepare image
    image = _to_grayscale(carrier_image)
    padded, original_size = _pad_to_blocks(image)
    
    # Create header + data
    header = _create_header(len(data))
    payload = header + data
    
    # Convert payload to bits
    bits = []
    for byte in payload:
        for i in range(7, -1, -1):
            bits.append((byte >> i) & 1)
    
    # Generate block order
    num_blocks = capacity_info.total_blocks
    block_order = _generate_block_order(num_blocks, seed)
    
    # Embed bits
    bit_idx = 0
    blocks_used = 0
    h, w = padded.shape
    
    for block_num in block_order:
        if bit_idx >= len(bits):
            break
            
        # Calculate block position
        by = (block_num // (w // BLOCK_SIZE)) * BLOCK_SIZE
        bx = (block_num % (w // BLOCK_SIZE)) * BLOCK_SIZE
        
        # Extract and transform block
        block = padded[by:by+BLOCK_SIZE, bx:bx+BLOCK_SIZE].copy()
        dct_block = _dct2(block)
        
        # Embed bits in selected coefficients
        for pos in DEFAULT_EMBED_POSITIONS:
            if bit_idx >= len(bits):
                break
            dct_block[pos] = _embed_bit_in_coeff(dct_block[pos], bits[bit_idx])
            bit_idx += 1
        
        # Inverse transform and store
        modified_block = _idct2(dct_block)
        padded[by:by+BLOCK_SIZE, bx:bx+BLOCK_SIZE] = modified_block
        blocks_used += 1
    
    # Remove padding and save
    result = _unpad_image(padded, original_size)
    stego_bytes = _save_stego_image(result, output_format)
    
    stats = DCTEmbedStats(
        blocks_used=blocks_used,
        blocks_available=capacity_info.total_blocks,
        bits_embedded=len(bits),
        capacity_bits=capacity_info.total_capacity_bits,
        usage_percent=(len(bits) / capacity_info.total_capacity_bits) * 100,
        image_width=original_size[1],
        image_height=original_size[0],
        output_format=output_format,
    )
    
    return stego_bytes, stats


def extract_from_dct(
    stego_image: bytes,
    seed: bytes,
) -> bytes:
    """
    Extract data from DCT stego image.
    
    Args:
        stego_image: Stego image bytes
        seed: Same seed used for embedding
        
    Returns:
        Extracted data bytes
        
    Raises:
        ImportError: If scipy is not available
        ValueError: If image is not a valid DCT stego image
    """
    _check_scipy()
    
    # Prepare image
    image = _to_grayscale(stego_image)
    padded, original_size = _pad_to_blocks(image)
    
    # Calculate capacity
    h, w = padded.shape
    blocks_x = w // BLOCK_SIZE
    blocks_y = h // BLOCK_SIZE
    num_blocks = blocks_x * blocks_y
    
    # Generate same block order
    block_order = _generate_block_order(num_blocks, seed)
    
    # Extract all bits (we'll stop when we have enough based on header)
    all_bits = []
    
    for block_num in block_order:
        by = (block_num // blocks_x) * BLOCK_SIZE
        bx = (block_num % blocks_x) * BLOCK_SIZE
        
        block = padded[by:by+BLOCK_SIZE, bx:bx+BLOCK_SIZE]
        dct_block = _dct2(block)
        
        for pos in DEFAULT_EMBED_POSITIONS:
            bit = _extract_bit_from_coeff(dct_block[pos])
            all_bits.append(bit)
        
        # Check if we have enough for header
        if len(all_bits) >= HEADER_SIZE * 8:
            try:
                _, _, data_length = _parse_header(all_bits[:HEADER_SIZE * 8])
                total_needed = (HEADER_SIZE + data_length) * 8
                if len(all_bits) >= total_needed:
                    break
            except ValueError:
                # Not enough data yet or invalid, continue
                pass
    
    # Parse header
    version, flags, data_length = _parse_header(all_bits)
    
    # Extract data bits
    data_bits = all_bits[HEADER_SIZE * 8:(HEADER_SIZE + data_length) * 8]
    
    # Convert bits to bytes
    data = bytes([
        sum(data_bits[i*8:(i+1)*8][j] << (7-j) for j in range(8))
        for i in range(data_length)
    ])
    
    return data


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
