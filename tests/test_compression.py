"""
Tests for Stegasoo compression module.
"""

import pytest
from stegasoo.compression import (
    compress,
    decompress,
    CompressionAlgorithm,
    CompressionError,
    get_compression_ratio,
    estimate_compressed_size,
    get_available_algorithms,
    algorithm_name,
    MIN_COMPRESS_SIZE,
    COMPRESSION_MAGIC,
    HAS_LZ4,
)


class TestCompress:
    """Tests for compress function."""
    
    def test_compress_small_data_not_compressed(self):
        """Small data should not be compressed (overhead not worth it)."""
        small_data = b"hello"
        result = compress(small_data)
        # Should have magic header but NONE algorithm
        assert result.startswith(COMPRESSION_MAGIC)
        assert result[4] == CompressionAlgorithm.NONE
    
    def test_compress_zlib_reduces_size(self):
        """Zlib should reduce size for compressible data."""
        # Highly compressible data
        data = b"A" * 1000
        result = compress(data, CompressionAlgorithm.ZLIB)
        assert len(result) < len(data)
        assert result.startswith(COMPRESSION_MAGIC)
        assert result[4] == CompressionAlgorithm.ZLIB
    
    def test_compress_incompressible_data(self):
        """Incompressible data should be stored uncompressed."""
        import os
        # Random data doesn't compress well
        data = os.urandom(500)
        result = compress(data, CompressionAlgorithm.ZLIB)
        # Should fall back to NONE if compression didn't help
        assert result.startswith(COMPRESSION_MAGIC)
    
    def test_compress_none_algorithm(self):
        """NONE algorithm should just wrap data."""
        data = b"Test data" * 100
        result = compress(data, CompressionAlgorithm.NONE)
        assert result.startswith(COMPRESSION_MAGIC)
        assert result[4] == CompressionAlgorithm.NONE
        # Data should be after 9-byte header
        assert result[9:] == data
    
    @pytest.mark.skipif(not HAS_LZ4, reason="LZ4 not installed")
    def test_compress_lz4(self):
        """LZ4 compression should work if available."""
        data = b"B" * 1000
        result = compress(data, CompressionAlgorithm.LZ4)
        assert len(result) < len(data)
        assert result.startswith(COMPRESSION_MAGIC)
        assert result[4] == CompressionAlgorithm.LZ4


class TestDecompress:
    """Tests for decompress function."""
    
    def test_decompress_zlib(self):
        """Decompression should restore original data."""
        original = b"Hello, World! " * 100
        compressed = compress(original, CompressionAlgorithm.ZLIB)
        result = decompress(compressed)
        assert result == original
    
    def test_decompress_none(self):
        """Uncompressed wrapped data should decompress correctly."""
        original = b"Small data"
        wrapped = compress(original, CompressionAlgorithm.NONE)
        result = decompress(wrapped)
        assert result == original
    
    def test_decompress_no_magic(self):
        """Data without magic header should be returned as-is."""
        data = b"Not compressed at all"
        result = decompress(data)
        assert result == data
    
    def test_decompress_truncated_header(self):
        """Truncated header should raise CompressionError."""
        bad_data = COMPRESSION_MAGIC + b"\x01"  # Too short
        with pytest.raises(CompressionError, match="Truncated"):
            decompress(bad_data)
    
    @pytest.mark.skipif(not HAS_LZ4, reason="LZ4 not installed")
    def test_decompress_lz4(self):
        """LZ4 decompression should work."""
        original = b"LZ4 test data " * 100
        compressed = compress(original, CompressionAlgorithm.LZ4)
        result = decompress(compressed)
        assert result == original
    
    def test_roundtrip_large_data(self):
        """Large data should survive compress/decompress roundtrip."""
        import os
        original = os.urandom(50000)
        compressed = compress(original)
        result = decompress(compressed)
        assert result == original


class TestUtilities:
    """Tests for utility functions."""
    
    def test_compression_ratio_compressed(self):
        """Ratio should be < 1 for well-compressed data."""
        original = b"X" * 1000
        compressed = compress(original)
        ratio = get_compression_ratio(original, compressed)
        assert ratio < 1.0
    
    def test_compression_ratio_empty(self):
        """Empty data should return ratio of 1.0."""
        ratio = get_compression_ratio(b"", b"")
        assert ratio == 1.0
    
    def test_estimate_compressed_size_small(self):
        """Small data estimation should be accurate."""
        data = b"Test " * 100
        estimate = estimate_compressed_size(data)
        actual = len(compress(data))
        # Should be within 20% for small data
        assert abs(estimate - actual) / actual < 0.2
    
    def test_available_algorithms(self):
        """Should always include NONE and ZLIB."""
        algos = get_available_algorithms()
        assert CompressionAlgorithm.NONE in algos
        assert CompressionAlgorithm.ZLIB in algos
    
    def test_algorithm_name(self):
        """Algorithm names should be human-readable."""
        assert "Zlib" in algorithm_name(CompressionAlgorithm.ZLIB)
        assert "None" in algorithm_name(CompressionAlgorithm.NONE)
        assert "LZ4" in algorithm_name(CompressionAlgorithm.LZ4)


class TestEdgeCases:
    """Edge case tests."""
    
    def test_empty_data(self):
        """Empty data should be handled gracefully."""
        result = compress(b"")
        assert decompress(result) == b""
    
    def test_exact_min_size(self):
        """Data at exactly MIN_COMPRESS_SIZE should be compressed."""
        data = b"x" * MIN_COMPRESS_SIZE
        result = compress(data, CompressionAlgorithm.ZLIB)
        assert result.startswith(COMPRESSION_MAGIC)
        assert decompress(result) == data
    
    def test_binary_data(self):
        """Binary data with null bytes should work."""
        data = b"\x00\x01\x02\x03" * 500
        compressed = compress(data)
        assert decompress(compressed) == data
    
    def test_unicode_after_encoding(self):
        """UTF-8 encoded Unicode should compress correctly."""
        text = "Hello, 世界! 🎉 " * 100
        data = text.encode('utf-8')
        compressed = compress(data)
        result = decompress(compressed)
        assert result.decode('utf-8') == text
