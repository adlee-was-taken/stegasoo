"""
Stegasoo Key Generation (v3.2.0)

Generate PINs, passphrases, and RSA keys.

Changes in v3.2.0:
- generate_credentials() now returns Credentials with single passphrase
- Removed generate_day_phrases() from main API (kept for legacy compatibility)
- Updated to use PASSPHRASE constants
"""

import secrets

from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.asymmetric.types import PrivateKeyTypes
from cryptography.hazmat.primitives.serialization import load_pem_private_key

from .constants import (
    DAY_NAMES,
    DEFAULT_PASSPHRASE_WORDS,
    DEFAULT_PIN_LENGTH,
    DEFAULT_RSA_BITS,
    MAX_PASSPHRASE_WORDS,
    MAX_PIN_LENGTH,
    MIN_PASSPHRASE_WORDS,
    MIN_PIN_LENGTH,
    VALID_RSA_SIZES,
    get_wordlist,
)
from .debug import debug
from .exceptions import KeyGenerationError, KeyPasswordError
from .models import Credentials, KeyInfo


def generate_pin(length: int = DEFAULT_PIN_LENGTH) -> str:
    """
    Generate a random PIN.

    PINs never start with zero for usability.

    Args:
        length: PIN length (6-9 digits)

    Returns:
        PIN string

    Example:
        >>> generate_pin(6)
        "812345"
    """
    debug.validate(
        MIN_PIN_LENGTH <= length <= MAX_PIN_LENGTH,
        f"PIN length must be between {MIN_PIN_LENGTH} and {MAX_PIN_LENGTH}",
    )

    length = max(MIN_PIN_LENGTH, min(MAX_PIN_LENGTH, length))

    # First digit: 1-9 (no leading zero)
    first_digit = str(secrets.randbelow(9) + 1)

    # Remaining digits: 0-9
    rest = "".join(str(secrets.randbelow(10)) for _ in range(length - 1))

    pin = first_digit + rest
    debug.print(f"Generated PIN: {pin}")
    return pin


def generate_phrase(words_per_phrase: int = DEFAULT_PASSPHRASE_WORDS) -> str:
    """
    Generate a random passphrase from BIP-39 wordlist.

    Args:
        words_per_phrase: Number of words (3-12)

    Returns:
        Space-separated phrase

    Example:
        >>> generate_phrase(4)
        "apple forest thunder mountain"
    """
    debug.validate(
        MIN_PASSPHRASE_WORDS <= words_per_phrase <= MAX_PASSPHRASE_WORDS,
        f"Words per phrase must be between {MIN_PASSPHRASE_WORDS} and {MAX_PASSPHRASE_WORDS}",
    )

    words_per_phrase = max(MIN_PASSPHRASE_WORDS, min(MAX_PASSPHRASE_WORDS, words_per_phrase))
    wordlist = get_wordlist()

    words = [secrets.choice(wordlist) for _ in range(words_per_phrase)]
    phrase = " ".join(words)
    debug.print(f"Generated phrase: {phrase}")
    return phrase


# Alias for backward compatibility and public API consistency
generate_passphrase = generate_phrase


def generate_day_phrases(words_per_phrase: int = DEFAULT_PASSPHRASE_WORDS) -> dict[str, str]:
    """
    Generate phrases for all days of the week.

    DEPRECATED in v3.2.0: Use generate_phrase() for single passphrase.
    Kept for legacy compatibility and organizational use cases.

    Args:
        words_per_phrase: Number of words per phrase (3-12)

    Returns:
        Dict mapping day names to phrases

    Example:
        >>> generate_day_phrases(3)
        {'Monday': 'apple forest thunder', 'Tuesday': 'banana river lightning', ...}
    """
    import warnings

    warnings.warn(
        "generate_day_phrases() is deprecated in v3.2.0. "
        "Use generate_phrase() for single passphrase.",
        DeprecationWarning,
        stacklevel=2,
    )

    phrases = {day: generate_phrase(words_per_phrase) for day in DAY_NAMES}
    debug.print(f"Generated phrases for {len(phrases)} days")
    return phrases


