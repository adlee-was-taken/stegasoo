"""
Stegasoo Compression Module

Provides transparent compression/decompression for payloads before encryption.
Supports multiple algorithms with automatic detection on decompression.
"""

import struct
import zlib
from enum import IntEnum

# Optional LZ4 support (faster, slightly worse ratio)
try:
    import lz4.frame
    HAS_LZ4 = True
except ImportError:
    HAS_LZ4 = False


class CompressionAlgorithm(IntEnum):
    """Supported compression algorithms."""
    NONE = 0
    ZLIB = 1
    LZ4 = 2


# Magic bytes for compressed payloads
COMPRESSION_MAGIC = b'\x00CMP'

# Minimum size to bother compressing (small data often expands)
MIN_COMPRESS_SIZE = 64

# Compression level for zlib (1-9, higher = better ratio but slower)
ZLIB_LEVEL = 6


class CompressionError(Exception):
    """Raised when compression/decompression fails."""
    pass


def compress(data: bytes, algorithm: CompressionAlgorithm = CompressionAlgorithm.ZLIB) -> bytes:
    """
    Compress data with specified algorithm.

    Format: MAGIC (4) + ALGORITHM (1) + ORIGINAL_SIZE (4) + COMPRESSED_DATA

    Args:
        data: Raw bytes to compress
        algorithm: Compression algorithm to use

    Returns:
        Compressed data with header, or original data if compression didn't help
    """
    if len(data) < MIN_COMPRESS_SIZE:
        # Too small to benefit from compression
        return _wrap_uncompressed(data)

    if algorithm == CompressionAlgorithm.NONE:
        return _wrap_uncompressed(data)

    elif algorithm == CompressionAlgorithm.ZLIB:
        compressed = zlib.compress(data, level=ZLIB_LEVEL)

    elif algorithm == CompressionAlgorithm.LZ4:
        if not HAS_LZ4:
            # Fall back to zlib if LZ4 not available
            compressed = zlib.compress(data, level=ZLIB_LEVEL)
            algorithm = CompressionAlgorithm.ZLIB
        else:
            compressed = lz4.frame.compress(data)
    else:
        raise CompressionError(f"Unknown compression algorithm: {algorithm}")

    # Only use compression if it actually reduced size
    if len(compressed) >= len(data):
        return _wrap_uncompressed(data)

    # Build header: MAGIC + algorithm + original_size + compressed_data
    header = COMPRESSION_MAGIC + struct.pack('<BI', algorithm, len(data))
    return header + compressed


def decompress(data: bytes) -> bytes:
    """
    Decompress data, auto-detecting algorithm from header.

    Args:
        data: Potentially compressed data

    Returns:
        Decompressed data (or original if not compressed)
    """
    # Check for compression magic
    if not data.startswith(COMPRESSION_MAGIC):
        # Not compressed by us, return as-is
        return data

    if len(data) < 9:  # MAGIC(4) + ALGO(1) + SIZE(4)
        raise CompressionError("Truncated compression header")

    # Parse header
    algorithm = CompressionAlgorithm(data[4])
    original_size = struct.unpack('<I', data[5:9])[0]
    compressed_data = data[9:]

    if algorithm == CompressionAlgorithm.NONE:
        result = compressed_data

    elif algorithm == CompressionAlgorithm.ZLIB:
        try:
            result = zlib.decompress(compressed_data)
        except zlib.error as e:
            raise CompressionError(f"Zlib decompression failed: {e}")

    elif algorithm == CompressionAlgorithm.LZ4:
        if not HAS_LZ4:
            raise CompressionError("LZ4 compression used but lz4 package not installed")
        try:
            result = lz4.frame.decompress(compressed_data)
        except Exception as e:
            raise CompressionError(f"LZ4 decompression failed: {e}")
    else:
        raise CompressionError(f"Unknown compression algorithm: {algorithm}")

    # Verify size
    if len(result) != original_size:
        raise CompressionError(
            f"Size mismatch: expected {original_size}, got {len(result)}"
        )

    return result


def _wrap_uncompressed(data: bytes) -> bytes:
    """Wrap uncompressed data with header for consistency."""
    header = COMPRESSION_MAGIC + struct.pack('<BI', CompressionAlgorithm.NONE, len(data))
    return header + data


def get_compression_ratio(original: bytes, compressed: bytes) -> float:
    """
    Calculate compression ratio.

    Returns:
        Ratio where < 1.0 means compression helped, > 1.0 means it expanded
    """
    if len(original) == 0:
        return 1.0
    return len(compressed) / len(original)


def estimate_compressed_size(data: bytes, algorithm: CompressionAlgorithm = CompressionAlgorithm.ZLIB) -> int:
    """
    Estimate compressed size without full compression.
    Uses sampling for large data.

    Args:
        data: Data to estimate
        algorithm: Algorithm to estimate for

    Returns:
        Estimated compressed size in bytes
    """
    if len(data) < MIN_COMPRESS_SIZE:
        return len(data) + 9  # Header overhead

    # For small data, just compress it
    if len(data) < 10000:
        compressed = compress(data, algorithm)
        return len(compressed)

    # For large data, sample and extrapolate
    sample_size = 8192
    sample = data[:sample_size]

    if algorithm == CompressionAlgorithm.ZLIB:
        compressed_sample = zlib.compress(sample, level=ZLIB_LEVEL)
    elif algorithm == CompressionAlgorithm.LZ4 and HAS_LZ4:
        compressed_sample = lz4.frame.compress(sample)
    else:
        compressed_sample = zlib.compress(sample, level=ZLIB_LEVEL)

    ratio = len(compressed_sample) / len(sample)
    estimated = int(len(data) * ratio) + 9  # Add header

    return estimated


def get_available_algorithms() -> list[CompressionAlgorithm]:
    """Get list of available compression algorithms."""
    algorithms = [CompressionAlgorithm.NONE, CompressionAlgorithm.ZLIB]
    if HAS_LZ4:
        algorithms.append(CompressionAlgorithm.LZ4)
    return algorithms


def algorithm_name(algo: CompressionAlgorithm) -> str:
    """Get human-readable algorithm name."""
    names = {
        CompressionAlgorithm.NONE: "None",
        CompressionAlgorithm.ZLIB: "Zlib (deflate)",
        CompressionAlgorithm.LZ4: "LZ4 (fast)",
    }
    return names.get(algo, "Unknown")
