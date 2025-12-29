"""
Stegasoo Key Generation

Generate PINs, passphrases, and RSA keys.
"""

import secrets
from typing import Optional, Dict

from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key
from cryptography.hazmat.backends import default_backend

from .constants import (
    DAY_NAMES,
    MIN_PIN_LENGTH, MAX_PIN_LENGTH, DEFAULT_PIN_LENGTH,
    MIN_PHRASE_WORDS, MAX_PHRASE_WORDS, DEFAULT_PHRASE_WORDS,
    MIN_RSA_BITS, VALID_RSA_SIZES, DEFAULT_RSA_BITS,
    get_wordlist,
)
from .models import Credentials, KeyInfo
from .exceptions import KeyGenerationError, KeyPasswordError
from .debug import debug


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
    debug.validate(length >= MIN_PIN_LENGTH and length <= MAX_PIN_LENGTH,
                f"PIN length must be between {MIN_PIN_LENGTH} and {MAX_PIN_LENGTH}")
    
    length = max(MIN_PIN_LENGTH, min(MAX_PIN_LENGTH, length))
    
    # First digit: 1-9 (no leading zero)
    first_digit = str(secrets.randbelow(9) + 1)
    
    # Remaining digits: 0-9
    rest = ''.join(str(secrets.randbelow(10)) for _ in range(length - 1))
    
    pin = first_digit + rest
    debug.print(f"Generated PIN: {pin}")
    return pin


def generate_phrase(words_per_phrase: int = DEFAULT_PHRASE_WORDS) -> str:
    """
    Generate a random passphrase from BIP-39 wordlist.
    
    Args:
        words_per_phrase: Number of words (3-12)
        
    Returns:
        Space-separated phrase
        
    Example:
        >>> generate_phrase(3)
        "apple forest thunder"
    """
    debug.validate(words_per_phrase >= MIN_PHRASE_WORDS and words_per_phrase <= MAX_PHRASE_WORDS,
                f"Words per phrase must be between {MIN_PHRASE_WORDS} and {MAX_PHRASE_WORDS}")
    
    words_per_phrase = max(MIN_PHRASE_WORDS, min(MAX_PHRASE_WORDS, words_per_phrase))
    wordlist = get_wordlist()
    
    words = [secrets.choice(wordlist) for _ in range(words_per_phrase)]
    phrase = ' '.join(words)
    debug.print(f"Generated phrase: {phrase}")
    return phrase


def generate_day_phrases(words_per_phrase: int = DEFAULT_PHRASE_WORDS) -> Dict[str, str]:
    """
    Generate phrases for all days of the week.
    
    Args:
        words_per_phrase: Number of words per phrase (3-12)
        
    Returns:
        Dict mapping day names to phrases
        
    Example:
        >>> generate_day_phrases(3)
        {'Monday': 'apple forest thunder', 'Tuesday': 'banana river lightning', ...}
    """
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
    debug.validate(bits in VALID_RSA_SIZES,
                f"RSA key size must be one of {VALID_RSA_SIZES}")
    
    if bits not in VALID_RSA_SIZES:
        bits = DEFAULT_RSA_BITS
    
    debug.print(f"Generating {bits}-bit RSA key...")
    try:
        key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=bits,
            backend=default_backend()
        )
        debug.print(f"RSA key generated: {bits} bits")
        return key
    except Exception as e:
        debug.exception(e, "RSA key generation")
        raise KeyGenerationError(f"Failed to generate RSA key: {e}") from e


def export_rsa_key_pem(
    private_key: rsa.RSAPrivateKey,
    password: Optional[str] = None
) -> bytes:
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
    
    if password:
        encryption = serialization.BestAvailableEncryption(password.encode())
        debug.print("Exporting RSA key with encryption")
    else:
        encryption = serialization.NoEncryption()
        debug.print("Exporting RSA key without encryption")
    
    return private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption
    )


def load_rsa_key(
    key_data: bytes,
    password: Optional[str] = None
) -> rsa.RSAPrivateKey:
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
    debug.validate(key_data is not None and len(key_data) > 0,
                "Key data cannot be empty")
    
    try:
        pwd_bytes = password.encode() if password else None
        debug.print(f"Loading RSA key (encrypted: {bool(password)})")
        key = load_pem_private_key(key_data, password=pwd_bytes, backend=default_backend())
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


def get_key_info(key_data: bytes, password: Optional[str] = None) -> KeyInfo:
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
    is_encrypted = b'ENCRYPTED' in key_data
    
    private_key = load_rsa_key(key_data, password)
    
    info = KeyInfo(
        key_size=private_key.key_size,
        is_encrypted=is_encrypted,
        pem_data=key_data
    )
    
    debug.print(f"Key info: {info.key_size} bits, encrypted: {info.is_encrypted}")
    return info


def generate_credentials(
    use_pin: bool = True,
    use_rsa: bool = False,
    pin_length: int = DEFAULT_PIN_LENGTH,
    rsa_bits: int = DEFAULT_RSA_BITS,
    words_per_phrase: int = DEFAULT_PHRASE_WORDS
) -> Credentials:
    """
    Generate a complete set of credentials.
    
    At least one of use_pin or use_rsa must be True.
    
    Args:
        use_pin: Whether to generate a PIN
        use_rsa: Whether to generate an RSA key
        pin_length: PIN length if generating
        rsa_bits: RSA key size if generating
        words_per_phrase: Words per daily phrase
        
    Returns:
        Credentials object
        
    Raises:
        ValueError: If neither PIN nor RSA is selected
        
    Example:
        >>> creds = generate_credentials(use_pin=True, use_rsa=False)
        >>> creds.pin
        "812345"
        >>> creds.phrases['Monday']
        "apple forest thunder"
    """
    debug.validate(use_pin or use_rsa,
                "Must select at least one security factor (PIN or RSA key)")
    
    if not use_pin and not use_rsa:
        raise ValueError("Must select at least one security factor (PIN or RSA key)")
    
    debug.print(f"Generating credentials: PIN={use_pin}, RSA={use_rsa}, "
                f"words={words_per_phrase}")
    
    phrases = generate_day_phrases(words_per_phrase)
    
    pin = generate_pin(pin_length) if use_pin else None
    
    rsa_key_pem = None
    rsa_key_obj = None
    if use_rsa:
        rsa_key_obj = generate_rsa_key(rsa_bits)
        rsa_key_pem = export_rsa_key_pem(rsa_key_obj).decode('utf-8')
    
    creds = Credentials(
        phrases=phrases,
        pin=pin,
        rsa_key_pem=rsa_key_pem,
        rsa_bits=rsa_bits if use_rsa else None,
        words_per_phrase=words_per_phrase
    )
    
    debug.print(f"Credentials generated: {creds.total_entropy} bits total entropy")
    return creds