def generate_rsa_key(bits: int = DEFAULT_RSA_BITS) -> rsa.RSAPrivateKey:
    """
    Generate an RSA private key.

    Args:
        bits: Key size (2048, 3072, or 4096)

    Returns:
        RSA private key object

    Raises:
        KeyGenerationError: If generation fails

    Example:
        >>> key = generate_rsa_key(2048)
        >>> key.key_size
        2048
    """
    debug.validate(bits in VALID_RSA_SIZES, f"RSA key size must be one of {VALID_RSA_SIZES}")

    if bits not in VALID_RSA_SIZES:
        bits = DEFAULT_RSA_BITS

    debug.print(f"Generating {bits}-bit RSA key...")
    try:
        key = rsa.generate_private_key(
            public_exponent=65537, key_size=bits, backend=default_backend()
        )
        debug.print(f"RSA key generated: {bits} bits")
        return key
    except Exception as e:
        debug.exception(e, "RSA key generation")
        raise KeyGenerationError(f"Failed to generate RSA key: {e}") from e


def export_rsa_key_pem(private_key: rsa.RSAPrivateKey, password: str | None = None) -> bytes:
    """
    Export RSA key to PEM format.

    Args:
        private_key: RSA private key object
        password: Optional password for encryption

    Returns:
        PEM-encoded key bytes

    Example:
        >>> key = generate_rsa_key()
        >>> pem = export_rsa_key_pem(key)
        >>> pem[:50]
        b'-----BEGIN PRIVATE KEY-----\\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYw'
    """
    debug.validate(private_key is not None, "Private key cannot be None")

    encryption_algorithm: serialization.BestAvailableEncryption | serialization.NoEncryption

    if password:
        encryption_algorithm = serialization.BestAvailableEncryption(password.encode())
        debug.print("Exporting RSA key with encryption")
    else:
        encryption_algorithm = serialization.NoEncryption()
        debug.print("Exporting RSA key without encryption")

    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption_algorithm,
    )


def load_rsa_key(key_data: bytes, password: str | None = None) -> rsa.RSAPrivateKey:
    """
    Load RSA private key from PEM data.

    Args:
        key_data: PEM-encoded key bytes
        password: Password if key is encrypted

    Returns:
        RSA private key object

    Raises:
        KeyPasswordError: If password is wrong or missing
        KeyGenerationError: If key is invalid

    Example:
        >>> key = load_rsa_key(pem_data, "my_password")
    """
    debug.validate(key_data is not None and len(key_data) > 0, "Key data cannot be empty")

    try:
        pwd_bytes = password.encode() if password else None
        debug.print(f"Loading RSA key (encrypted: {bool(password)})")
        key: PrivateKeyTypes = load_pem_private_key(
            key_data, password=pwd_bytes, backend=default_backend()
        )

        # Verify it's an RSA key
        if not isinstance(key, rsa.RSAPrivateKey):
            raise KeyGenerationError(f"Expected RSA key, got {type(key).__name__}")

        debug.print(f"RSA key loaded: {key.key_size} bits")
        return key
    except TypeError:
        debug.print("RSA key is password-protected but no password provided")
        raise KeyPasswordError("RSA key is password-protected. Please provide the password.")
    except ValueError as e:
        error_msg = str(e).lower()
        if "password" in error_msg or "encrypted" in error_msg:
            debug.print("Incorrect password for RSA key")
            raise KeyPasswordError("Incorrect password for RSA key.")
        debug.exception(e, "RSA key loading")
        raise KeyGenerationError(f"Invalid RSA key: {e}") from e
    except Exception as e:
        debug.exception(e, "RSA key loading")
        raise KeyGenerationError(f"Could not load RSA key: {e}") from e


def get_key_info(key_data: bytes, password: str | None = None) -> KeyInfo:
    """
    Get information about an RSA key.

    Args:
        key_data: PEM-encoded key bytes
        password: Password if key is encrypted

    Returns:
        KeyInfo with key size and encryption status

    Example:
        >>> info = get_key_info(pem_data)
        >>> info.key_size
        2048
        >>> info.is_encrypted
        False
    """
    debug.print("Getting RSA key info")
    # Check if encrypted
    is_encrypted = b"ENCRYPTED" in key_data

    private_key = load_rsa_key(key_data, password)

    info = KeyInfo(key_size=private_key.key_size, is_encrypted=is_encrypted, pem_data=key_data)

    debug.print(f"Key info: {info.key_size} bits, encrypted: {info.is_encrypted}")
    return info


