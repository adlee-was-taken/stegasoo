#!/usr/bin/env python3
"""
Stegasoo CLI - Command-line interface for steganography operations (v4.0.0).

CHANGES in v4.0.0:
- Added channel key support for deployment/group isolation
- Messages encoded with a channel key can only be decoded with the same key
- New `channel` command group for key management

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
    stegasoo channel [SUBCOMMAND]
"""

import sys
from pathlib import Path

import click

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

from stegasoo import (
    DecryptionError,
    ExtractionError,
    # Models
    FilePayload,
    # Exceptions
    StegasooError,
    # Utilities
    __version__,
    clear_channel_key,
    compare_modes,
    decode,
    # Core operations
    encode,
    export_rsa_key_pem,
    # Channel key functions (v4.0.0)
    generate_channel_key,
    # Credential generation
    generate_credentials,
    get_channel_status,
    # Validation
    get_image_info,
    has_channel_key,
    has_dct_support,
    load_rsa_key,
    set_channel_key,
    validate_channel_key,
    will_fit_by_mode,
)

# Import constants - try main module first, then constants submodule
try:
    from stegasoo import (  # noqa: F401
        EMBED_MODE_AUTO,
        EMBED_MODE_DCT,
        EMBED_MODE_LSB,
    )
except ImportError:
    pass

