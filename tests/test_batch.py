"""
Tests for Stegasoo batch processing module (v4.0.0).

Updated for v4.0.0:
- Uses 'passphrase' instead of 'phrase' in credentials dict
- No date_str parameter
- BatchCredentials.passphrase is a single string
"""

import pytest
import tempfile
import shutil
from pathlib import Path
from unittest.mock import Mock, patch

from stegasoo.batch import (
    BatchProcessor,
    BatchResult,
    BatchItem,
    BatchStatus,
    BatchCredentials,
    batch_capacity_check,
    print_batch_result,
)


@pytest.fixture
def temp_dir():
    """Create a temporary directory for tests."""
    path = Path(tempfile.mkdtemp())
    yield path
    shutil.rmtree(path)


@pytest.fixture
def sample_images(temp_dir):
    """Create sample PNG images for testing."""
    from PIL import Image
    
    images = []
    for i in range(3):
        img_path = temp_dir / f"test_image_{i}.png"
        img = Image.new('RGB', (100, 100), color=(i * 50, i * 50, i * 50))
        img.save(img_path, 'PNG')
        images.append(img_path)
    
    return images


@pytest.fixture
def sample_credentials():
    """Create sample v3.2.0 credentials dict."""
    return {
        "passphrase": "test phrase four words",  # v3.2.0: single passphrase
        "pin": "123456"
    }


class TestBatchItem:
    """Tests for BatchItem dataclass."""
    
    def test_duration_calculation(self):
        """Duration should be calculated from start/end times."""
        item = BatchItem(input_path=Path("test.png"))
        item.start_time = 100.0
        item.end_time = 105.5
        assert item.duration == 5.5
    
    def test_duration_none_without_times(self):
        """Duration should be None if times not set."""
        item = BatchItem(input_path=Path("test.png"))
        assert item.duration is None
    
    def test_to_dict(self):
        """to_dict should serialize all fields."""
        item = BatchItem(
            input_path=Path("input.png"),
            output_path=Path("output.png"),
            status=BatchStatus.SUCCESS,
            message="Done",
        )
        result = item.to_dict()
        assert result['input_path'] == "input.png"
        assert result['output_path'] == "output.png"
        assert result['status'] == "success"


class TestBatchResult:
    """Tests for BatchResult dataclass."""
    
    def test_to_json(self):
        """Should serialize to valid JSON."""
        import json
        result = BatchResult(operation="encode", total=5, succeeded=4, failed=1)
        json_str = result.to_json()
        parsed = json.loads(json_str)
        assert parsed['operation'] == "encode"
        assert parsed['summary']['total'] == 5
    
    def test_duration_with_end_time(self):
        """Duration should work when end_time is set."""
        result = BatchResult(operation="test")
        result.start_time = 100.0
        result.end_time = 110.0
        assert result.duration == 10.0


class TestBatchCredentials:
    """Tests for BatchCredentials dataclass (v3.2.0)."""
    
    def test_from_dict_new_format(self):
        """Should parse v3.2.0 format with 'passphrase' key."""
        data = {
            "passphrase": "test phrase four words",
            "pin": "123456"
        }
        creds = BatchCredentials.from_dict(data)
        assert creds.passphrase == "test phrase four words"
        assert creds.pin == "123456"
    
    def test_from_dict_legacy_format(self):
        """Should parse legacy format with 'day_phrase' key for migration."""
        data = {
            "day_phrase": "legacy phrase here",  # Old key name
            "pin": "123456"
        }
        creds = BatchCredentials.from_dict(data)
        # Should accept old key and map to passphrase
        assert creds.passphrase == "legacy phrase here"
        assert creds.pin == "123456"
    
    def test_to_dict(self):
        """Should serialize to v3.2.0 format."""
        creds = BatchCredentials(
            passphrase="test phrase four words",
            pin="123456"
        )
        result = creds.to_dict()
        assert result['passphrase'] == "test phrase four words"
        assert result['pin'] == "123456"
        assert 'day_phrase' not in result  # Old key should not be present
    
    def test_passphrase_is_string(self):
        """Passphrase should be a string, not a dict."""
        creds = BatchCredentials(
            passphrase="test phrase four words",
            pin="123456"
        )
        assert isinstance(creds.passphrase, str)


