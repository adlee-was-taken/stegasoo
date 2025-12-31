"""
Stegasoo Steganography Functions

LSB embedding and extraction with pseudo-random pixel selection.
"""

import io
import struct
from typing import Optional, Tuple, List, Union

from PIL import Image
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.backends import default_backend

from .models import EmbedStats, FilePayload
from .exceptions import CapacityError, ExtractionError, EmbeddingError
from .debug import debug


# Lossless formats that preserve LSB data
LOSSLESS_FORMATS = {'PNG', 'BMP', 'TIFF'}

# Format to extension mapping
FORMAT_TO_EXT = {
    'PNG': 'png',
    'BMP': 'bmp',
    'TIFF': 'tiff',
}

# Extension to PIL format mapping
EXT_TO_FORMAT = {
    'png': 'PNG',
    'bmp': 'BMP',
    'tiff': 'TIFF',
    'tif': 'TIFF',
}

# Overhead constants for capacity estimation
HEADER_OVERHEAD = 104  # Magic + version + date + salt + iv + tag
LENGTH_PREFIX = 4      # 4 bytes for payload length
ENCRYPTION_OVERHEAD = HEADER_OVERHEAD + LENGTH_PREFIX


def get_output_format(input_format: Optional[str]) -> Tuple[str, str]:
    """
    Determine the output format based on input format.
    
    Args:
        input_format: PIL format string of input image (e.g., 'JPEG', 'PNG')
        
    Returns:
        Tuple of (PIL format string, file extension) for output
        Falls back to PNG for lossy or unknown formats.
        
    Example:
        >>> get_output_format('JPEG')
        ('PNG', 'png')
        >>> get_output_format('PNG')
        ('PNG', 'png')
    """
    debug.validate(input_format is None or isinstance(input_format, str),
                "Input format must be string or None")
    
    if input_format and input_format.upper() in LOSSLESS_FORMATS:
        fmt = input_format.upper()
        ext = FORMAT_TO_EXT.get(fmt, 'png')
        debug.print(f"Using lossless format: {fmt} -> .{ext}")
        return fmt, ext
    
    # Default to PNG for lossy formats (JPEG, GIF) or unknown
    debug.print(f"Input format {input_format} is lossy or unknown, defaulting to PNG")
    return 'PNG', 'png'


def will_fit(
    payload: Union[str, bytes, FilePayload, int],
    carrier_image: bytes,
    bits_per_channel: int = 1,
    include_compression_estimate: bool = True,
) -> dict:
    """
    Check if a payload will fit in a carrier image without performing encryption.
    
    This is a lightweight pre-check to avoid wasted work on payloads that
    are too large. For accurate results with compression, the actual compressed
    size may vary.
    
    Args:
        payload: Message string, raw bytes, FilePayload, or size in bytes
        carrier_image: Carrier image bytes
        bits_per_channel: Bits to use per color channel (1-2)
        include_compression_estimate: Estimate compressed size (requires payload data)
        
    Returns:
        Dict with:
        - fits: bool - Whether payload will fit
        - payload_size: int - Raw payload size in bytes
        - estimated_encrypted_size: int - Estimated size after encryption + overhead
        - capacity: int - Available capacity in bytes
        - usage_percent: float - Estimated capacity usage (0-100)
        - headroom: int - Bytes remaining (negative if won't fit)
        - compressed_estimate: int | None - Estimated compressed size (if applicable)
        
    Example:
        >>> result = will_fit("Hello world", carrier_bytes)
        >>> result['fits']
        True
        >>> result['usage_percent']
        0.5
        
        >>> result = will_fit(50000, carrier_bytes)  # Check if 50KB would fit
        >>> result['fits']
        False
    """
    # Determine payload size
    if isinstance(payload, int):
        payload_size = payload
        payload_data = None
    elif isinstance(payload, str):
        payload_data = payload.encode('utf-8')
        payload_size = len(payload_data)
    elif isinstance(payload, FilePayload):
        payload_data = payload.data
        # Account for filename/mime metadata
        filename_overhead = len(payload.filename.encode('utf-8')) if payload.filename else 0
        mime_overhead = len(payload.mime_type.encode('utf-8')) if payload.mime_type else 0
        payload_size = len(payload.data) + filename_overhead + mime_overhead + 5  # +5 for length prefixes + type byte
    else:
        payload_data = payload
        payload_size = len(payload)
    
    # Calculate capacity
    capacity = calculate_capacity(carrier_image, bits_per_channel)
    
    # Estimate encrypted size (payload + random padding + overhead)
    # Padding adds 64-319 bytes, averaging ~190
    estimated_padding = 190
    estimated_encrypted_size = payload_size + estimated_padding + ENCRYPTION_OVERHEAD
    
    # Compression estimate
    compressed_estimate = None
    if include_compression_estimate and payload_data is not None and len(payload_data) >= 64:
        try:
            import zlib
            compressed = zlib.compress(payload_data, level=6)
            # Add compression header overhead (9 bytes)
            compressed_size = len(compressed) + 9
            if compressed_size < payload_size:
                compressed_estimate = compressed_size
                # Use compressed size for fit calculation
                estimated_encrypted_size = compressed_size + estimated_padding + ENCRYPTION_OVERHEAD
        except Exception:
            pass  # Ignore compression errors
    
    headroom = capacity - estimated_encrypted_size
    fits = headroom >= 0
    usage_percent = (estimated_encrypted_size / capacity * 100) if capacity > 0 else 100.0
    
    result = {
        'fits': fits,
        'payload_size': payload_size,
        'estimated_encrypted_size': estimated_encrypted_size,
        'capacity': capacity,
        'usage_percent': min(usage_percent, 100.0),
        'headroom': headroom,
        'compressed_estimate': compressed_estimate,
    }
    
    debug.print(f"will_fit: payload={payload_size}, encrypted~={estimated_encrypted_size}, "
                f"capacity={capacity}, fits={fits}")
    
    return result


