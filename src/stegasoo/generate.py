"""
Stegasoo Generate Module (v3.2.0)

Public API for generating credentials (PINs, passphrases, RSA keys).
"""


from .constants import (
    DEFAULT_PASSPHRASE_WORDS,
    DEFAULT_PIN_LENGTH,
    DEFAULT_RSA_BITS,
)
from .debug import debug
from .keygen import (
    export_rsa_key_pem,
    generate_phrase,
    load_rsa_key,
)
from .keygen import (
    generate_pin as _generate_pin,
)
from .keygen import (
    generate_rsa_key as _generate_rsa_key,
)
from .models import Credentials

# Re-export from keygen for convenience
__all__ = [
    'generate_pin',
    'generate_passphrase',
    'generate_rsa_key',
    'generate_credentials',
    'export_rsa_key_pem',
    'load_rsa_key',
]


def generate_pin(length: int = DEFAULT_PIN_LENGTH) -> str:
    """
    Generate a random PIN.

    PINs never start with zero for usability.

    Args:
        length: PIN length (6-9 digits, default 6)

    Returns:
        PIN string

    Example:
        >>> pin = generate_pin()
        >>> len(pin)
        6
        >>> pin[0] != '0'
        True
    """
    return _generate_pin(length)


def generate_passphrase(words: int = DEFAULT_PASSPHRASE_WORDS) -> str:
    """
    Generate a random passphrase from BIP-39 wordlist.

    In v3.2.0, this generates a single passphrase (not daily phrases).
    Default is 4 words for good security (increased from 3 in v3.1.0).

    Args:
        words: Number of words (3-12, default 4)

    Returns:
        Space-separated passphrase

    Example:
        >>> passphrase = generate_passphrase(4)
        >>> len(passphrase.split())
        4
    """
    return generate_phrase(words)


def generate_rsa_key(
    bits: int = DEFAULT_RSA_BITS,
    password: str | None = None
) -> str:
    """
    Generate an RSA private key in PEM format.

    Args:
        bits: Key size (2048, 3072, or 4096, default 2048)
        password: Optional password to encrypt the key

    Returns:
        PEM-encoded key string

    Example:
        >>> key_pem = generate_rsa_key(2048)
        >>> '-----BEGIN PRIVATE KEY-----' in key_pem
        True
    """
    key_obj = _generate_rsa_key(bits)
    pem_bytes = export_rsa_key_pem(key_obj, password)
    return pem_bytes.decode('utf-8')


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

    In v3.2.0, this generates a single passphrase (not daily phrases).
    At least one of use_pin or use_rsa must be True.

    Args:
        use_pin: Whether to generate a PIN
        use_rsa: Whether to generate an RSA key
        pin_length: PIN length (default 6)
        rsa_bits: RSA key size (default 2048)
        passphrase_words: Number of words in passphrase (default 4)
        rsa_password: Optional password for RSA key

    Returns:
        Credentials object with passphrase, PIN, and/or RSA key

    Raises:
        ValueError: If neither PIN nor RSA is selected

    Example:
        >>> creds = generate_credentials(use_pin=True, use_rsa=False)
        >>> len(creds.passphrase.split())
        4
        >>> len(creds.pin)
        6
    """
    if not use_pin and not use_rsa:
        raise ValueError("Must select at least one security factor (PIN or RSA key)")

    debug.print(f"Generating credentials: PIN={use_pin}, RSA={use_rsa}, "
                f"passphrase_words={passphrase_words}")

    # Generate passphrase (single, not daily)
    passphrase = generate_phrase(passphrase_words)

    # Generate PIN if requested
    pin = _generate_pin(pin_length) if use_pin else None

    # Generate RSA key if requested
    rsa_key_pem = None
    if use_rsa:
        rsa_key_obj = _generate_rsa_key(rsa_bits)
        rsa_key_bytes = export_rsa_key_pem(rsa_key_obj, rsa_password)
        rsa_key_pem = rsa_key_bytes.decode('utf-8')

    # Create Credentials object (v3.2.0 format)
    creds = Credentials(
        passphrase=passphrase,
        pin=pin,
        rsa_key_pem=rsa_key_pem,
        rsa_bits=rsa_bits if use_rsa else None,
        words_per_passphrase=passphrase_words,
    )

    debug.print(f"Credentials generated: {creds.total_entropy} bits total entropy")
    return creds
