#!/usr/bin/env python3
"""
Stegasoo CLI - Command-line interface for steganography operations (v3.2.0).

CHANGES in v3.2.0:
- Removed date dependency from all operations
- Renamed day_phrase → passphrase
- No longer need to specify or remember encoding dates
- Default passphrase length increased to 4 words

Usage:
    stegasoo generate [OPTIONS]
    stegasoo encode [OPTIONS]
    stegasoo decode [OPTIONS]
    stegasoo verify [OPTIONS]
    stegasoo info [OPTIONS]
    stegasoo compare [OPTIONS]
    stegasoo modes [OPTIONS]
"""

import sys
from pathlib import Path
from typing import Optional

import click

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import stegasoo
from stegasoo import (
    # Core operations
    encode, decode,
    
    # Credential generation
    generate_credentials,
    generate_passphrase,
    generate_pin,
    export_rsa_key_pem, 
    load_rsa_key,
    
    # Validation
    validate_image,
    
    # Image utilities
    get_image_info,
    compare_capacity,
    
    # Steganography functions
    has_dct_support,
    compare_modes,
    will_fit_by_mode,
    
    # Utilities  
    generate_filename,
    
    # Version
    __version__,
    
    # Exceptions
    StegasooError, 
    DecryptionError, 
    ExtractionError,
    
    # Models
    FilePayload,
)

# Import constants - try main module first, then constants submodule
try:
    from stegasoo import (
        EMBED_MODE_LSB,
        EMBED_MODE_DCT,
        EMBED_MODE_AUTO,
    )
except ImportError:
    from stegasoo.constants import (
        EMBED_MODE_LSB,
        EMBED_MODE_DCT,
        EMBED_MODE_AUTO,
    )

# Import constants that may not be in main __init__
try:
    from stegasoo.constants import (
        DEFAULT_PASSPHRASE_WORDS,
        DEFAULT_PIN_LENGTH,
        MIN_PIN_LENGTH,
        MAX_PIN_LENGTH,
    )
except ImportError:
    # Fallback defaults if constants not available
    DEFAULT_PASSPHRASE_WORDS = 4
    DEFAULT_PIN_LENGTH = 6
    MIN_PIN_LENGTH = 6
    MAX_PIN_LENGTH = 9

# Optional: strip_image_metadata from utils
try:
    from stegasoo.utils import strip_image_metadata
    HAS_STRIP_METADATA = True
except ImportError:
    HAS_STRIP_METADATA = False

# QR Code utilities
try:
    from stegasoo.qr_utils import (
        extract_key_from_qr_file,
        generate_qr_code,
        has_qr_read, has_qr_write,
        can_fit_in_qr, needs_compression,
    )
    HAS_QR = True
except ImportError:
    HAS_QR = False
    has_qr_read = lambda: False
    has_qr_write = lambda: False


# ============================================================================
# CLI SETUP
# ============================================================================

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, '-v', '--version')
def cli():
    """
    Stegasoo - Secure steganography with hybrid authentication.
    
    Hide encrypted messages or files in images using a combination of:
    
    \b
    - Reference photo (something you have)
    - Passphrase (something you know)
    - Static PIN or RSA key (additional security)
    
    \b
    Version 3.2.0 Changes:
    - No more date parameters - encode/decode anytime!
    - Simplified passphrase (no daily rotation)
    - Default passphrase increased to 4 words
    - True asynchronous communications
    
    \b
    Embedding Modes:
    - LSB mode (default): Full color output, higher capacity
    - DCT mode: Frequency domain, ~20% capacity, better stealth
    
    \b
    DCT Options:
    - Color mode: grayscale (default) or color (preserves colors)
    - Output format: png (lossless) or jpeg (smaller, natural)
    """
    pass


# ============================================================================
# GENERATE COMMAND
# ============================================================================

@cli.command()
@click.option('--pin/--no-pin', default=True, help='Generate a PIN (default: yes)')
@click.option('--rsa/--no-rsa', default=False, help='Generate an RSA key')
@click.option('--pin-length', type=click.IntRange(6, 9), default=DEFAULT_PIN_LENGTH, 
              help=f'PIN length (6-9, default: {DEFAULT_PIN_LENGTH})')
@click.option('--rsa-bits', type=click.Choice(['2048', '3072', '4096']), default='2048', 
              help='RSA key size')
@click.option('--words', type=click.IntRange(3, 12), default=DEFAULT_PASSPHRASE_WORDS, 
              help=f'Words per passphrase (default: {DEFAULT_PASSPHRASE_WORDS})')
