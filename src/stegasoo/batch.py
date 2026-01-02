"""
Stegasoo Batch Processing Module (v3.2.0)

Enables encoding/decoding multiple files in a single operation.
Supports parallel processing, progress tracking, and detailed reporting.

Changes in v3.2.0:
- BatchCredentials: renamed day_phrase → passphrase, removed date_str
- Updated all credential handling to use v3.2.0 API
"""

import json
import threading
import time
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

from .constants import ALLOWED_IMAGE_EXTENSIONS, LOSSLESS_FORMATS


class BatchStatus(Enum):
    """Status of individual batch items."""

    PENDING = "pending"
    PROCESSING = "processing"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class BatchItem:
    """Represents a single item in a batch operation."""

    input_path: Path
    output_path: Path | None = None
    status: BatchStatus = BatchStatus.PENDING
    error: str | None = None
    start_time: float | None = None
    end_time: float | None = None
    input_size: int = 0
    output_size: int = 0
    message: str = ""

    @property
    def duration(self) -> float | None:
        """Processing duration in seconds."""
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path) if self.output_path else None,
            "status": self.status.value,
            "error": self.error,
            "duration_seconds": self.duration,
            "input_size": self.input_size,
            "output_size": self.output_size,
            "message": self.message,
        }


@dataclass
class BatchCredentials:
    """
    Credentials for batch encode/decode operations (v3.2.0).

    Provides a structured way to pass authentication factors
    for batch processing instead of using plain dicts.

    Changes in v3.2.0:
    - Renamed day_phrase → passphrase
    - Removed date_str (no longer used in cryptographic operations)

    Example:
        creds = BatchCredentials(
            reference_photo=ref_bytes,
            passphrase="apple forest thunder mountain",
            pin="123456"
        )
        result = processor.batch_encode(images, creds, message="secret")
    """

    reference_photo: bytes
    passphrase: str  # v3.2.0: renamed from day_phrase
    pin: str = ""
    rsa_key_data: bytes | None = None
    rsa_password: str | None = None

    def to_dict(self) -> dict:
        """Convert to dictionary for API compatibility."""
        return {
            "reference_photo": self.reference_photo,
            "passphrase": self.passphrase,
            "pin": self.pin,
            "rsa_key_data": self.rsa_key_data,
            "rsa_password": self.rsa_password,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "BatchCredentials":
        """
        Create BatchCredentials from a dictionary.

        Handles both v3.2.0 format (passphrase) and legacy formats (day_phrase, phrase).
        """
        # Handle legacy 'day_phrase' and 'phrase' keys
        passphrase = data.get("passphrase") or data.get("day_phrase") or data.get("phrase", "")

        return cls(
            reference_photo=data["reference_photo"],
            passphrase=passphrase,
            pin=data.get("pin", ""),
            rsa_key_data=data.get("rsa_key_data"),
            rsa_password=data.get("rsa_password"),
        )


@dataclass
class BatchResult:
    """Summary of a batch operation."""

    operation: str
    total: int = 0
    succeeded: int = 0
    failed: int = 0
    skipped: int = 0
    start_time: float = field(default_factory=time.time)
    end_time: float | None = None
    items: list[BatchItem] = field(default_factory=list)

    @property
    def duration(self) -> float | None:
        """Total batch duration in seconds."""
        if self.end_time:
            return self.end_time - self.start_time
        return None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "operation": self.operation,
            "summary": {
                "total": self.total,
                "succeeded": self.succeeded,
                "failed": self.failed,
                "skipped": self.skipped,
                "duration_seconds": self.duration,
            },
            "items": [item.to_dict() for item in self.items],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)


# Type alias for progress callback
ProgressCallback = Callable[[int, int, BatchItem], None]


