"""
Stegasoo Utilities

Secure deletion, filename generation, and other helpers.
"""

import io
import os
import random
import secrets
import shutil
from datetime import date
from pathlib import Path

from PIL import Image

from .constants import DAY_NAMES
from .debug import debug


def read_image_exif(image_data: bytes) -> dict:
    """
    Read EXIF metadata from an image.

    Args:
        image_data: Raw image bytes

    Returns:
        Dict with EXIF fields (tag names as keys)

    Example:
        >>> exif = read_image_exif(photo_bytes)
        >>> print(exif.get('Make'))  # Camera manufacturer
    """
    from PIL.ExifTags import GPSTAGS, TAGS

    result = {}

    try:
        img = Image.open(io.BytesIO(image_data))
        exif_data = img._getexif()

        if exif_data:
            for tag_id, value in exif_data.items():
                tag = TAGS.get(tag_id, str(tag_id))

                # Handle GPS data specially
                if tag == "GPSInfo" and isinstance(value, dict):
                    gps = {}
                    for gps_tag_id, gps_value in value.items():
                        gps_tag = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                        # Convert tuples/IFDRational to simple types
                        if hasattr(gps_value, "numerator"):
                            gps[gps_tag] = float(gps_value)
                        elif isinstance(gps_value, tuple):
                            gps[gps_tag] = [
                                float(v) if hasattr(v, "numerator") else v
                                for v in gps_value
                            ]
                        else:
                            gps[gps_tag] = gps_value
                    result[tag] = gps
                # Convert IFDRational to float
                elif hasattr(value, "numerator"):
                    result[tag] = float(value)
                # Convert bytes to string if possible
                elif isinstance(value, bytes):
                    try:
                        result[tag] = value.decode("utf-8", errors="replace").strip("\x00")
                    except Exception:
                        result[tag] = f"<{len(value)} bytes>"
                # Handle tuples of IFDRational
                elif isinstance(value, tuple) and value and hasattr(value[0], "numerator"):
                    result[tag] = [float(v) for v in value]
                else:
                    result[tag] = value

        img.close()
    except Exception as e:
        debug.print(f"Error reading EXIF: {e}")

    return result


def write_image_exif(image_data: bytes, exif_updates: dict) -> bytes:
    """
    Write/update EXIF metadata in a JPEG image.

    Args:
        image_data: Raw JPEG image bytes
        exif_updates: Dict of EXIF fields to update (tag names as keys)
                     Use None as value to delete a field

    Returns:
        Image bytes with updated EXIF

    Raises:
        ValueError: If image is not JPEG or piexif not available

    Example:
        >>> updated = write_image_exif(jpeg_bytes, {"Artist": "John Doe"})
    """
    try:
        import piexif
    except ImportError:
        raise ValueError("piexif required for EXIF editing: pip install piexif")

    # Verify it's a JPEG
    if not image_data[:2] == b"\xff\xd8":
        raise ValueError("EXIF editing only supported for JPEG images")

    debug.print(f"Writing EXIF updates: {list(exif_updates.keys())}")

    # Load existing EXIF
    try:
        exif_dict = piexif.load(image_data)
    except Exception:
        # No existing EXIF, start fresh
        exif_dict = {"0th": {}, "Exif": {}, "GPS": {}, "1st": {}, "thumbnail": None}

    # Map common tag names to piexif IFD and tag IDs
    tag_mapping = {
        # 0th IFD (main image)
        "Make": (piexif.ImageIFD.Make, "0th"),
        "Model": (piexif.ImageIFD.Model, "0th"),
        "Software": (piexif.ImageIFD.Software, "0th"),
        "Artist": (piexif.ImageIFD.Artist, "0th"),
        "Copyright": (piexif.ImageIFD.Copyright, "0th"),
        "ImageDescription": (piexif.ImageIFD.ImageDescription, "0th"),
        "DateTime": (piexif.ImageIFD.DateTime, "0th"),
        "Orientation": (piexif.ImageIFD.Orientation, "0th"),
        # Exif IFD
        "DateTimeOriginal": (piexif.ExifIFD.DateTimeOriginal, "Exif"),
        "DateTimeDigitized": (piexif.ExifIFD.DateTimeDigitized, "Exif"),
        "UserComment": (piexif.ExifIFD.UserComment, "Exif"),
        "ExposureTime": (piexif.ExifIFD.ExposureTime, "Exif"),
        "FNumber": (piexif.ExifIFD.FNumber, "Exif"),
        "ISOSpeedRatings": (piexif.ExifIFD.ISOSpeedRatings, "Exif"),
        "FocalLength": (piexif.ExifIFD.FocalLength, "Exif"),
        "LensMake": (piexif.ExifIFD.LensMake, "Exif"),
        "LensModel": (piexif.ExifIFD.LensModel, "Exif"),
    }

    for tag_name, value in exif_updates.items():
        if tag_name not in tag_mapping:
            debug.print(f"Unknown EXIF tag: {tag_name}, skipping")
            continue

        tag_id, ifd = tag_mapping[tag_name]

        if value is None:
            # Delete the tag
            if tag_id in exif_dict[ifd]:
                del exif_dict[ifd][tag_id]
                debug.print(f"Deleted EXIF tag: {tag_name}")
        else:
            # Set the tag (encode strings as bytes)
            if isinstance(value, str):
                value = value.encode("utf-8")
            exif_dict[ifd][tag_id] = value
            debug.print(f"Set EXIF tag: {tag_name}")

    # Serialize EXIF and insert into image
    exif_bytes = piexif.dump(exif_dict)
    output = io.BytesIO()
    img = Image.open(io.BytesIO(image_data))
    img.save(output, "JPEG", exif=exif_bytes, quality=95)
    output.seek(0)

    debug.print(f"EXIF updated: {len(image_data)} -> {len(output.getvalue())} bytes")
    return output.getvalue()


