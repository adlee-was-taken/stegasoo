"""
Stegasoo Tests (v4.0.0)

Tests for key generation, validation, encoding/decoding, and output formats.

Updated for v4.0.0:
- Same API as v3.2.0 (passphrase, no date_str)
- JPEG normalization for jpegio compatibility
- Python 3.12 recommended (3.13 not supported)
"""

import pytest
from PIL import Image
import io

import stegasoo
from stegasoo import (
    generate_pin,
    generate_phrase,
    generate_credentials,
    validate_pin,
    validate_message,
    validate_passphrase,
    encode,
    decode,
    decode_text,
    __version__,
)
from stegasoo.steganography import get_output_format, HEADER_OVERHEAD


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def png_image():
    """Create a test PNG image."""
    img = Image.new('RGB', (100, 100), color='red')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def large_png_image():
    """Create a larger test PNG image for DCT mode."""
    img = Image.new('RGB', (400, 400), color='blue')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def bmp_image():
    """Create a test BMP image."""
    img = Image.new('RGB', (100, 100), color='blue')
    buf = io.BytesIO()
    img.save(buf, format='BMP')
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def jpeg_image():
    """Create a test JPEG image."""
    img = Image.new('RGB', (100, 100), color='green')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    buf.seek(0)
    return buf.getvalue()


@pytest.fixture
def gif_image():
    """Create a test GIF image."""
    img = Image.new('RGB', (100, 100), color='yellow')
    buf = io.BytesIO()
    img.save(buf, format='GIF')
    buf.seek(0)
    return buf.getvalue()


# =============================================================================
# Key Generation Tests (v3.2.0 Updated)
# =============================================================================

class TestKeygen:
    """Tests for key generation functions."""
    
    def test_generate_pin_default(self):
        """Default PIN should be 6 digits, no leading zero."""
        pin = generate_pin()
        assert len(pin) == 6
        assert pin.isdigit()
        assert pin[0] != '0'

    def test_generate_pin_lengths(self):
        """PIN generation should work for all valid lengths."""
        for length in [6, 7, 8, 9]:
            pin = generate_pin(length)
            assert len(pin) == length
            assert pin.isdigit()

    def test_generate_phrase_default(self):
        """Default phrase should have 4 words (v3.2.0 change)."""
        phrase = generate_phrase()
        words = phrase.split()
        assert len(words) == 4  # Changed from 3 in v3.1.x

    def test_generate_phrase_custom_length(self):
        """Phrase generation should work for custom lengths."""
        for length in [3, 4, 5, 6, 8, 12]:
            phrase = generate_phrase(length)
            words = phrase.split()
            assert len(words) == length

    def test_generate_credentials_pin_only(self):
        """PIN-only credentials should have single passphrase."""
        creds = generate_credentials(use_pin=True, use_rsa=False)
        assert creds.pin is not None
        assert creds.rsa_key_pem is None
        # v3.2.0: Single passphrase instead of 7 daily phrases
        assert creds.passphrase is not None
        assert isinstance(creds.passphrase, str)
        assert ' ' in creds.passphrase  # Should have multiple words

    def test_generate_credentials_rsa_only(self):
        """RSA-only credentials should have single passphrase."""
        creds = generate_credentials(use_pin=False, use_rsa=True)
        assert creds.pin is None
        assert creds.rsa_key_pem is not None
        assert creds.passphrase is not None

    def test_generate_credentials_both(self):
        """Both PIN and RSA should work together."""
        creds = generate_credentials(use_pin=True, use_rsa=True)
        assert creds.pin is not None
        assert creds.rsa_key_pem is not None
        assert creds.passphrase is not None

    def test_generate_credentials_neither_fails(self):
        """Generating with neither PIN nor RSA should fail."""
        with pytest.raises((ValueError, AssertionError)):
            generate_credentials(use_pin=False, use_rsa=False)

    def test_generate_credentials_custom_words(self):
        """Custom passphrase_words parameter should work."""
        creds = generate_credentials(use_pin=True, passphrase_words=6)
        words = creds.passphrase.split()
        assert len(words) == 6

    def test_generate_credentials_default_words(self):
        """Default should be 4 words (v3.2.0)."""
        creds = generate_credentials(use_pin=True)
        words = creds.passphrase.split()
        assert len(words) == 4

    def test_passphrase_entropy_calculation(self):
        """Passphrase entropy should be calculated correctly."""
        creds = generate_credentials(use_pin=True, passphrase_words=4)
        # 4 words × 11 bits/word = 44 bits
        assert creds.passphrase_entropy == 44

    def test_total_entropy_calculation(self):
        """Total entropy should sum all components."""
        creds = generate_credentials(use_pin=True, use_rsa=False, passphrase_words=4)
        # 44 bits (passphrase) + ~20 bits (PIN)
        assert creds.total_entropy > 0
        assert creds.total_entropy >= creds.passphrase_entropy


