"""
Stegasoo - Secure Steganography with Multi-Factor Authentication (v4.0.1)

Changes in v4.0.0:
- Added channel key support for deployment/group isolation
- New functions: get_channel_key, get_channel_fingerprint, generate_channel_key, etc.
- encode() and decode() now accept channel_key parameter
"""

__version__ = "4.0.1"

# Core functionality
from .encode import encode
from .decode import decode, decode_file, decode_text

# Credential generation
from .generate import (
    generate_pin,
    generate_passphrase,
    generate_rsa_key,
    generate_credentials,
    export_rsa_key_pem,
    load_rsa_key,
)

# Image utilities
from .image_utils import (
    get_image_info,
    compare_capacity,
)

# Utilities
from .utils import generate_filename

# Crypto functions
from .crypto import has_argon2, get_active_channel_key, get_channel_fingerprint

# Channel key management (v4.0.0)
from .channel import (
    generate_channel_key,
    get_channel_key,
    set_channel_key,
    clear_channel_key,
    has_channel_key,
    get_channel_status,
    validate_channel_key,
    format_channel_key,
)

# Steganography functions
from .steganography import (
    has_dct_support,
    compare_modes,
    will_fit_by_mode,
)

# QR Code utilities - optional, may not be available
try:
    from .qr_utils import (
        generate_qr_code,
        extract_key_from_qr,
        detect_and_crop_qr,
    )
    HAS_QR_UTILS = True
except ImportError:
    HAS_QR_UTILS = False
    generate_qr_code = None
    extract_key_from_qr = None
    detect_and_crop_qr = None

# Validation
from .validation import (
    validate_passphrase,
    validate_pin,
    validate_rsa_key,
    validate_message,
    validate_file_payload,
    validate_image,
    validate_security_factors,
)

# Validation aliases for public API
validate_reference_photo = validate_image
validate_carrier = validate_image

# Additional validators
from .validation import (
    validate_embed_mode,
    validate_dct_output_format,
    validate_dct_color_mode,
)

# Models
from .models import (
    ImageInfo,
    CapacityComparison,
    GenerateResult,
    EncodeResult,
    DecodeResult,
    FilePayload,
    Credentials,
    ValidationResult,
)

# Exceptions
from .exceptions import (
    StegasooError,
    ValidationError,
    PinValidationError,
    MessageValidationError,
    ImageValidationError,
    KeyValidationError,
    SecurityFactorError,
    CryptoError,
    EncryptionError,
    DecryptionError,
    KeyDerivationError,
    KeyGenerationError,
    KeyPasswordError,
    SteganographyError,
    CapacityError,
    ExtractionError,
    EmbeddingError,
    InvalidHeaderError,
)

# Constants
from .constants import (
    FORMAT_VERSION,
    MIN_PASSPHRASE_WORDS,
    RECOMMENDED_PASSPHRASE_WORDS,
    DEFAULT_PASSPHRASE_WORDS,
    MAX_PASSPHRASE_WORDS,
    MIN_PIN_LENGTH,
    MAX_PIN_LENGTH,
    MAX_MESSAGE_SIZE,
    MIN_IMAGE_PIXELS,
    MAX_IMAGE_PIXELS,
    LOSSLESS_FORMATS,
    EMBED_MODE_LSB,
    EMBED_MODE_DCT,
    EMBED_MODE_AUTO,
)

# Aliases for backward compatibility
MIN_MESSAGE_LENGTH = 1
MAX_MESSAGE_LENGTH = MAX_MESSAGE_SIZE
MAX_PAYLOAD_SIZE = MAX_MESSAGE_SIZE
SUPPORTED_IMAGE_FORMATS = LOSSLESS_FORMATS
LSB_BYTES_PER_PIXEL = 3 / 8
DCT_BYTES_PER_PIXEL = 0.125

__all__ = [
    # Version
    "__version__",

    # Core
    "encode",
    "decode",
    "decode_file",
    "decode_text",
    
    # Generation
    "generate_pin",
    "generate_passphrase",
    "generate_rsa_key",
    "generate_credentials",
    "export_rsa_key_pem",
    "load_rsa_key",
    
    # Channel key management (v4.0.0)
    "generate_channel_key",
    "get_channel_key",
    "set_channel_key",
    "clear_channel_key",
    "has_channel_key",
    "get_channel_status",
    "validate_channel_key",
    "format_channel_key",
    "get_active_channel_key",
    "get_channel_fingerprint",
    
    # Image utilities
    "get_image_info",
    "compare_capacity",
    
    # Utilities
    "generate_filename",
    
    # Crypto
    "has_argon2",
    
    # Steganography
    "has_dct_support",
    "compare_modes",
    "will_fit_by_mode",
    
    # QR utilities
    "generate_qr_code",
    "extract_key_from_qr",
    "detect_and_crop_qr",
    "HAS_QR_UTILS",
    
    # Validation
    "validate_reference_photo",
    "validate_carrier",
    "validate_message",
    "validate_file_payload",
    "validate_passphrase",
    "validate_pin",
    "validate_rsa_key",
    "validate_security_factors",
    "validate_embed_mode",
    "validate_dct_output_format",
    "validate_dct_color_mode",
    "validate_channel_key",
    
    # Models
    "ImageInfo",
    "CapacityComparison",
    "GenerateResult",
    "EncodeResult",
    "DecodeResult",
    "FilePayload",
    "Credentials",
    "ValidationResult",
    
    # Exceptions
    "StegasooError",
    "ValidationError",
    "PinValidationError",
    "MessageValidationError",
    "ImageValidationError",
    "KeyValidationError",
    "SecurityFactorError",
    "CryptoError",
    "EncryptionError",
    "DecryptionError",
    "KeyDerivationError",
    "KeyGenerationError",
    "KeyPasswordError",
    "SteganographyError",
    "CapacityError",
    "ExtractionError",
    "EmbeddingError",
    "InvalidHeaderError",
    
    # Constants
    "FORMAT_VERSION",
    "MIN_PASSPHRASE_WORDS",
    "RECOMMENDED_PASSPHRASE_WORDS",
    "DEFAULT_PASSPHRASE_WORDS",
    "MAX_PASSPHRASE_WORDS",
    "MIN_PIN_LENGTH",
    "MAX_PIN_LENGTH",
    "MIN_MESSAGE_LENGTH",
    "MAX_MESSAGE_LENGTH",
    "MAX_MESSAGE_SIZE",
    "MAX_PAYLOAD_SIZE",
    "MIN_IMAGE_PIXELS",
    "MAX_IMAGE_PIXELS",
    "SUPPORTED_IMAGE_FORMATS",
    "LOSSLESS_FORMATS",
    "LSB_BYTES_PER_PIXEL",
    "DCT_BYTES_PER_PIXEL",
    "EMBED_MODE_LSB",
    "EMBED_MODE_DCT",
    "EMBED_MODE_AUTO",
]