def strip_image_metadata(image_data: bytes, output_format: str = "PNG") -> bytes:
    """
    Remove all metadata (EXIF, ICC profiles, etc.) from an image.

    Creates a fresh image with only pixel data - no EXIF, GPS coordinates,
    camera info, timestamps, or other potentially sensitive metadata.

    Args:
        image_data: Raw image bytes
        output_format: Output format ('PNG', 'BMP', 'TIFF')

    Returns:
        Clean image bytes with no metadata

    Example:
        >>> clean = strip_image_metadata(photo_bytes)
        >>> # EXIF data is now removed
    """
    debug.print(f"Stripping metadata, output format: {output_format}")

    img = Image.open(io.BytesIO(image_data))

    # Convert to RGB if needed (handles RGBA, P, L, etc.)
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGB")

    # Create fresh image - this discards all metadata
    clean = Image.new(img.mode, img.size)
    clean.putdata(list(img.getdata()))

    output = io.BytesIO()
    clean.save(output, output_format.upper())
    output.seek(0)

    debug.print(f"Metadata stripped: {len(image_data)} -> {len(output.getvalue())} bytes")
    return output.getvalue()


def generate_filename(date_str: str | None = None, prefix: str = "", extension: str = "png") -> str:
    """
    Generate a filename for stego images.

    Format: {prefix}{random}_{YYYYMMDD}.{extension}

    Args:
        date_str: Date string (YYYY-MM-DD), defaults to today
        prefix: Optional prefix
        extension: File extension without dot (default: 'png')

    Returns:
        Filename string

    Example:
        >>> generate_filename("2023-12-25", "secret_", "png")
        "secret_a1b2c3d4_20231225.png"
    """
    debug.validate(
        bool(extension) and "." not in extension,
        f"Extension must not contain dot, got '{extension}'",
    )

    if date_str is None:
        date_str = date.today().isoformat()

    date_compact = date_str.replace("-", "")
    random_hex = secrets.token_hex(4)

    # Ensure extension doesn't have a leading dot
    extension = extension.lstrip(".")

    filename = f"{prefix}{random_hex}_{date_compact}.{extension}"
    debug.print(f"Generated filename: {filename}")
    return filename


def parse_date_from_filename(filename: str) -> str | None:
    """
    Extract date from a stego filename.

    Looks for patterns like _20251227 or _2025-12-27

    Args:
        filename: Filename to parse

    Returns:
        Date string (YYYY-MM-DD) or None

    Example:
        >>> parse_date_from_filename("secret_a1b2c3d4_20231225.png")
        "2023-12-25"
    """
    import re

    # Try YYYYMMDD format
    match = re.search(r"_(\d{4})(\d{2})(\d{2})(?:\.|$)", filename)
    if match:
        year, month, day = match.groups()
        date_str = f"{year}-{month}-{day}"
        debug.print(f"Parsed date (compact): {date_str}")
        return date_str

    # Try YYYY-MM-DD format
    match = re.search(r"_(\d{4})-(\d{2})-(\d{2})(?:\.|$)", filename)
    if match:
        year, month, day = match.groups()
        date_str = f"{year}-{month}-{day}"
        debug.print(f"Parsed date (dashed): {date_str}")
        return date_str

    debug.print(f"No date found in filename: {filename}")
    return None


def get_day_from_date(date_str: str) -> str:
    """
    Get day of week name from date string.

    Args:
        date_str: Date string (YYYY-MM-DD)

    Returns:
        Day name (e.g., "Monday")

    Example:
        >>> get_day_from_date("2023-12-25")
        "Monday"
    """
    debug.validate(
        len(date_str) == 10 and date_str[4] == "-" and date_str[7] == "-",
        f"Invalid date format: {date_str}, expected YYYY-MM-DD",
    )

    try:
        year, month, day = map(int, date_str.split("-"))
        d = date(year, month, day)
        day_name = DAY_NAMES[d.weekday()]
        debug.print(f"Date {date_str} is {day_name}")
        return day_name
    except Exception as e:
        debug.exception(e, f"get_day_from_date for {date_str}")
        return ""


def get_today_date() -> str:
    """
    Get today's date as YYYY-MM-DD.

    Returns:
        Today's date string

    Example:
        >>> get_today_date()
        "2023-12-25"
    """
    today = date.today().isoformat()
    debug.print(f"Today's date: {today}")
    return today