@click.option('--output', '-o', type=click.Path(), help='Save RSA key to file (requires password)')
@click.option('--password', '-p', help='Password for RSA key file')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def generate(pin, rsa, pin_length, rsa_bits, words, output, password, as_json):
    """
    Generate credentials for encoding/decoding.
    
    Creates a passphrase and optionally a PIN and/or RSA key.
    At least one of --pin or --rsa must be enabled.
    
    v3.2.0: Single passphrase (no more daily rotation!)
    Default increased to 4 words for better security.
    
    \b
    Examples:
        stegasoo generate
        stegasoo generate --words 5
        stegasoo generate --rsa --rsa-bits 4096
        stegasoo generate --rsa -o mykey.pem -p "secretpassword"
        stegasoo generate --no-pin --rsa
    """
    if not pin and not rsa:
        raise click.UsageError("Must enable at least one of --pin or --rsa")
    
    if output and not password:
        raise click.UsageError("--password is required when saving RSA key to file")
    
    if password and len(password) < 8:
        raise click.UsageError("Password must be at least 8 characters")
    
    try:
        creds = generate_credentials(
            use_pin=pin,
            use_rsa=rsa,
            pin_length=pin_length,
            rsa_bits=int(rsa_bits),
            passphrase_words=words,  # v3.2.0: renamed parameter
            rsa_password=password if output else None,
        )
        
        if as_json:
            import json
            data = {
                'passphrase': creds.passphrase,
                'pin': creds.pin,
                'rsa_key': creds.rsa_key_pem,
                'entropy': {
                    'passphrase': creds.passphrase_entropy,
                    'pin': creds.pin_entropy,
                    'rsa': creds.rsa_entropy,
                    'total': creds.total_entropy,
                }
            }
            click.echo(json.dumps(data, indent=2))
            return
        
        # Pretty output
        click.echo()
        click.secho("=" * 60, fg='cyan')
        click.secho("  STEGASOO CREDENTIALS (v3.2.0)", fg='cyan', bold=True)
        click.secho("=" * 60, fg='cyan')
        click.echo()
        
        click.secho("⚠️  MEMORIZE THESE AND CLOSE THIS WINDOW", fg='yellow', bold=True)
        click.secho("    Do not screenshot or save to file!", fg='yellow')
        click.echo()
        
        if creds.pin:
            click.secho("─── STATIC PIN ───", fg='green')
            click.secho(f"    {creds.pin}", fg='bright_yellow', bold=True)
            click.echo()
        
        click.secho("─── PASSPHRASE ───", fg='green')
        click.secho(f"    {creds.passphrase}", fg='bright_white', bold=True)
        click.echo()
        
        if creds.rsa_key_pem:
            click.secho("─── RSA KEY ───", fg='green')
            if output:
                # Save to file
                private_key = load_rsa_key(creds.rsa_key_pem.encode())
                encrypted_pem = export_rsa_key_pem(private_key, password)
                Path(output).write_bytes(encrypted_pem)
                click.secho(f"    Saved to: {output}", fg='bright_white')
                click.secho(f"    Password: {'*' * len(password)}", dim=True)
            else:
                click.echo(creds.rsa_key_pem)
            click.echo()
        
        click.secho("─── SECURITY ───", fg='green')
        click.echo(f"    Passphrase entropy: {creds.passphrase_entropy} bits ({words} words)")
        if creds.pin:
            click.echo(f"    PIN entropy:        {creds.pin_entropy} bits")
        if creds.rsa_key_pem:
            click.echo(f"    RSA entropy:        {creds.rsa_entropy} bits")
        click.echo(f"    Combined:           {creds.total_entropy} bits")
        click.secho(f"    + photo entropy:    80-256 bits", dim=True)
        click.echo()
        
        click.secho("✓ v3.2.0: Use this passphrase anytime - no date needed!", fg='cyan')
        click.echo()
        
    except Exception as e:
        raise click.ClickException(str(e))


# ============================================================================
# ENCODE COMMAND
# ============================================================================

@cli.command()
@click.option('--ref', '-r', required=True, type=click.Path(exists=True), help='Reference photo')
@click.option('--carrier', '-c', required=True, type=click.Path(exists=True), help='Carrier image')
@click.option('--message', '-m', help='Text message to encode')
@click.option('--message-file', '-f', type=click.Path(exists=True), help='Read text message from file')
@click.option('--embed-file', '-e', type=click.Path(exists=True), help='Embed a file (binary)')
@click.option('--passphrase', '-p', required=True, help='Passphrase')
@click.option('--pin', help='Static PIN')
@click.option('--key', '-k', type=click.Path(exists=True), help='RSA key file (.pem)')
@click.option('--key-qr', type=click.Path(exists=True), help='RSA key from QR code image')
@click.option('--key-password', help='RSA key password (for encrypted .pem files)')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: auto-generated)')
@click.option('--mode', 'embed_mode', type=click.Choice(['lsb', 'dct']), default='lsb',
              help='Embedding mode: lsb (default, color) or dct (requires scipy)')
@click.option('--dct-format', 'dct_output_format', type=click.Choice(['png', 'jpeg']), default='png',
              help='DCT output format: png (lossless, default) or jpeg (smaller)')
