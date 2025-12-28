"""
Stegasoo Constants and Configuration

Central location for all magic numbers, limits, and crypto parameters.
"""

import os
from pathlib import Path

# ============================================================================
# VERSION
# ============================================================================

__version__ = "2.1.1"

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

MAX_IMAGE_PIXELS = 16_000_000     # ~16 megapixels (4000x4000)
MAX_MESSAGE_SIZE = 250_000        # 250 KB (text messages)
MAX_FILE_PAYLOAD_SIZE = 250_000   # 250 KB (file payloads)
MAX_FILENAME_LENGTH = 255         # Max filename length to store
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB (upload limit)

MIN_PIN_LENGTH = 6
MAX_PIN_LENGTH = 9
DEFAULT_PIN_LENGTH = 6

MIN_PHRASE_WORDS = 3
MAX_PHRASE_WORDS = 12
DEFAULT_PHRASE_WORDS = 3

MIN_RSA_BITS = 2048
VALID_RSA_SIZES = (2048, 3072, 4096)
DEFAULT_RSA_BITS = 2048

MIN_KEY_PASSWORD_LENGTH = 8

# ============================================================================
# FILE TYPES
# ============================================================================

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}
ALLOWED_KEY_EXTENSIONS = {'pem', 'key'}

# ============================================================================
# DAYS
# ============================================================================

DAY_NAMES = ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')

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
