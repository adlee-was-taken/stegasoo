"""
Stegasoo Data Models

Dataclasses for structured data exchange between modules and frontends.
"""

from dataclasses import dataclass, field
from datetime import date
from typing import Optional, Union


@dataclass
class Credentials:
    """Generated credentials for encoding/decoding."""
    phrases: dict[str, str]  # Day -> phrase mapping
    pin: Optional[str] = None
    rsa_key_pem: Optional[str] = None
    rsa_bits: Optional[int] = None
    words_per_phrase: int = 3
    
    @property
    def phrase_entropy(self) -> int:
        """Entropy in bits from phrases (~11 bits per BIP-39 word)."""
        return self.words_per_phrase * 11
    
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
        return self.phrase_entropy + self.pin_entropy + self.rsa_entropy


@dataclass
class FilePayload:
    """Represents a file to be embedded."""
    data: bytes
    filename: str
    mime_type: Optional[str] = None
    
    @property
    def size(self) -> int:
        return len(self.data)
    
    @classmethod
    def from_file(cls, filepath: str, filename: Optional[str] = None) -> 'FilePayload':
        """Create FilePayload from a file path."""
        from pathlib import Path
        import mimetypes
        
        path = Path(filepath)
        data = path.read_bytes()
        name = filename or path.name
        mime, _ = mimetypes.guess_type(name)
        
        return cls(data=data, filename=name, mime_type=mime)


@dataclass
class EncodeInput:
    """Input parameters for encoding a message."""
    message: Union[str, bytes, FilePayload]  # Text, raw bytes, or file
    reference_photo: bytes
    carrier_image: bytes
    day_phrase: str
    pin: str = ""
    rsa_key_data: Optional[bytes] = None
    rsa_password: Optional[str] = None
    date_str: Optional[str] = None  # YYYY-MM-DD, defaults to today
    
    def __post_init__(self):
        if self.date_str is None:
            self.date_str = date.today().isoformat()


@dataclass
class EncodeResult:
    """Result of encoding operation."""
    stego_image: bytes
    filename: str
    pixels_modified: int
    total_pixels: int
    capacity_used: float  # 0.0 - 1.0
    date_used: str
    
    @property
    def capacity_percent(self) -> float:
        """Capacity used as percentage."""
        return self.capacity_used * 100


@dataclass
class DecodeInput:
    """Input parameters for decoding a message."""
    stego_image: bytes
    reference_photo: bytes
    day_phrase: str
    pin: str = ""
    rsa_key_data: Optional[bytes] = None
    rsa_password: Optional[str] = None


@dataclass
class DecodeResult:
    """Result of decoding operation."""
    payload_type: str  # 'text' or 'file'
    message: Optional[str] = None  # For text payloads
    file_data: Optional[bytes] = None  # For file payloads
    filename: Optional[str] = None  # Original filename for file payloads
    mime_type: Optional[str] = None  # MIME type hint
    date_encoded: Optional[str] = None
    
    @property
    def is_file(self) -> bool:
        return self.payload_type == 'file'
    
    @property
    def is_text(self) -> bool:
        return self.payload_type == 'text'
    
    def get_content(self) -> Union[str, bytes]:
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
    
    @classmethod
    def ok(cls, **details) -> 'ValidationResult':
        """Create a successful validation result."""
        return cls(is_valid=True, details=details)
    
    @classmethod
    def error(cls, message: str, **details) -> 'ValidationResult':
        """Create a failed validation result."""
        return cls(is_valid=False, error_message=message, details=details)