@click.option('--dct-color', 'dct_color_mode', type=click.Choice(['grayscale', 'color']), default='grayscale',
              help='DCT color mode: grayscale (default) or color (preserves original colors)')
@click.option('--quiet', '-q', is_flag=True, help='Suppress output except errors')
def encode_cmd(ref, carrier, message, message_file, embed_file, passphrase, pin, key, key_qr, 
               key_password, output, embed_mode, dct_output_format, dct_color_mode, quiet):
    """
    Encode a secret message or file into an image.
    
    Requires a reference photo, carrier image, and passphrase.
    Must provide either --pin or --key/--key-qr (or both).
    
    v3.2.0: No --date parameter needed! Encode and decode anytime.
    
    For text messages, use -m or -f or pipe via stdin.
    For binary files, use -e/--embed-file.
    RSA key can be provided as a .pem file (--key) or QR code image (--key-qr).
    
    \b
    Embedding Modes:
        --mode lsb   Spatial LSB embedding (default)
                     - Full color output (PNG/BMP)
                     - Higher capacity (~375 KB/megapixel)
        
        --mode dct   DCT domain embedding (requires scipy)
                     - Configurable color/grayscale output
                     - Lower capacity (~75 KB/megapixel)
                     - Better resistance to visual analysis
    
    \b
    DCT Options:
        --dct-format png     Lossless output (default)
        --dct-format jpeg    Smaller file, more natural appearance
        
        --dct-color grayscale   Convert to grayscale (default, traditional)
        --dct-color color       Preserve original colors (experimental)
    
    \b
    Examples:
        # Text message with PIN (LSB mode, default)
        stegasoo encode -r photo.jpg -c meme.png -p "apple forest thunder mountain" --pin 123456 -m "secret"
        
        # DCT mode - grayscale PNG (traditional)
        stegasoo encode -r photo.jpg -c meme.png -p "secure words here now" --pin 123456 -m "secret" --mode dct
        
        # DCT mode - color JPEG
        stegasoo encode -r photo.jpg -c meme.png -p "my strong passphrase" --pin 123456 -m "secret" \\
            --mode dct --dct-color color --dct-format jpeg
    """
    # Check DCT mode availability
    if embed_mode == 'dct' and not has_dct_support():
        raise click.ClickException(
            "DCT mode requires scipy. Install with: pip install scipy"
        )
    
    # Warn if DCT options used with LSB mode
    if embed_mode == 'lsb':
        if dct_output_format != 'png' or dct_color_mode != 'grayscale':
            if not quiet:
                click.secho("Note: --dct-format and --dct-color only apply to DCT mode", fg='yellow', dim=True)
    
    # Determine what to encode
    payload = None
    
    if embed_file:
        # Binary file embedding
        payload = FilePayload.from_file(embed_file)
        if not quiet:
            click.echo(f"Embedding file: {payload.filename} ({len(payload.data):,} bytes)")
    elif message:
        payload = message
    elif message_file:
        payload = Path(message_file).read_text()
    elif not sys.stdin.isatty():
        payload = sys.stdin.read()
    else:
        raise click.UsageError("Must provide message via -m, -f, -e, or stdin")
    
    # Load key if provided (from .pem file or QR code image)
    rsa_key_data = None
    rsa_key_from_qr = False
    
    if key and key_qr:
        raise click.UsageError("Cannot use both --key and --key-qr. Choose one.")
    
    if key:
        rsa_key_data = Path(key).read_bytes()
    elif key_qr:
        if not HAS_QR or not has_qr_read():
            raise click.ClickException(
                "QR code reading not available. Install: pip install pyzbar\n"
                "Also requires system library: sudo apt-get install libzbar0"
            )
        key_pem = extract_key_from_qr_file(key_qr)
        if not key_pem:
            raise click.ClickException(f"Could not extract RSA key from QR code: {key_qr}")
        rsa_key_data = key_pem.encode('utf-8')
        rsa_key_from_qr = True
        if not quiet:
            click.echo(f"Loaded RSA key from QR code: {key_qr}")
    
    # QR code keys are never password-protected
    effective_key_password = None if rsa_key_from_qr else key_password
    
    # Validate security factors
    if not pin and not rsa_key_data:
        raise click.UsageError("Must provide --pin or --key/--key-qr (or both)")
    
    try:
        ref_photo = Path(ref).read_bytes()
        carrier_image = Path(carrier).read_bytes()
        
        # Pre-check capacity with selected mode
        fit_check = will_fit_by_mode(payload, carrier_image, embed_mode=embed_mode)
        if not fit_check['fits']:
            # Suggest alternative mode if it would fit
            alt_mode = 'lsb' if embed_mode == 'dct' else 'dct'
            alt_check = will_fit_by_mode(payload, carrier_image, embed_mode=alt_mode)
            
            suggestion = ""
            if alt_mode == 'lsb' and alt_check['fits']:
                suggestion = f"\n  Tip: Payload would fit in LSB mode (--mode lsb)"
            
            raise click.ClickException(
                f"Payload too large for {embed_mode.upper()} mode.\n"
                f"  Payload: {fit_check['payload_size']:,} bytes\n"
                f"  Capacity: {fit_check['capacity']:,} bytes\n"
                f"  Shortfall: {-fit_check['headroom']:,} bytes"
                f"{suggestion}"
            )
        
        if not quiet:
            mode_desc = embed_mode.upper()
            if embed_mode == 'dct':
                mode_desc += f" ({dct_color_mode}, {dct_output_format.upper()})"
            click.echo(f"Mode: {mode_desc} ({fit_check['usage_percent']:.1f}% capacity)")
        
        # v3.2.0: No date_str parameter
        result = encode(
            message=payload,
            reference_photo=ref_photo,
            carrier_image=carrier_image,
            passphrase=passphrase,
            pin=pin or "",
            rsa_key_data=rsa_key_data,
            rsa_password=effective_key_password,
            embed_mode=embed_mode,
            dct_output_format=dct_output_format,
            dct_color_mode=dct_color_mode,
        )
        
        # Determine output path
        if output:
            out_path = Path(output)
        else:
            out_path = Path(result.filename)
        
        # Write output
        out_path.write_bytes(result.stego_image)
        
        if not quiet:
            click.secho(f"✓ Encoded successfully!", fg='green')
            click.echo(f"  Output: {out_path}")
            click.echo(f"  Size: {len(result.stego_image):,} bytes")
            click.echo(f"  Capacity used: {result.capacity_percent:.1f}%")
            if embed_mode == 'dct':
                color_note = "color preserved" if dct_color_mode == 'color' else "grayscale"
                format_note = dct_output_format.upper()
                click.secho(f"  DCT output: {format_note} ({color_note})", dim=True)
        
    except StegasooError as e:
        raise click.ClickException(str(e))
    except click.ClickException:
        raise
    except Exception as e:
        raise click.ClickException(f"Error: {e}")


