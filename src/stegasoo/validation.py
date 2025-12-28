"""
Stegasoo Input Validation

Validators for all user inputs with clear error messages.
"""

import io
from typing import Optional, Union

from PIL import Image

from .constants import (
    MIN_PIN_LENGTH, MAX_PIN_LENGTH,
    MAX_MESSAGE_SIZE, MAX_FILE_PAYLOAD_SIZE, MAX_IMAGE_PIXELS, MAX_FILE_SIZE,
    MIN_RSA_BITS, MIN_KEY_PASSWORD_LENGTH,
    ALLOWED_IMAGE_EXTENSIONS, ALLOWED_KEY_EXTENSIONS,
)
from .models import ValidationResult, FilePayload
from .exceptions import (
    ValidationError, PinValidationError, MessageValidationError,
    ImageValidationError, KeyValidationError, SecurityFactorError,
    FileTooLargeError, UnsupportedFileTypeError,
)
from .keygen import load_rsa_key


def validate_pin(pin: str, required: bool = False) -> ValidationResult:
    """
    Validate PIN format.
    
    Rules:
    - 6-9 digits only
    - Cannot start with zero
    - Empty is OK if not required
    
    Args:
        pin: PIN string to validate
        required: Whether PIN is required
        
    Returns:
        ValidationResult
    """
    if not pin:
        if required:
            return ValidationResult.error("PIN is required")
        return ValidationResult.ok()
    
    if not pin.isdigit():
        return ValidationResult.error("PIN must contain only digits")
    
    if len(pin) < MIN_PIN_LENGTH or len(pin) > MAX_PIN_LENGTH:
        return ValidationResult.error(
            f"PIN must be {MIN_PIN_LENGTH}-{MAX_PIN_LENGTH} digits"
        )
    
    if pin[0] == '0':
        return ValidationResult.error("PIN cannot start with zero")
    
    return ValidationResult.ok(length=len(pin))


def validate_message(message: str) -> ValidationResult:
    """
    Validate text message content and size.
    
    Args:
        message: Message text
        
    Returns:
        ValidationResult
    """
    if not message:
        return ValidationResult.error("Message is required")
    
    if len(message) > MAX_MESSAGE_SIZE:
        return ValidationResult.error(
            f"Message too long ({len(message):,} chars). Maximum: {MAX_MESSAGE_SIZE:,} characters"
        )
    
    return ValidationResult.ok(length=len(message))


def validate_payload(payload: Union[str, bytes, FilePayload]) -> ValidationResult:
    """
    Validate a payload (text message, bytes, or file).
    
    Args:
        payload: Text string, raw bytes, or FilePayload
        
    Returns:
        ValidationResult
    """
    if isinstance(payload, str):
        return validate_message(payload)
    
    elif isinstance(payload, FilePayload):
        if not payload.data:
            return ValidationResult.error("File is empty")
        
        if len(payload.data) > MAX_FILE_PAYLOAD_SIZE:
            return ValidationResult.error(
                f"File too large ({len(payload.data):,} bytes). "
                f"Maximum: {MAX_FILE_PAYLOAD_SIZE:,} bytes ({MAX_FILE_PAYLOAD_SIZE // 1024} KB)"
            )
        
        return ValidationResult.ok(
            size=len(payload.data),
            filename=payload.filename,
            mime_type=payload.mime_type
        )
    
    elif isinstance(payload, bytes):
        if not payload:
            return ValidationResult.error("Payload is empty")
        
        if len(payload) > MAX_FILE_PAYLOAD_SIZE:
            return ValidationResult.error(
                f"Payload too large ({len(payload):,} bytes). "
                f"Maximum: {MAX_FILE_PAYLOAD_SIZE:,} bytes ({MAX_FILE_PAYLOAD_SIZE // 1024} KB)"
            )
        
        return ValidationResult.ok(size=len(payload))
    
    else:
        return ValidationResult.error(f"Invalid payload type: {type(payload)}")


