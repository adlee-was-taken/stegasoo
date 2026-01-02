"""
Stegasoo Data Models (v3.2.0)

Dataclasses for structured data exchange between modules and frontends.

Changes in v3.2.0:
- Renamed day_phrase → passphrase
- Credentials now uses single passphrase instead of day mapping
- Removed date_str from EncodeInput (date no longer used in crypto)
- Made date_used optional in EncodeResult (cosmetic only)
- Added ImageInfo, CapacityComparison, GenerateResult
"""

from dataclasses import dataclass, field


@dataclass
class Credentials:
    """
    Generated credentials for encoding/decoding.

    v3.2.0: Simplified to use single passphrase instead of daily rotation.
    """
    passphrase: str  # Single passphrase (no daily rotation)
    pin: str | None = None
    rsa_key_pem: str | None = None
    rsa_bits: int | None = None
    words_per_passphrase: int = 4  # Increased from 3 in v3.1.0

    # Optional: backup passphrases for multi-factor or rotation
    backup_passphrases: list[str] | None = None

    @property
    def passphrase_entropy(self) -> int:
        """Entropy in bits from passphrase (~11 bits per BIP-39 word)."""
        return self.words_per_passphrase * 11

    @property
    def pin_entropy(self) -> int:
        """Entropy in bits from PIN (~3.32 bits per digit)."""
        if self.pin:
            return int(len(self.pin) * 3.32)
        return 0

    @property
    def rsa_entropy(self) -> int:
        """Effective entropy from RSA key."""
        if self.rsa_key_pem and self.rsa_bits:
            return min(self.rsa_bits // 16, 128)
        return 0

    @property
    def total_entropy(self) -> int:
        """Total entropy in bits (excluding reference photo)."""
        return self.passphrase_entropy + self.pin_entropy + self.rsa_entropy

    # Legacy property for compatibility
    @property
    def phrase_entropy(self) -> int:
        """Alias for passphrase_entropy (backward compatibility)."""
        return self.passphrase_entropy


@dataclass
class FilePayload:
    """Represents a file to be embedded."""
    data: bytes
    filename: str
    mime_type: str | None = None

    @property
    def size(self) -> int:
        return len(self.data)

    @classmethod
    def from_file(cls, filepath: str, filename: str | None = None) -> 'FilePayload':
        """Create FilePayload from a file path."""
        import mimetypes
        from pathlib import Path

        path = Path(filepath)
        data = path.read_bytes()
        name = filename or path.name
        mime, _ = mimetypes.guess_type(name)

        return cls(data=data, filename=name, mime_type=mime)


@dataclass
class EncodeInput:
    """
    Input parameters for encoding a message.

    v3.2.0: Removed date_str (date no longer used in crypto).
    """
    message: str | bytes | FilePayload  # Text, raw bytes, or file
    reference_photo: bytes
    carrier_image: bytes
    passphrase: str  # Renamed from day_phrase
    pin: str = ""
    rsa_key_data: bytes | None = None
    rsa_password: str | None = None


@dataclass
class EncodeResult:
    """
    Result of encoding operation.

    v3.2.0: date_used is now optional/cosmetic (not used in crypto).
    """
    stego_image: bytes
    filename: str
    pixels_modified: int
    total_pixels: int
    capacity_used: float  # 0.0 - 1.0
    date_used: str | None = None  # Cosmetic only (for filename organization)

    @property
    def capacity_percent(self) -> float:
        """Capacity used as percentage."""
        return self.capacity_used * 100


@dataclass
class DecodeInput:
    """
    Input parameters for decoding a message.

    v3.2.0: Renamed day_phrase → passphrase, no date needed.
    """
    stego_image: bytes
    reference_photo: bytes
    passphrase: str  # Renamed from day_phrase
    pin: str = ""
    rsa_key_data: bytes | None = None
    rsa_password: str | None = None


@dataclass
class DecodeResult:
    """
    Result of decoding operation.

    v3.2.0: date_encoded is always None (date removed from crypto).
    """
    payload_type: str  # 'text' or 'file'
    message: str | None = None  # For text payloads
    file_data: bytes | None = None  # For file payloads
    filename: str | None = None  # Original filename for file payloads
    mime_type: str | None = None  # MIME type hint
    date_encoded: str | None = None  # Always None in v3.2.0 (kept for compatibility)

    @property
    def is_file(self) -> bool:
        return self.payload_type == 'file'

    @property
    def is_text(self) -> bool:
        return self.payload_type == 'text'

    def get_content(self) -> str | bytes:
        """Get the decoded content (text or bytes)."""
        if self.is_text:
            return self.message or ""
        return self.file_data or b""


@dataclass
class EmbedStats:
    """Statistics from image embedding."""
    pixels_modified: int
    total_pixels: int
    capacity_used: float
    bytes_embedded: int

    @property
    def modification_percent(self) -> float:
        """Percentage of pixels modified."""
        return (self.pixels_modified / self.total_pixels) * 100 if self.total_pixels > 0 else 0


@dataclass
class KeyInfo:
    """Information about an RSA key."""
    key_size: int
    is_encrypted: bool
    pem_data: bytes


@dataclass
class ValidationResult:
    """Result of input validation."""
    is_valid: bool
    error_message: str = ""
    details: dict = field(default_factory=dict)
    warning: str | None = None  # v3.2.0: Added for passphrase length warnings

    @classmethod
    def ok(cls, warning: str | None = None, **details) -> 'ValidationResult':
        """Create a successful validation result."""
        result = cls(is_valid=True, details=details)
        if warning:
            result.warning = warning
        return result

    @classmethod
    def error(cls, message: str, **details) -> 'ValidationResult':
        """Create a failed validation result."""
        return cls(is_valid=False, error_message=message, details=details)


# =============================================================================
# NEW MODELS FOR V3.2.0 PUBLIC API
# =============================================================================

@dataclass
class ImageInfo:
    """Information about an image for steganography."""
    width: int
    height: int
    pixels: int
    format: str
    mode: str
    file_size: int
    lsb_capacity_bytes: int
    lsb_capacity_kb: float
    dct_capacity_bytes: int | None = None
    dct_capacity_kb: float | None = None


@dataclass
class CapacityComparison:
    """Comparison of embedding capacity between modes."""
    image_width: int
    image_height: int
    lsb_available: bool
    lsb_bytes: int
    lsb_kb: float
    lsb_output_format: str
    dct_available: bool
    dct_bytes: int | None = None
    dct_kb: float | None = None
    dct_output_formats: list[str] | None = None
    dct_ratio_vs_lsb: float | None = None


@dataclass
class GenerateResult:
    """Result of credential generation."""
    passphrase: str
    pin: str | None = None
    rsa_key_pem: str | None = None
    passphrase_words: int = 4
    passphrase_entropy: int = 0
    pin_entropy: int = 0
    rsa_entropy: int = 0
    total_entropy: int = 0

    def __str__(self) -> str:
        lines = [
            "Generated Credentials:",
            f"  Passphrase: {self.passphrase}",
        ]
        if self.pin:
            lines.append(f"  PIN: {self.pin}")
        if self.rsa_key_pem:
            lines.append(f"  RSA Key: {len(self.rsa_key_pem)} bytes PEM")
        lines.append(f"  Total Entropy: {self.total_entropy} bits")
        return "\n".join(lines)