class TestBatchProcessor:
    """Tests for BatchProcessor class."""
    
    def test_init_default_workers(self):
        """Should default to 4 workers."""
        processor = BatchProcessor()
        assert processor.max_workers == 4
    
    def test_init_custom_workers(self):
        """Should accept custom worker count."""
        processor = BatchProcessor(max_workers=8)
        assert processor.max_workers == 8
    
    def test_is_valid_image_png(self, temp_dir):
        """Should recognize PNG as valid."""
        processor = BatchProcessor()
        png_path = temp_dir / "test.png"
        png_path.touch()
        assert processor._is_valid_image(png_path)
    
    def test_is_valid_image_txt(self, temp_dir):
        """Should reject non-image files."""
        processor = BatchProcessor()
        txt_path = temp_dir / "test.txt"
        txt_path.touch()
        assert not processor._is_valid_image(txt_path)
    
    def test_find_images_file(self, sample_images):
        """Should find single image file."""
        processor = BatchProcessor()
        results = list(processor.find_images([sample_images[0]]))
        assert len(results) == 1
        assert results[0] == sample_images[0]
    
    def test_find_images_directory(self, sample_images, temp_dir):
        """Should find images in directory."""
        processor = BatchProcessor()
        results = list(processor.find_images([temp_dir]))
        assert len(results) == 3
    
    def test_find_images_recursive(self, temp_dir):
        """Should find images recursively."""
        from PIL import Image
        
        # Create nested directory
        nested = temp_dir / "nested"
        nested.mkdir()
        img_path = nested / "nested.png"
        img = Image.new('RGB', (50, 50))
        img.save(img_path)
        
        processor = BatchProcessor()
        results = list(processor.find_images([temp_dir], recursive=True))
        assert any(p.name == "nested.png" for p in results)
    
    def test_batch_encode_requires_message_or_file(self, sample_images, sample_credentials):
        """Should raise if neither message nor file provided."""
        processor = BatchProcessor()
        with pytest.raises(ValueError, match="message or file_payload"):
            processor.batch_encode(
                images=sample_images,
                credentials=sample_credentials,
            )
    
    def test_batch_encode_requires_credentials(self, sample_images):
        """Should raise if credentials not provided."""
        processor = BatchProcessor()
        with pytest.raises(ValueError, match="Credentials"):
            processor.batch_encode(
                images=sample_images,
                message="test",
            )
    
    def test_batch_encode_accepts_passphrase_credentials(self, sample_images, temp_dir, sample_credentials):
        """Should accept v3.2.0 format credentials with passphrase."""
        processor = BatchProcessor()
        result = processor.batch_encode(
            images=sample_images,
            message="Test message",
            output_dir=temp_dir / "output",
            credentials=sample_credentials,  # Uses 'passphrase' key
        )
        
        assert isinstance(result, BatchResult)
        assert result.operation == "encode"
        assert result.total == 3
    
    def test_batch_encode_creates_result(self, sample_images, temp_dir, sample_credentials):
        """Should return BatchResult with correct structure."""
        processor = BatchProcessor()
        result = processor.batch_encode(
            images=sample_images,
            message="Test message",
            output_dir=temp_dir / "output",
            credentials=sample_credentials,
        )
        
        assert isinstance(result, BatchResult)
        assert result.operation == "encode"
        assert result.total == 3
        assert len(result.items) == 3
    
    def test_batch_decode_requires_credentials(self, sample_images):
        """Should raise if credentials not provided."""
        processor = BatchProcessor()
        with pytest.raises(ValueError, match="Credentials"):
            processor.batch_decode(images=sample_images)
    
    def test_batch_decode_accepts_passphrase_credentials(self, sample_images, sample_credentials):
        """Should accept v3.2.0 format credentials with passphrase."""
        processor = BatchProcessor()
        result = processor.batch_decode(
            images=sample_images,
            credentials=sample_credentials,  # Uses 'passphrase' key
        )
        
        assert isinstance(result, BatchResult)
        assert result.operation == "decode"
        assert result.total == 3
    
    def test_batch_decode_creates_result(self, sample_images, sample_credentials):
        """Should return BatchResult with correct structure."""
        processor = BatchProcessor()
        result = processor.batch_decode(
            images=sample_images,
            credentials=sample_credentials,
        )
        
        assert isinstance(result, BatchResult)
        assert result.operation == "decode"
        assert result.total == 3
    
    def test_progress_callback_called(self, sample_images, sample_credentials):
        """Progress callback should be called for each item."""
        processor = BatchProcessor()
        callback = Mock()
        
        processor.batch_encode(
            images=sample_images,
            message="Test",
            credentials=sample_credentials,
            progress_callback=callback,
        )
        
        assert callback.call_count == 3
    
    def test_custom_encode_func(self, sample_images, temp_dir, sample_credentials):
        """Should use custom encode function if provided."""
        processor = BatchProcessor()
        encode_mock = Mock()
        
        processor.batch_encode(
            images=sample_images,
            message="Test",
            output_dir=temp_dir / "output",
            credentials=sample_credentials,
            encode_func=encode_mock,
        )
        
        assert encode_mock.call_count == 3