# ============================================================================
# DECODE COMMAND
# ============================================================================

@cli.command()
@click.option('--ref', '-r', required=True, type=click.Path(exists=True), help='Reference photo')
@click.option('--stego', '-s', required=True, type=click.Path(exists=True), help='Stego image')
@click.option('--passphrase', '-p', required=True, help='Passphrase')
@click.option('--pin', help='Static PIN')
@click.option('--key', '-k', type=click.Path(exists=True), help='RSA key file (.pem)')
@click.option('--key-qr', type=click.Path(exists=True), help='RSA key from QR code image')
@click.option('--key-password', help='RSA key password (for encrypted .pem files)')
@click.option('--output', '-o', type=click.Path(), help='Save decoded content to file')
@click.option('--mode', 'embed_mode', type=click.Choice(['auto', 'lsb', 'dct']), default='auto',
              help='Extraction mode: auto (default), lsb, or dct')
@click.option('--quiet', '-q', is_flag=True, help='Output only the content (for text) or suppress messages (for files)')
@click.option('--force', is_flag=True, help='Overwrite existing output file')
def decode_cmd(ref, stego, passphrase, pin, key, key_qr, key_password, output, embed_mode, quiet, force):
    """
    Decode a secret message or file from a stego image.
    
    Must use the same credentials that were used for encoding.
    Automatically detects whether content is text or a file.
    RSA key can be provided as a .pem file (--key) or QR code image (--key-qr).
    
    v3.2.0: No --date parameter needed! Just use your passphrase.
    
    Note: Extraction works the same regardless of whether the image was
    created with color mode or grayscale mode - both use the same Y channel.
    
    \b
    Extraction Modes:
        --mode auto  Auto-detect (default) - tries LSB first, then DCT
        --mode lsb   Only try LSB extraction
        --mode dct   Only try DCT extraction (requires scipy)
    
    \b
    Examples:
        # Decode with PIN (auto-detect mode)
        stegasoo decode -r photo.jpg -s stego.png -p "apple forest thunder mountain" --pin 123456
        
        # Explicitly specify DCT mode
        stegasoo decode -r photo.jpg -s stego.png -p "my passphrase here" --pin 123456 --mode dct
        
        # Decode with RSA key file
        stegasoo decode -r photo.jpg -s stego.png -p "strong words" -k mykey.pem
        
        # Save output to file
        stegasoo decode -r photo.jpg -s stego.png -p "passphrase" --pin 123456 -o output.txt
    """
    # Check DCT mode availability
    if embed_mode == 'dct' and not has_dct_support():
        raise click.ClickException(
            "DCT mode requires scipy. Install with: pip install scipy"
        )
    
    # Load key if provided (from .pem file or QR code image)
    rsa_key_data = None
    rsa_key_from_qr = False
    
    if key and key_qr:
        raise click.UsageError("Cannot use both --key and --key-qr. Choose one.")
    
    if key:
        rsa_key_data = Path(key).read_bytes()
    elif key_qr:
        if not HAS_QR or not has_qr_read():
            raise click.ClickException(
                "QR code reading not available. Install: pip install pyzbar\n"
                "Also requires system library: sudo apt-get install libzbar0"
            )
        key_pem = extract_key_from_qr_file(key_qr)
        if not key_pem:
            raise click.ClickException(f"Could not extract RSA key from QR code: {key_qr}")
        rsa_key_data = key_pem.encode('utf-8')
        rsa_key_from_qr = True
        if not quiet:
            click.echo(f"Loaded RSA key from QR code: {key_qr}")
    
    # QR code keys are never password-protected
    effective_key_password = None if rsa_key_from_qr else key_password
    
    # Validate security factors
    if not pin and not rsa_key_data:
        raise click.UsageError("Must provide --pin or --key/--key-qr (or both)")
    
    try:
        ref_photo = Path(ref).read_bytes()
        stego_image = Path(stego).read_bytes()
        
        # v3.2.0: No date_str parameter
        result = decode(
            stego_image=stego_image,
            reference_photo=ref_photo,
            passphrase=passphrase,
            pin=pin or "",
            rsa_key_data=rsa_key_data,
            rsa_password=effective_key_password,
            embed_mode=embed_mode,
        )
        
        if result.is_file:
            # File content
            if output:
                out_path = Path(output)
            elif result.filename:
                out_path = Path(result.filename)
            else:
                out_path = Path("decoded_file")
            
            if out_path.exists() and not force:
                raise click.ClickException(
                    f"Output file '{out_path}' exists. Use --force to overwrite."
                )
            
            out_path.write_bytes(result.file_data)
            
            if not quiet:
                click.secho("✓ Decoded file successfully!", fg='green')
                click.echo(f"  Saved to: {out_path}")
                click.echo(f"  Size: {len(result.file_data):,} bytes")
                if result.mime_type:
                    click.echo(f"  Type: {result.mime_type}")
        else:
            # Text content
            if output:
                Path(output).write_text(result.message)
                if not quiet:
                    click.secho("✓ Decoded successfully!", fg='green')
                    click.echo(f"  Saved to: {output}")
            else:
                if quiet:
                    click.echo(result.message)
                else:
                    click.secho("✓ Decoded successfully!", fg='green')
                    click.echo()
                    click.echo(result.message)
        
    except (DecryptionError, ExtractionError) as e:
        raise click.ClickException(f"Decryption failed: {e}")
    except StegasooError as e:
        raise click.ClickException(str(e))
    except Exception as e:
        raise click.ClickException(f"Error: {e}")


