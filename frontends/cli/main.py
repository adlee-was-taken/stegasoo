#!/usr/bin/env python3
"""
Stegasoo CLI - Command-line interface for steganography operations.

Usage:
    stegasoo generate [OPTIONS]
    stegasoo encode [OPTIONS]
    stegasoo decode [OPTIONS]
    stegasoo verify [OPTIONS]
    stegasoo info [OPTIONS]
    stegasoo compare [OPTIONS]  # NEW in v3.0
"""

import sys
from pathlib import Path
from typing import Optional

import click

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import stegasoo
from stegasoo import (
    encode, encode_file, decode,
    generate_credentials,
    export_rsa_key_pem, load_rsa_key,
    validate_image, calculate_capacity,
    get_day_from_date, parse_date_from_filename,
    DAY_NAMES, __version__,
    StegasooError, DecryptionError, ExtractionError,
    FilePayload,
    will_fit,
    strip_image_metadata,
    # NEW in v3.0 - Embedding modes
    EMBED_MODE_LSB,
    EMBED_MODE_DCT,
    EMBED_MODE_AUTO,
    has_dct_support,
    compare_modes,
    will_fit_by_mode,
    calculate_capacity_by_mode,
)

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
    • Reference photo (something you have)
    • Daily passphrase (something you know)
    • Static PIN or RSA key (additional security)
    
    \b
    NEW in v3.0 - Embedding Modes:
    • LSB mode (default): Full color output, higher capacity
    • DCT mode: Grayscale output, ~20% capacity, better stealth
    """
    pass


# ============================================================================
# GENERATE COMMAND
# ============================================================================

@cli.command()
@click.option('--pin/--no-pin', default=True, help='Generate a PIN (default: yes)')
@click.option('--rsa/--no-rsa', default=False, help='Generate an RSA key')
@click.option('--pin-length', type=click.IntRange(6, 9), default=6, help='PIN length (6-9)')
@click.option('--rsa-bits', type=click.Choice(['2048', '3072', '4096']), default='2048', help='RSA key size')
@click.option('--words', type=click.IntRange(3, 12), default=3, help='Words per phrase (3-12)')
@click.option('--output', '-o', type=click.Path(), help='Save RSA key to file (requires password)')
@click.option('--password', '-p', help='Password for RSA key file')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def generate(pin, rsa, pin_length, rsa_bits, words, output, password, as_json):
    """
    Generate credentials for encoding/decoding.
    
    Creates daily passphrases and optionally a PIN and/or RSA key.
    At least one of --pin or --rsa must be enabled.
    
    \b
    Examples:
        stegasoo generate
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
            words_per_phrase=words
        )
        
        if as_json:
            import json
            data = {
                'phrases': creds.phrases,
                'pin': creds.pin,
                'rsa_key': creds.rsa_key_pem,
                'entropy': {
                    'phrase': creds.phrase_entropy,
                    'pin': creds.pin_entropy,
                    'rsa': creds.rsa_entropy,
                    'total': creds.total_entropy,
                }
            }
            click.echo(json.dumps(data, indent=2))
            return
        
        # Pretty output
        click.echo()
        click.secho("═" * 60, fg='cyan')
        click.secho("  STEGASOO CREDENTIALS", fg='cyan', bold=True)
        click.secho("═" * 60, fg='cyan')
        click.echo()
        
        click.secho("⚠️  MEMORIZE THESE AND CLOSE THIS WINDOW", fg='yellow', bold=True)
        click.secho("    Do not screenshot or save to file!", fg='yellow')
        click.echo()
        
        if creds.pin:
            click.secho("─── STATIC PIN ───", fg='green')
            click.secho(f"    {creds.pin}", fg='bright_yellow', bold=True)
            click.echo()
        
        click.secho("─── DAILY PHRASES ───", fg='green')
        for day in DAY_NAMES:
            phrase = creds.phrases[day]
            click.echo(f"    {day:9} │ ", nl=False)
            click.secho(phrase, fg='bright_white')
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
        click.echo(f"    Phrase entropy:  {creds.phrase_entropy} bits")
        if creds.pin:
            click.echo(f"    PIN entropy:     {creds.pin_entropy} bits")
        if creds.rsa_key_pem:
            click.echo(f"    RSA entropy:     {creds.rsa_entropy} bits")
        click.echo(f"    Combined:        {creds.total_entropy} bits")
        click.secho(f"    + photo entropy: 80-256 bits", dim=True)
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
@click.option('--phrase', '-p', required=True, help='Day phrase')
@click.option('--pin', help='Static PIN')
@click.option('--key', '-k', type=click.Path(exists=True), help='RSA key file (.pem)')
@click.option('--key-qr', type=click.Path(exists=True), help='RSA key from QR code image')
@click.option('--key-password', help='RSA key password (for encrypted .pem files)')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: auto-generated)')
@click.option('--date', 'date_str', help='Date override (YYYY-MM-DD)')
@click.option('--mode', 'embed_mode', type=click.Choice(['lsb', 'dct']), default='lsb',
              help='Embedding mode: lsb (default, color) or dct (grayscale, requires scipy)')