@debug.time
def generate_pixel_indices(key: bytes, num_pixels: int, num_needed: int) -> List[int]:
    """
    Generate pseudo-random pixel indices for embedding.
    
    Uses ChaCha20 as a CSPRNG seeded by the key to deterministically
    select which pixels will hold hidden data.
    
    Args:
        key: 32-byte key for pixel selection
        num_pixels: Total pixels in image
        num_needed: Number of pixels needed for embedding
        
    Returns:
        List of pixel indices
        
    Note:
        Optimizes for both small and large num_needed values.
    """
    debug.validate(len(key) == 32, f"Pixel key must be 32 bytes, got {len(key)}")
    debug.validate(num_pixels > 0, f"Number of pixels must be positive, got {num_pixels}")
    debug.validate(num_needed > 0, f"Number needed must be positive, got {num_needed}")
    debug.validate(num_needed <= num_pixels, 
                f"Cannot select {num_needed} pixels from {num_pixels} available")
    
    debug.print(f"Generating {num_needed} pixel indices from {num_pixels} total pixels")
    
    if num_needed >= num_pixels // 2:
        # If we need many pixels, shuffle all indices
        debug.print(f"Using full shuffle (needed {num_needed}/{num_pixels} pixels)")
        nonce = b'\x00' * 16
        cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None, backend=default_backend())
        encryptor = cipher.encryptor()
        
        indices = list(range(num_pixels))
        random_bytes = encryptor.update(b'\x00' * (num_pixels * 4))
        
        # Fisher-Yates shuffle using CSPRNG
        for i in range(num_pixels - 1, 0, -1):
            j_bytes = random_bytes[(num_pixels - 1 - i) * 4:(num_pixels - i) * 4]
            j = int.from_bytes(j_bytes, 'big') % (i + 1)
            indices[i], indices[j] = indices[j], indices[i]
        
        selected = indices[:num_needed]
        debug.print(f"Generated {len(selected)} indices via shuffle")
        return selected
    
    # Optimized path: generate indices directly (for smaller selections)
    debug.print(f"Using optimized selection (needed {num_needed}/{num_pixels} pixels)")
    selected = []
    used = set()
    
    nonce = b'\x00' * 16
    cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None, backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Generate more than needed to handle collisions
    bytes_needed = (num_needed * 2) * 4
    random_bytes = encryptor.update(b'\x00' * bytes_needed)
    
    byte_offset = 0
    collisions = 0
    while len(selected) < num_needed and byte_offset < len(random_bytes) - 4:
        idx = int.from_bytes(random_bytes[byte_offset:byte_offset + 4], 'big') % num_pixels
        byte_offset += 4
        
        if idx not in used:
            used.add(idx)
            selected.append(idx)
        else:
            collisions += 1
    
    # Generate additional if needed (rare)
    if len(selected) < num_needed:
        debug.print(f"Need {num_needed - len(selected)} more indices, generating...")
        extra_needed = num_needed - len(selected)
        for _ in range(extra_needed * 2):  # Try twice as many to account for collisions
            extra_bytes = encryptor.update(b'\x00' * 4)
            idx = int.from_bytes(extra_bytes, 'big') % num_pixels
            if idx not in used:
                used.add(idx)
                selected.append(idx)
                if len(selected) == num_needed:
                    break
    
    debug.print(f"Generated {len(selected)} indices with {collisions} collisions")
    debug.validate(len(selected) == num_needed,
                f"Failed to generate enough indices: {len(selected)}/{num_needed}")
    return selected