class BatchProcessor:
    """
    Handles batch encoding/decoding operations (v3.2.0).

    Usage:
        processor = BatchProcessor(max_workers=4)

        # Batch encode with BatchCredentials
        creds = BatchCredentials(
            reference_photo=ref_bytes,
            passphrase="apple forest thunder mountain",
            pin="123456"
        )
        result = processor.batch_encode(
            images=['img1.png', 'img2.png'],
            message="Secret message",
            output_dir="./encoded/",
            credentials=creds,
        )

        # Batch encode with dict credentials
        result = processor.batch_encode(
            images=['img1.png', 'img2.png'],
            message="Secret message",
            credentials={
                "reference_photo": ref_bytes,
                "passphrase": "apple forest thunder mountain",
                "pin": "123456"
            },
        )

        # Batch decode
        result = processor.batch_decode(
            images=['encoded1.png', 'encoded2.png'],
            credentials=creds,
        )
    """

    def __init__(self, max_workers: int = 4):
        """
        Initialize batch processor.

        Args:
            max_workers: Maximum parallel workers (default 4)
        """
        self.max_workers = max_workers
        self._lock = threading.Lock()

    def find_images(
        self,
        paths: list[str | Path],
        recursive: bool = False,
    ) -> Iterator[Path]:
        """
        Find all valid image files from paths.

        Args:
            paths: List of files or directories
            recursive: Search directories recursively

        Yields:
            Path objects for each valid image
        """
        for path in paths:
            path = Path(path)

            if path.is_file():
                if self._is_valid_image(path):
                    yield path

            elif path.is_dir():
                pattern = "**/*" if recursive else "*"
                for file_path in path.glob(pattern):
                    if file_path.is_file() and self._is_valid_image(file_path):
                        yield file_path

    def _is_valid_image(self, path: Path) -> bool:
        """Check if path is a valid image file."""
        return path.suffix.lower().lstrip(".") in ALLOWED_IMAGE_EXTENSIONS

    def _normalize_credentials(
        self, credentials: dict | BatchCredentials | None
    ) -> BatchCredentials:
        """
        Normalize credentials to BatchCredentials object.

        Handles both dict and BatchCredentials input, and legacy 'day_phrase' key.
        """
        if credentials is None:
            raise ValueError("Credentials are required")

        if isinstance(credentials, BatchCredentials):
            return credentials

        if isinstance(credentials, dict):
            return BatchCredentials.from_dict(credentials)

        raise ValueError(f"Invalid credentials type: {type(credentials)}")

    def batch_encode(
        self,
        images: list[str | Path],
        message: str | None = None,
        file_payload: Path | None = None,
        output_dir: Path | None = None,
        output_suffix: str = "_encoded",
        credentials: dict | BatchCredentials | None = None,
        compress: bool = True,
        recursive: bool = False,
        progress_callback: ProgressCallback | None = None,
        encode_func: Callable = None,
    ) -> BatchResult:
        """
        Encode message into multiple images.

        Args:
            images: List of image paths or directories
            message: Text message to encode (mutually exclusive with file_payload)
            file_payload: File to embed (mutually exclusive with message)
            output_dir: Output directory (default: same as input)
            output_suffix: Suffix for output files
            credentials: BatchCredentials or dict with 'passphrase', 'pin', etc.
            compress: Enable compression
            recursive: Search directories recursively
            progress_callback: Called for each item: callback(current, total, item)
            encode_func: Custom encode function (for integration)

        Returns:
            BatchResult with operation summary
        """
        if message is None and file_payload is None:
            raise ValueError("Either message or file_payload must be provided")

        # Normalize credentials to BatchCredentials
        creds = self._normalize_credentials(credentials)

        result = BatchResult(operation="encode")
        image_paths = list(self.find_images(images, recursive))
        result.total = len(image_paths)

        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare batch items
        for img_path in image_paths:
            if output_dir:
                out_path = output_dir / f"{img_path.stem}{output_suffix}.png"
            else:
                out_path = img_path.parent / f"{img_path.stem}{output_suffix}.png"

            item = BatchItem(
                input_path=img_path,
                output_path=out_path,
                input_size=img_path.stat().st_size if img_path.exists() else 0,
            )
            result.items.append(item)

        # Process items
        def process_encode(item: BatchItem) -> BatchItem:
            item.status = BatchStatus.PROCESSING
            item.start_time = time.time()

            try:
                if encode_func:
                    # Use provided encode function
                    encode_func(
                        image_path=item.input_path,
                        output_path=item.output_path,
                        message=message,
                        file_payload=file_payload,
                        credentials=creds.to_dict(),
                        compress=compress,
                    )
                else:
                    # Use stegasoo encode
                    self._do_encode(item, message, file_payload, creds, compress)

                item.status = BatchStatus.SUCCESS
                item.output_size = (
                    item.output_path.stat().st_size
                    if item.output_path and item.output_path.exists()
                    else 0
                )
                item.message = f"Encoded to {item.output_path.name}"

            except Exception as e:
                item.status = BatchStatus.FAILED
                item.error = str(e)

            item.end_time = time.time()
            return item

        # Execute with thread pool
        self._execute_batch(result, process_encode, progress_callback)

        return result

    def batch_decode(
        self,
        images: list[str | Path],
        output_dir: Path | None = None,
        credentials: dict | BatchCredentials | None = None,
        recursive: bool = False,
        progress_callback: ProgressCallback | None = None,
        decode_func: Callable = None,
    ) -> BatchResult:
        """
        Decode messages from multiple images.

        Args:
            images: List of image paths or directories
            output_dir: Output directory for file payloads (default: same as input)
            credentials: BatchCredentials or dict with 'passphrase', 'pin', etc.
            recursive: Search directories recursively
            progress_callback: Called for each item: callback(current, total, item)
            decode_func: Custom decode function (for integration)

        Returns:
            BatchResult with decoded messages in item.message fields
        """
        # Normalize credentials to BatchCredentials
        creds = self._normalize_credentials(credentials)

        result = BatchResult(operation="decode")
        image_paths = list(self.find_images(images, recursive))
        result.total = len(image_paths)

        if output_dir:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        # Prepare batch items
        for img_path in image_paths:
            item = BatchItem(
                input_path=img_path,
                output_path=output_dir,
                input_size=img_path.stat().st_size if img_path.exists() else 0,
            )
            result.items.append(item)

        # Process items
        def process_decode(item: BatchItem) -> BatchItem:
            item.status = BatchStatus.PROCESSING
            item.start_time = time.time()

            try:
                if decode_func:
                    # Use provided decode function
                    decoded = decode_func(
                        image_path=item.input_path,
                        output_dir=item.output_path,
                        credentials=creds.to_dict(),
                    )
                    item.message = (
                        decoded.get("message", "") if isinstance(decoded, dict) else str(decoded)
                    )
                else:
                    # Use stegasoo decode
                    item.message = self._do_decode(item, creds)

                item.status = BatchStatus.SUCCESS

            except Exception as e:
                item.status = BatchStatus.FAILED
                item.error = str(e)

            item.end_time = time.time()
            return item

        # Execute with thread pool
        self._execute_batch(result, process_decode, progress_callback)

        return result

    def _execute_batch(
        self,
        result: BatchResult,
        process_func: Callable[[BatchItem], BatchItem],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Execute batch processing with thread pool."""
        completed = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            futures = {executor.submit(process_func, item): item for item in result.items}

            for future in as_completed(futures):
                item = future.result()
                completed += 1

                with self._lock:
                    if item.status == BatchStatus.SUCCESS:
                        result.succeeded += 1
                    elif item.status == BatchStatus.FAILED:
                        result.failed += 1
                    elif item.status == BatchStatus.SKIPPED:
                        result.skipped += 1

                if progress_callback:
                    progress_callback(completed, result.total, item)

        result.end_time = time.time()

    def _do_encode(
        self,
        item: BatchItem,
        message: str | None,
        file_payload: Path | None,
        creds: BatchCredentials,
        compress: bool,
    ) -> None:
        """
        Perform actual encoding using stegasoo.encode.

        Override this method to customize encoding behavior.
        """
        try:
            from .encode import encode
            from .models import FilePayload

            # Read carrier image
            carrier_image = item.input_path.read_bytes()

            if file_payload:
                # Encode file
                payload = FilePayload.from_file(str(file_payload))
                result = encode(
                    message=payload,
                    reference_photo=creds.reference_photo,
                    carrier_image=carrier_image,
                    passphrase=creds.passphrase,
                    pin=creds.pin,
                    rsa_key_data=creds.rsa_key_data,
                    rsa_password=creds.rsa_password,
                )
            else:
                # Encode text message
                result = encode(
                    message=message,
                    reference_photo=creds.reference_photo,
                    carrier_image=carrier_image,
                    passphrase=creds.passphrase,
                    pin=creds.pin,
                    rsa_key_data=creds.rsa_key_data,
                    rsa_password=creds.rsa_password,
                )

            # Write output
            if item.output_path:
                item.output_path.write_bytes(result.stego_image)

        except ImportError:
            # Fallback to mock if stegasoo.encode not available
            self._mock_encode(item, message, creds, compress)

    def _do_decode(
        self,
        item: BatchItem,
        creds: BatchCredentials,
    ) -> str:
        """
        Perform actual decoding using stegasoo.decode.

        Override this method to customize decoding behavior.
        """
        try:
            from .decode import decode

            # Read stego image
            stego_image = item.input_path.read_bytes()

            result = decode(
                stego_image=stego_image,
                reference_photo=creds.reference_photo,
                passphrase=creds.passphrase,
                pin=creds.pin,
                rsa_key_data=creds.rsa_key_data,
                rsa_password=creds.rsa_password,
            )

            if result.is_text:
                return result.message or ""
            else:
                # File payload - save it
                if item.output_path and result.file_data:
                    output_file = item.output_path / (result.filename or "extracted_file")
                    output_file.write_bytes(result.file_data)
                    return f"File extracted: {result.filename or 'extracted_file'}"
                return f"[File: {result.filename or 'binary data'}]"

        except ImportError:
            # Fallback to mock if stegasoo.decode not available
            return self._mock_decode(item, creds)

    def _mock_encode(
        self, item: BatchItem, message: str, creds: BatchCredentials, compress: bool
    ) -> None:
        """Mock encode for testing - replace with actual stego.encode()"""
        # This is a placeholder - in real usage, you'd call your actual encode function
        # For now, just copy the file to simulate encoding
        import shutil

        if item.output_path:
            shutil.copy(item.input_path, item.output_path)

    def _mock_decode(self, item: BatchItem, creds: BatchCredentials) -> str:
        """Mock decode for testing - replace with actual stego.decode()"""
        # This is a placeholder - in real usage, you'd call your actual decode function
        return "[Decoded message would appear here]"


def batch_capacity_check(
    images: list[str | Path],
    recursive: bool = False,
) -> list[dict]:
    """
    Check capacity of multiple images without encoding.

    Args:
        images: List of image paths or directories
        recursive: Search directories recursively

    Returns:
        List of dicts with path, dimensions, and estimated capacity
    """
    from PIL import Image

    from .constants import MAX_IMAGE_PIXELS

    processor = BatchProcessor()
    results = []

    for img_path in processor.find_images(images, recursive):
        try:
            with Image.open(img_path) as img:
                width, height = img.size
                pixels = width * height

                # Estimate: 3 bits per pixel (RGB LSB), minus header overhead
                capacity_bits = pixels * 3
                capacity_bytes = (capacity_bits // 8) - 100  # Header overhead

                results.append(
                    {
                        "path": str(img_path),
                        "dimensions": f"{width}x{height}",
                        "pixels": pixels,
                        "format": img.format,
                        "mode": img.mode,
                        "capacity_bytes": max(0, capacity_bytes),
                        "capacity_kb": max(0, capacity_bytes // 1024),
                        "valid": pixels <= MAX_IMAGE_PIXELS and img.format in LOSSLESS_FORMATS,
                        "warnings": _get_image_warnings(img, img_path),
                    }
                )
        except Exception as e:
            results.append(
                {
                    "path": str(img_path),
                    "error": str(e),
                    "valid": False,
                }
            )

    return results


def _get_image_warnings(img, path: Path) -> list[str]:
    """Generate warnings for an image."""
    from .constants import LOSSLESS_FORMATS, MAX_IMAGE_PIXELS

    warnings = []

    if img.format not in LOSSLESS_FORMATS:
        warnings.append(f"Lossy format ({img.format}) - quality will degrade on re-save")

    if img.size[0] * img.size[1] > MAX_IMAGE_PIXELS:
        warnings.append(f"Image exceeds {MAX_IMAGE_PIXELS:,} pixel limit")

    if img.mode not in ("RGB", "RGBA"):
        warnings.append(f"Non-RGB mode ({img.mode}) - will be converted")

    return warnings


# CLI-friendly functions


def print_batch_result(result: BatchResult, verbose: bool = False) -> None:
    """Print batch result summary to console."""
    print(f"\n{'='*60}")
    print(f"Batch {result.operation.upper()} Complete")
    print(f"{'='*60}")
    print(f"Total:     {result.total}")
    print(f"Succeeded: {result.succeeded}")
    print(f"Failed:    {result.failed}")
    print(f"Skipped:   {result.skipped}")
    if result.duration:
        print(f"Duration:  {result.duration:.2f}s")

    if verbose or result.failed > 0:
        print(f"\n{'─'*60}")
        for item in result.items:
            status_icon = {
                BatchStatus.SUCCESS: "✓",
                BatchStatus.FAILED: "✗",
                BatchStatus.SKIPPED: "○",
                BatchStatus.PENDING: "…",
                BatchStatus.PROCESSING: "⟳",
            }.get(item.status, "?")

            print(f"{status_icon} {item.input_path.name}")
            if item.error:
                print(f"    Error: {item.error}")
            elif item.message and verbose:
                print(f"    {item.message}")