# ============================================================================
# VERIFY COMMAND
# ============================================================================

@cli.command()
@click.option('--ref', '-r', required=True, type=click.Path(exists=True), help='Reference photo')
@click.option('--stego', '-s', required=True, type=click.Path(exists=True), help='Stego image')
@click.option('--passphrase', '-p', required=True, help='Passphrase')
@click.option('--pin', help='Static PIN')
@click.option('--key', '-k', type=click.Path(exists=True), help='RSA key file (.pem)')
@click.option('--key-qr', type=click.Path(exists=True), help='RSA key from QR code image')
@click.option('--key-password', help='RSA key password (for encrypted .pem files)')
@click.option('--mode', 'embed_mode', type=click.Choice(['auto', 'lsb', 'dct']), default='auto',
              help='Extraction mode: auto (default), lsb, or dct')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def verify(ref, stego, passphrase, pin, key, key_qr, key_password, embed_mode, as_json):
    """
    Verify that a stego image can be decoded without extracting the message.
    
    Quick check to validate credentials are correct and data is intact.
    Does NOT output the actual message content.
    
    \b
    Examples:
        stegasoo verify -r photo.jpg -s stego.png -p "my passphrase" --pin 123456
        
        stegasoo verify -r photo.jpg -s stego.png -p "words here" -k mykey.pem --json
        
        stegasoo verify -r photo.jpg -s stego.png -p "test phrase" --pin 123456 --mode dct
    """
    # Check DCT mode availability
    if embed_mode == 'dct' and not has_dct_support():
        raise click.ClickException(
            "DCT mode requires scipy. Install with: pip install scipy"
        )
    
    # Load key if provided
    rsa_key_data = None
    rsa_key_from_qr = False
    
    if key and key_qr:
        raise click.UsageError("Cannot use both --key and --key-qr. Choose one.")
    
    if key:
        rsa_key_data = Path(key).read_bytes()
    elif key_qr:
        if not HAS_QR or not has_qr_read():
            raise click.ClickException(
                "QR code reading not available. Install: pip install pyzbar\n"
                "Also requires system library: sudo apt-get install libzbar0"
            )
        key_pem = extract_key_from_qr_file(key_qr)
        if not key_pem:
            raise click.ClickException(f"Could not extract RSA key from QR code: {key_qr}")
        rsa_key_data = key_pem.encode('utf-8')
        rsa_key_from_qr = True
    
    effective_key_password = None if rsa_key_from_qr else key_password
    
    if not pin and not rsa_key_data:
        raise click.UsageError("Must provide --pin or --key/--key-qr (or both)")
    
    try:
        ref_photo = Path(ref).read_bytes()
        stego_image = Path(stego).read_bytes()
        
        # Attempt to decode
        result = decode(
            stego_image=stego_image,
            reference_photo=ref_photo,
            passphrase=passphrase,
            pin=pin or "",
            rsa_key_data=rsa_key_data,
            rsa_password=effective_key_password,
            embed_mode=embed_mode,
        )
        
        # Calculate payload size
        if result.is_file:
            payload_size = len(result.file_data) if result.file_data else 0
            payload_type = "file"
            payload_desc = result.filename or "unnamed file"
            if result.mime_type:
                payload_desc += f" ({result.mime_type})"
        else:
            payload_size = len(result.message.encode('utf-8')) if result.message else 0
            payload_type = "text"
            payload_desc = f"{payload_size} bytes"
        
        if as_json:
            import json
            output_data = {
                "valid": True,
                "stego_file": stego,
                "payload_type": payload_type,
                "payload_size": payload_size,
            }
            if result.is_file:
                output_data["filename"] = result.filename
                output_data["mime_type"] = result.mime_type
            click.echo(json.dumps(output_data, indent=2))
        else:
            click.secho("✓ Valid stego image", fg='green', bold=True)
            click.echo(f"  Payload:  {payload_type} ({payload_desc})")
            click.echo(f"  Size:     {payload_size:,} bytes")
        
    except (DecryptionError, ExtractionError) as e:
        if as_json:
            import json
            output_data = {
                "valid": False,
                "stego_file": stego,
                "error": str(e),
            }
            click.echo(json.dumps(output_data, indent=2))
            sys.exit(1)
        else:
            click.secho("✗ Verification failed", fg='red', bold=True)
            click.echo(f"  Error: {e}")
            sys.exit(1)
    except StegasooError as e:
        raise click.ClickException(str(e))
    except Exception as e:
        raise click.ClickException(f"Error: {e}")