@click.option('--quiet', '-q', is_flag=True, help='Suppress output except errors')
def encode_cmd(ref, carrier, message, message_file, embed_file, phrase, pin, key, key_qr, key_password, output, date_str, embed_mode, quiet):
    """
    Encode a secret message or file into an image.
    
    Requires a reference photo, carrier image, and day phrase.
    Must provide either --pin or --key/--key-qr (or both).
    
    For text messages, use -m or -f or pipe via stdin.
    For binary files, use -e/--embed-file.
    RSA key can be provided as a .pem file (--key) or QR code image (--key-qr).
    
    \b
    Embedding Modes (v3.0):
        --mode lsb   Spatial LSB embedding (default)
                     • Full color output (PNG/BMP)
                     • Higher capacity (~375 KB/megapixel)
        
        --mode dct   DCT domain embedding (requires scipy)
                     • Grayscale output only
                     • Lower capacity (~75 KB/megapixel)
                     • Better resistance to visual analysis
    
    \b
    Examples:
        # Text message with PIN (LSB mode, default)
        stegasoo encode -r photo.jpg -c meme.png -p "apple forest thunder" --pin 123456 -m "secret"
        
        # DCT mode for better stealth
        stegasoo encode -r photo.jpg -c meme.png -p "words" --pin 123456 -m "secret" --mode dct
        
        # With RSA key file
        stegasoo encode -r photo.jpg -c meme.png -p "words" -k mykey.pem -m "secret"
        
        # Embed a binary file
        stegasoo encode -r photo.jpg -c meme.png -p "words" --pin 123456 -e secret.pdf
    """
    # Check DCT mode availability
    if embed_mode == 'dct' and not has_dct_support():
        raise click.ClickException(
            "DCT mode requires scipy. Install with: pip install scipy"
        )
    
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
            click.echo(f"Mode: {embed_mode.upper()} ({fit_check['usage_percent']:.1f}% capacity)")
        
        result = encode(
            message=payload,
            reference_photo=ref_photo,
            carrier_image=carrier_image,
            day_phrase=phrase,
            pin=pin or "",
            rsa_key_data=rsa_key_data,
            rsa_password=effective_key_password,
            date_str=date_str,
            embed_mode=embed_mode,  # NEW in v3.0
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
            click.echo(f"  Date: {result.date_used}")
            if embed_mode == 'dct':
                click.secho(f"  Note: Output is grayscale (DCT mode)", dim=True)
        
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
@click.option('--phrase', '-p', required=True, help='Day phrase')
@click.option('--pin', help='Static PIN')
@click.option('--key', '-k', type=click.Path(exists=True), help='RSA key file (.pem)')
@click.option('--key-qr', type=click.Path(exists=True), help='RSA key from QR code image')
@click.option('--key-password', help='RSA key password (for encrypted .pem files)')
@click.option('--output', '-o', type=click.Path(), help='Save decoded content to file')
@click.option('--mode', 'embed_mode', type=click.Choice(['auto', 'lsb', 'dct']), default='auto',
              help='Extraction mode: auto (default), lsb, or dct')
@click.option('--quiet', '-q', is_flag=True, help='Output only the content (for text) or suppress messages (for files)')
@click.option('--force', is_flag=True, help='Overwrite existing output file')
def decode_cmd(ref, stego, phrase, pin, key, key_qr, key_password, output, embed_mode, quiet, force):
    """
    Decode a secret message or file from a stego image.
    
    Must use the same credentials that were used for encoding.
    Automatically detects whether content is text or a file.
    RSA key can be provided as a .pem file (--key) or QR code image (--key-qr).
    
    \b
    Extraction Modes (v3.0):
        --mode auto  Auto-detect (default) - tries LSB first, then DCT
        --mode lsb   Only try LSB extraction
        --mode dct   Only try DCT extraction (requires scipy)
    
    \b
    Examples:
        # Decode with PIN (auto-detect mode)
        stegasoo decode -r photo.jpg -s stego.png -p "apple forest thunder" --pin 123456
        
        # Explicitly specify DCT mode
        stegasoo decode -r photo.jpg -s stego.png -p "words" --pin 123456 --mode dct
        
        # Decode with RSA key file
        stegasoo decode -r photo.jpg -s stego.png -p "words" -k mykey.pem
        
        # Save output to file
        stegasoo decode -r photo.jpg -s stego.png -p "words" --pin 123456 -o output.txt
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
        
        result = decode(
            stego_image=stego_image,
            reference_photo=ref_photo,
            day_phrase=phrase,
            pin=pin or "",
            rsa_key_data=rsa_key_data,
            rsa_password=effective_key_password,
            embed_mode=embed_mode,  # NEW in v3.0
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
@click.option('--phrase', '-p', required=True, help='Day phrase')
@click.option('--pin', help='Static PIN')
@click.option('--key', '-k', type=click.Path(exists=True), help='RSA key file (.pem)')
@click.option('--key-qr', type=click.Path(exists=True), help='RSA key from QR code image')
@click.option('--key-password', help='RSA key password (for encrypted .pem files)')
@click.option('--mode', 'embed_mode', type=click.Choice(['auto', 'lsb', 'dct']), default='auto',
              help='Extraction mode: auto (default), lsb, or dct')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def verify(ref, stego, phrase, pin, key, key_qr, key_password, embed_mode, as_json):
    """
    Verify that a stego image can be decoded without extracting the message.
    
    Quick check to validate credentials are correct and data is intact.
    Does NOT output the actual message content.
    
    \b
    Examples:
        stegasoo verify -r photo.jpg -s stego.png -p "apple forest thunder" --pin 123456
        
        stegasoo verify -r photo.jpg -s stego.png -p "words" -k mykey.pem --json
        
        stegasoo verify -r photo.jpg -s stego.png -p "words" --pin 123456 --mode dct
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
            day_phrase=phrase,
            pin=pin or "",
            rsa_key_data=rsa_key_data,
            rsa_password=effective_key_password,
            embed_mode=embed_mode,  # NEW in v3.0
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
        
        # Get date info
        date_encoded = result.date_encoded
        day_name = get_day_from_date(date_encoded) if date_encoded else None
        
        if as_json:
            import json
            output = {
                "valid": True,
                "stego_file": stego,
                "payload_type": payload_type,
                "payload_size": payload_size,
                "date_encoded": date_encoded,
                "day_encoded": day_name,
            }
            if result.is_file:
                output["filename"] = result.filename
                output["mime_type"] = result.mime_type
            click.echo(json.dumps(output, indent=2))
        else:
            click.secho("✓ Valid stego image", fg='green', bold=True)
            click.echo(f"  Payload:  {payload_type} ({payload_desc})")
            click.echo(f"  Size:     {payload_size:,} bytes")
            if date_encoded:
                click.echo(f"  Encoded:  {date_encoded} ({day_name})")
        
    except (DecryptionError, ExtractionError) as e:
        if as_json:
            import json
            output = {
                "valid": False,
                "stego_file": stego,
                "error": str(e),
            }
            click.echo(json.dumps(output, indent=2))
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
    
    Displays dimensions, capacity for both LSB and DCT modes,
    and attempts to detect date from filename.
    """
    try:
        image_data = Path(image).read_bytes()
        
        result = validate_image(image_data, check_size=False)
        if not result.is_valid:
            raise click.ClickException(result.error_message)
        
        # Get capacity comparison
        comparison = compare_modes(image_data)
        
        # Try to get date from filename
        date_str = parse_date_from_filename(image)
        day_name = get_day_from_date(date_str) if date_str else None
        
        if as_json:
            import json
            output = {
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
                    },
                },
            }
            if date_str:
                output["embed_date"] = date_str
                output["embed_day"] = day_name
            click.echo(json.dumps(output, indent=2))
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
        
        if date_str:
            click.echo()
            click.echo(f"  Embed date:  {date_str} ({day_name})")
        
        click.echo()
        
    except Exception as e:
        raise click.ClickException(str(e))


# ============================================================================
# COMPARE COMMAND (NEW in v3.0)
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
            output = {
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
                        "output_format": comparison['dct']['output'],
                        "ratio_vs_lsb_percent": round(comparison['dct']['ratio_vs_lsb'], 1),
                    },
                },
            }
            
            if payload_size:
                output["payload_check"] = {
                    "size_bytes": payload_size,
                    "fits_lsb": payload_size <= comparison['lsb']['capacity_bytes'],
                    "fits_dct": payload_size <= comparison['dct']['capacity_bytes'],
                }
            
            click.echo(json.dumps(output, indent=2))
            return
        
        click.echo()
        click.secho(f"═══ Mode Comparison: {image} ═══", fg='cyan', bold=True)
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
        click.echo(f"  │ Output:    {comparison['dct']['output']}")
        click.echo(f"  │ Ratio:     {comparison['dct']['ratio_vs_lsb']:.1f}% of LSB capacity")
        if comparison['dct']['available']:
            click.echo(f"  │ Status:    ✓ Available")
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
            click.echo("  Use LSB mode (DCT unavailable)")
        elif payload_size:
            if fits_dct:
                click.echo("  DCT mode for better stealth (payload fits both modes)")
            elif fits_lsb:
                click.echo("  LSB mode (payload too large for DCT)")
            else:
                click.secho("  ✗ Payload too large for both modes!", fg='red')
        else:
            click.echo("  LSB for larger payloads, DCT for better stealth")
        
        click.echo()
        
    except Exception as e:
        raise click.ClickException(str(e))


# ============================================================================
# STRIP-METADATA COMMAND
# ============================================================================

@cli.command('strip-metadata')
@click.argument('image', type=click.Path(exists=True))
@click.option('--output', '-o', type=click.Path(), help='Output file (default: overwrites input)')
@click.option('--format', '-f', 'output_format', type=click.Choice(['PNG', 'BMP']), default='PNG', help='Output format')
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
# MODES COMMAND (NEW in v3.0)
# ============================================================================

@cli.command()
def modes():
    """
    Show available embedding modes and their status.
    
    Displays which modes are available and their characteristics.
    """
    click.echo()
    click.secho("═══ Stegasoo Embedding Modes ═══", fg='cyan', bold=True)
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
    click.echo("    Output:      PNG (grayscale only)")
    click.echo("    Capacity:    ~75 KB per megapixel (~20% of LSB)")
    click.echo("    Use case:    Better stealth, smaller messages")
    click.echo("    CLI flag:    --mode dct")
    click.echo()
    
    click.secho("  Tip:", dim=True)
    click.echo("    Use 'stegasoo compare <image>' to see capacity for both modes")
    click.echo()


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Entry point."""
    cli()


if __name__ == '__main__':
    main()