# Import constants that may not be in main __init__
try:
    from stegasoo.constants import (
        DEFAULT_PASSPHRASE_WORDS,
        DEFAULT_PIN_LENGTH,
        MAX_PIN_LENGTH,
        MIN_PIN_LENGTH,
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
    from stegasoo.qr_utils import (  # noqa: F401
        can_fit_in_qr,
        extract_key_from_qr_file,
        generate_qr_code,
        has_qr_read,
        has_qr_write,
        needs_compression,
    )
    HAS_QR = True
except ImportError:
    HAS_QR = False

    def has_qr_read() -> bool:
        return False

    def has_qr_write() -> bool:
        return False


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
    - Channel key (deployment/group isolation) [v4.0.0]

    \b
    Version 4.0.0 Changes:
    - Channel key support for group/deployment isolation
    - Messages encoded with a channel key require the same key to decode
    - New `stegasoo channel` command for key management

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
# CHANNEL KEY HELPERS
# ============================================================================

def resolve_channel_key_option(channel: str | None, channel_file: str | None,
                                no_channel: bool) -> str | None:
    """
    Resolve channel key from CLI options.

    Returns:
        None: Use server-configured key (auto mode)
        "": Public mode (no channel key)
        str: Explicit channel key
    """
    if no_channel:
        return ""  # Public mode

    if channel_file:
        # Load from file
        path = Path(channel_file)
        if not path.exists():
            raise click.ClickException(f"Channel key file not found: {channel_file}")
        key = path.read_text().strip()
        if not validate_channel_key(key):
            raise click.ClickException(f"Invalid channel key format in file: {channel_file}")
        return key

    if channel:
        if channel.lower() == 'auto':
            return None  # Use server config
        # Explicit key provided
        if not validate_channel_key(channel):
            raise click.ClickException(
                "Invalid channel key format. Expected: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX\n"
                "Generate a new key with: stegasoo channel generate"
            )
        return channel

    # Default: use server-configured key (auto mode)
    return None


def format_channel_status_line(quiet: bool = False) -> str | None:
    """Get a one-line status for channel key configuration."""
    if quiet:
        return None

    status = get_channel_status()
    if status['mode'] == 'public':
        return None

    return f"Channel: {status['fingerprint']} ({status['source']})"


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
        click.secho("  STEGASOO CREDENTIALS (v4.0.0)", fg='cyan', bold=True)
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
        click.secho("    + photo entropy:    80-256 bits", dim=True)
        click.echo()

        # Show channel key status
        if has_channel_key():
            status = get_channel_status()
            click.secho("─── CHANNEL KEY ───", fg='magenta')
            click.echo("    Status: Private mode")
            click.echo(f"    Fingerprint: {status['fingerprint']}")
            click.secho(f"    (configured via {status['source']})", dim=True)
            click.echo()

        click.secho("✓ v4.0.0: Use this passphrase anytime - no date needed!", fg='cyan')
        click.echo()

    except Exception as e:
        raise click.ClickException(str(e))


# ============================================================================
# CHANNEL COMMAND GROUP (v4.0.0)
# ============================================================================

@cli.group()
def channel():
    """
    Manage channel keys for deployment/group isolation.

    Channel keys allow different deployments or groups to use Stegasoo
    without being able to read each other's messages, even with identical
    credentials.

    \b
    Key Storage (checked in order):
    1. Environment variable: STEGASOO_CHANNEL_KEY
    2. Project config: ./config/channel.key
    3. User config: ~/.stegasoo/channel.key

    \b
    Subcommands:
        generate  Create a new channel key
        show      Display current channel key status
        set       Save a channel key to config file
        clear     Remove channel key from config

    \b
    Examples:
        stegasoo channel generate
        stegasoo channel show
        stegasoo channel set XXXX-XXXX-...
        stegasoo channel clear
    """
    pass


@channel.command('generate')
@click.option('--save', '-s', is_flag=True, help='Save to user config (~/.stegasoo/channel.key)')
@click.option('--save-project', is_flag=True, help='Save to project config (./config/channel.key)')
@click.option('--env', '-e', is_flag=True, help='Output as environment variable export')
@click.option('--quiet', '-q', is_flag=True, help='Output only the key')
def channel_generate(save, save_project, env, quiet):
    """
    Generate a new channel key.

    Creates a cryptographically secure 256-bit channel key in the format:
    XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX

    \b
    Examples:
        # Just display a new key
        stegasoo channel generate

        # Save to user config
        stegasoo channel generate --save

        # Output for .env file
        stegasoo channel generate --env >> .env

        # For scripts
        KEY=$(stegasoo channel generate -q)
    """
    key = generate_channel_key()

    if save and save_project:
        raise click.UsageError("Cannot use both --save and --save-project")

    if save:
        set_channel_key(key, location='user')
        if not quiet:
            click.secho("✓ Channel key saved to ~/.stegasoo/channel.key", fg='green')
            click.echo()

    if save_project:
        set_channel_key(key, location='project')
        if not quiet:
            click.secho("✓ Channel key saved to ./config/channel.key", fg='green')
            click.echo()

    if env:
        click.echo(f"STEGASOO_CHANNEL_KEY={key}")
    elif quiet:
        click.echo(key)
    else:
        click.echo()
        click.secho("─── NEW CHANNEL KEY ───", fg='cyan', bold=True)
        click.echo()
        click.secho(f"    {key}", fg='bright_yellow', bold=True)
        click.echo()

        fingerprint = f"{key[:4]}-••••-••••-••••-••••-••••-••••-{key[-4:]}"
        click.echo(f"    Fingerprint: {fingerprint}")
        click.echo()

        click.secho("Usage:", dim=True)
        click.echo("    # Environment variable (recommended)")
        click.echo(f"    export STEGASOO_CHANNEL_KEY={key}")
        click.echo()
        click.echo("    # Or save to config")
        click.echo("    stegasoo channel generate --save")
        click.echo()
        click.echo("    # Or add to .env file")
        click.echo("    stegasoo channel generate --env >> .env")
        click.echo()


@channel.command('show')
@click.option('--reveal', '-r', is_flag=True, help='Show full key (not just fingerprint)')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def channel_show(reveal, as_json):
    """
    Display current channel key status.

    Shows whether a channel key is configured and where it comes from.
    By default shows only fingerprint; use --reveal to see full key.

    \b
    Examples:
        stegasoo channel show
        stegasoo channel show --reveal
        stegasoo channel show --json
    """
    status = get_channel_status()

    if as_json:
        import json
        output = {
            'mode': status['mode'],
            'configured': status['configured'],
            'fingerprint': status.get('fingerprint'),
            'source': status.get('source'),
        }
        if reveal and status['configured']:
            output['key'] = status.get('key')
        click.echo(json.dumps(output, indent=2))
        return

    click.echo()
    click.secho("─── CHANNEL KEY STATUS ───", fg='cyan', bold=True)
    click.echo()

    if status['mode'] == 'public':
        click.secho("    Mode: PUBLIC", fg='yellow', bold=True)
        click.echo("    No channel key configured.")
        click.echo()
        click.secho("    Messages can be read by any Stegasoo installation", dim=True)
        click.secho("    with matching credentials.", dim=True)
    else:
        click.secho("    Mode: PRIVATE", fg='green', bold=True)
        click.echo(f"    Fingerprint: {status['fingerprint']}")
        click.echo(f"    Source: {status['source']}")

        if reveal:
            click.echo()
            click.secho(f"    Full key: {status['key']}", fg='bright_yellow')

        click.echo()
        click.secho("    Messages require this channel key to decode.", dim=True)

    click.echo()


@channel.command('set')
@click.argument('key', required=False)
@click.option('--file', '-f', 'key_file', type=click.Path(exists=True), help='Read key from file')
@click.option('--project', '-p', is_flag=True, help='Save to project config instead of user config')
def channel_set(key, key_file, project):
    """
    Save a channel key to config file.

    Saves to user config (~/.stegasoo/channel.key) by default,
    or project config (./config/channel.key) with --project.

    \b
    Examples:
        stegasoo channel set XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX
        stegasoo channel set --file channel.key
        stegasoo channel set XXXX-... --project
    """
    if not key and not key_file:
        raise click.UsageError("Must provide KEY argument or --file option")

    if key and key_file:
        raise click.UsageError("Cannot use both KEY argument and --file option")

    if key_file:
        key = Path(key_file).read_text().strip()

    if not validate_channel_key(key):
        raise click.ClickException(
            "Invalid channel key format.\n"
            "Expected: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX\n"
            "Generate a new key with: stegasoo channel generate"
        )

    location = 'project' if project else 'user'
    set_channel_key(key, location=location)

    status = get_channel_status()
    click.secho("✓ Channel key saved", fg='green')
    click.echo(f"  Location: {status['source']}")
    click.echo(f"  Fingerprint: {status['fingerprint']}")


@channel.command('clear')
@click.option('--project', '-p', is_flag=True, help='Clear project config instead of user config')
@click.option('--all', 'clear_all', is_flag=True, help='Clear both user and project configs')
@click.option('--force', '-f', is_flag=True, help='Skip confirmation')
def channel_clear(project, clear_all, force):
    """
    Remove channel key from config.

    Clears user config by default. Use --project for project config,
    or --all to clear both.

    Note: This does not affect environment variables.

    \b
    Examples:
        stegasoo channel clear
        stegasoo channel clear --project
        stegasoo channel clear --all
    """
    if not force:
        if clear_all:
            msg = "Clear channel key from both user and project configs?"
        elif project:
            msg = "Clear channel key from project config (./config/channel.key)?"
        else:
            msg = "Clear channel key from user config (~/.stegasoo/channel.key)?"

        if not click.confirm(msg):
            click.echo("Cancelled.")
            return

    if clear_all:
        clear_channel_key(location='user')
        clear_channel_key(location='project')
        click.secho("✓ Cleared channel key from user and project configs", fg='green')
    elif project:
        clear_channel_key(location='project')
        click.secho("✓ Cleared channel key from project config", fg='green')
    else:
        clear_channel_key(location='user')
        click.secho("✓ Cleared channel key from user config", fg='green')

    # Show current status
    status = get_channel_status()
    if status['configured']:
        click.echo()
        click.secho(f"Note: Channel key still active from {status['source']}", fg='yellow')
        click.echo(f"  Fingerprint: {status['fingerprint']}")
    else:
        click.echo("  Mode is now: PUBLIC")


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
@click.option('--channel', 'channel_key', help='Channel key (or "auto" for server config)')
@click.option('--channel-file', type=click.Path(exists=True), help='Read channel key from file')
@click.option('--no-channel', is_flag=True, help='Force public mode (no channel key)')
@click.option('--output', '-o', type=click.Path(), help='Output file (default: auto-generated)')
@click.option('--mode', 'embed_mode', type=click.Choice(['lsb', 'dct']), default='lsb',
              help='Embedding mode: lsb (default, color) or dct (requires scipy)')
@click.option('--dct-format', 'dct_output_format', type=click.Choice(['png', 'jpeg']), default='png',
              help='DCT output format: png (lossless, default) or jpeg (smaller)')
@click.option('--dct-color', 'dct_color_mode', type=click.Choice(['grayscale', 'color']), default='grayscale',
              help='DCT color mode: grayscale (default) or color (preserves original colors)')
@click.option('--quiet', '-q', is_flag=True, help='Suppress output except errors')
def encode_cmd(ref, carrier, message, message_file, embed_file, passphrase, pin, key, key_qr,
               key_password, channel_key, channel_file, no_channel, output, embed_mode,
               dct_output_format, dct_color_mode, quiet):
    """
    Encode a secret message or file into an image.

    Requires a reference photo, carrier image, and passphrase.
    Must provide either --pin or --key/--key-qr (or both).

    v4.0.0: Channel key support for deployment isolation.
    v3.2.0: No --date parameter needed! Encode and decode anytime.

    \b
    Channel Key Options:
        (no option)       Use server-configured key (auto mode)
        --channel KEY     Use explicit channel key
        --channel-file F  Read channel key from file
        --no-channel      Force public mode (no isolation)

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
    Examples:
        # Text message with PIN (auto channel key)
        stegasoo encode -r photo.jpg -c meme.png -p "apple forest thunder" --pin 123456 -m "secret"

        # Explicit channel key
        stegasoo encode -r photo.jpg -c meme.png -p "words here" --pin 123456 -m "msg" \\
            --channel ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456

        # Public mode (no channel key)
        stegasoo encode -r photo.jpg -c meme.png -p "words" --pin 123456 -m "msg" --no-channel
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

    # Resolve channel key
    try:
        resolved_channel_key = resolve_channel_key_option(channel_key, channel_file, no_channel)
    except click.ClickException:
        raise

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
                suggestion = "\n  Tip: Payload would fit in LSB mode (--mode lsb)"

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

            # Show channel status
            channel_status = format_channel_status_line()
            if resolved_channel_key == "":
                click.echo("Channel: PUBLIC (no isolation)")
            elif resolved_channel_key:
                fingerprint = f"{resolved_channel_key[:4]}-••••-...-{resolved_channel_key[-4:]}"
                click.echo(f"Channel: {fingerprint} (explicit)")
            elif channel_status:
                click.echo(channel_status)

        # v4.0.0: Include channel_key parameter
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
            channel_key=resolved_channel_key,
        )

        # Determine output path
        if output:
            out_path = Path(output)
        else:
            out_path = Path(result.filename)

        # Write output
        out_path.write_bytes(result.stego_image)

        if not quiet:
            click.secho("✓ Encoded successfully!", fg='green')
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
@click.option('--channel', 'channel_key', help='Channel key (or "auto" for server config)')
@click.option('--channel-file', type=click.Path(exists=True), help='Read channel key from file')
@click.option('--no-channel', is_flag=True, help='Force public mode (no channel key)')
@click.option('--output', '-o', type=click.Path(), help='Save decoded content to file')
@click.option('--mode', 'embed_mode', type=click.Choice(['auto', 'lsb', 'dct']), default='auto',
              help='Extraction mode: auto (default), lsb, or dct')
@click.option('--quiet', '-q', is_flag=True, help='Output only the content (for text) or suppress messages (for files)')
@click.option('--force', is_flag=True, help='Overwrite existing output file')
def decode_cmd(ref, stego, passphrase, pin, key, key_qr, key_password, channel_key, channel_file,
               no_channel, output, embed_mode, quiet, force):
    """
    Decode a secret message or file from a stego image.

    Must use the same credentials that were used for encoding.
    Automatically detects whether content is text or a file.

    v4.0.0: Channel key support - must match what was used for encoding.
    v3.2.0: No --date parameter needed! Just use your passphrase.

    \b
    Channel Key Options:
        (no option)       Use server-configured key (auto mode)
        --channel KEY     Use explicit channel key
        --channel-file F  Read channel key from file
        --no-channel      Force public mode (for images encoded without channel key)

    \b
    Examples:
        # Decode with auto channel key
        stegasoo decode -r photo.jpg -s stego.png -p "apple forest thunder" --pin 123456

        # Decode with explicit channel key
        stegasoo decode -r photo.jpg -s stego.png -p "words" --pin 123456 \\
            --channel ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456

        # Decode public image (no channel key was used)
        stegasoo decode -r photo.jpg -s stego.png -p "words" --pin 123456 --no-channel
    """
    # Check DCT mode availability
    if embed_mode == 'dct' and not has_dct_support():
        raise click.ClickException(
            "DCT mode requires scipy. Install with: pip install scipy"
        )

    # Resolve channel key
    try:
        resolved_channel_key = resolve_channel_key_option(channel_key, channel_file, no_channel)
    except click.ClickException:
        raise

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

        # v4.0.0: Include channel_key parameter
        result = decode(
            stego_image=stego_image,
            reference_photo=ref_photo,
            passphrase=passphrase,
            pin=pin or "",
            rsa_key_data=rsa_key_data,
            rsa_password=effective_key_password,
            embed_mode=embed_mode,
            channel_key=resolved_channel_key,
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
        # Provide helpful hints for channel key mismatches
        error_msg = str(e)
        if 'channel key' in error_msg.lower():
            raise click.ClickException(error_msg)
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
@click.option('--channel', 'channel_key', help='Channel key (or "auto" for server config)')
@click.option('--channel-file', type=click.Path(exists=True), help='Read channel key from file')
@click.option('--no-channel', is_flag=True, help='Force public mode (no channel key)')
@click.option('--mode', 'embed_mode', type=click.Choice(['auto', 'lsb', 'dct']), default='auto',
              help='Extraction mode: auto (default), lsb, or dct')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def verify(ref, stego, passphrase, pin, key, key_qr, key_password, channel_key, channel_file,
           no_channel, embed_mode, as_json):
    """
    Verify that a stego image can be decoded without extracting the message.

    Quick check to validate credentials are correct and data is intact.
    Does NOT output the actual message content.

    v4.0.0: Also verifies channel key matches.

    \b
    Examples:
        stegasoo verify -r photo.jpg -s stego.png -p "my passphrase" --pin 123456

        stegasoo verify -r photo.jpg -s stego.png -p "words here" -k mykey.pem --json

        stegasoo verify -r photo.jpg -s stego.png -p "test phrase" --pin 123456 --no-channel
    """
    # Check DCT mode availability
    if embed_mode == 'dct' and not has_dct_support():
        raise click.ClickException(
            "DCT mode requires scipy. Install with: pip install scipy"
        )

    # Resolve channel key
    try:
        resolved_channel_key = resolve_channel_key_option(channel_key, channel_file, no_channel)
    except click.ClickException:
        raise

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

        # Attempt to decode (v4.0.0: with channel_key)
        result = decode(
            stego_image=stego_image,
            reference_photo=ref_photo,
            passphrase=passphrase,
            pin=pin or "",
            rsa_key_data=rsa_key_data,
            rsa_password=effective_key_password,
            embed_mode=embed_mode,
            channel_key=resolved_channel_key,
        )

        # Calculate payload size
        if result.is_file:
            payload_size = len(result.file_data)
            content_type = result.mime_type or 'file'
        else:
            payload_size = len(result.message.encode('utf-8'))
            content_type = 'text'

        if as_json:
            import json
            output = {
                'valid': True,
                'content_type': content_type,
                'payload_size': payload_size,
                'filename': result.filename if result.is_file else None,
            }
            click.echo(json.dumps(output, indent=2))
        else:
            click.secho("✓ Verification successful!", fg='green')
            click.echo(f"  Content type: {content_type}")
            click.echo(f"  Payload size: {payload_size:,} bytes")
            if result.is_file and result.filename:
                click.echo(f"  Filename: {result.filename}")

    except (DecryptionError, ExtractionError) as e:
        if as_json:
            import json
            output = {
                'valid': False,
                'error': str(e),
            }
            click.echo(json.dumps(output, indent=2))
            sys.exit(1)
        else:
            raise click.ClickException(f"Verification failed: {e}")
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
    Show information about an image file.

    Displays dimensions, format, capacity estimates for different modes,
    and whether the image appears suitable as a carrier.

    \b
    Examples:
        stegasoo info photo.png
        stegasoo info carrier.jpg --json
    """
    try:
        image_data = Path(image).read_bytes()
        img_info = get_image_info(image_data)

        if as_json:
            import json
            click.echo(json.dumps(img_info, indent=2))
            return

        click.echo()
        click.secho(f"=== Image Info: {image} ===", fg='cyan', bold=True)
        click.echo(f"  Format:     {img_info.get('format', 'Unknown')}")
        click.echo(f"  Dimensions: {img_info.get('width', '?')} × {img_info.get('height', '?')}")
        click.echo(f"  Mode:       {img_info.get('mode', '?')}")
        click.echo(f"  Size:       {len(image_data):,} bytes")

        if 'lsb_capacity' in img_info:
            click.echo()
            click.secho("  Capacity Estimates:", fg='green')
            click.echo(f"    LSB mode: {img_info['lsb_capacity']:,} bytes")
            if 'dct_capacity' in img_info:
                click.echo(f"    DCT mode: {img_info['dct_capacity']:,} bytes")

        click.echo()

    except Exception as e:
        raise click.ClickException(str(e))


# ============================================================================
# COMPARE COMMAND
# ============================================================================

@cli.command()
@click.argument('image', type=click.Path(exists=True))
@click.option('--payload', '-p', type=click.Path(exists=True), help='Check if this file would fit')
@click.option('--size', '-s', type=int, help='Check if this many bytes would fit')
@click.option('--json', 'as_json', is_flag=True, help='Output as JSON')
def compare(image, payload, size, as_json):
    """
    Compare embedding mode capacities for an image.

    Shows LSB vs DCT capacity and helps choose the right mode.
    Optionally checks if a specific payload would fit.

    \b
    Examples:
        stegasoo compare carrier.png
        stegasoo compare carrier.png --payload secret.pdf
        stegasoo compare carrier.png --size 50000
    """
    try:
        image_data = Path(image).read_bytes()

        # Get payload size if provided
        payload_size = None
        if payload:
            payload_size = len(Path(payload).read_bytes())
        elif size:
            payload_size = size

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
        click.echo("  │ Status:    ✓ Available")
        click.echo("  │")

        # DCT mode
        click.secho("  ├─── DCT Mode ───", fg='blue')
        click.echo(f"  │ Capacity:  {comparison['dct']['capacity_bytes']:,} bytes ({comparison['dct']['capacity_kb']:.1f} KB)")
        click.echo(f"  │ Ratio:     {comparison['dct']['ratio_vs_lsb']:.1f}% of LSB capacity")
        if comparison['dct']['available']:
            click.echo("  │ Status:    ✓ Available")
            click.echo("  │ Formats:   PNG (lossless), JPEG (smaller)")
            click.echo("  │ Colors:    Grayscale (default), Color")
        else:
            click.secho("  │ Status:    ✗ Requires scipy (pip install scipy)", fg='yellow')
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

            click.echo("  │ LSB mode:  ", nl=False)
            click.secho(f"{lsb_icon} {'Fits' if fits_lsb else 'Too large'}", fg=lsb_color)
            click.echo("  │ DCT mode:  ", nl=False)
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
    click.secho("=== Stegasoo Embedding Modes (v4.0.0) ===", fg='cyan', bold=True)
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

    # Channel Key Status (v4.0.0)
    click.secho("  Channel Key (v4.0.0)", fg='cyan', bold=True)
    status = get_channel_status()
    if status['mode'] == 'public':
        click.echo("    Status:      PUBLIC (no key configured)")
        click.echo("    Effect:      Messages readable by any installation")
    else:
        click.echo("    Status:      PRIVATE")
        click.echo(f"    Fingerprint: {status['fingerprint']}")
        click.echo(f"    Source:      {status['source']}")
        click.echo("    Effect:      Messages isolated to this channel")
    click.echo()
    click.echo("    CLI flags:")
    click.echo("      --channel KEY        Use explicit channel key")
    click.echo("      --channel-file F     Read key from file")
    click.echo("      --no-channel         Force public mode")
    click.echo()

    # v4.0.0 Changes
    click.secho("  v4.0.0 Changes:", fg='cyan', bold=True)
    click.echo("    ✓ Channel key support for deployment isolation")
    click.echo("    ✓ New `stegasoo channel` command group")
    click.echo("    ✓ Messages encoded with channel key require same key to decode")
    click.echo()

    # Examples
    click.secho("  Examples:", dim=True)
    click.echo("    # Generate channel key")
    click.echo("    stegasoo channel generate --save")
    click.echo()
    click.echo("    # Encode with channel isolation")
    click.echo("    stegasoo encode ... --channel XXXX-XXXX-...")
    click.echo()
    click.echo("    # Decode public message (no channel key)")
    click.echo("    stegasoo decode ... --no-channel")
    click.echo()


# ============================================================================
# MAIN
# ============================================================================

def main():
    """Entry point."""
    cli()


if __name__ == '__main__':
    main()