# ============================================================================
# INFO COMMAND
# ============================================================================

@cli.command()
@click.argument('image', type=click.Path(exists=True))
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def info(image, as_json):
    """
    Show information about an image.
    
    Displays dimensions, capacity for both LSB and DCT modes.
    """
    try:
        image_data = Path(image).read_bytes()
        
        result = validate_image(image_data, check_size=False)
        if not result.is_valid:
            raise click.ClickException(result.error_message)
        
        # Get capacity comparison
        comparison = compare_modes(image_data)
        
        if as_json:
            import json
            output_data = {
                "file": image,
                "width": result.details['width'],
                "height": result.details['height'],
                "pixels": result.details['pixels'],
                "mode": result.details['mode'],
                "format": result.details['format'],
                "capacity": {
                    "lsb": {
                        "bytes": comparison['lsb']['capacity_bytes'],
                        "kb": round(comparison['lsb']['capacity_kb'], 1),
                    },
                    "dct": {
                        "bytes": comparison['dct']['capacity_bytes'],
                        "kb": round(comparison['dct']['capacity_kb'], 1),
                        "available": comparison['dct']['available'],
                        "ratio_vs_lsb": round(comparison['dct']['ratio_vs_lsb'], 1),
                        "output_formats": ["png", "jpeg"],
                        "color_modes": ["grayscale", "color"],
                    },
                },
            }
            click.echo(json.dumps(output_data, indent=2))
            return
        
        click.echo()
        click.secho(f"Image: {image}", bold=True)
        click.echo(f"  Dimensions:  {result.details['width']} × {result.details['height']}")
        click.echo(f"  Pixels:      {result.details['pixels']:,}")
        click.echo(f"  Mode:        {result.details['mode']}")
        click.echo(f"  Format:      {result.details['format']}")
        click.echo()
        
        click.secho("  Capacity:", bold=True)
        click.echo(f"    LSB mode:  ~{comparison['lsb']['capacity_bytes']:,} bytes ({comparison['lsb']['capacity_kb']:.1f} KB)")
        
        dct_status = "✓" if comparison['dct']['available'] else "✗ (scipy not installed)"
        click.echo(f"    DCT mode:  ~{comparison['dct']['capacity_bytes']:,} bytes ({comparison['dct']['capacity_kb']:.1f} KB) {dct_status}")
        click.echo(f"    DCT ratio: {comparison['dct']['ratio_vs_lsb']:.1f}% of LSB")
        
        if comparison['dct']['available']:
            click.secho("    DCT options: grayscale/color, png/jpeg", dim=True)
        
        click.echo()
        
    except Exception as e:
        raise click.ClickException(str(e))


