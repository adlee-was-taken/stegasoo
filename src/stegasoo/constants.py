"""
Stegasoo Constants and Configuration

Central location for all magic numbers, limits, and crypto parameters.
All version numbers, limits, and configuration values should be defined here.
"""

import os
from pathlib import Path

# ============================================================================
# VERSION
# ============================================================================

__version__ = "2.2.0"

# ============================================================================
# FILE FORMAT
# ============================================================================

MAGIC_HEADER = b'\x89ST3'
FORMAT_VERSION = 3

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

MAX_IMAGE_PIXELS = 24_000_000     # ~24 megapixels
MAX_MESSAGE_SIZE = 250_000        # 250 KB (text messages)
MAX_MESSAGE_CHARS = 250_000       # Alias for clarity in templates
MAX_FILENAME_LENGTH = 255         # Max filename length to store

# File size limits
MAX_FILE_SIZE = 30 * 1024 * 1024        # 30MB total file size
MAX_FILE_PAYLOAD_SIZE = 2 * 1024 * 1024  # 2MB payload
MAX_UPLOAD_SIZE = 30 * 1024 * 1024       # 30MB max upload (Flask)

# PIN configuration
MIN_PIN_LENGTH = 6
MAX_PIN_LENGTH = 9
DEFAULT_PIN_LENGTH = 6

# Phrase configuration
MIN_PHRASE_WORDS = 3
MAX_PHRASE_WORDS = 12
DEFAULT_PHRASE_WORDS = 3

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

# ============================================================================
# FILE TYPES
# ============================================================================

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}
ALLOWED_KEY_EXTENSIONS = {'pem', 'key'}

# Lossless image formats (safe for steganography)
LOSSLESS_FORMATS = {'PNG', 'BMP', 'TIFF'}

# ============================================================================
# DAYS
# ============================================================================

DAY_NAMES = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')

# ============================================================================
# COMPRESSION
# ============================================================================

# Minimum payload size to attempt compression (smaller often expands)
MIN_COMPRESS_SIZE = 64

# Zlib compression level (1-9, higher = better ratio, slower)
ZLIB_COMPRESSION_LEVEL = 6

# Compression header magic bytes
COMPRESSION_MAGIC = b'\x00CMP'

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
        Path(__file__).parent.parent.parent / 'data',          # Development: src/stegasoo -> project root
        Path(__file__).parent / 'data',                        # Installed package
        Path('/app/data'),                                     # Docker
        Path.cwd() / 'data',                                   # Current directory
        Path.cwd().parent / 'data',                            # One level up from cwd
        Path.cwd().parent.parent / 'data',                     # Two levels up from cwd
    ]
    
    for path in candidates:
        if path.exists():
            return path
    
    # Default to first candidate
    return candidates[0]


def get_bip39_words() -> list[str]:
    """Load BIP-39 wordlist."""
    wordlist_path = get_data_dir() / 'bip39-words.txt'
    
    if not wordlist_path.exists():
        raise FileNotFoundError(
            f"BIP-39 wordlist not found at {wordlist_path}. "
            "Please ensure bip39-words.txt is in the data directory."
        )
    
    with open(wordlist_path, 'r') as f:
        return [line.strip() for line in f if line.strip()]


# Lazy-loaded wordlist
_bip39_words: list[str] | None = None


def get_wordlist() -> list[str]:
    """Get the BIP-39 wordlist (cached)."""
    global _bip39_words
    if _bip39_words is None:
        _bip39_words = get_bip39_words()
    return _bip39_words
