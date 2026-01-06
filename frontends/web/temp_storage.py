"""
File-based Temporary Storage

Stores temp files on disk instead of in-memory dict.
This allows multiple Gunicorn workers to share temp files
and survives service restarts within the expiry window.

Files are stored in a temp directory with:
- {file_id}.data - The actual file data
- {file_id}.json - Metadata (filename, timestamp, mime_type, etc.)

IMPORTANT: This module ONLY manages files in the temp_files/ directory.
It does NOT touch instance/ (auth database) or any other directories.
"""

import json
import os
import shutil
import time
from pathlib import Path
from threading import Lock

# Default temp directory (can be overridden)
DEFAULT_TEMP_DIR = Path(__file__).parent / "temp_files"

# Lock for thread-safe operations
_lock = Lock()

# Module-level temp directory (set on init)
_temp_dir: Path = DEFAULT_TEMP_DIR


def init(temp_dir: Path | str | None = None):
    """Initialize temp storage with optional custom directory."""
    global _temp_dir
    _temp_dir = Path(temp_dir) if temp_dir else DEFAULT_TEMP_DIR
    _temp_dir.mkdir(parents=True, exist_ok=True)


def _data_path(file_id: str) -> Path:
    """Get path for file data."""
    return _temp_dir / f"{file_id}.data"


def _meta_path(file_id: str) -> Path:
    """Get path for file metadata."""
    return _temp_dir / f"{file_id}.json"


def _thumb_path(thumb_id: str) -> Path:
    """Get path for thumbnail data."""
    return _temp_dir / f"{thumb_id}.thumb"


def save_temp_file(file_id: str, data: bytes, metadata: dict) -> None:
    """
    Save a temp file with its metadata.

    Args:
        file_id: Unique identifier for the file
        data: File contents as bytes
        metadata: Dict with filename, mime_type, timestamp, etc.
    """
    init()  # Ensure directory exists

    with _lock:
        # Add timestamp if not present
        if "timestamp" not in metadata:
            metadata["timestamp"] = time.time()

        # Write data file
        _data_path(file_id).write_bytes(data)

        # Write metadata
        _meta_path(file_id).write_text(json.dumps(metadata))


def get_temp_file(file_id: str) -> dict | None:
    """
    Get a temp file and its metadata.

    Returns:
        Dict with 'data' (bytes) and all metadata fields, or None if not found.
    """
    init()

    data_file = _data_path(file_id)
    meta_file = _meta_path(file_id)

    if not data_file.exists() or not meta_file.exists():
        return None

    try:
        data = data_file.read_bytes()
        metadata = json.loads(meta_file.read_text())
        return {"data": data, **metadata}
    except (OSError, json.JSONDecodeError):
        return None


def has_temp_file(file_id: str) -> bool:
    """Check if a temp file exists."""
    init()
    return _data_path(file_id).exists() and _meta_path(file_id).exists()


def delete_temp_file(file_id: str) -> None:
    """Delete a temp file and its metadata."""
    init()

    with _lock:
        _data_path(file_id).unlink(missing_ok=True)
        _meta_path(file_id).unlink(missing_ok=True)


def save_thumbnail(thumb_id: str, data: bytes) -> None:
    """Save a thumbnail."""
    init()

    with _lock:
        _thumb_path(thumb_id).write_bytes(data)


def get_thumbnail(thumb_id: str) -> bytes | None:
    """Get thumbnail data."""
    init()

    thumb_file = _thumb_path(thumb_id)
    if not thumb_file.exists():
        return None

    try:
        return thumb_file.read_bytes()
    except OSError:
        return None


def delete_thumbnail(thumb_id: str) -> None:
    """Delete a thumbnail."""
    init()

    with _lock:
        _thumb_path(thumb_id).unlink(missing_ok=True)


def cleanup_expired(max_age_seconds: float) -> int:
    """
    Delete expired temp files.

    Args:
        max_age_seconds: Maximum age in seconds before expiry

    Returns:
        Number of files deleted
    """
    init()

    now = time.time()
    deleted = 0

    with _lock:
        # Find all metadata files
        for meta_file in _temp_dir.glob("*.json"):
            try:
                metadata = json.loads(meta_file.read_text())
                timestamp = metadata.get("timestamp", 0)

                if now - timestamp > max_age_seconds:
                    file_id = meta_file.stem
                    _data_path(file_id).unlink(missing_ok=True)
                    meta_file.unlink(missing_ok=True)
                    # Also delete thumbnail if exists
                    _thumb_path(f"{file_id}_thumb").unlink(missing_ok=True)
                    deleted += 1
            except (OSError, json.JSONDecodeError):
                # Remove corrupted files
                meta_file.unlink(missing_ok=True)
                deleted += 1

    return deleted


def cleanup_all() -> int:
    """
    Delete all temp files. Call on service start/stop.

    Returns:
        Number of files deleted
    """
    init()

    deleted = 0

    with _lock:
        for f in _temp_dir.iterdir():
            if f.is_file():
                f.unlink(missing_ok=True)
                deleted += 1

    return deleted


def get_stats() -> dict:
    """Get temp storage statistics."""
    init()

    files = list(_temp_dir.glob("*.data"))
    total_size = sum(f.stat().st_size for f in files if f.exists())

    return {
        "file_count": len(files),
        "total_size_bytes": total_size,
        "temp_dir": str(_temp_dir),
    }