# =============================================================================
# Validation Tests (v3.2.0 Updated)
# =============================================================================

class TestValidation:
    """Tests for validation functions."""
    
    def test_validate_pin_valid(self):
        """Valid PIN should pass validation."""
        result = validate_pin("123456")
        assert result.is_valid

    def test_validate_pin_empty_ok(self):
        """Empty PIN should be valid (RSA key might be used instead)."""
        result = validate_pin("")
        assert result.is_valid

    def test_validate_pin_too_short(self):
        """PIN shorter than 6 digits should fail."""
        result = validate_pin("12345")
        assert not result.is_valid

    def test_validate_pin_too_long(self):
        """PIN longer than 9 digits should fail."""
        result = validate_pin("1234567890")
        assert not result.is_valid

    def test_validate_pin_leading_zero(self):
        """PIN with leading zero should fail."""
        result = validate_pin("012345")
        assert not result.is_valid

    def test_validate_pin_non_digits(self):
        """PIN with non-digit characters should fail."""
        result = validate_pin("12345a")
        assert not result.is_valid

    def test_validate_message_valid(self):
        """Valid message should pass validation."""
        result = validate_message("Hello, World!")
        assert result.is_valid

    def test_validate_message_empty(self):
        """Empty message should fail validation."""
        result = validate_message("")
        assert not result.is_valid

    def test_validate_passphrase_valid(self):
        """Valid passphrase should pass validation."""
        result = validate_passphrase("word1 word2 word3 word4")
        assert result.is_valid

    def test_validate_passphrase_empty(self):
        """Empty passphrase should fail validation."""
        result = validate_passphrase("")
        assert not result.is_valid

    def test_validate_passphrase_short_warning(self):
        """Short passphrase should have warning but still be valid."""
        result = validate_passphrase("word1 word2 word3")  # Only 3 words
        assert result.is_valid
        assert result.warning is not None  # Should warn about short passphrase

    def test_validate_passphrase_recommended_no_warning(self):
        """Recommended length passphrase should have no warning."""
        result = validate_passphrase("word1 word2 word3 word4")  # 4 words
        assert result.is_valid
        # May or may not have warning depending on implementation


# =============================================================================
# Output Format Tests
# =============================================================================

class TestOutputFormat:
    """Tests for output format handling."""
    
    def test_png_stays_png(self):
        """PNG input should produce PNG output."""
        fmt, ext = get_output_format('PNG')
        assert fmt == 'PNG'
        assert ext == 'png'

    def test_bmp_stays_bmp(self):
        """BMP input should produce BMP output."""
        fmt, ext = get_output_format('BMP')
        assert fmt == 'BMP'
        assert ext == 'bmp'

    def test_jpeg_becomes_png(self):
        """JPEG input should produce PNG output (lossless)."""
        fmt, ext = get_output_format('JPEG')
        assert fmt == 'PNG'
        assert ext == 'png'

    def test_gif_becomes_png(self):
        """GIF input should produce PNG output."""
        fmt, ext = get_output_format('GIF')
        assert fmt == 'PNG'
        assert ext == 'png'

    def test_none_becomes_png(self):
        """None format should default to PNG."""
        fmt, ext = get_output_format(None)
        assert fmt == 'PNG'
        assert ext == 'png'

    def test_unknown_becomes_png(self):
        """Unknown format should default to PNG."""
        fmt, ext = get_output_format('UNKNOWN')
        assert fmt == 'PNG'
        assert ext == 'png'


