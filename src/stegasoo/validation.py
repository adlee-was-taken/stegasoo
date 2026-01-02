"""
Stegasoo Input Validation (v3.2.0)

Validators for all user inputs with clear error messages.

Changes in v3.2.0:
- Renamed validate_phrase() → validate_passphrase()
- Added word count validation with warnings for passphrases
- Added validators for embed modes and DCT parameters
"""

import io

from PIL import Image

from .constants import (
    ALLOWED_IMAGE_EXTENSIONS,
    ALLOWED_KEY_EXTENSIONS,
    EMBED_MODE_AUTO,
    EMBED_MODE_DCT,
    EMBED_MODE_LSB,
    MAX_FILE_PAYLOAD_SIZE,
    MAX_FILE_SIZE,
    MAX_IMAGE_PIXELS,
    MAX_MESSAGE_SIZE,
    MAX_PIN_LENGTH,
    MIN_KEY_PASSWORD_LENGTH,
    MIN_PASSPHRASE_WORDS,
    MIN_PIN_LENGTH,
    MIN_RSA_BITS,
    RECOMMENDED_PASSPHRASE_WORDS,
)
from .exceptions import (
    ImageValidationError,
    KeyValidationError,
    MessageValidationError,
    PinValidationError,
    SecurityFactorError,
)
from .keygen import load_rsa_key
from .models import FilePayload, ValidationResult


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
        return ValidationResult.error(f"PIN must be {MIN_PIN_LENGTH}-{MAX_PIN_LENGTH} digits")

    if pin[0] == "0":
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


def validate_payload(payload: str | bytes | FilePayload) -> ValidationResult:
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
            size=len(payload.data), filename=payload.filename, mime_type=payload.mime_type
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
    file_data: bytes, filename: str = "", max_size: int = MAX_FILE_PAYLOAD_SIZE
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
    image_data: bytes, name: str = "Image", check_size: bool = True
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
            max_dim = int(MAX_IMAGE_PIXELS**0.5)
            return ValidationResult.error(
                f"{name} too large ({width}×{height} = {num_pixels:,} pixels). "
                f"Maximum: ~{MAX_IMAGE_PIXELS:,} pixels ({max_dim}×{max_dim})"
            )

        return ValidationResult.ok(
            width=width, height=height, pixels=num_pixels, mode=img.mode, format=img.format
        )

    except Exception as e:
        return ValidationResult.error(f"Could not read {name}: {e}")


def validate_rsa_key(
    key_data: bytes, password: str | None = None, required: bool = False
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


def validate_security_factors(pin: str, rsa_key_data: bytes | None) -> ValidationResult:
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
        return ValidationResult.error("You must provide at least a PIN or RSA Key")

    return ValidationResult.ok(has_pin=has_pin, has_key=has_key)


def validate_file_extension(
    filename: str, allowed: set[str], file_type: str = "File"
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
    if not filename or "." not in filename:
        return ValidationResult.error(f"{file_type} must have a file extension")

    ext = filename.rsplit(".", 1)[1].lower()

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


def validate_passphrase(passphrase: str) -> ValidationResult:
    """
    Validate passphrase.

    v3.2.0: Recommend 4+ words for good entropy (since date is no longer used).

    Args:
        passphrase: Passphrase string

    Returns:
        ValidationResult with word_count and optional warning
    """
    if not passphrase or not passphrase.strip():
        return ValidationResult.error("Passphrase is required")

    words = passphrase.strip().split()

    if len(words) < MIN_PASSPHRASE_WORDS:
        return ValidationResult.error(
            f"Passphrase should have at least {MIN_PASSPHRASE_WORDS} words"
        )

    # Provide warning if below recommended length
    if len(words) < RECOMMENDED_PASSPHRASE_WORDS:
        return ValidationResult.ok(
            word_count=len(words),
            warning=f"Recommend {RECOMMENDED_PASSPHRASE_WORDS}+ words for better security",
        )

    return ValidationResult.ok(word_count=len(words))


# =============================================================================
# NEW VALIDATORS FOR V3.2.0
# =============================================================================


def validate_reference_photo(photo_data: bytes) -> ValidationResult:
    """Validate reference photo. Alias for validate_image."""
    return validate_image(photo_data, "Reference photo")


def validate_carrier(carrier_data: bytes) -> ValidationResult:
    """Validate carrier image. Alias for validate_image."""
    return validate_image(carrier_data, "Carrier image")


def validate_embed_mode(mode: str) -> ValidationResult:
    """
    Validate embedding mode.

    Args:
        mode: Embedding mode string

    Returns:
        ValidationResult
    """
    valid_modes = {EMBED_MODE_LSB, EMBED_MODE_DCT, EMBED_MODE_AUTO}

    if mode not in valid_modes:
        return ValidationResult.error(
            f"Invalid embed_mode: '{mode}'. Valid options: {', '.join(sorted(valid_modes))}"
        )

    return ValidationResult.ok(mode=mode)


def validate_dct_output_format(format_str: str) -> ValidationResult:
    """
    Validate DCT output format.

    Args:
        format_str: Output format ('png' or 'jpeg')

    Returns:
        ValidationResult
    """
    valid_formats = {"png", "jpeg"}

    if format_str.lower() not in valid_formats:
        return ValidationResult.error(
            f"Invalid DCT output format: '{format_str}'. Valid options: {', '.join(sorted(valid_formats))}"
        )

    return ValidationResult.ok(format=format_str.lower())


def validate_dct_color_mode(mode: str) -> ValidationResult:
    """
    Validate DCT color mode.

    Args:
        mode: Color mode ('grayscale' or 'color')

    Returns:
        ValidationResult
    """
    valid_modes = {"grayscale", "color"}

    if mode.lower() not in valid_modes:
        return ValidationResult.error(
            f"Invalid DCT color mode: '{mode}'. Valid options: {', '.join(sorted(valid_modes))}"
        )

    return ValidationResult.ok(mode=mode.lower())


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


def require_valid_payload(payload: str | bytes | FilePayload) -> None:
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
    key_data: bytes, password: str | None = None, required: bool = False
) -> None:
    """Validate RSA key, raising exception on failure."""
    result = validate_rsa_key(key_data, password, required)
    if not result.is_valid:
        raise KeyValidationError(result.error_message)


def require_security_factors(pin: str, rsa_key_data: bytes | None) -> None:
    """Validate security factors, raising exception on failure."""
    result = validate_security_factors(pin, rsa_key_data)
    if not result.is_valid:
        raise SecurityFactorError(result.error_message)
