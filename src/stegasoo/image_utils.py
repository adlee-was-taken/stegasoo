"""
Stegasoo Image Utilities (v3.2.0)

Functions for analyzing images and comparing capacity.
"""

from typing import Optional
import io
from PIL import Image

from .models import ImageInfo, CapacityComparison
from .steganography import calculate_capacity, has_dct_support
from .constants import EMBED_MODE_LSB, EMBED_MODE_DCT
from .debug import debug


def get_image_info(image_data: bytes) -> ImageInfo:
    """
    Get detailed information about an image.
    
    Args:
        image_data: Image file bytes
        
    Returns:
        ImageInfo with dimensions, format, capacity estimates
        
    Example:
        >>> info = get_image_info(carrier_bytes)
        >>> print(f"{info.width}x{info.height}, {info.lsb_capacity_kb} KB capacity")
    """
    img = Image.open(io.BytesIO(image_data))
    
    width, height = img.size
    pixels = width * height
    format_str = img.format or "Unknown"
    mode = img.mode
    
    # Calculate LSB capacity
    lsb_capacity = calculate_capacity(image_data, bits_per_channel=1)
    
    # Calculate DCT capacity if available
    dct_capacity = None
    if has_dct_support():
        try:
            from .dct_steganography import calculate_dct_capacity
            dct_info = calculate_dct_capacity(image_data)
            dct_capacity = dct_info.usable_capacity_bytes
        except Exception as e:
            debug.print(f"Could not calculate DCT capacity: {e}")
    
    info = ImageInfo(
        width=width,
        height=height,
        pixels=pixels,
        format=format_str,
        mode=mode,
        file_size=len(image_data),
        lsb_capacity_bytes=lsb_capacity,
        lsb_capacity_kb=lsb_capacity / 1024,
        dct_capacity_bytes=dct_capacity,
        dct_capacity_kb=dct_capacity / 1024 if dct_capacity else None,
    )
    
    debug.print(f"Image info: {width}x{height}, LSB={lsb_capacity} bytes, "
                f"DCT={dct_capacity or 'N/A'} bytes")
    
    return info


def compare_capacity(
    carrier_image: bytes,
    reference_photo: Optional[bytes] = None,
) -> CapacityComparison:
    """
    Compare embedding capacity between LSB and DCT modes.
    
    Args:
        carrier_image: Carrier image bytes
        reference_photo: Optional reference photo (not used in v3.2.0, kept for API compatibility)
        
    Returns:
        CapacityComparison with capacity info for both modes
        
    Example:
        >>> comparison = compare_capacity(carrier_bytes)
        >>> print(f"LSB: {comparison.lsb_kb:.1f} KB")
        >>> print(f"DCT: {comparison.dct_kb:.1f} KB")
    """
    img = Image.open(io.BytesIO(carrier_image))
    width, height = img.size
    
    # LSB capacity
    lsb_bytes = calculate_capacity(carrier_image, bits_per_channel=1)
    lsb_kb = lsb_bytes / 1024
    
    # DCT capacity
    dct_available = has_dct_support()
    dct_bytes = None
    dct_kb = None
    
    if dct_available:
        try:
            from .dct_steganography import calculate_dct_capacity
            dct_info = calculate_dct_capacity(carrier_image)
            dct_bytes = dct_info.usable_capacity_bytes
            dct_kb = dct_bytes / 1024
        except Exception as e:
            debug.print(f"DCT capacity calculation failed: {e}")
            dct_available = False
    
    comparison = CapacityComparison(
        image_width=width,
        image_height=height,
        lsb_available=True,
        lsb_bytes=lsb_bytes,
        lsb_kb=lsb_kb,
        lsb_output_format="PNG/BMP (color)",
        dct_available=dct_available,
        dct_bytes=dct_bytes,
        dct_kb=dct_kb,
        dct_output_formats=["PNG (grayscale)", "JPEG (grayscale)"] if dct_available else None,
        dct_ratio_vs_lsb=(dct_bytes / lsb_bytes * 100) if dct_bytes else None,
    )
    
    debug.print(f"Capacity comparison: LSB={lsb_kb:.1f}KB, DCT={dct_kb or 'N/A'}KB")
    
    return comparison


def validate_carrier_capacity(
    carrier_image: bytes,
    payload_size: int,
    embed_mode: str = EMBED_MODE_LSB,
) -> dict:
    """
    Check if a payload will fit in a carrier image.
    
    Args:
        carrier_image: Carrier image bytes
        payload_size: Size of payload in bytes
        embed_mode: 'lsb' or 'dct'
        
    Returns:
        Dict with 'fits', 'capacity', 'usage_percent', 'headroom'
    """
    from .steganography import calculate_capacity_by_mode
    
    capacity_info = calculate_capacity_by_mode(carrier_image, embed_mode)
    capacity = capacity_info['capacity_bytes']
    
    # Add encryption overhead estimate
    estimated_size = payload_size + 200  # Approximate overhead
    
    fits = estimated_size <= capacity
    usage_percent = (estimated_size / capacity * 100) if capacity > 0 else 100.0
    headroom = capacity - estimated_size
    
    return {
        'fits': fits,
        'capacity': capacity,
        'payload_size': payload_size,
        'estimated_size': estimated_size,
        'usage_percent': min(usage_percent, 100.0),
        'headroom': headroom,
        'mode': embed_mode,
    }