@debug.time
def embed_in_image(
    carrier_data: bytes,
    encrypted_data: bytes,
    pixel_key: bytes,
    bits_per_channel: int = 1,
    output_format: Optional[str] = None
) -> Tuple[bytes, EmbedStats, str]:
    """
    Embed encrypted data in carrier image using LSB steganography.
    
    Uses pseudo-random pixel selection based on pixel_key to scatter
    the data across the image, defeating statistical analysis.
    
    Note: Output images have all metadata (EXIF, etc.) stripped automatically.
    
    Args:
        carrier_data: Carrier image bytes
        encrypted_data: Data to embed
        pixel_key: Key for pixel selection
        bits_per_channel: Bits to use per color channel (1-2)
        output_format: Force specific output format (PNG, BMP). 
                       If None, auto-detect from carrier (lossless) or default to PNG.
        
    Returns:
        Tuple of (image bytes, EmbedStats, file extension)
        
    Raises:
        CapacityError: If carrier is too small
        EmbeddingError: If embedding fails
        
    Example:
        >>> stego_bytes, stats, ext = embed_in_image(carrier, encrypted, key)
        >>> stats.pixels_modified
        1500
    """
    debug.print(f"Embedding {len(encrypted_data)} bytes into image")
    debug.data(pixel_key, "Pixel key for embedding")
    debug.validate(bits_per_channel in (1, 2), 
                f"bits_per_channel must be 1 or 2, got {bits_per_channel}")
    debug.validate(len(pixel_key) == 32,
                f"Pixel key must be 32 bytes, got {len(pixel_key)}")
    
    try:
        img_file = Image.open(io.BytesIO(carrier_data))
        input_format = img_file.format
        
        debug.print(f"Carrier image: {img_file.size[0]}x{img_file.size[1]}, format: {input_format}")
        
        # Convert to RGB - this returns Image.Image, not ImageFile
        img: Image.Image = img_file.convert('RGB') if img_file.mode != 'RGB' else img_file.copy()
        if img_file.mode != 'RGB':
            debug.print(f"Converting image from {img_file.mode} to RGB")
        
        pixels = list(img.getdata())
        num_pixels = len(pixels)
        
        bits_per_pixel = 3 * bits_per_channel
        max_bytes = (num_pixels * bits_per_pixel) // 8
        
        debug.print(f"Image capacity: {max_bytes} bytes at {bits_per_channel} bit(s)/channel")
        
        # Prepend length
        data_with_len = struct.pack('>I', len(encrypted_data)) + encrypted_data
        
        if len(data_with_len) > max_bytes:
            debug.print(f"Capacity error: need {len(data_with_len)}, have {max_bytes}")
            raise CapacityError(len(data_with_len), max_bytes)
        
        debug.print(f"Total data to embed: {len(data_with_len)} bytes "
                   f"({len(data_with_len)/max_bytes*100:.1f}% of capacity)")
        
        # Convert to binary string
        binary_data = ''.join(format(b, '08b') for b in data_with_len)
        pixels_needed = (len(binary_data) + bits_per_pixel - 1) // bits_per_pixel
        
        debug.print(f"Need {pixels_needed} pixels to embed {len(binary_data)} bits")
        
        # Get pixel indices
        selected_indices = generate_pixel_indices(pixel_key, num_pixels, pixels_needed)
        
        # Embed data
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
                bits = binary_data[bit_idx:bit_idx + bits_per_channel].ljust(bits_per_channel, '0')
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
        
        # Create output image (fresh image = no metadata/EXIF carried over)
        stego_img = Image.new('RGB', img.size)
        stego_img.putdata(new_pixels)
        
        # Determine output format
        if output_format:
            out_fmt = output_format.upper()
            out_ext = FORMAT_TO_EXT.get(out_fmt, 'png')
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
            bytes_embedded=len(data_with_len)
        )
        
        debug.print(f"Embedding complete: {out_fmt} image, {len(output.getvalue())} bytes")
        return output.getvalue(), stats, out_ext
        
    except CapacityError:
        raise
    except Exception as e:
        debug.exception(e, "embed_in_image")
        raise EmbeddingError(f"Failed to embed data: {e}") from e