def get_today_day() -> str:
    """
    Get today's day name.

    Returns:
        Today's day name

    Example:
        >>> get_today_day()
        "Monday"
    """
    today_day = DAY_NAMES[date.today().weekday()]
    debug.print(f"Today is {today_day}")
    return today_day


class SecureDeleter:
    """
    Securely delete files by overwriting with random data.

    Implements multi-pass overwriting before deletion.

    Example:
        >>> deleter = SecureDeleter("secret.txt", passes=3)
        >>> deleter.execute()
    """

    def __init__(self, path: str | Path, passes: int = 7):
        """
        Initialize secure deleter.

        Args:
            path: Path to file or directory
            passes: Number of overwrite passes
        """
        debug.validate(passes > 0, f"Passes must be positive, got {passes}")

        self.path = Path(path)
        self.passes = passes
        debug.print(f"SecureDeleter initialized for {self.path} with {passes} passes")

    def _overwrite_file(self, file_path: Path) -> None:
        """Overwrite file with random data multiple times."""
        if not file_path.exists() or not file_path.is_file():
            debug.print(f"File does not exist or is not a file: {file_path}")
            return

        length = file_path.stat().st_size
        debug.print(f"Overwriting file {file_path} ({length} bytes)")

        if length == 0:
            debug.print("File is empty, nothing to overwrite")
            return

        patterns = [b"\x00", b"\xff", bytes([random.randint(0, 255)])]

        for pass_num in range(self.passes):
            debug.print(f"Overwrite pass {pass_num + 1}/{self.passes}")
            with open(file_path, "r+b") as f:
                for pattern_idx, pattern in enumerate(patterns):
                    f.seek(0)
                    # Write pattern in chunks for large files
                    chunk_size = 1024 * 1024  # 1MB chunks
                    for offset in range(0, length, chunk_size):
                        chunk = min(chunk_size, length - offset)
                        f.write(pattern * (chunk // len(pattern)))
                        f.write(pattern[: chunk % len(pattern)])

                # Final pass with random data
                f.seek(0)
                f.write(os.urandom(length))

        debug.print(f"Completed {self.passes} overwrite passes")

    def delete_file(self) -> None:
        """Securely delete a single file."""
        if self.path.is_file():
            debug.print(f"Securely deleting file: {self.path}")
            self._overwrite_file(self.path)
            self.path.unlink()
            debug.print(f"File deleted: {self.path}")
        else:
            debug.print(f"Not a file: {self.path}")

    def delete_directory(self) -> None:
        """Securely delete a directory and all contents."""
        if not self.path.is_dir():
            debug.print(f"Not a directory: {self.path}")
            return

        debug.print(f"Securely deleting directory: {self.path}")

        # First, securely overwrite all files
        file_count = 0
        for file_path in self.path.rglob("*"):
            if file_path.is_file():
                self._overwrite_file(file_path)
                file_count += 1

        debug.print(f"Overwrote {file_count} files")

        # Then remove the directory tree
        shutil.rmtree(self.path)
        debug.print(f"Directory deleted: {self.path}")

    def execute(self) -> None:
        """Securely delete the path (file or directory)."""
        debug.print(f"Executing secure deletion: {self.path}")
        if self.path.is_file():
            self.delete_file()
        elif self.path.is_dir():
            self.delete_directory()
        else:
            debug.print(f"Path does not exist: {self.path}")


def secure_delete(path: str | Path, passes: int = 7) -> None:
    """
    Convenience function for secure deletion.

    Args:
        path: Path to file or directory
        passes: Number of overwrite passes

    Example:
        >>> secure_delete("secret.txt", passes=3)
    """
    debug.print(f"secure_delete called: {path}, passes={passes}")
    SecureDeleter(path, passes).execute()


def format_file_size(size_bytes: int) -> str:
    """
    Format file size for display.

    Args:
        size_bytes: Size in bytes

    Returns:
        Human-readable string (e.g., "1.5 MB")

    Example:
        >>> format_file_size(1500000)
        "1.5 MB"
    """
    debug.validate(size_bytes >= 0, f"File size cannot be negative: {size_bytes}")

    size: float = float(size_bytes)
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def format_number(n: int) -> str:
    """
    Format number with commas.

    Args:
        n: Integer to format

    Returns:
        Formatted string

    Example:
        >>> format_number(1234567)
        "1,234,567"
    """
    debug.validate(isinstance(n, int), f"Input must be integer, got {type(n)}")
    return f"{n:,}"


def clamp(value: int, min_val: int, max_val: int) -> int:
    """
    Clamp value to range.

    Args:
        value: Value to clamp
        min_val: Minimum allowed value
        max_val: Maximum allowed value

    Returns:
        Clamped value

    Example:
        >>> clamp(15, 0, 10)
        10
    """
    debug.validate(min_val <= max_val, f"min_val ({min_val}) must be <= max_val ({max_val})")
    return max(min_val, min(max_val, value))
