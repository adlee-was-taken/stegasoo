"""
Stegasoo Constants and Configuration (v4.0.2 - Web UI Authentication)

Central location for all magic numbers, limits, and crypto parameters.
All version numbers, limits, and configuration values should be defined here.

CHANGES in v4.0.2:
- Added Web UI authentication with SQLite3 user storage
- Added optional HTTPS with auto-generated self-signed certificates
- UI improvements for QR preview panels and PIN/channel columns

BREAKING CHANGES in v4.0.0:
- Added channel key support for deployment/group isolation
- FORMAT_VERSION bumped to 5 (adds flags byte to header)
- Header size increased by 1 byte for flags

BREAKING CHANGES in v3.2.0:
- Removed date dependency from cryptographic operations
- Renamed day_phrase → passphrase throughout codebase
"""

from pathlib import Path

# ============================================================================
# VERSION
# ============================================================================

__version__ = "4.1.3"

# ============================================================================
# FILE FORMAT
# ============================================================================

MAGIC_HEADER = b"\x89ST3"

# FORMAT VERSION HISTORY:
# Version 1-3: Date-dependent encryption (v3.0.x - v3.1.x)
# Version 4: Date-independent encryption (v3.2.0)
# Version 5: Channel key support (v4.0.0) - adds flags byte to header
FORMAT_VERSION = 5

# Payload type markers
PAYLOAD_TEXT = 0x01
PAYLOAD_FILE = 0x02

# ============================================================================
# CRYPTO PARAMETERS
# ============================================================================

SALT_SIZE = 32
IV_SIZE = 12
TAG_SIZE = 16

# Argon2 parameters (memory-hard KDF)
ARGON2_TIME_COST = 4
ARGON2_MEMORY_COST = 256 * 1024  # 256 MB
ARGON2_PARALLELISM = 4

# PBKDF2 fallback parameters
PBKDF2_ITERATIONS = 600000

# ============================================================================
# INPUT LIMITS
# ============================================================================

MAX_IMAGE_PIXELS = 24_000_000  # ~24 megapixels
MIN_IMAGE_PIXELS = 256 * 256  # Minimum viable image size

MAX_MESSAGE_SIZE = 250_000  # 250 KB (text messages)
MAX_MESSAGE_CHARS = 250_000  # Alias for clarity in templates
MIN_MESSAGE_LENGTH = 1  # Minimum message length
MAX_MESSAGE_LENGTH = MAX_MESSAGE_SIZE  # Alias for consistency

MAX_PAYLOAD_SIZE = MAX_MESSAGE_SIZE  # Maximum payload size (alias)
MAX_FILENAME_LENGTH = 255  # Max filename length to store

# File size limits
MAX_FILE_SIZE = 30 * 1024 * 1024  # 30MB total file size
MAX_FILE_PAYLOAD_SIZE = 2 * 1024 * 1024  # 2MB payload
MAX_UPLOAD_SIZE = 30 * 1024 * 1024  # 30MB max upload (Flask)

# PIN configuration
MIN_PIN_LENGTH = 6
MAX_PIN_LENGTH = 9
DEFAULT_PIN_LENGTH = 6

# Passphrase configuration (v3.2.0: renamed from PHRASE to PASSPHRASE)
# Increased defaults to compensate for removed date entropy (~33 bits)
MIN_PASSPHRASE_WORDS = 3
MAX_PASSPHRASE_WORDS = 12
DEFAULT_PASSPHRASE_WORDS = 4  # Increased from 3 (was DEFAULT_PHRASE_WORDS)
RECOMMENDED_PASSPHRASE_WORDS = 4  # Best practice guideline

# Legacy aliases for backward compatibility during transition
MIN_PHRASE_WORDS = MIN_PASSPHRASE_WORDS
MAX_PHRASE_WORDS = MAX_PASSPHRASE_WORDS
DEFAULT_PHRASE_WORDS = DEFAULT_PASSPHRASE_WORDS

# RSA configuration
MIN_RSA_BITS = 2048
VALID_RSA_SIZES = (2048, 3072, 4096)
DEFAULT_RSA_BITS = 2048

MIN_KEY_PASSWORD_LENGTH = 8

# ============================================================================
# WEB/API CONFIGURATION
# ============================================================================

# Temporary file storage
TEMP_FILE_EXPIRY = 300  # 5 minutes in seconds
TEMP_FILE_EXPIRY_MINUTES = 5

# Thumbnail settings
THUMBNAIL_SIZE = (250, 250)  # Maximum dimensions for thumbnails
THUMBNAIL_QUALITY = 85

# QR Code limits
QR_MAX_BINARY = 2900  # Safe limit for binary data in QR
QR_CROP_PADDING_PERCENT = 0.1  # Default padding when cropping QR codes
QR_CROP_MIN_PADDING_PX = 10  # Minimum padding in pixels