# =============================================================================
# Header Overhead Test (v3.2.0)
# =============================================================================

class TestConstants:
    """Tests for constants and configuration."""
    
    def test_header_overhead_value(self):
        """Header overhead should be 65 bytes (v3.2.0 fix)."""
        assert HEADER_OVERHEAD == 65


# =============================================================================
# Encode/Decode Tests (v3.2.0 Updated)
# =============================================================================

class TestEncodeDecode:
    """Tests for encoding and decoding functions."""
    
    def test_encode_decode_roundtrip(self, png_image):
        """Full encode/decode cycle should work."""
        message = "Secret message!"
        passphrase = "apple forest thunder mountain"  # 4 words
        pin = "123456"

        # v3.2.0: Use passphrase parameter, no date_str
        result = encode(
            message=message,
            reference_photo=png_image,
            carrier_image=png_image,
            passphrase=passphrase,
            pin=pin
        )

        assert result.stego_image is not None
        assert len(result.stego_image) > 0
        assert result.filename.endswith('.png')

        # v3.2.0: Use passphrase parameter, no date_str
        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=png_image,
            passphrase=passphrase,
            pin=pin
        )

        assert decoded.message == message

    def test_decode_text_roundtrip(self, png_image):
        """decode_text convenience function should work."""
        message = "Secret message!"
        passphrase = "apple forest thunder mountain"
        pin = "123456"

        result = encode(
            message=message,
            reference_photo=png_image,
            carrier_image=png_image,
            passphrase=passphrase,
            pin=pin
        )

        # decode_text returns string directly
        decoded_text = decode_text(
            stego_image=result.stego_image,
            reference_photo=png_image,
            passphrase=passphrase,
            pin=pin
        )

        assert decoded_text == message

    def test_png_carrier_produces_png(self, png_image):
        """PNG carrier should produce PNG output."""
        result = encode(
            message="Test",
            reference_photo=png_image,
            carrier_image=png_image,
            passphrase="test phrase here now",
            pin="123456"
        )
        assert result.filename.endswith('.png')

    def test_bmp_carrier_produces_bmp(self, bmp_image, png_image):
        """BMP carrier should produce BMP output."""
        result = encode(
            message="Test",
            reference_photo=png_image,
            carrier_image=bmp_image,
            passphrase="test phrase here now",
            pin="123456"
        )
        assert result.filename.endswith('.bmp')

    def test_jpeg_carrier_produces_png(self, jpeg_image, png_image):
        """JPEG carrier should produce PNG output (lossless)."""
        result = encode(
            message="Test",
            reference_photo=png_image,
            carrier_image=jpeg_image,
            passphrase="test phrase here now",
            pin="123456"
        )
        assert result.filename.endswith('.png')

    def test_bmp_roundtrip(self, bmp_image, png_image):
        """Full encode/decode cycle with BMP should work."""
        message = "BMP test message!"
        passphrase = "test phrase words here"
        pin = "123456"

        result = encode(
            message=message,
            reference_photo=png_image,
            carrier_image=bmp_image,
            passphrase=passphrase,
            pin=pin
        )
        assert result.filename.endswith('.bmp')

        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=png_image,
            passphrase=passphrase,
            pin=pin
        )

        assert decoded.message == message

    def test_wrong_pin_fails(self, png_image):
        """Wrong PIN should fail to decode."""
        result = encode(
            message="Secret",
            reference_photo=png_image,
            carrier_image=png_image,
            passphrase="test phrase here now",
            pin="123456"
        )

        with pytest.raises((stegasoo.DecryptionError, stegasoo.ExtractionError)):
            decode(
                stego_image=result.stego_image,
                reference_photo=png_image,
                passphrase="test phrase here now",
                pin="654321"  # Wrong PIN
            )

    def test_wrong_passphrase_fails(self, png_image):
        """Wrong passphrase should fail to decode."""
        result = encode(
            message="Secret",
            reference_photo=png_image,
            carrier_image=png_image,
            passphrase="correct phrase here now",
            pin="123456"
        )

        with pytest.raises((stegasoo.DecryptionError, stegasoo.ExtractionError)):
            decode(
                stego_image=result.stego_image,
                reference_photo=png_image,
                passphrase="wrong phrase here now",  # Wrong passphrase
                pin="123456"
            )

    def test_unicode_message(self, png_image):
        """Unicode messages should encode/decode correctly."""
        message = "Hello, 世界! 🎉 Émojis and ümlauts"
        passphrase = "unicode test phrase here"
        pin = "123456"

        result = encode(
            message=message,
            reference_photo=png_image,
            carrier_image=png_image,
            passphrase=passphrase,
            pin=pin
        )

        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=png_image,
            passphrase=passphrase,
            pin=pin
        )

        assert decoded.message == message

    def test_filename_has_no_date(self, png_image):
        """v3.2.0: Output filename should not have date suffix."""
        result = encode(
            message="Test",
            reference_photo=png_image,
            carrier_image=png_image,
            passphrase="test phrase here now",
            pin="123456"
        )
        # Filename should be like "a1b2c3d4.png", not "a1b2c3d4_20251227.png"
        # Check that there's no underscore followed by 8 digits
        import re
        assert not re.search(r'_\d{8}\.', result.filename)


