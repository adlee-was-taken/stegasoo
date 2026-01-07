"""
Stegasoo Library Unit Tests

Tests core functionality: encode/decode, LSB/DCT modes, channel keys, validation.
"""

import io
from pathlib import Path

import pytest
from PIL import Image

import stegasoo
from stegasoo import (
    decode,
    decode_text,
    encode,
    generate_channel_key,
    generate_passphrase,
    generate_pin,
    has_dct_support,
    validate_image,
    validate_message,
    validate_passphrase,
    validate_pin,
)

# Test data paths
TEST_DATA = Path(__file__).parent.parent / "test_data"
CARRIER_PATH = TEST_DATA / "carrier.jpg"
REF_PATH = TEST_DATA / "ref.jpg"

# Test credentials
TEST_PASSPHRASE = "tower booty sunny windy toasty spicy"
TEST_PIN = "727643678"
TEST_MESSAGE = "Hello, Stegasoo!"


@pytest.fixture
def carrier_bytes():
    """Load carrier image as bytes."""
    return CARRIER_PATH.read_bytes()


@pytest.fixture
def ref_bytes():
    """Load reference image as bytes."""
    return REF_PATH.read_bytes()


@pytest.fixture
def small_image():
    """Create a small test image in memory."""
    img = Image.new("RGB", (200, 200), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestVersion:
    """Test version info."""

    def test_version_exists(self):
        assert hasattr(stegasoo, "__version__")
        assert stegasoo.__version__

    def test_version_format(self):
        parts = stegasoo.__version__.split(".")
        assert len(parts) >= 2
        assert all(p.isdigit() for p in parts[:2])


class TestGeneration:
    """Test credential generation."""

    def test_generate_passphrase_default(self):
        passphrase = generate_passphrase()
        words = passphrase.split()
        assert len(words) == stegasoo.DEFAULT_PASSPHRASE_WORDS

    def test_generate_passphrase_custom_length(self):
        passphrase = generate_passphrase(words=8)
        words = passphrase.split()
        assert len(words) == 8

    def test_generate_pin_default(self):
        pin = generate_pin()
        assert pin.isdigit()
        assert len(pin) == 6  # Default is 6 digits

    def test_generate_pin_custom_length(self):
        pin = generate_pin(length=9)
        assert pin.isdigit()
        assert len(pin) == 9

    def test_generate_channel_key(self):
        key = generate_channel_key()
        # Format: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX (39 chars)
        assert len(key) == 39
        assert key.count("-") == 7


class TestValidation:
    """Test validation functions."""

    def test_validate_passphrase_valid(self):
        result = validate_passphrase(TEST_PASSPHRASE)
        assert result.is_valid

    def test_validate_passphrase_too_short(self):
        result = validate_passphrase("one two")
        assert not result.is_valid

    def test_validate_pin_valid(self):
        result = validate_pin(TEST_PIN)
        assert result.is_valid

    def test_validate_pin_too_short(self):
        result = validate_pin("123")
        assert not result.is_valid

    def test_validate_pin_non_numeric(self):
        result = validate_pin("abc123")
        assert not result.is_valid

    def test_validate_message_valid(self):
        result = validate_message("Hello world")
        assert result.is_valid

    def test_validate_message_empty(self):
        result = validate_message("")
        assert not result.is_valid

    def test_validate_image_valid(self, carrier_bytes):
        result = validate_image(carrier_bytes)
        assert result.is_valid

    def test_validate_image_invalid(self):
        result = validate_image(b"not an image")
        assert not result.is_valid


class TestLSBMode:
    """Test LSB (Least Significant Bit) encoding/decoding."""

    def test_encode_decode_roundtrip(self, carrier_bytes, ref_bytes):
        """Basic encode/decode roundtrip."""
        result = encode(
            message=TEST_MESSAGE,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        assert result.stego_image
        assert len(result.stego_image) > 0

        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=ref_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        assert decoded.message == TEST_MESSAGE

    def test_decode_text_helper(self, carrier_bytes, ref_bytes):
        """Test decode_text convenience function."""
        result = encode(
            message=TEST_MESSAGE,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        text = decode_text(
            stego_image=result.stego_image,
            reference_photo=ref_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        assert text == TEST_MESSAGE

    def test_wrong_passphrase_fails(self, carrier_bytes, ref_bytes):
        """Decoding with wrong passphrase should fail."""
        result = encode(
            message=TEST_MESSAGE,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        with pytest.raises(Exception):
            decode(
                stego_image=result.stego_image,
                reference_photo=ref_bytes,
                passphrase="wrong passphrase words here now",
                pin=TEST_PIN,
                embed_mode="lsb",
            )

    def test_wrong_pin_fails(self, carrier_bytes, ref_bytes):
        """Decoding with wrong PIN should fail."""
        result = encode(
            message=TEST_MESSAGE,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        with pytest.raises(Exception):
            decode(
                stego_image=result.stego_image,
                reference_photo=ref_bytes,
                passphrase=TEST_PASSPHRASE,
                pin="999999999",
                embed_mode="lsb",
            )

    def test_wrong_reference_fails(self, carrier_bytes, ref_bytes, small_image):
        """Decoding with wrong reference should fail."""
        result = encode(
            message=TEST_MESSAGE,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        with pytest.raises(Exception):
            decode(
                stego_image=result.stego_image,
                reference_photo=small_image,  # Wrong reference
                passphrase=TEST_PASSPHRASE,
                pin=TEST_PIN,
                embed_mode="lsb",
            )


class TestDCTMode:
    """Test DCT (Discrete Cosine Transform) encoding/decoding."""

    @pytest.fixture(autouse=True)
    def check_dct_support(self):
        """Skip DCT tests if not supported."""
        if not has_dct_support():
            pytest.skip("DCT support not available")

    def test_encode_decode_roundtrip(self, carrier_bytes, ref_bytes):
        """Basic DCT encode/decode roundtrip."""
        result = encode(
            message=TEST_MESSAGE,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="dct",
        )

        assert result.stego_image

        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=ref_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="dct",
        )

        assert decoded.message == TEST_MESSAGE

    def test_dct_jpeg_output(self, carrier_bytes, ref_bytes):
        """Test DCT mode with JPEG output."""
        result = encode(
            message=TEST_MESSAGE,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="dct",
            dct_output_format="jpeg",
        )

        assert result.stego_image
        # Verify it's JPEG by checking magic bytes
        assert result.stego_image[:2] == b"\xff\xd8"


class TestChannelKey:
    """Test channel key functionality."""

    def test_encode_with_channel_key(self, carrier_bytes, ref_bytes):
        """Encode with channel key."""
        channel_key = generate_channel_key()

        result = encode(
            message=TEST_MESSAGE,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            channel_key=channel_key,
            embed_mode="lsb",
        )

        assert result.stego_image

        # Decode with same channel key
        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=ref_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            channel_key=channel_key,
            embed_mode="lsb",
        )

        assert decoded.message == TEST_MESSAGE

    def test_wrong_channel_key_fails(self, carrier_bytes, ref_bytes):
        """Decoding with wrong channel key should fail."""
        channel_key = generate_channel_key()
        wrong_key = generate_channel_key()

        result = encode(
            message=TEST_MESSAGE,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            channel_key=channel_key,
            embed_mode="lsb",
        )

        with pytest.raises(Exception):
            decode(
                stego_image=result.stego_image,
                reference_photo=ref_bytes,
                passphrase=TEST_PASSPHRASE,
                pin=TEST_PIN,
                channel_key=wrong_key,
                embed_mode="lsb",
            )


class TestCompression:
    """Test message compression."""

    def test_long_message_compresses(self, carrier_bytes, ref_bytes):
        """Long messages should be compressed."""
        long_message = "A" * 1000

        result = encode(
            message=long_message,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        assert result.stego_image

        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=ref_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        assert decoded.message == long_message


class TestEdgeCases:
    """Test edge cases and error handling."""

    def test_unicode_message(self, carrier_bytes, ref_bytes):
        """Test encoding Unicode messages."""
        unicode_msg = "Hello 🦖 Stegasoo! 日本語 émojis"

        result = encode(
            message=unicode_msg,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        assert result.stego_image

        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=ref_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        assert decoded.message == unicode_msg

    def test_minimum_passphrase(self, carrier_bytes, ref_bytes):
        """Test with minimum valid passphrase."""
        min_passphrase = "one two three four"  # 4 words minimum

        result = encode(
            message=TEST_MESSAGE,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=min_passphrase,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        assert result.stego_image

    def test_special_characters_in_message(self, carrier_bytes, ref_bytes):
        """Test special characters in message."""
        special_msg = "Line1\nLine2\tTab\r\nCRLF"

        result = encode(
            message=special_msg,
            reference_photo=ref_bytes,
            carrier_image=carrier_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        assert result.stego_image

        decoded = decode(
            stego_image=result.stego_image,
            reference_photo=ref_bytes,
            passphrase=TEST_PASSPHRASE,
            pin=TEST_PIN,
            embed_mode="lsb",
        )

        assert decoded.message == special_msg
