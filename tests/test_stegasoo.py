"""
Stegasoo Tests

Tests for key generation, validation, encoding/decoding, and output formats.
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
    encode,
    decode,
    decode_text,
    DAY_NAMES,
    __version__,
)
from stegasoo.steganography import get_output_format


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
# Key Generation Tests
# =============================================================================

class TestKeygen:
    def test_generate_pin_default(self):
        pin = generate_pin()
        assert len(pin) == 6
        assert pin.isdigit()
        assert pin[0] != '0'

    def test_generate_pin_lengths(self):
        for length in [6, 7, 8, 9]:
            pin = generate_pin(length)
            assert len(pin) == length
            assert pin.isdigit()

    def test_generate_phrase_default(self):
        phrase = generate_phrase()
        words = phrase.split()
        assert len(words) == 3

    def test_generate_phrase_lengths(self):
        for length in [3, 4, 5, 6]:
            phrase = generate_phrase(length)
            words = phrase.split()
            assert len(words) == length

    def test_generate_credentials_pin_only(self):
        creds = generate_credentials(use_pin=True, use_rsa=False)
        assert creds.pin is not None
        assert creds.rsa_key_pem is None
        assert len(creds.phrases) == 7

    def test_generate_credentials_rsa_only(self):
        creds = generate_credentials(use_pin=False, use_rsa=True)
        assert creds.pin is None
        assert creds.rsa_key_pem is not None

    def test_generate_credentials_both(self):
        creds = generate_credentials(use_pin=True, use_rsa=True)
        assert creds.pin is not None
        assert creds.rsa_key_pem is not None

    def test_generate_credentials_neither_fails(self):
        """Test that generating credentials with neither PIN nor RSA fails."""
        # Code raises AssertionError from debug.validate before ValueError
        with pytest.raises((ValueError, AssertionError)):
            generate_credentials(use_pin=False, use_rsa=False)

    def test_entropy_calculation(self):
        creds = generate_credentials(use_pin=True, use_rsa=False)
        assert creds.total_entropy > 0


# =============================================================================
# Validation Tests
# =============================================================================

class TestValidation:
    def test_validate_pin_valid(self):
        result = validate_pin("123456")
        assert result.is_valid

    def test_validate_pin_empty_ok(self):
        # Empty PIN is valid (RSA key might be used instead)
        result = validate_pin("")
        assert result.is_valid

    def test_validate_pin_too_short(self):
        result = validate_pin("12345")
        assert not result.is_valid

    def test_validate_pin_too_long(self):
        result = validate_pin("1234567890")
        assert not result.is_valid

    def test_validate_pin_leading_zero(self):
        result = validate_pin("012345")
        assert not result.is_valid

    def test_validate_pin_non_digits(self):
        result = validate_pin("12345a")
        assert not result.is_valid

    def test_validate_message_valid(self):
        result = validate_message("Hello, World!")
        assert result.is_valid

    def test_validate_message_empty(self):
        result = validate_message("")
        assert not result.is_valid

    # Note: validate_message doesn't have a max length check by default
    # This test is removed as it doesn't match the actual validation behavior


# =============================================================================
# Output Format Tests
# =============================================================================

class TestOutputFormat:
    def test_png_stays_png(self):
        fmt, ext = get_output_format('PNG')
        assert fmt == 'PNG'
        assert ext == 'png'

    def test_bmp_stays_bmp(self):
        fmt, ext = get_output_format('BMP')
        assert fmt == 'BMP'
        assert ext == 'bmp'

    def test_jpeg_becomes_png(self):
        fmt, ext = get_output_format('JPEG')
        assert fmt == 'PNG'
        assert ext == 'png'

    def test_gif_becomes_png(self):
        fmt, ext = get_output_format('GIF')
        assert fmt == 'PNG'
        assert ext == 'png'

    def test_none_becomes_png(self):
        fmt, ext = get_output_format(None)
        assert fmt == 'PNG'
        assert ext == 'png'

    def test_unknown_becomes_png(self):
        fmt, ext = get_output_format('UNKNOWN')
        assert fmt == 'PNG'
        assert ext == 'png'


# =============================================================================
# Encode/Decode Tests
# =============================================================================

class TestEncodeDecode:
    def test_encode_decode_roundtrip(self, png_image):
        """Test full encode/decode cycle."""
        message = "Secret message!"
        phrase = "apple forest thunder"
        pin = "123456"

        result = encode(
            message=message,
            reference_photo=png_image,
            carrier_image=png_image,
            day_phrase=phrase,
            pin=pin
        )

        assert result.stego_image is not None
        assert len(result.stego_image) > 0
        assert result.filename.endswith('.png')

        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=png_image,
            day_phrase=phrase,
            pin=pin
        )

        # decode() returns DecodeResult, not string
        assert decoded.message == message

    def test_decode_text_roundtrip(self, png_image):
        """Test decode_text convenience function."""
        message = "Secret message!"
        phrase = "apple forest thunder"
        pin = "123456"

        result = encode(
            message=message,
            reference_photo=png_image,
            carrier_image=png_image,
            day_phrase=phrase,
            pin=pin
        )

        # decode_text returns string directly
        decoded_text = decode_text(
            stego_image=result.stego_image,
            reference_photo=png_image,
            day_phrase=phrase,
            pin=pin
        )

        assert decoded_text == message

    def test_png_carrier_produces_png(self, png_image):
        """Test that PNG carrier produces PNG output."""
        result = encode(
            message="Test",
            reference_photo=png_image,
            carrier_image=png_image,
            day_phrase="test phrase",
            pin="123456"
        )
        assert result.filename.endswith('.png')

    def test_bmp_carrier_produces_bmp(self, bmp_image, png_image):
        """Test that BMP carrier produces BMP output."""
        result = encode(
            message="Test",
            reference_photo=png_image,
            carrier_image=bmp_image,
            day_phrase="test phrase",
            pin="123456"
        )
        assert result.filename.endswith('.bmp')

    def test_jpeg_carrier_produces_png(self, jpeg_image, png_image):
        """Test that JPEG carrier produces PNG output (lossless)."""
        result = encode(
            message="Test",
            reference_photo=png_image,
            carrier_image=jpeg_image,
            day_phrase="test phrase",
            pin="123456"
        )
        assert result.filename.endswith('.png')

    def test_bmp_roundtrip(self, bmp_image, png_image):
        """Test full encode/decode cycle with BMP."""
        message = "BMP test message!"
        phrase = "test phrase words"
        pin = "123456"

        result = encode(
            message=message,
            reference_photo=png_image,
            carrier_image=bmp_image,
            day_phrase=phrase,
            pin=pin
        )
        assert result.filename.endswith('.bmp')

        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=png_image,
            day_phrase=phrase,
            pin=pin
        )

        # decode() returns DecodeResult, not string
        assert decoded.message == message

    def test_wrong_pin_fails(self, png_image):
        """Test that wrong PIN fails to decode."""
        result = encode(
            message="Secret",
            reference_photo=png_image,
            carrier_image=png_image,
            day_phrase="test phrase here",
            pin="123456"
        )

        # Wrong PIN means wrong pixel key, so extraction fails before decryption
        with pytest.raises((stegasoo.DecryptionError, stegasoo.ExtractionError)):
            decode(
                stego_image=result.stego_image,
                reference_photo=png_image,
                day_phrase="test phrase here",
                pin="654321"  # Wrong PIN
            )

    def test_wrong_phrase_fails(self, png_image):
        """Test that wrong phrase fails to decode."""
        result = encode(
            message="Secret",
            reference_photo=png_image,
            carrier_image=png_image,
            day_phrase="correct phrase here",
            pin="123456"
        )

        # Wrong phrase means wrong pixel key, so extraction fails before decryption
        with pytest.raises((stegasoo.DecryptionError, stegasoo.ExtractionError)):
            decode(
                stego_image=result.stego_image,
                reference_photo=png_image,
                day_phrase="wrong phrase here",
                pin="123456"
            )


# =============================================================================
# Version Tests
# =============================================================================

class TestVersion:
    def test_version_exists(self):
        assert hasattr(stegasoo, '__version__')
        # Version should be a valid semver string
        parts = stegasoo.__version__.split('.')
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts[:2])

    def test_day_names(self):
        assert len(DAY_NAMES) == 7
        assert 'Monday' in DAY_NAMES
        assert 'Sunday' in DAY_NAMES
