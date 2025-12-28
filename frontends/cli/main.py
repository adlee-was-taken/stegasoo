#!/usr/bin/env python3
"""
Stegasoo CLI - Command-line interface for steganography operations.

Usage:
    stegasoo generate [OPTIONS]
    stegasoo encode [OPTIONS]
    stegasoo decode [OPTIONS]
    stegasoo info [OPTIONS]
"""

import sys
from pathlib import Path
from typing import Optional

import click

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import stegasoo
from stegasoo import (
    encode, decode, generate_credentials,
    export_rsa_key_pem, load_rsa_key,
    validate_image, calculate_capacity,
    get_day_from_date, parse_date_from_filename,
    DAY_NAMES, __version__,
    StegasooError, DecryptionError, ExtractionError,
)


# ============================================================================
# CLI SETUP
# ============================================================================

CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, '-v', '--version')
def cli():
    """
    Stegasoo - Secure steganography with hybrid authentication.
    
    Hide encrypted messages in images using a combination of:
    
    \b
    • Reference photo (something you have)
    • Daily passphrase (something you know)
    • Static PIN or RSA key (additional security)
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
@click.option('--message', '-m', help='Message to encode (or use stdin)')
@click.option('--message-file', '-f', type=click.Path(exists=True), help='Read message from file')
@click.option('--phrase', '-p', required=True, help='Day phrase')
@click.option('--pin', help='Static PIN')
@click.option('--key', '-k', type=click.Path(exists=True), help='RSA key file')
@click.option('--key-password', help='RSA key password')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: auto-generated)')
@click.option('--date', 'date_str', help='Date override (YYYY-MM-DD)')
@click.option('--quiet', '-q', is_flag=True, help='Suppress output except errors')
def encode_cmd(ref, carrier, message, message_file, phrase, pin, key, key_password, output, date_str, quiet):
    """
    Encode a secret message into an image.
    
    Requires a reference photo, carrier image, and day phrase.
    Must provide either --pin or --key (or both).
    
    \b
    Examples:
        stegasoo encode -r photo.jpg -c meme.png -p "apple forest thunder" --pin 123456 -m "secret"
        echo "secret" | stegasoo encode -r photo.jpg -c meme.png -p "word1 word2 word3" --pin 123456
        stegasoo encode -r photo.jpg -c meme.png -p "words" -k mykey.pem --key-password "pass"
    """
    # Get message
    if message:
        msg = message
    elif message_file:
        msg = Path(message_file).read_text()
    elif not sys.stdin.isatty():
        msg = sys.stdin.read()
    else:
        raise click.UsageError("Must provide message via -m, -f, or stdin")
    
    # Load key if provided
    rsa_key_data = None
    if key:
        rsa_key_data = Path(key).read_bytes()
    
    # Validate security factors
    if not pin and not rsa_key_data:
        raise click.UsageError("Must provide --pin or --key (or both)")
    
    try:
        ref_photo = Path(ref).read_bytes()
        carrier_image = Path(carrier).read_bytes()
        
        result = encode(
            message=msg,
            reference_photo=ref_photo,
            carrier_image=carrier_image,
            day_phrase=phrase,
            pin=pin or "",
            rsa_key_data=rsa_key_data,
            rsa_password=key_password,
            date_str=date_str,
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
        
    except StegasooError as e:
        raise click.ClickException(str(e))
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
@click.option('--key', '-k', type=click.Path(exists=True), help='RSA key file')
@click.option('--key-password', help='RSA key password')
@click.option('--output', '-o', type=click.Path(), help='Save message to file')
@click.option('--quiet', '-q', is_flag=True, help='Output only the message')
def decode_cmd(ref, stego, phrase, pin, key, key_password, output, quiet):
    """
    Decode a secret message from a stego image.
    
    Must use the same credentials that were used for encoding.
    
    \b
    Examples:
        stegasoo decode -r photo.jpg -s stego.png -p "apple forest thunder" --pin 123456
        stegasoo decode -r photo.jpg -s stego.png -p "words" -k mykey.pem --key-password "pass"
        stegasoo decode -r photo.jpg -s stego.png -p "words" --pin 123456 -o message.txt
    """
    # Load key if provided
    rsa_key_data = None
    if key:
        rsa_key_data = Path(key).read_bytes()
    
    # Validate security factors
    if not pin and not rsa_key_data:
        raise click.UsageError("Must provide --pin or --key (or both)")
    
    try:
        ref_photo = Path(ref).read_bytes()
        stego_image = Path(stego).read_bytes()
        
        message = decode(
            stego_image=stego_image,
            reference_photo=ref_photo,
            day_phrase=phrase,
            pin=pin or "",
            rsa_key_data=rsa_key_data,
            rsa_password=key_password,
        )
        
        if output:
            Path(output).write_text(message)
            if not quiet:
                click.secho(f"✓ Decoded successfully!", fg='green')
                click.echo(f"  Saved to: {output}")
        else:
            if quiet:
                click.echo(message)
            else:
                click.secho("✓ Decoded successfully!", fg='green')
                click.echo()
                click.echo(message)
        
    except (DecryptionError, ExtractionError) as e:
        raise click.ClickException(f"Decryption failed: {e}")
    except StegasooError as e:
        raise click.ClickException(str(e))
    except Exception as e:
        raise click.ClickException(f"Error: {e}")


# ============================================================================
# INFO COMMAND
# ============================================================================

@cli.command()
@click.argument('image', type=click.Path(exists=True))
def info(image):
    """
    Show information about an image.
    
    Displays dimensions, capacity, and attempts to detect date from filename.
    """
    try:
        image_data = Path(image).read_bytes()
        
        result = validate_image(image_data, check_size=False)
        if not result.is_valid:
            raise click.ClickException(result.error_message)
        
        capacity = calculate_capacity(image_data)
        
        # Try to get date from filename
        date_str = parse_date_from_filename(image)
        day_name = get_day_from_date(date_str) if date_str else None
        
        click.echo()
        click.secho(f"Image: {image}", bold=True)
        click.echo(f"  Dimensions:  {result.details['width']} × {result.details['height']}")
        click.echo(f"  Pixels:      {result.details['pixels']:,}")
        click.echo(f"  Mode:        {result.details['mode']}")
        click.echo(f"  Format:      {result.details['format']}")
        click.echo(f"  Capacity:    ~{capacity:,} bytes ({capacity // 1024} KB)")
        
        if date_str:
            click.echo(f"  Embed date:  {date_str} ({day_name})")
        
        click.echo()
        
    except Exception as e:
        raise click.ClickException(str(e))


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Entry point."""
    cli()


if __name__ == '__main__':
    main()