def validate_file_payload(
    file_data: bytes,
    filename: str = "",
    max_size: int = MAX_FILE_PAYLOAD_SIZE
) -> ValidationResult:
    """
    Validate a file for embedding.
    
    Args:
        file_data: Raw file bytes
        filename: Original filename (for display in errors)
        max_size: Maximum allowed size in bytes
        
    Returns:
        ValidationResult
    """
    if not file_data:
        return ValidationResult.error("File is empty")
    
    if len(file_data) > max_size:
        size_kb = len(file_data) / 1024
        max_kb = max_size / 1024
        return ValidationResult.error(
            f"File '{filename or 'unnamed'}' too large ({size_kb:.1f} KB). "
            f"Maximum: {max_kb:.0f} KB"
        )
    
    return ValidationResult.ok(size=len(file_data), filename=filename)


def validate_image(
    image_data: bytes,
    name: str = "Image",
    check_size: bool = True
) -> ValidationResult:
    """
    Validate image data and dimensions.
    
    Args:
        image_data: Raw image bytes
        name: Name for error messages
        check_size: Whether to check pixel dimensions
        
    Returns:
        ValidationResult with width, height, pixels
    """
    if not image_data:
        return ValidationResult.error(f"{name} is required")
    
    if len(image_data) > MAX_FILE_SIZE:
        return ValidationResult.error(
            f"{name} too large ({len(image_data):,} bytes). Maximum: {MAX_FILE_SIZE:,} bytes"
        )
    
    try:
        img = Image.open(io.BytesIO(image_data))
        width, height = img.size
        num_pixels = width * height
        
        if check_size and num_pixels > MAX_IMAGE_PIXELS:
            max_dim = int(MAX_IMAGE_PIXELS ** 0.5)
            return ValidationResult.error(
                f"{name} too large ({width}×{height} = {num_pixels:,} pixels). "
                f"Maximum: ~{MAX_IMAGE_PIXELS:,} pixels ({max_dim}×{max_dim})"
            )
        
        return ValidationResult.ok(
            width=width,
            height=height,
            pixels=num_pixels,
            mode=img.mode,
            format=img.format
        )
        
    except Exception as e:
        return ValidationResult.error(f"Could not read {name}: {e}")


def validate_rsa_key(
    key_data: bytes,
    password: Optional[str] = None,
    required: bool = False
) -> ValidationResult:
    """
    Validate RSA private key.
    
    Args:
        key_data: PEM-encoded key bytes
        password: Password if key is encrypted
        required: Whether key is required
        
    Returns:
        ValidationResult with key_size
    """
    if not key_data:
        if required:
            return ValidationResult.error("RSA key is required")
        return ValidationResult.ok()
    
    try:
        private_key = load_rsa_key(key_data, password)
        key_size = private_key.key_size
        
        if key_size < MIN_RSA_BITS:
            return ValidationResult.error(
                f"RSA key must be at least {MIN_RSA_BITS} bits (got {key_size})"
            )
        
        return ValidationResult.ok(key_size=key_size)
        
    except Exception as e:
        return ValidationResult.error(str(e))


def validate_security_factors(
    pin: str,
    rsa_key_data: Optional[bytes]
) -> ValidationResult:
    """
    Validate that at least one security factor is provided.
    
    Args:
        pin: PIN string (may be empty)
        rsa_key_data: RSA key bytes (may be None/empty)
        
    Returns:
        ValidationResult
    """
    has_pin = bool(pin and pin.strip())
    has_key = bool(rsa_key_data and len(rsa_key_data) > 0)
    
    if not has_pin and not has_key:
        return ValidationResult.error(
            "You must provide at least a PIN or RSA Key"
        )
    
    return ValidationResult.ok(has_pin=has_pin, has_key=has_key)


def validate_file_extension(
    filename: str,
    allowed: set[str],
    file_type: str = "File"
) -> ValidationResult:
    """
    Validate file extension.
    
    Args:
        filename: Filename to check
        allowed: Set of allowed extensions (lowercase, no dot)
        file_type: Name for error messages
        
    Returns:
        ValidationResult with extension
    """
    if not filename or '.' not in filename:
        return ValidationResult.error(f"{file_type} must have a file extension")
    
    ext = filename.rsplit('.', 1)[1].lower()
    
    if ext not in allowed:
        return ValidationResult.error(
            f"Unsupported {file_type.lower()} type: .{ext}. "
            f"Allowed: {', '.join(sorted('.' + e for e in allowed))}"
        )
    
    return ValidationResult.ok(extension=ext)


