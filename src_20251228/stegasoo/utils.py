"""
Stegasoo Utilities

Secure deletion, filename generation, and other helpers.
"""

import os
import random
import secrets
import shutil
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from .constants import DAY_NAMES


def generate_filename(
    date_str: Optional[str] = None,
    prefix: str = "",
    extension: str = "png"
) -> str:
    """
    Generate a filename for stego images.
    
    Format: {prefix}{random}_{YYYYMMDD}.{extension}
    
    Args:
        date_str: Date string (YYYY-MM-DD), defaults to today
        prefix: Optional prefix
        extension: File extension without dot (default: 'png')
        
    Returns:
        Filename string
    """
    if date_str is None:
        date_str = date.today().isoformat()
    
    date_compact = date_str.replace('-', '')
    random_hex = secrets.token_hex(4)
    
    # Ensure extension doesn't have a leading dot
    extension = extension.lstrip('.')
    
    return f"{prefix}{random_hex}_{date_compact}.{extension}"


def parse_date_from_filename(filename: str) -> Optional[str]:
    """
    Extract date from a stego filename.
    
    Looks for patterns like _20251227 or _2025-12-27
    
    Args:
        filename: Filename to parse
        
    Returns:
        Date string (YYYY-MM-DD) or None
    """
    import re
    
    # Try YYYYMMDD format
    match = re.search(r'_(\d{4})(\d{2})(\d{2})(?:\.|$)', filename)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    
    # Try YYYY-MM-DD format
    match = re.search(r'_(\d{4})-(\d{2})-(\d{2})(?:\.|$)', filename)
    if match:
        year, month, day = match.groups()
        return f"{year}-{month}-{day}"
    
    return None


def get_day_from_date(date_str: str) -> str:
    """
    Get day of week name from date string.
    
    Args:
        date_str: Date string (YYYY-MM-DD)
        
    Returns:
        Day name (e.g., "Monday")
    """
    try:
        year, month, day = map(int, date_str.split('-'))
        d = date(year, month, day)
        return DAY_NAMES[d.weekday()]
    except Exception:
        return ""


def get_today_date() -> str:
    """Get today's date as YYYY-MM-DD."""
    return date.today().isoformat()


def get_today_day() -> str:
    """Get today's day name."""
    return DAY_NAMES[date.today().weekday()]


class SecureDeleter:
    """
    Securely delete files by overwriting with random data.
    
    Implements multi-pass overwriting before deletion.
    """
    
    def __init__(self, path: str | Path, passes: int = 7):
        """
        Initialize secure deleter.
        
        Args:
            path: Path to file or directory
            passes: Number of overwrite passes
        """
        self.path = Path(path)
        self.passes = passes
    
    def _overwrite_file(self, file_path: Path) -> None:
        """Overwrite file with random data multiple times."""
        if not file_path.exists() or not file_path.is_file():
            return
        
        length = file_path.stat().st_size
        if length == 0:
            return
        
        patterns = [b'\x00', b'\xFF', bytes([random.randint(0, 255)])]
        
        for _ in range(self.passes):
            with open(file_path, 'r+b') as f:
                for pattern in patterns:
                    f.seek(0)
                    for _ in range(length):
                        f.write(pattern)
                
                # Final pass with random data
                f.seek(0)
                f.write(os.urandom(length))
    
    def delete_file(self) -> None:
        """Securely delete a single file."""
        if self.path.is_file():
            self._overwrite_file(self.path)
            self.path.unlink()
    
    def delete_directory(self) -> None:
        """Securely delete a directory and all contents."""
        if not self.path.is_dir():
            return
        
        # First, securely overwrite all files
        for file_path in self.path.rglob('*'):
            if file_path.is_file():
                self._overwrite_file(file_path)
        
        # Then remove the directory tree
        shutil.rmtree(self.path)
    
    def execute(self) -> None:
        """Securely delete the path (file or directory)."""
        if self.path.is_file():
            self.delete_file()
        elif self.path.is_dir():
            self.delete_directory()


def secure_delete(path: str | Path, passes: int = 7) -> None:
    """
    Convenience function for secure deletion.
    
    Args:
        path: Path to file or directory
        passes: Number of overwrite passes
    """
    SecureDeleter(path, passes).execute()


def format_file_size(size_bytes: int) -> str:
    """
    Format file size for display.
    
    Args:
        size_bytes: Size in bytes
        
    Returns:
        Human-readable string (e.g., "1.5 MB")
    """
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            if unit == 'B':
                return f"{size_bytes} {unit}"
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


def format_number(n: int) -> str:
    """Format number with commas."""
    return f"{n:,}"


def clamp(value: int, min_val: int, max_val: int) -> int:
    """Clamp value to range."""
    return max(min_val, min(max_val, value))
