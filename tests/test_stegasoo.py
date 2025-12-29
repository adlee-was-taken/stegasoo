"""
Basic tests for Stegasoo library.
"""

import io
import sys
from pathlib import Path

import pytest

# Add src to path for development
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

import stegasoo
from stegasoo import (
    generate_credentials,
    generate_pin,
    generate_phrase,
    validate_pin,
    validate_message,
    encode,
    decode,
    DAY_NAMES,
)
from stegasoo.steganography import get_output_format, get_image_format


class TestKeygen:
    """Test credential generation."""
    
    def test_generate_pin_default(self):
        pin = generate_pin()
        assert len(pin) == 6
        assert pin.isdigit()
        assert pin[0] != '0'
    
    def test_generate_pin_lengths(self):
        for length in range(6, 10):
            pin = generate_pin(length)
            assert len(pin) == length
    
    def test_generate_phrase_default(self):
        phrase = generate_phrase()
        words = phrase.split()
        assert len(words) == 3
    
    def test_generate_phrase_lengths(self):
        for length in range(3, 13):
            phrase = generate_phrase(length)
            words = phrase.split()
            assert len(words) == length
    
    def test_generate_credentials_pin_only(self):
        creds = generate_credentials(use_pin=True, use_rsa=False)
        assert creds.pin is not None
        assert creds.rsa_key_pem is None
        assert len(creds.phrases) == 7
        assert set(creds.phrases.keys()) == set(DAY_NAMES)
    
    def test_generate_credentials_rsa_only(self):
        creds = generate_credentials(use_pin=False, use_rsa=True)
        assert creds.pin is None
        assert creds.rsa_key_pem is not None
        assert '-----BEGIN PRIVATE KEY-----' in creds.rsa_key_pem
    
    def test_generate_credentials_both(self):
        creds = generate_credentials(use_pin=True, use_rsa=True)
        assert creds.pin is not None
        assert creds.rsa_key_pem is not None
    
    def test_generate_credentials_neither_fails(self):
        with pytest.raises(ValueError):
            generate_credentials(use_pin=False, use_rsa=False)
    
    def test_entropy_calculation(self):
        creds = generate_credentials(
            use_pin=True,
            use_rsa=True,
            pin_length=6,
            rsa_bits=2048,
            words_per_phrase=3
        )
        assert creds.phrase_entropy == 33  # 3 * 11
        assert creds.pin_entropy == 19  # floor(6 * 3.32)
        assert creds.rsa_entropy == 128
        assert creds.total_entropy == 33 + 19 + 128


class TestValidation:
    """Test input validation."""
    
    def test_validate_pin_valid(self):
        result = validate_pin("123456")
        assert result.is_valid
    
    def test_validate_pin_empty_ok(self):
        result = validate_pin("")
        assert result.is_valid
    
    def test_validate_pin_too_short(self):
        result = validate_pin("12345")
        assert not result.is_valid
        assert "6-9" in result.error_message
    
    def test_validate_pin_too_long(self):
        result = validate_pin("1234567890")
        assert not result.is_valid
    
    def test_validate_pin_leading_zero(self):
        result = validate_pin("012345")
        assert not result.is_valid
        assert "zero" in result.error_message.lower()
    
    def test_validate_pin_non_digits(self):
        result = validate_pin("12345a")
        assert not result.is_valid
    
    def test_validate_message_valid(self):
        result = validate_message("Hello, world!")
        assert result.is_valid
    
    def test_validate_message_empty(self):
        result = validate_message("")
        assert not result.is_valid
    
    def test_validate_message_too_long(self):
        result = validate_message("x" * 60000)
        assert not result.is_valid


class TestOutputFormat:
    """Test output format detection and preservation."""
    
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
        fmt, ext = get_output_format('WEBP')
        assert fmt == 'PNG'
        assert ext == 'png'


class TestEncodeDecode:
    """Test encoding and decoding (requires test images)."""
    
    @pytest.fixture
    def png_image(self):
        """Create a simple PNG test image."""
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='red')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()
    
    @pytest.fixture
    def bmp_image(self):
        """Create a simple BMP test image."""
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='blue')
        buf = io.BytesIO()
        img.save(buf, format='BMP')
        return buf.getvalue()
    
    @pytest.fixture
    def jpeg_image(self):
        """Create a simple JPEG test image."""
        from PIL import Image
        img = Image.new('RGB', (100, 100), color='green')
        buf = io.BytesIO()
        img.save(buf, format='JPEG', quality=95)
        return buf.getvalue()
    
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
        
        assert decoded == message
    
    def test_png_carrier_produces_png(self, png_image):
        """Test that PNG carrier produces PNG output."""
        result = encode(
            message="Test",
            reference_photo=png_image,
            carrier_image=png_image,
            day_phrase="test phrase here",
            pin="123456"
        )
        
        assert result.filename.endswith('.png')
        # Verify actual format
        output_format = get_image_format(result.stego_image)
        assert output_format == 'PNG'
    
    def test_bmp_carrier_produces_bmp(self, bmp_image, png_image):
        """Test that BMP carrier produces BMP output."""
        result = encode(
            message="Test",
            reference_photo=png_image,
            carrier_image=bmp_image,
            day_phrase="test phrase here",
            pin="123456"
        )
        
        assert result.filename.endswith('.bmp')
        # Verify actual format
        output_format = get_image_format(result.stego_image)
        assert output_format == 'BMP'
    
    def test_jpeg_carrier_produces_png(self, jpeg_image, png_image):
        """Test that JPEG carrier produces PNG output (lossy -> lossless)."""
        result = encode(
            message="Test",
            reference_photo=png_image,
            carrier_image=jpeg_image,
            day_phrase="test phrase here",
            pin="123456"
        )
        
        assert result.filename.endswith('.png')
        # Verify actual format
        output_format = get_image_format(result.stego_image)
        assert output_format == 'PNG'
    
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
        
        assert decoded == message
    
    def test_wrong_pin_fails(self, png_image):
        """Test that wrong PIN fails to decode."""
        result = encode(
            message="Secret",
            reference_photo=png_image,
            carrier_image=png_image,
            day_phrase="test phrase here",
            pin="123456"
        )
        
        with pytest.raises(stegasoo.DecryptionError):
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
        
        with pytest.raises(stegasoo.DecryptionError):
            decode(
                stego_image=result.stego_image,
                reference_photo=png_image,
                day_phrase="wrong phrase here",
                pin="123456"
            )


class TestVersion:
    """Test version information."""
    
    def test_version_exists(self):
        assert hasattr(stegasoo, '__version__')
        assert stegasoo.__version__ == "2.0.1"
    
    def test_day_names(self):
        assert len(stegasoo.DAY_NAMES) == 7
        assert stegasoo.DAY_NAMES[0] == 'Monday'
        assert stegasoo.DAY_NAMES[6] == 'Sunday'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
