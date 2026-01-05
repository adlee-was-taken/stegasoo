"""
Stegasoo Exceptions

Custom exception classes for clear error handling across all frontends.
"""


class StegasooError(Exception):
    """Base exception for all Stegasoo errors."""

    pass


# ============================================================================
# VALIDATION ERRORS
# ============================================================================


class ValidationError(StegasooError):
    """Base class for validation errors."""

    pass


class PinValidationError(ValidationError):
    """PIN validation failed."""

    pass


class MessageValidationError(ValidationError):
    """Message validation failed."""

    pass


class ImageValidationError(ValidationError):
    """Image validation failed."""

    pass


class KeyValidationError(ValidationError):
    """RSA key validation failed."""

    pass


class SecurityFactorError(ValidationError):
    """Security factor requirements not met."""

    pass


# ============================================================================
# CRYPTO ERRORS
# ============================================================================


class CryptoError(StegasooError):
    """Base class for cryptographic errors."""

    pass


class EncryptionError(CryptoError):
    """Encryption failed."""

    pass


class DecryptionError(CryptoError):
    """Decryption failed (wrong key, corrupted data, etc.)."""

    pass


class KeyDerivationError(CryptoError):
    """Key derivation failed."""

    pass


class KeyGenerationError(CryptoError):
    """Key generation failed."""

    pass


class KeyPasswordError(CryptoError):
    """RSA key password is incorrect or missing."""

    pass


# ============================================================================
# STEGANOGRAPHY ERRORS
# ============================================================================


class SteganographyError(StegasooError):
    """Base class for steganography errors."""

    pass


class CapacityError(SteganographyError):
    """Carrier image too small for message."""

    def __init__(self, needed: int, available: int):
        self.needed = needed
        self.available = available
        super().__init__(
            f"Carrier image too small. Need {needed:,} bytes, have {available:,} bytes capacity."
        )


class ExtractionError(SteganographyError):
    """Failed to extract hidden data from image."""

    pass


class EmbeddingError(SteganographyError):
    """Failed to embed data in image."""

    pass


class InvalidHeaderError(SteganographyError):
    """Invalid or missing Stegasoo header in extracted data."""

    pass


class InvalidMagicBytesError(SteganographyError):
    """Magic bytes don't match - not a Stegasoo image or wrong mode."""

    pass


class ReedSolomonError(SteganographyError):
    """Reed-Solomon error correction failed - image too corrupted."""

    pass


class NoDataFoundError(SteganographyError):
    """No hidden data found in image."""

    pass


class ModeMismatchError(SteganographyError):
    """Wrong steganography mode (LSB vs DCT)."""

    pass


# ============================================================================
# FILE ERRORS
# ============================================================================


class FileError(StegasooError):
    """Base class for file-related errors."""

    pass


class FileNotFoundError(FileError):
    """Required file not found."""

    pass


class FileTooLargeError(FileError):
    """File exceeds size limit."""

    def __init__(self, size: int, limit: int, filename: str = "File"):
        self.size = size
        self.limit = limit
        self.filename = filename
        super().__init__(
            f"{filename} too large ({size:,} bytes). Maximum allowed: {limit:,} bytes."
        )


class UnsupportedFileTypeError(FileError):
    """File type not supported."""

    def __init__(self, extension: str, allowed: set[str]):
        self.extension = extension
        self.allowed = allowed
        super().__init__(
            f"Unsupported file type: .{extension}. Allowed: {', '.join(sorted(allowed))}"
        )