# ============================================================================
# FILE TYPES
# ============================================================================

ALLOWED_IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "bmp", "gif"}
ALLOWED_KEY_EXTENSIONS = {"pem", "key"}

# Lossless image formats (safe for steganography)
LOSSLESS_FORMATS = {"PNG", "BMP", "TIFF"}

# Supported image formats for steganography
SUPPORTED_IMAGE_FORMATS = LOSSLESS_FORMATS

# ============================================================================
# DAYS (kept for organizational/UI purposes, not crypto)
# ============================================================================

DAY_NAMES = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")

# ============================================================================
# COMPRESSION
# ============================================================================

# Minimum payload size to attempt compression (smaller often expands)
MIN_COMPRESS_SIZE = 64

# Zlib compression level (1-9, higher = better ratio, slower)
ZLIB_COMPRESSION_LEVEL = 6

# Compression header magic bytes
COMPRESSION_MAGIC = b"\x00CMP"

# ============================================================================
# BATCH PROCESSING
# ============================================================================

# Default parallel workers for batch operations
BATCH_DEFAULT_WORKERS = 4

# Maximum parallel workers
BATCH_MAX_WORKERS = 16

# Output filename suffix for batch encode
BATCH_OUTPUT_SUFFIX = "_encoded"

# ============================================================================
# DATA FILES
# ============================================================================


def get_data_dir() -> Path:
    """Get the data directory path."""
    # Check multiple locations
    # From src/stegasoo/constants.py:
    #   .parent = src/stegasoo/
    #   .parent.parent = src/
    #   .parent.parent.parent = project root (where data/ lives)
    candidates = [
        Path(__file__).parent.parent.parent / "data",  # Development: src/stegasoo -> project root
        Path(__file__).parent / "data",  # Installed package
        Path("/app/data"),  # Docker
        Path.cwd() / "data",  # Current directory
        Path.cwd().parent / "data",  # One level up from cwd
        Path.cwd().parent.parent / "data",  # Two levels up from cwd
    ]

    for path in candidates:
        if path.exists():
            return path

    # Default to first candidate
    return candidates[0]


def get_bip39_words() -> list[str]:
    """Load BIP-39 wordlist."""
    wordlist_path = get_data_dir() / "bip39-words.txt"

    if not wordlist_path.exists():
        raise FileNotFoundError(
            f"BIP-39 wordlist not found at {wordlist_path}. "
            "Please ensure bip39-words.txt is in the data directory."
        )

    with open(wordlist_path) as f:
        return [line.strip() for line in f if line.strip()]


# Lazy-loaded wordlist
_bip39_words: list[str] | None = None


def get_wordlist() -> list[str]:
    """Get the BIP-39 wordlist (cached)."""
    global _bip39_words
    if _bip39_words is None:
        _bip39_words = get_bip39_words()
    return _bip39_words


# =============================================================================
# DCT STEGANOGRAPHY (v3.0+)
# =============================================================================

# Embedding modes
EMBED_MODE_LSB = "lsb"  # Spatial LSB embedding (default, original mode)
EMBED_MODE_DCT = "dct"  # DCT domain embedding (new in v3.0)
EMBED_MODE_AUTO = "auto"  # Auto-detect on decode

# DCT-specific constants
DCT_MAGIC_HEADER = b"\x89DCT"  # Magic header for DCT mode
DCT_FORMAT_VERSION = 1
DCT_STEP_SIZE = 8  # QIM quantization step

# Recovery key obfuscation - FIXED value for admin recovery QR codes
# SHA256("\x89ST3\x89DCT") - hardcoded so it never changes even if headers are added
# Used to XOR recovery keys in QR codes so they scan as gibberish
RECOVERY_OBFUSCATION_KEY = bytes.fromhex(
    "d6c70bce27780db942562550e9fe1459"
    "9dfdb8421f5acc79696b05db4e7afbd2"
)  # 32 bytes

# Valid embedding modes
VALID_EMBED_MODES = {EMBED_MODE_LSB, EMBED_MODE_DCT}

# Capacity estimation constants
LSB_BYTES_PER_PIXEL = 3 / 8  # 3 bits per pixel (RGB, 1 bit per channel) / 8 bits per byte
DCT_BYTES_PER_PIXEL = 0.125  # Approximate for DCT mode (varies by implementation)


def detect_stego_mode(encrypted_data: bytes) -> str:
    """
    Detect embedding mode from encrypted payload header.

    Args:
        encrypted_data: First few bytes of extracted payload

    Returns:
        'lsb' or 'dct' or 'unknown'
    """
    if len(encrypted_data) < 4:
        return "unknown"

    header = encrypted_data[:4]

    if header == b"\x89ST3":
        return EMBED_MODE_LSB
    elif header == b"\x89DCT":
        return EMBED_MODE_DCT
    else:
        return "unknown"