# ============================================================================
# COMPARE COMMAND
# ============================================================================

@cli.command()
@click.argument('image', type=click.Path(exists=True))
@click.option('--payload-size', '-s', type=int, help='Check if specific payload size fits')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def compare(image, payload_size, as_json):
    """
    Compare LSB and DCT embedding modes for an image.
    
    Shows capacity for each mode and recommends which to use.
    Optionally checks if a specific payload size would fit.
    
    \b
    Examples:
        stegasoo compare carrier.png
        stegasoo compare carrier.png --payload-size 50000
        stegasoo compare carrier.png --json
    """
    try:
        image_data = Path(image).read_bytes()
        
        comparison = compare_modes(image_data)
        
        if as_json:
            import json
            output_data = {
                "file": image,
                "width": comparison['width'],
                "height": comparison['height'],
                "modes": {
                    "lsb": {
                        "capacity_bytes": comparison['lsb']['capacity_bytes'],
                        "capacity_kb": round(comparison['lsb']['capacity_kb'], 1),
                        "available": True,
                        "output_format": comparison['lsb']['output'],
                    },
                    "dct": {
                        "capacity_bytes": comparison['dct']['capacity_bytes'],
                        "capacity_kb": round(comparison['dct']['capacity_kb'], 1),
                        "available": comparison['dct']['available'],
                        "output_formats": ["png", "jpeg"],
                        "color_modes": ["grayscale", "color"],
                        "ratio_vs_lsb_percent": round(comparison['dct']['ratio_vs_lsb'], 1),
                    },
                },
            }
            
            if payload_size:
                output_data["payload_check"] = {
                    "size_bytes": payload_size,
                    "fits_lsb": payload_size <= comparison['lsb']['capacity_bytes'],
                    "fits_dct": payload_size <= comparison['dct']['capacity_bytes'],
                }
            
            click.echo(json.dumps(output_data, indent=2))
            return
        
        click.echo()
        click.secho(f"=== Mode Comparison: {image} ===", fg='cyan', bold=True)
        click.echo(f"  Dimensions: {comparison['width']} × {comparison['height']}")
        click.echo()
        
        # LSB mode
        click.secho("  ┌─── LSB Mode ───", fg='green')
        click.echo(f"  │ Capacity:  {comparison['lsb']['capacity_bytes']:,} bytes ({comparison['lsb']['capacity_kb']:.1f} KB)")
        click.echo(f"  │ Output:    {comparison['lsb']['output']}")
        click.echo(f"  │ Status:    ✓ Available")
        click.echo("  │")
        
        # DCT mode
        click.secho("  ├─── DCT Mode ───", fg='blue')
        click.echo(f"  │ Capacity:  {comparison['dct']['capacity_bytes']:,} bytes ({comparison['dct']['capacity_kb']:.1f} KB)")
        click.echo(f"  │ Ratio:     {comparison['dct']['ratio_vs_lsb']:.1f}% of LSB capacity")
        if comparison['dct']['available']:
            click.echo(f"  │ Status:    ✓ Available")
            click.echo(f"  │ Formats:   PNG (lossless), JPEG (smaller)")
            click.echo(f"  │ Colors:    Grayscale (default), Color")
        else:
            click.secho(f"  │ Status:    ✗ Requires scipy (pip install scipy)", fg='yellow')
        click.echo("  │")
        
        # Payload check
        if payload_size:
            click.secho("  ├─── Payload Check ───", fg='magenta')
            click.echo(f"  │ Size:      {payload_size:,} bytes")
            
            fits_lsb = payload_size <= comparison['lsb']['capacity_bytes']
            fits_dct = payload_size <= comparison['dct']['capacity_bytes']
            
            lsb_icon = "✓" if fits_lsb else "✗"
            dct_icon = "✓" if fits_dct else "✗"
            lsb_color = 'green' if fits_lsb else 'red'
            dct_color = 'green' if fits_dct else 'red'
            
            click.echo(f"  │ LSB mode:  ", nl=False)
            click.secho(f"{lsb_icon} {'Fits' if fits_lsb else 'Too large'}", fg=lsb_color)
            click.echo(f"  │ DCT mode:  ", nl=False)
            click.secho(f"{dct_icon} {'Fits' if fits_dct else 'Too large'}", fg=dct_color)
            click.echo("  │")
        
        # Recommendation
        click.secho("  └─── Recommendation ───", fg='yellow')
        if not comparison['dct']['available']:
            click.echo("    Use LSB mode (DCT unavailable)")
        elif payload_size:
            if fits_dct:
                click.echo("    DCT mode for better stealth (payload fits both modes)")
                click.echo("    Use --dct-color color to preserve original colors")
            elif fits_lsb:
                click.echo("    LSB mode (payload too large for DCT)")
            else:
                click.secho("    ✗ Payload too large for both modes!", fg='red')
        else:
            click.echo("    LSB for larger payloads, DCT for better stealth")
            click.echo("    DCT supports color output with --dct-color color")
        
        click.echo()
        
    except Exception as e:
        raise click.ClickException(str(e))