def validate_image_file(filename: str) -> ValidationResult:
    """Validate image file extension."""
    return validate_file_extension(filename, ALLOWED_IMAGE_EXTENSIONS, "Image")


def validate_key_file(filename: str) -> ValidationResult:
    """Validate key file extension."""
    return validate_file_extension(filename, ALLOWED_KEY_EXTENSIONS, "Key file")


def validate_key_password(password: str) -> ValidationResult:
    """
    Validate password for key encryption.
    
    Args:
        password: Password string
        
    Returns:
        ValidationResult
    """
    if not password:
        return ValidationResult.error("Password is required")
    
    if len(password) < MIN_KEY_PASSWORD_LENGTH:
        return ValidationResult.error(
            f"Password must be at least {MIN_KEY_PASSWORD_LENGTH} characters"
        )
    
    return ValidationResult.ok(length=len(password))


def validate_phrase(phrase: str) -> ValidationResult:
    """
    Validate day phrase.
    
    Args:
        phrase: Phrase string
        
    Returns:
        ValidationResult with word_count
    """
    if not phrase or not phrase.strip():
        return ValidationResult.error("Day phrase is required")
    
    words = phrase.strip().split()
    
    return ValidationResult.ok(word_count=len(words))


def validate_date_string(date_str: str) -> ValidationResult:
    """
    Validate date string format (YYYY-MM-DD).
    
    Args:
        date_str: Date string
        
    Returns:
        ValidationResult
    """
    if not date_str:
        return ValidationResult.error("Date is required")
    
    if len(date_str) != 10:
        return ValidationResult.error("Date must be in YYYY-MM-DD format")
    
    if date_str[4] != '-' or date_str[7] != '-':
        return ValidationResult.error("Date must be in YYYY-MM-DD format")
    
    try:
        year = int(date_str[0:4])
        month = int(date_str[5:7])
        day = int(date_str[8:10])
        
        if not (1 <= month <= 12 and 1 <= day <= 31 and 2000 <= year <= 2100):
            return ValidationResult.error("Invalid date values")
        
        return ValidationResult.ok(year=year, month=month, day=day)
        
    except ValueError:
        return ValidationResult.error("Date must contain valid numbers")


# ============================================================================
# EXCEPTION-RAISING VALIDATORS (for CLI/API use)
# ============================================================================

def require_valid_pin(pin: str, required: bool = False) -> None:
    """Validate PIN, raising exception on failure."""
    result = validate_pin(pin, required)
    if not result.is_valid:
        raise PinValidationError(result.error_message)


def require_valid_message(message: str) -> None:
    """Validate message, raising exception on failure."""
    result = validate_message(message)
    if not result.is_valid:
        raise MessageValidationError(result.error_message)


def require_valid_payload(payload: Union[str, bytes, FilePayload]) -> None:
    """Validate payload (text, bytes, or file), raising exception on failure."""
    result = validate_payload(payload)
    if not result.is_valid:
        raise MessageValidationError(result.error_message)


def require_valid_image(image_data: bytes, name: str = "Image") -> None:
    """Validate image, raising exception on failure."""
    result = validate_image(image_data, name)
    if not result.is_valid:
        raise ImageValidationError(result.error_message)


def require_valid_rsa_key(
    key_data: bytes,
    password: Optional[str] = None,
    required: bool = False
) -> None:
    """Validate RSA key, raising exception on failure."""
    result = validate_rsa_key(key_data, password, required)
    if not result.is_valid:
        raise KeyValidationError(result.error_message)


def require_security_factors(pin: str, rsa_key_data: Optional[bytes]) -> None:
    """Validate security factors, raising exception on failure."""
    result = validate_security_factors(pin, rsa_key_data)
    if not result.is_valid:
        raise SecurityFactorError(result.error_message)