@debug.time
def extract_from_image(
    image_data: bytes,
    pixel_key: bytes,
    bits_per_channel: int = 1
) -> Optional[bytes]:
    """
    Extract hidden data from a stego image.
    
    Args:
        image_data: Stego image bytes
        pixel_key: Key for pixel selection (must match encoding)
        bits_per_channel: Bits per channel (must match encoding)
        
    Returns:
        Extracted data bytes, or None if extraction fails
        
    Raises:
        ExtractionError: If extraction fails critically
        
    Example:
        >>> extracted = extract_from_image(stego_bytes, key)
        >>> len(extracted)
        1024
    """
    debug.print(f"Extracting from {len(image_data)} byte image")
    debug.data(pixel_key, "Pixel key for extraction")
    debug.validate(bits_per_channel in (1, 2),
                f"bits_per_channel must be 1 or 2, got {bits_per_channel}")
    
    try:
        img_file = Image.open(io.BytesIO(image_data))
        debug.print(f"Image: {img_file.size[0]}x{img_file.size[1]}, format: {img_file.format}")
        
        # Convert to RGB
        img: Image.Image = img_file.convert('RGB') if img_file.mode != 'RGB' else img_file.copy()
        if img_file.mode != 'RGB':
            debug.print(f"Converting image from {img_file.mode} to RGB")
        
        pixels = list(img.getdata())
        num_pixels = len(pixels)
        bits_per_pixel = 3 * bits_per_channel
        
        debug.print(f"Image has {num_pixels} pixels, {bits_per_pixel} bits/pixel")
        
        # First, extract enough to get the length (4 bytes = 32 bits)
        initial_pixels = (32 + bits_per_pixel - 1) // bits_per_pixel + 10
        debug.print(f"Extracting initial {initial_pixels} pixels to find length")
        
        initial_indices = generate_pixel_indices(pixel_key, num_pixels, initial_pixels)
        
        binary_data = ''
        for pixel_idx in initial_indices:
            r, g, b = pixels[pixel_idx]
            for channel in [r, g, b]:
                for bit_pos in range(bits_per_channel - 1, -1, -1):
                    binary_data += str((channel >> bit_pos) & 1)
        
        # Parse length
        try:
            length_bits = binary_data[:32]
            if len(length_bits) < 32:
                debug.print(f"Not enough bits for length: {len(length_bits)}/32")
                return None
            
            data_length = struct.unpack('>I', int(length_bits, 2).to_bytes(4, 'big'))[0]
            debug.print(f"Extracted length: {data_length} bytes")
        except Exception as e:
            debug.print(f"Failed to parse length: {e}")
            return None
        
        # Sanity check
        max_possible = (num_pixels * bits_per_pixel) // 8 - 4
        if data_length > max_possible or data_length < 10:
            debug.print(f"Invalid data length: {data_length} (max possible: {max_possible})")
            return None
        
        # Extract full data
        total_bits = (4 + data_length) * 8
        pixels_needed = (total_bits + bits_per_pixel - 1) // bits_per_pixel
        
        debug.print(f"Need {pixels_needed} pixels to extract {data_length} bytes")
        
        selected_indices = generate_pixel_indices(pixel_key, num_pixels, pixels_needed)
        
        binary_data = ''
        for pixel_idx in selected_indices:
            r, g, b = pixels[pixel_idx]
            for channel in [r, g, b]:
                for bit_pos in range(bits_per_channel - 1, -1, -1):
                    binary_data += str((channel >> bit_pos) & 1)
        
        data_bits = binary_data[32:32 + (data_length * 8)]
        
        if len(data_bits) < data_length * 8:
            debug.print(f"Insufficient bits: {len(data_bits)} < {data_length * 8}")
            return None
        
        data_bytes = bytearray()
        for i in range(0, len(data_bits), 8):
            byte_bits = data_bits[i:i + 8]
            if len(byte_bits) == 8:
                data_bytes.append(int(byte_bits, 2))
        
        debug.print(f"Successfully extracted {len(data_bytes)} bytes")
        return bytes(data_bytes)
        
    except Exception as e:
        debug.exception(e, "extract_from_image")
        raise ExtractionError(f"Failed to extract data: {e}") from e