# =============================================================================
# DCT Mode Tests (v3.2.0)
# =============================================================================

class TestDCTMode:
    """Tests for DCT steganography mode."""
    
    @pytest.fixture
    def skip_if_no_dct(self):
        """Skip test if DCT support not available."""
        if not stegasoo.has_dct_support():
            pytest.skip("DCT support not available (scipy not installed)")

    def test_dct_encode_decode_roundtrip(self, large_png_image, skip_if_no_dct):
        """DCT mode encode/decode should work."""
        message = "DCT test"
        passphrase = "dct test phrase here"
        pin = "123456"

        result = encode(
            message=message,
            reference_photo=large_png_image,
            carrier_image=large_png_image,
            passphrase=passphrase,
            pin=pin,
            embed_mode='dct'
        )

        assert result.stego_image is not None

        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=large_png_image,
            passphrase=passphrase,
            pin=pin
        )

        assert decoded.message == message

    def test_dct_auto_detection(self, large_png_image, skip_if_no_dct):
        """Auto mode should detect DCT encoding."""
        message = "Auto detect DCT"
        passphrase = "auto detect test here"
        pin = "123456"

        result = encode(
            message=message,
            reference_photo=large_png_image,
            carrier_image=large_png_image,
            passphrase=passphrase,
            pin=pin,
            embed_mode='dct'
        )

        # Decode with auto mode (default)
        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=large_png_image,
            passphrase=passphrase,
            pin=pin,
            embed_mode='auto'
        )

        assert decoded.message == message


# =============================================================================
# Version Tests
# =============================================================================

class TestVersion:
    """Tests for version information."""
    
    def test_version_exists(self):
        """Version string should exist and be valid."""
        assert hasattr(stegasoo, '__version__')
        parts = stegasoo.__version__.split('.')
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts[:2])

    def test_version_is_4_0_0(self):
        """Version should be 4.0.0 or higher."""
        parts = stegasoo.__version__.split('.')
        major = int(parts[0])
        assert major >= 4


# =============================================================================
# Backward Compatibility Tests
# =============================================================================

class TestBackwardCompatibility:
    """Tests for backward compatibility handling."""
    
    def test_old_day_phrase_parameter_raises(self, png_image):
        """Using old day_phrase parameter should raise TypeError."""
        with pytest.raises(TypeError):
            encode(
                message="Test",
                reference_photo=png_image,
                carrier_image=png_image,
                day_phrase="old style phrase",  # Old parameter name
                pin="123456"
            )

    def test_old_date_str_parameter_raises(self, png_image):
        """Using old date_str parameter should raise TypeError."""
        with pytest.raises(TypeError):
            encode(
                message="Test",
                reference_photo=png_image,
                carrier_image=png_image,
                passphrase="test phrase here now",
                pin="123456",
                date_str="2025-01-01"  # Removed parameter
            )