# ============================================================================
# STRIP-METADATA COMMAND
# ============================================================================

@cli.command('strip-metadata')
@click.argument('image', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file (default: overwrites input)')
@click.option('--format', '-f', 'output_format', type=click.Choice(['PNG', 'BMP']), default='PNG', 
              help='Output format')
@click.option('--quiet', '-q', is_flag=True, help='Suppress output')
def strip_metadata_cmd(image, output, output_format, quiet):
    """
    Remove all metadata (EXIF, GPS, etc.) from an image.
    
    Creates a clean image with only pixel data - no camera info,
    location data, timestamps, or other potentially sensitive metadata.
    
    \b
    Examples:
        stegasoo strip-metadata photo.jpg -o clean.png
        stegasoo strip-metadata photo.jpg  # Overwrites as PNG
    """
    if not HAS_STRIP_METADATA:
        raise click.ClickException("strip_image_metadata not available")
    
    try:
        image_data = Path(image).read_bytes()
        original_size = len(image_data)
        
        clean_data = strip_image_metadata(image_data, output_format)
        
        if output:
            out_path = Path(output)
        else:
            # Replace extension with output format
            out_path = Path(image).with_suffix(f'.{output_format.lower()}')
        
        out_path.write_bytes(clean_data)
        
        if not quiet:
            click.secho("✓ Metadata stripped", fg='green')
            click.echo(f"  Input:  {image} ({original_size:,} bytes)")
            click.echo(f"  Output: {out_path} ({len(clean_data):,} bytes)")
        
    except Exception as e:
        raise click.ClickException(str(e))


# ============================================================================
# MODES COMMAND
# ============================================================================

@cli.command()
def modes():
    """
    Show available embedding modes and their status.
    
    Displays which modes are available and their characteristics.
    """
    click.echo()
    click.secho("=== Stegasoo Embedding Modes (v3.2.0) ===", fg='cyan', bold=True)
    click.echo()
    
    # LSB Mode
    click.secho("  LSB Mode (Spatial LSB)", fg='green', bold=True)
    click.echo("    Status:      ✓ Always available")
    click.echo("    Output:      PNG/BMP (full color)")
    click.echo("    Capacity:    ~375 KB per megapixel")
    click.echo("    Use case:    Larger payloads, color preservation")
    click.echo("    CLI flag:    --mode lsb (default)")
    click.echo()
    
    # DCT Mode
    click.secho("  DCT Mode (Frequency Domain)", fg='blue', bold=True)
    if has_dct_support():
        click.echo("    Status:      ✓ Available")
    else:
        click.secho("    Status:      ✗ Requires scipy", fg='yellow')
        click.echo("    Install:     pip install scipy")
    click.echo("    Capacity:    ~75 KB per megapixel (~20% of LSB)")
    click.echo("    Use case:    Better stealth, frequency domain hiding")
    click.echo("    CLI flag:    --mode dct")
    click.echo()
    
    # DCT Options
    click.secho("  DCT Options", fg='magenta', bold=True)
    click.echo("    Output format:")
    click.echo("      --dct-format png     Lossless, larger file (default)")
    click.echo("      --dct-format jpeg    Lossy, smaller, more natural")
    click.echo()
    click.echo("    Color mode:")
    click.echo("      --dct-color grayscale   Traditional DCT (default)")
    click.echo("      --dct-color color       Preserves original colors")
    click.echo()
    
    # v3.2.0 Note
    click.secho("  v3.2.0 Changes:", fg='cyan', bold=True)
    click.echo("    ✓ No date parameters needed")
    click.echo("    ✓ Single passphrase (no daily rotation)")
    click.echo("    ✓ Default passphrase increased to 4 words")
    click.echo("    ✓ True asynchronous communications")
    click.echo()
    
    # Examples
    click.secho("  Examples:", dim=True)
    click.echo("    # Traditional DCT (grayscale PNG)")
    click.echo("    stegasoo encode ... --mode dct")
    click.echo()
    click.echo("    # Color-preserving DCT with JPEG output")
    click.echo("    stegasoo encode ... --mode dct --dct-color color --dct-format jpeg")
    click.echo()
    click.echo("    # Compare modes for an image")
    click.echo("    stegasoo compare carrier.png")
    click.echo()


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Entry point."""
    cli()


if __name__ == '__main__':
    main()