def calculate_capacity(image_data: bytes, bits_per_channel: int = 1) -> int:
    """
    Calculate the maximum message capacity of an image.
    
    Args:
        image_data: Image bytes
        bits_per_channel: Bits to use per color channel
        
    Returns:
        Maximum bytes that can be embedded (minus overhead)
        
    Example:
        >>> capacity = calculate_capacity(image_bytes)
        >>> capacity
        12000
    """
    debug.validate(bits_per_channel in (1, 2),
                f"bits_per_channel must be 1 or 2, got {bits_per_channel}")
    
    img_file = Image.open(io.BytesIO(image_data))
    img: Image.Image = img_file.convert('RGB') if img_file.mode != 'RGB' else img_file
    
    num_pixels = img.size[0] * img.size[1]
    bits_per_pixel = 3 * bits_per_channel
    max_bytes = (num_pixels * bits_per_pixel) // 8
    
    # Subtract overhead: 4 bytes length + ~100 bytes header
    capacity = max(0, max_bytes - ENCRYPTION_OVERHEAD)
    debug.print(f"Image capacity: {capacity} bytes at {bits_per_channel} bit(s)/channel")
    return capacity


def get_image_dimensions(image_data: bytes) -> Tuple[int, int]:
    """
    Get image dimensions without loading full image.
    
    Args:
        image_data: Image bytes
        
    Returns:
        Tuple of (width, height)
        
    Example:
        >>> width, height = get_image_dimensions(image_bytes)
        >>> width, height
        (800, 600)
    """
    debug.validate(len(image_data) > 0, "Image data cannot be empty")
    
    img = Image.open(io.BytesIO(image_data))
    dimensions = img.size
    debug.print(f"Image dimensions: {dimensions[0]}x{dimensions[1]}")
    return dimensions


def get_image_format(image_data: bytes) -> Optional[str]:
    """
    Get image format (PIL format string like 'PNG', 'JPEG').
    
    Args:
        image_data: Image bytes
        
    Returns:
        Format string or None if invalid
        
    Example:
        >>> format = get_image_format(image_bytes)
        >>> format
        'PNG'
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        format_str = img.format
        debug.print(f"Image format: {format_str}")
        return format_str
    except Exception as e:
        debug.print(f"Failed to get image format: {e}")
        return None


def is_lossless_format(image_data: bytes) -> bool:
    """
    Check if image is in a lossless format suitable for steganography.
    
    Args:
        image_data: Image bytes
        
    Returns:
        True if format is lossless (PNG, BMP, TIFF)
        
    Example:
        >>> is_lossless_format(image_bytes)
        True
    """
    fmt = get_image_format(image_data)
    is_lossless = fmt is not None and fmt.upper() in LOSSLESS_FORMATS
    debug.print(f"Image is lossless: {is_lossless} (format: {fmt})")
    return is_lossless