def generate_credentials(
    use_pin: bool = True,
    use_rsa: bool = False,
    pin_length: int = DEFAULT_PIN_LENGTH,
    rsa_bits: int = DEFAULT_RSA_BITS,
    passphrase_words: int = DEFAULT_PASSPHRASE_WORDS,
    rsa_password: str | None = None,
) -> Credentials:
    """
    Generate a complete set of credentials.

    v3.2.0: Now generates a single passphrase instead of daily phrases.
    At least one of use_pin or use_rsa must be True.

    Args:
        use_pin: Whether to generate a PIN
        use_rsa: Whether to generate an RSA key
        pin_length: PIN length if generating (default 6)
        rsa_bits: RSA key size if generating (default 2048)
        passphrase_words: Words in passphrase (default 4)
        rsa_password: Optional password for RSA key encryption

    Returns:
        Credentials object with passphrase, PIN, and/or RSA key

    Raises:
        ValueError: If neither PIN nor RSA is selected

    Example:
        >>> creds = generate_credentials(use_pin=True, use_rsa=False)
        >>> creds.passphrase
        "apple forest thunder mountain"
        >>> creds.pin
        "812345"
    """
    debug.validate(use_pin or use_rsa, "Must select at least one security factor (PIN or RSA key)")

    if not use_pin and not use_rsa:
        raise ValueError("Must select at least one security factor (PIN or RSA key)")

    debug.print(
        f"Generating credentials: PIN={use_pin}, RSA={use_rsa}, "
        f"passphrase_words={passphrase_words}"
    )

    # Generate single passphrase (v3.2.0 - no daily rotation)
    passphrase = generate_phrase(passphrase_words)

    # Generate PIN if requested
    pin = generate_pin(pin_length) if use_pin else None

    # Generate RSA key if requested
    rsa_key_pem = None
    if use_rsa:
        rsa_key_obj = generate_rsa_key(rsa_bits)
        rsa_key_pem = export_rsa_key_pem(rsa_key_obj, rsa_password).decode("utf-8")

    # Create Credentials object (v3.2.0 format with single passphrase)
    creds = Credentials(
        passphrase=passphrase,
        pin=pin,
        rsa_key_pem=rsa_key_pem,
        rsa_bits=rsa_bits if use_rsa else None,
        words_per_passphrase=passphrase_words,
    )

    debug.print(f"Credentials generated: {creds.total_entropy} bits total entropy")
    return creds


# =============================================================================
# LEGACY COMPATIBILITY
# =============================================================================


def generate_credentials_legacy(
    use_pin: bool = True,
    use_rsa: bool = False,
    pin_length: int = DEFAULT_PIN_LENGTH,
    rsa_bits: int = DEFAULT_RSA_BITS,
    words_per_phrase: int = DEFAULT_PASSPHRASE_WORDS,
) -> dict:
    """
    Generate credentials in legacy format (v3.1.0 style with daily phrases).

    DEPRECATED: Use generate_credentials() for v3.2.0 format.

    This function exists only for migration tools that need to work with
    old-format credentials.

    Args:
        use_pin: Whether to generate a PIN
        use_rsa: Whether to generate an RSA key
        pin_length: PIN length if generating
        rsa_bits: RSA key size if generating
        words_per_phrase: Words per daily phrase

    Returns:
        Dict with 'phrases' (dict), 'pin', 'rsa_key_pem', etc.
    """
    import warnings

    warnings.warn(
        "generate_credentials_legacy() returns v3.1.0 format. "
        "Use generate_credentials() for v3.2.0 format.",
        DeprecationWarning,
        stacklevel=2,
    )

    if not use_pin and not use_rsa:
        raise ValueError("Must select at least one security factor (PIN or RSA key)")

    # Generate daily phrases (old format)
    phrases = {day: generate_phrase(words_per_phrase) for day in DAY_NAMES}

    pin = generate_pin(pin_length) if use_pin else None

    rsa_key_pem = None
    if use_rsa:
        rsa_key_obj = generate_rsa_key(rsa_bits)
        rsa_key_pem = export_rsa_key_pem(rsa_key_obj).decode("utf-8")

    return {
        "phrases": phrases,
        "pin": pin,
        "rsa_key_pem": rsa_key_pem,
        "rsa_bits": rsa_bits if use_rsa else None,
        "words_per_phrase": words_per_phrase,
    }
