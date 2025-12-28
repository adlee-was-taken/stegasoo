"""
Stegasoo Steganography Functions

LSB embedding and extraction with pseudo-random pixel selection.
"""

import io
import struct
from typing import Optional

from PIL import Image
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms
from cryptography.hazmat.backends import default_backend

from .models import EmbedStats
from .exceptions import CapacityError, ExtractionError, EmbeddingError


def generate_pixel_indices(key: bytes, num_pixels: int, num_needed: int) -> list[int]:
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
    """
    if num_needed >= num_pixels // 2:
        # If we need many pixels, shuffle all indices
        nonce = b'\x00' * 16
        cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None, backend=default_backend())
        encryptor = cipher.encryptor()
        
        indices = list(range(num_pixels))
        random_bytes = encryptor.update(b'\x00' * (num_pixels * 4))
        
        for i in range(num_pixels - 1, 0, -1):
            j_bytes = random_bytes[(num_pixels - 1 - i) * 4:(num_pixels - i) * 4]
            j = int.from_bytes(j_bytes, 'big') % (i + 1)
            indices[i], indices[j] = indices[j], indices[i]
        
        return indices[:num_needed]
    
    # Optimized path: generate indices directly
    selected = []
    used = set()
    
    nonce = b'\x00' * 16
    cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None, backend=default_backend())
    encryptor = cipher.encryptor()
    
    # Generate more than needed to handle collisions
    bytes_needed = (num_needed * 2) * 4
    random_bytes = encryptor.update(b'\x00' * bytes_needed)
    
    byte_offset = 0
    while len(selected) < num_needed and byte_offset < len(random_bytes) - 4:
        idx = int.from_bytes(random_bytes[byte_offset:byte_offset + 4], 'big') % num_pixels
        byte_offset += 4
        
        if idx not in used:
            used.add(idx)
            selected.append(idx)
    
    # Generate additional if needed (rare)
    while len(selected) < num_needed:
        extra_bytes = encryptor.update(b'\x00' * 4)
        idx = int.from_bytes(extra_bytes, 'big') % num_pixels
        if idx not in used:
            used.add(idx)
            selected.append(idx)
    
    return selected


def embed_in_image(
    carrier_data: bytes,
    encrypted_data: bytes,
    pixel_key: bytes,
    bits_per_channel: int = 1
) -> tuple[bytes, EmbedStats]:
    """
    Embed encrypted data in carrier image using LSB steganography.
    
    Uses pseudo-random pixel selection based on pixel_key to scatter
    the data across the image, defeating statistical analysis.
    
    Args:
        carrier_data: Carrier image bytes
        encrypted_data: Data to embed
        pixel_key: Key for pixel selection
        bits_per_channel: Bits to use per color channel (1-2)
        
    Returns:
        Tuple of (PNG image bytes, EmbedStats)
        
    Raises:
        CapacityError: If carrier is too small
        EmbeddingError: If embedding fails
    """
    try:
        img = Image.open(io.BytesIO(carrier_data))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        pixels = list(img.getdata())
        num_pixels = len(pixels)
        
        bits_per_pixel = 3 * bits_per_channel
        max_bytes = (num_pixels * bits_per_pixel) // 8
        
        # Prepend length
        data_with_len = struct.pack('>I', len(encrypted_data)) + encrypted_data
        
        if len(data_with_len) > max_bytes:
            raise CapacityError(len(data_with_len), max_bytes)
        
        # Convert to binary string
        binary_data = ''.join(format(b, '08b') for b in data_with_len)
        pixels_needed = (len(binary_data) + bits_per_pixel - 1) // bits_per_pixel
        
        # Get pixel indices
        selected_indices = generate_pixel_indices(pixel_key, num_pixels, pixels_needed)
        
        # Embed data
        new_pixels = list(pixels)
        clear_mask = 0xFF ^ ((1 << bits_per_channel) - 1)
        
        bit_idx = 0
        for pixel_idx in selected_indices:
            if bit_idx >= len(binary_data):
                break
            
            r, g, b = new_pixels[pixel_idx]
            
            for channel_idx, channel_val in enumerate([r, g, b]):
                if bit_idx >= len(binary_data):
                    break
                bits = binary_data[bit_idx:bit_idx + bits_per_channel].ljust(bits_per_channel, '0')
                new_val = (channel_val & clear_mask) | int(bits, 2)
                
                if channel_idx == 0:
                    r = new_val
                elif channel_idx == 1:
                    g = new_val
                else:
                    b = new_val
                
                bit_idx += bits_per_channel
            
            new_pixels[pixel_idx] = (r, g, b)
        
        # Create output image
        stego_img = Image.new('RGB', img.size)
        stego_img.putdata(new_pixels)
        
        output = io.BytesIO()
        stego_img.save(output, 'PNG')
        output.seek(0)
        
        stats = EmbedStats(
            pixels_modified=len(selected_indices),
            total_pixels=num_pixels,
            capacity_used=len(data_with_len) / max_bytes,
            bytes_embedded=len(data_with_len)
        )
        
        return output.getvalue(), stats
        
    except CapacityError:
        raise
    except Exception as e:
        raise EmbeddingError(f"Failed to embed data: {e}") from e


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
    """
    try:
        img = Image.open(io.BytesIO(image_data))
        if img.mode != 'RGB':
            img = img.convert('RGB')
        
        pixels = list(img.getdata())
        num_pixels = len(pixels)
        bits_per_pixel = 3 * bits_per_channel
        
        # First, extract enough to get the length (4 bytes = 32 bits)
        initial_pixels = (32 + bits_per_pixel - 1) // bits_per_pixel + 10
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
            data_length = struct.unpack('>I', int(length_bits, 2).to_bytes(4, 'big'))[0]
        except Exception:
            return None
        
        # Sanity check
        max_possible = (num_pixels * bits_per_pixel) // 8 - 4
        if data_length > max_possible or data_length < 10:
            return None
        
        # Extract full data
        total_bits = (4 + data_length) * 8
        pixels_needed = (total_bits + bits_per_pixel - 1) // bits_per_pixel
        
        selected_indices = generate_pixel_indices(pixel_key, num_pixels, pixels_needed)
        
        binary_data = ''
        for pixel_idx in selected_indices:
            r, g, b = pixels[pixel_idx]
            for channel in [r, g, b]:
                for bit_pos in range(bits_per_channel - 1, -1, -1):
                    binary_data += str((channel >> bit_pos) & 1)
        
        data_bits = binary_data[32:32 + (data_length * 8)]
        
        data_bytes = bytearray()
        for i in range(0, len(data_bits), 8):
            byte_bits = data_bits[i:i + 8]
            if len(byte_bits) == 8:
                data_bytes.append(int(byte_bits, 2))
        
        return bytes(data_bytes)
        
    except Exception as e:
        raise ExtractionError(f"Failed to extract data: {e}") from e


def calculate_capacity(image_data: bytes, bits_per_channel: int = 1) -> int:
    """
    Calculate the maximum message capacity of an image.
    
    Args:
        image_data: Image bytes
        bits_per_channel: Bits to use per color channel
        
    Returns:
        Maximum bytes that can be embedded (minus overhead)
    """
    img = Image.open(io.BytesIO(image_data))
    if img.mode != 'RGB':
        img = img.convert('RGB')
    
    num_pixels = img.size[0] * img.size[1]
    bits_per_pixel = 3 * bits_per_channel
    max_bytes = (num_pixels * bits_per_pixel) // 8
    
    # Subtract overhead: 4 bytes length + ~100 bytes header
    return max(0, max_bytes - 104)


def get_image_dimensions(image_data: bytes) -> tuple[int, int]:
    """Get image dimensions without loading full image."""
    img = Image.open(io.BytesIO(image_data))
    return img.size