class TestBatchCapacityCheck:
    """Tests for batch_capacity_check function."""
    
    def test_returns_list(self, sample_images):
        """Should return list of results."""
        results = batch_capacity_check(sample_images)
        assert isinstance(results, list)
        assert len(results) == 3
    
    def test_includes_capacity(self, sample_images):
        """Results should include capacity info."""
        results = batch_capacity_check(sample_images)
        for item in results:
            assert 'capacity_bytes' in item
            assert 'dimensions' in item
            assert 'valid' in item
    
    def test_handles_invalid_files(self, temp_dir):
        """Should handle non-image files gracefully."""
        bad_file = temp_dir / "not_an_image.png"
        bad_file.write_bytes(b"not a png")
        
        results = batch_capacity_check([bad_file])
        assert len(results) == 1
        assert 'error' in results[0]


class TestPrintBatchResult:
    """Tests for print_batch_result function."""
    
    def test_prints_summary(self, capsys, sample_images):
        """Should print summary without errors."""
        result = BatchResult(
            operation="encode",
            total=3,
            succeeded=2,
            failed=1,
        )
        result.end_time = result.start_time + 5.0
        
        print_batch_result(result)
        
        captured = capsys.readouterr()
        assert "ENCODE" in captured.out
        assert "3" in captured.out  # total
        assert "2" in captured.out  # succeeded
    
    def test_verbose_shows_items(self, capsys):
        """Verbose mode should show individual items."""
        result = BatchResult(operation="decode", total=1, succeeded=1)
        result.items = [
            BatchItem(
                input_path=Path("test.png"),
                status=BatchStatus.SUCCESS,
                message="Decoded successfully",
            )
        ]
        result.end_time = result.start_time + 1.0
        
        print_batch_result(result, verbose=True)
        
        captured = capsys.readouterr()
        assert "test.png" in captured.out


class TestCredentialsMigration:
    """Tests for v3.1.x to v3.2.0 credentials migration."""
    
    def test_old_phrase_key_accepted(self):
        """Old 'phrase' key should be accepted for migration."""
        old_format = {
            "phrase": "old style phrase",
            "pin": "123456"
        }
        # Should not raise
        creds = BatchCredentials.from_dict(old_format)
        assert creds.passphrase == "old style phrase"
    
    def test_old_day_phrase_key_accepted(self):
        """Old 'day_phrase' key should be accepted for migration."""
        old_format = {
            "day_phrase": "old day phrase",
            "pin": "123456"
        }
        creds = BatchCredentials.from_dict(old_format)
        assert creds.passphrase == "old day phrase"
    
    def test_new_passphrase_key_preferred(self):
        """New 'passphrase' key should take precedence if both present."""
        mixed_format = {
            "passphrase": "new style passphrase",
            "day_phrase": "old day phrase",
            "pin": "123456"
        }
        creds = BatchCredentials.from_dict(mixed_format)
        assert creds.passphrase == "new style passphrase"
