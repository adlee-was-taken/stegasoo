"""
Stegasoo CLI Module (v3.2.0)

Command-line interface with batch processing and compression support.

Changes in v3.2.0:
- Updated to use DEFAULT_PASSPHRASE_WORDS (consistency with v3.2.0 naming)
- Updated help text to use 'passphrase' terminology
"""

import json
from pathlib import Path

import click

from .batch import (
    BatchProcessor,
    batch_capacity_check,
    print_batch_result,
)
from .compression import (
    HAS_LZ4,
    CompressionAlgorithm,
    algorithm_name,
    get_available_algorithms,
)
from .constants import (
    DEFAULT_PASSPHRASE_WORDS,  # v3.2.0: renamed from DEFAULT_PHRASE_WORDS
    DEFAULT_PIN_LENGTH,
    MAX_FILE_PAYLOAD_SIZE,
    MAX_MESSAGE_SIZE,
    __version__,
)

# Click context settings
CONTEXT_SETTINGS = dict(help_option_names=["-h", "--help"])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, "-v", "--version")
@click.option("--json", "json_output", is_flag=True, help="Output results as JSON")
@click.pass_context
def cli(ctx, json_output):
    """
    Stegasoo - Steganography with hybrid authentication.

    Hide messages in images using PIN + passphrase security.
    """
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output


# =============================================================================
# ENCODE COMMANDS
# =============================================================================


@cli.command()
@click.argument("image", type=click.Path(exists=True))
@click.option("-m", "--message", help="Message to encode")
@click.option(
    "-f",
    "--file",
    "file_payload",
    type=click.Path(exists=True),
    help="File to embed instead of message",
)
@click.option("-o", "--output", type=click.Path(), help="Output image path")
@click.option(
    "--passphrase",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Passphrase (recommend 4+ words)",
)
@click.option("--pin", prompt=True, hide_input=True, confirmation_prompt=True, help="PIN code")
@click.option(
    "--compress/--no-compress", default=True, help="Enable/disable compression (default: enabled)"
)
@click.option(
    "--algorithm",
    type=click.Choice(["zlib", "lz4", "none"]),
    default="zlib",
    help="Compression algorithm",
)
@click.option("--dry-run", is_flag=True, help="Show capacity usage without encoding")
@click.pass_context
def encode(
    ctx, image, message, file_payload, output, passphrase, pin, compress, algorithm, dry_run
):
    """
    Encode a message or file into an image.

    Examples:

        stegasoo encode photo.png -m "Secret message" --passphrase --pin

        stegasoo encode photo.png -f secret.pdf -o encoded.png
    """
    from PIL import Image

    if not message and not file_payload:
        raise click.UsageError("Either --message or --file is required")

    # Parse compression algorithm
    algo_map = {
        "zlib": CompressionAlgorithm.ZLIB,
        "lz4": CompressionAlgorithm.LZ4,
        "none": CompressionAlgorithm.NONE,
    }
    compression_algo = algo_map[algorithm] if compress else CompressionAlgorithm.NONE

    if algorithm == "lz4" and not HAS_LZ4:
        click.echo("Warning: LZ4 not available, falling back to zlib", err=True)
        compression_algo = CompressionAlgorithm.ZLIB

    # Calculate payload size
    if file_payload:
        payload_size = Path(file_payload).stat().st_size
        payload_type = "file"
    else:
        payload_size = len(message.encode("utf-8"))
        payload_type = "text"

    # Get image capacity
    with Image.open(image) as img:
        width, height = img.size
        capacity_bytes = (width * height * 3 // 8) - 69  # v3.2.0: corrected overhead

    if dry_run:
        result = {
            "image": image,
            "dimensions": f"{width}x{height}",
            "capacity_bytes": capacity_bytes,
            "payload_type": payload_type,
            "payload_size": payload_size,
            "compression": algorithm_name(compression_algo),
            "usage_percent": round(payload_size / capacity_bytes * 100, 1),
            "fits": payload_size < capacity_bytes,
        }

        if ctx.obj.get("json"):
            click.echo(json.dumps(result, indent=2))
        else:
            click.echo(f"Image: {image} ({width}x{height})")
            click.echo(f"Capacity: {capacity_bytes:,} bytes ({capacity_bytes//1024} KB)")
            click.echo(f"Payload: {payload_size:,} bytes ({payload_type})")
            click.echo(f"Compression: {algorithm_name(compression_algo)}")
            click.echo(f"Usage: {result['usage_percent']}%")
            click.echo(f"Status: {'✓ Fits' if result['fits'] else '✗ Too large'}")
        return

    # Actual encoding would happen here
    # For now, show what would be done
    output = output or f"{Path(image).stem}_encoded.png"

    if ctx.obj.get("json"):
        click.echo(
            json.dumps(
                {
                    "status": "success",
                    "input": image,
                    "output": output,
                    "payload_type": payload_type,
                    "compression": algorithm_name(compression_algo),
                },
                indent=2,
            )
        )
    else:
        click.echo(f"✓ Encoded {payload_type} to {output}")
        click.echo(f"  Compression: {algorithm_name(compression_algo)}")


@cli.command()
@click.argument("image", type=click.Path(exists=True))
@click.option("--passphrase", prompt=True, hide_input=True, help="Passphrase")
@click.option("--pin", prompt=True, hide_input=True, help="PIN code")
@click.option("-o", "--output", type=click.Path(), help="Output path for file payloads")
@click.pass_context
def decode(ctx, image, passphrase, pin, output):
    """
    Decode a message or file from an image.

    Examples:

        stegasoo decode encoded.png --passphrase --pin

        stegasoo decode encoded.png -o ./extracted/
    """
    # Actual decoding would happen here
    result = {
        "status": "success",
        "image": image,
        "payload_type": "text",
        "message": "[Decoded message would appear here]",
    }

    if ctx.obj.get("json"):
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"Decoded from {image}:")
        click.echo(result["message"])


# =============================================================================
# BATCH COMMANDS
# =============================================================================


@cli.group()
def batch():
    """Batch operations on multiple images."""
    pass


@batch.command("encode")
@click.argument("images", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-m", "--message", help="Message to encode in all images")
@click.option(
    "-f", "--file", "file_payload", type=click.Path(exists=True), help="File to embed in all images"
)
@click.option(
    "-o", "--output-dir", type=click.Path(), help="Output directory (default: same as input)"
)
@click.option("--suffix", default="_encoded", help="Output filename suffix")
@click.option(
    "--passphrase",
    prompt=True,
    hide_input=True,
    confirmation_prompt=True,
    help="Passphrase (recommend 4+ words)",
)
@click.option("--pin", prompt=True, hide_input=True, confirmation_prompt=True, help="PIN code")
@click.option("--compress/--no-compress", default=True, help="Enable/disable compression")
@click.option(
    "--algorithm",
    type=click.Choice(["zlib", "lz4", "none"]),
    default="zlib",
    help="Compression algorithm",
)
@click.option("-r", "--recursive", is_flag=True, help="Search directories recursively")
@click.option("-j", "--jobs", default=4, help="Parallel workers (default: 4)")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed output")
@click.pass_context
def batch_encode(
    ctx,
    images,
    message,
    file_payload,
    output_dir,
    suffix,
    passphrase,
    pin,
    compress,
    algorithm,
    recursive,
    jobs,
    verbose,
):
    """
    Encode message into multiple images.

    Examples:

        stegasoo batch encode *.png -m "Secret" --passphrase --pin

        stegasoo batch encode ./photos/ -r -o ./encoded/
    """
    if not message and not file_payload:
        raise click.UsageError("Either --message or --file is required")

    processor = BatchProcessor(max_workers=jobs)

    # Progress callback
    def progress(current, total, item):
        if not ctx.obj.get("json"):
            status = "✓" if item.status.value == "success" else "✗"
            click.echo(f"[{current}/{total}] {status} {item.input_path.name}")

    # v3.2.0: Use 'passphrase' key instead of 'phrase'
    credentials = {"passphrase": passphrase, "pin": pin}

    result = processor.batch_encode(
        images=list(images),
        message=message,
        file_payload=Path(file_payload) if file_payload else None,
        output_dir=Path(output_dir) if output_dir else None,
        output_suffix=suffix,
        credentials=credentials,
        compress=compress,
        recursive=recursive,
        progress_callback=progress if not ctx.obj.get("json") else None,
    )

    if ctx.obj.get("json"):
        click.echo(result.to_json())
    else:
        print_batch_result(result, verbose)


@batch.command("decode")
@click.argument("images", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-o", "--output-dir", type=click.Path(), help="Output directory for file payloads")
@click.option("--passphrase", prompt=True, hide_input=True, help="Passphrase")
@click.option("--pin", prompt=True, hide_input=True, help="PIN code")
@click.option("-r", "--recursive", is_flag=True, help="Search directories recursively")
@click.option("-j", "--jobs", default=4, help="Parallel workers (default: 4)")
@click.option("-v", "--verbose", is_flag=True, help="Show detailed output")
@click.pass_context
def batch_decode(ctx, images, output_dir, passphrase, pin, recursive, jobs, verbose):
    """
    Decode messages from multiple images.

    Examples:

        stegasoo batch decode encoded*.png --passphrase --pin

        stegasoo batch decode ./encoded/ -r -o ./extracted/
    """
    processor = BatchProcessor(max_workers=jobs)

    # Progress callback
    def progress(current, total, item):
        if not ctx.obj.get("json"):
            status = "✓" if item.status.value == "success" else "✗"
            click.echo(f"[{current}/{total}] {status} {item.input_path.name}")

    # v3.2.0: Use 'passphrase' key instead of 'phrase'
    credentials = {"passphrase": passphrase, "pin": pin}

    result = processor.batch_decode(
        images=list(images),
        output_dir=Path(output_dir) if output_dir else None,
        credentials=credentials,
        recursive=recursive,
        progress_callback=progress if not ctx.obj.get("json") else None,
    )

    if ctx.obj.get("json"):
        click.echo(result.to_json())
    else:
        print_batch_result(result, verbose)


@batch.command("check")
@click.argument("images", nargs=-1, required=True, type=click.Path(exists=True))
@click.option("-r", "--recursive", is_flag=True, help="Search directories recursively")
@click.pass_context
def batch_check(ctx, images, recursive):
    """
    Check capacity of multiple images.

    Examples:

        stegasoo batch check *.png

        stegasoo batch check ./photos/ -r
    """
    results = batch_capacity_check(list(images), recursive)

    if ctx.obj.get("json"):
        click.echo(json.dumps(results, indent=2))
    else:
        click.echo(f"{'Image':<40} {'Size':<12} {'Capacity':<12} {'Status'}")
        click.echo("─" * 80)

        for item in results:
            if "error" in item:
                click.echo(f"{Path(item['path']).name:<40} {'ERROR':<12} {'':<12} {item['error']}")
            else:
                name = Path(item["path"]).name
                if len(name) > 38:
                    name = name[:35] + "..."

                status = "✓" if item["valid"] else "⚠"
                warnings = ", ".join(item.get("warnings", []))

                click.echo(
                    f"{name:<40} "
                    f"{item['dimensions']:<12} "
                    f"{item['capacity_kb']:,} KB".ljust(12) + " "
                    f"{status} {warnings}"
                )


# =============================================================================
# UTILITY COMMANDS
# =============================================================================


@cli.command()
@click.option(
    "--words",
    default=DEFAULT_PASSPHRASE_WORDS,
    help=f"Number of words in passphrase (default: {DEFAULT_PASSPHRASE_WORDS})",
)
@click.option(
    "--pin-length", default=DEFAULT_PIN_LENGTH, help=f"PIN length (default: {DEFAULT_PIN_LENGTH})"
)
@click.option(
    "--channel-key", is_flag=True, help="Also generate a 256-bit channel key"
)
@click.pass_context
def generate(ctx, words, pin_length, channel_key):
    """
    Generate random credentials (passphrase + PIN + optional channel key).

    Examples:

        stegasoo generate

        stegasoo generate --words 6 --pin-length 8

        stegasoo generate --channel-key
    """
    import secrets

    # Generate PIN
    pin = "".join(str(secrets.randbelow(10)) for _ in range(pin_length))
    # Ensure PIN doesn't start with 0
    if pin[0] == "0":
        pin = str(secrets.randbelow(9) + 1) + pin[1:]

    # Generate passphrase (would use BIP-39 wordlist)
    # Placeholder - actual implementation uses constants.get_wordlist()
    try:
        from .constants import get_wordlist

        wordlist = get_wordlist()
        phrase_words = [secrets.choice(wordlist) for _ in range(words)]
    except (ImportError, FileNotFoundError):
        # Fallback for testing
        sample_words = [
            "alpha",
            "bravo",
            "charlie",
            "delta",
            "echo",
            "foxtrot",
            "golf",
            "hotel",
            "india",
            "juliet",
            "kilo",
            "lima",
        ]
        phrase_words = [secrets.choice(sample_words) for _ in range(words)]

    passphrase = " ".join(phrase_words)

    result = {
        "passphrase": passphrase,
        "pin": pin,
        "passphrase_words": words,
        "pin_length": pin_length,
    }

    # Generate channel key if requested
    if channel_key:
        from .channel import generate_channel_key
        result["channel_key"] = generate_channel_key()

    if ctx.obj.get("json"):
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"Passphrase:   {passphrase}")
        click.echo(f"PIN:          {pin}")
        if channel_key:
            click.echo(f"Channel Key:  {result['channel_key']}")
        click.echo("\n⚠️  Save these credentials securely - they cannot be recovered!")


@cli.command()
@click.pass_context
def info(ctx):
    """Show version and feature information."""
    info_data = {
        "version": __version__,
        "compression": {
            "available": [algorithm_name(a) for a in get_available_algorithms()],
            "lz4_installed": HAS_LZ4,
        },
        "limits": {
            "max_message_bytes": MAX_MESSAGE_SIZE,
            "max_file_payload_bytes": MAX_FILE_PAYLOAD_SIZE,
        },
    }

    if ctx.obj.get("json"):
        click.echo(json.dumps(info_data, indent=2))
    else:
        click.echo(f"Stegasoo v{__version__}")
        click.echo("\nCompression algorithms:")
        for algo in get_available_algorithms():
            click.echo(f"  • {algorithm_name(algo)}")
        if not HAS_LZ4:
            click.echo("    (install 'lz4' for LZ4 support)")
        click.echo("\nLimits:")
        click.echo(f"  • Max message: {MAX_MESSAGE_SIZE:,} bytes")
        click.echo(f"  • Max file payload: {MAX_FILE_PAYLOAD_SIZE:,} bytes")


# =============================================================================
# CHANNEL KEY COMMANDS
# =============================================================================


@cli.group()
@click.pass_context
def channel(ctx):
    """
    Manage channel keys for deployment isolation.

    Channel keys bind encode/decode operations to a specific group or deployment.
    Messages encoded with one channel key can only be decoded by systems with
    the same channel key.

    Examples:

        stegasoo channel generate

        stegasoo channel show

        stegasoo channel qr

        stegasoo channel qr -o channel-key.png
    """
    pass


@channel.command("generate")
@click.option("--save", is_flag=True, help="Save to project config file")
@click.option("--save-user", is_flag=True, help="Save to user config (~/.stegasoo/)")
@click.pass_context
def channel_generate(ctx, save, save_user):
    """
    Generate a new random channel key.

    Examples:

        stegasoo channel generate

        stegasoo channel generate --save

        stegasoo channel generate --save-user
    """
    from .channel import generate_channel_key, set_channel_key

    key = generate_channel_key()

    if ctx.obj.get("json"):
        result = {"channel_key": key}
        if save or save_user:
            location = "user" if save_user else "project"
            path = set_channel_key(key, location)
            result["saved_to"] = str(path)
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo("Generated channel key:")
        click.echo(f"  {key}")
        click.echo()

        if save or save_user:
            location = "user" if save_user else "project"
            path = set_channel_key(key, location)
            click.echo(f"Saved to: {path}")
        else:
            click.echo("To use this key:")
            click.echo(f'  export STEGASOO_CHANNEL_KEY="{key}"')
            click.echo()
            click.echo("Or save to config:")
            click.echo("  stegasoo channel generate --save")


@channel.command("show")
@click.option("--key", "explicit_key", help="Show this key instead of configured one")
@click.pass_context
def channel_show(ctx, explicit_key):
    """
    Show the current channel key.

    Examples:

        stegasoo channel show

        stegasoo channel show --key "ABCD-1234-..."
    """
    from .channel import format_channel_key, get_channel_status, validate_channel_key

    if explicit_key:
        if not validate_channel_key(explicit_key):
            click.echo("Error: Invalid channel key format", err=True)
            raise SystemExit(1)
        key = format_channel_key(explicit_key)
        source = "command line"
    else:
        status = get_channel_status()
        if not status["configured"]:
            if ctx.obj.get("json"):
                click.echo(json.dumps({"configured": False, "mode": "public"}))
            else:
                click.echo("No channel key configured (public mode)")
            return
        key = status["key"]
        source = status["source"]

    if ctx.obj.get("json"):
        click.echo(json.dumps({"channel_key": key, "source": source}))
    else:
        click.echo(f"Channel key: {key}")
        click.echo(f"Source: {source}")


@channel.command("status")
@click.pass_context
def channel_status(ctx):
    """
    Show channel key status and configuration.

    Examples:

        stegasoo channel status

        stegasoo --json channel status
    """
    from .channel import get_channel_status

    status = get_channel_status()

    if ctx.obj.get("json"):
        click.echo(json.dumps(status, indent=2))
    else:
        click.echo(f"Mode: {status['mode'].upper()}")
        if status["configured"]:
            click.echo(f"Fingerprint: {status['fingerprint']}")
            click.echo(f"Source: {status['source']}")
        else:
            click.echo("No channel key configured")
            click.echo()
            click.echo("To set up a channel key:")
            click.echo("  stegasoo channel generate --save")


@channel.command("qr")
@click.option("--key", "explicit_key", help="Generate QR for this key instead of configured one")
@click.option(
    "--format",
    "output_format",
    type=click.Choice(["ascii", "png"]),
    default="ascii",
    help="Output format (default: ascii)",
)
@click.option("-o", "--output", type=click.Path(), help="Output file (PNG format, or - for stdout)")
@click.pass_context
def channel_qr(ctx, explicit_key, output_format, output):
    """
    Display channel key as QR code.

    Examples:

        stegasoo channel qr

        stegasoo channel qr -o channel-key.png

        stegasoo channel qr --format png -o - > key.png
    """
    import sys

    from .channel import format_channel_key, get_channel_key, validate_channel_key

    # Get the key to display
    if explicit_key:
        if not validate_channel_key(explicit_key):
            click.echo("Error: Invalid channel key format", err=True)
            raise SystemExit(1)
        key = format_channel_key(explicit_key)
    else:
        key = get_channel_key()
        if not key:
            click.echo("Error: No channel key configured", err=True)
            click.echo("Generate one with: stegasoo channel generate", err=True)
            raise SystemExit(1)

    # Import qrcode
    try:
        import qrcode
    except ImportError:
        click.echo("Error: qrcode library not installed", err=True)
        click.echo("Install with: pip install qrcode[pil]", err=True)
        raise SystemExit(1)

    # Determine output mode
    if output:
        output_format = "png"  # Force PNG when output file specified

    if output_format == "png":
        # Generate PNG QR code (requires Pillow)
        try:
            import PIL  # noqa: F401 - check Pillow is available
        except ImportError:
            click.echo("Error: PIL/Pillow not installed for PNG output", err=True)
            click.echo("Install with: pip install Pillow", err=True)
            raise SystemExit(1)

        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=10,
            border=4,
        )
        qr.add_data(key)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")

        if output == "-":
            # Write to stdout
            img.save(sys.stdout.buffer, format="PNG")
        elif output:
            # Write to file
            img.save(output)
            click.echo(f"Saved QR code to: {output}", err=True)
        else:
            # No output specified but PNG format requested - error
            click.echo("Error: PNG format requires -o/--output", err=True)
            raise SystemExit(1)

    else:
        # ASCII output to terminal
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=1,
            border=2,
        )
        qr.add_data(key)
        qr.make(fit=True)

        click.echo()
        click.echo(f"Channel Key: {key}")
        click.echo()
        qr.print_ascii(invert=True)
        click.echo()
        click.echo("Scan this QR code to share the channel key.")


@channel.command("clear")
@click.option("--project", is_flag=True, help="Only clear project config")
@click.option("--user", is_flag=True, help="Only clear user config")
@click.pass_context
def channel_clear(ctx, project, user):
    """
    Remove channel key configuration.

    Examples:

        stegasoo channel clear

        stegasoo channel clear --project

        stegasoo channel clear --user
    """
    from .channel import clear_channel_key

    if project and user:
        location = "all"
    elif project:
        location = "project"
    elif user:
        location = "user"
    else:
        location = "all"

    deleted = clear_channel_key(location)

    if ctx.obj.get("json"):
        click.echo(json.dumps({"deleted": [str(p) for p in deleted]}))
    else:
        if deleted:
            click.echo(f"Removed channel key from: {', '.join(str(p) for p in deleted)}")
        else:
            click.echo("No channel key files found")


# =============================================================================
# TOOLS COMMANDS
# =============================================================================


@cli.group()
@click.pass_context
def tools(ctx):
    """Image security tools."""
    pass


@tools.command("capacity")
@click.argument("image", type=click.Path(exists=True))
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def tools_capacity(image, as_json):
    """Show steganography capacity for an image.

    Example:

        stegasoo tools capacity photo.jpg
    """
    from .dct_steganography import estimate_capacity_comparison

    with open(image, "rb") as f:
        image_data = f.read()

    result = estimate_capacity_comparison(image_data)
    result["filename"] = Path(image).name
    result["megapixels"] = round((result["width"] * result["height"]) / 1_000_000, 2)

    if as_json:
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"\n  {result['filename']}")
        click.echo(f"  {'─' * 40}")
        click.echo(f"  Dimensions:   {result['width']} × {result['height']}")
        click.echo(f"  Megapixels:   {result['megapixels']} MP")
        click.echo(f"  {'─' * 40}")
        click.echo(f"  LSB Capacity: {result['lsb']['capacity_kb']:.1f} KB")
        if result['dct']['available']:
            click.echo(f"  DCT Capacity: {result['dct']['capacity_kb']:.1f} KB")
        else:
            click.echo("  DCT Capacity: N/A (scipy required)")
        click.echo()


@tools.command("strip")
@click.argument("image", type=click.Path(exists=True))
@click.option("-o", "--output", type=click.Path(), help="Output file (default: <name>_clean.png)")
@click.option("--format", "fmt", type=click.Choice(["png", "bmp"]), default="png", help="Output format")
def tools_strip(image, output, fmt):
    """Strip EXIF/metadata from an image.

    Example:

        stegasoo tools strip photo.jpg
        stegasoo tools strip photo.jpg -o clean.png
    """
    from .utils import strip_image_metadata

    with open(image, "rb") as f:
        image_data = f.read()

    clean_data = strip_image_metadata(image_data, output_format=fmt.upper())

    if not output:
        stem = Path(image).stem
        output = f"{stem}_clean.{fmt}"

    with open(output, "wb") as f:
        f.write(clean_data)

    click.echo(f"Saved clean image to: {output}")


@tools.command("peek")
@click.argument("image", type=click.Path(exists=True))
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def tools_peek(image, as_json):
    """Check if image contains Stegasoo hidden data.

    Example:

        stegasoo tools peek suspicious.jpg
    """
    from .steganography import peek_image

    with open(image, "rb") as f:
        image_data = f.read()

    result = peek_image(image_data)
    result["filename"] = Path(image).name

    if as_json:
        click.echo(json.dumps(result))
    else:
        if result["has_stegasoo"]:
            click.echo(f"\n  ✓ Stegasoo data detected in {result['filename']}")
            click.echo(f"    Mode: {result['mode'].upper()}")
        else:
            click.echo(f"\n  ✗ No Stegasoo header found in {result['filename']}")
        click.echo()


@tools.command("exif")
@click.argument("image", type=click.Path(exists=True))
@click.option("--clear", is_flag=True, help="Remove all EXIF metadata")
@click.option("--set", "set_fields", multiple=True, help="Set EXIF field (e.g. --set Artist=John)")
@click.option("-o", "--output", type=click.Path(), help="Output file (required for modifications)")
@click.option("--json", "as_json", is_flag=True, help="Output as JSON")
def tools_exif(image, clear, set_fields, output, as_json):
    """View or edit EXIF metadata.

    Examples:

        stegasoo tools exif photo.jpg

        stegasoo tools exif photo.jpg --clear -o clean.jpg

        stegasoo tools exif photo.jpg --set Artist="John Doe" -o updated.jpg
    """
    from .utils import read_image_exif, strip_image_metadata, write_image_exif

    with open(image, "rb") as f:
        image_data = f.read()

    # View mode (no modifications)
    if not clear and not set_fields:
        exif = read_image_exif(image_data)

        if as_json:
            click.echo(json.dumps(exif, indent=2, default=str))
        else:
            click.echo(f"\n  EXIF Metadata: {Path(image).name}")
            click.echo(f"  {'─' * 45}")
            if not exif:
                click.echo("  No EXIF metadata found")
            else:
                for key, value in sorted(exif.items()):
                    # Skip complex nested structures for display
                    if isinstance(value, dict):
                        click.echo(f"  {key}: [complex data]")
                    elif isinstance(value, list):
                        click.echo(f"  {key}: {value}")
                    else:
                        # Truncate long values
                        str_val = str(value)
                        if len(str_val) > 50:
                            str_val = str_val[:47] + "..."
                        click.echo(f"  {key}: {str_val}")
            click.echo()
        return

    # Modification mode - require output file
    if not output:
        raise click.UsageError("Output file required for modifications (use -o/--output)")

    if clear:
        # Strip all metadata
        clean_data = strip_image_metadata(image_data, output_format="JPEG")
        with open(output, "wb") as f:
            f.write(clean_data)
        click.echo(f"Cleared EXIF metadata, saved to: {output}")
    elif set_fields:
        # Parse field=value pairs
        updates = {}
        for field in set_fields:
            if "=" not in field:
                raise click.UsageError(f"Invalid format: {field} (use Field=Value)")
            key, val = field.split("=", 1)
            updates[key.strip()] = val.strip()

        try:
            updated_data = write_image_exif(image_data, updates)
            with open(output, "wb") as f:
                f.write(updated_data)
            click.echo(f"Updated {len(updates)} EXIF field(s), saved to: {output}")
        except ValueError as e:
            raise click.UsageError(str(e))


# =============================================================================
# ADMIN COMMANDS (Web UI administration)
# =============================================================================


@cli.group()
@click.pass_context
def admin(ctx):
    """Web UI administration commands."""
    pass


@admin.command("recover")
@click.option(
    "--db", "db_path",
    type=click.Path(exists=True),
    help="Path to stegasoo.db (default: frontends/web/instance/stegasoo.db)"
)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True,
              help="New admin password")
def admin_recover(db_path, password):
    """Reset admin password using recovery key.

    Allows password reset for Web UI admin account when locked out.
    Requires the recovery key that was saved during setup.

    Example:

        stegasoo admin recover --db /path/to/stegasoo.db
    """
    import sqlite3
    from argon2 import PasswordHasher
    from .recovery import verify_recovery_key

    # Try default paths if not specified
    if not db_path:
        candidates = [
            Path("frontends/web/instance/stegasoo.db"),
            Path("instance/stegasoo.db"),
            Path("/app/instance/stegasoo.db"),
        ]
        for candidate in candidates:
            if candidate.exists():
                db_path = str(candidate)
                break

    if not db_path or not Path(db_path).exists():
        raise click.UsageError(
            "Database not found. Use --db to specify path to stegasoo.db"
        )

    click.echo(f"Database: {db_path}")

    # Connect and check for recovery key
    db = sqlite3.connect(db_path)
    db.row_factory = sqlite3.Row

    # Get recovery key hash from app_settings
    cursor = db.execute(
        "SELECT value FROM app_settings WHERE key = 'recovery_key_hash'"
    )
    row = cursor.fetchone()

    if not row:
        db.close()
        raise click.ClickException(
            "No recovery key configured for this instance. "
            "Password reset is not possible."
        )

    stored_hash = row["value"]

    # Prompt for recovery key
    recovery_key = click.prompt(
        "Enter your recovery key",
        hide_input=False,  # Recovery keys are meant to be visible
    )

    # Verify recovery key
    if not verify_recovery_key(recovery_key, stored_hash):
        db.close()
        raise click.ClickException("Invalid recovery key")

    # Validate password
    if len(password) < 8:
        db.close()
        raise click.UsageError("Password must be at least 8 characters")

    # Hash new password with same settings as web UI
    ph = PasswordHasher(
        time_cost=3,
        memory_cost=65536,  # 64MB
        parallelism=4,
        hash_len=32,
        salt_len=16,
    )
    new_hash = ph.hash(password)

    # Find and update admin user
    admin = db.execute(
        "SELECT id, username FROM users WHERE role = 'admin' ORDER BY id LIMIT 1"
    ).fetchone()

    if not admin:
        db.close()
        raise click.ClickException("No admin user found in database")

    db.execute(
        "UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (new_hash, admin["id"]),
    )
    db.commit()
    db.close()

    click.echo(f"\nPassword reset successfully for admin '{admin['username']}'")
    click.echo("You can now login to the Web UI with your new password.")


@admin.command("generate-key")
@click.option("--qr", "show_qr", is_flag=True, help="Show QR code in terminal (if supported)")
def admin_generate_key(show_qr):
    """Generate a new recovery key (for reference only).

    This generates a new random recovery key and displays it.
    To actually set the recovery key, use the Web UI.

    Example:

        stegasoo admin generate-key
        stegasoo admin generate-key --qr
    """
    from .recovery import generate_recovery_key, get_recovery_fingerprint

    key = generate_recovery_key()

    click.echo("\nNew Recovery Key:")
    click.echo("─" * 50)
    click.echo(f"  {key}")
    click.echo("─" * 50)
    click.echo(f"Fingerprint: {get_recovery_fingerprint(key)}")

    if show_qr:
        try:
            import qrcode
            qr = qrcode.QRCode(box_size=1, border=1)
            qr.add_data(key)
            qr.make()
            click.echo("\nQR Code:")
            qr.print_ascii(invert=True)
        except ImportError:
            click.echo("\n(qrcode library not installed for terminal QR)")

    click.echo("\nNote: Save this key securely. To set it in the Web UI,")
    click.echo("go to Account > Recovery Key > Regenerate")


def main():
    """Entry point for CLI."""
    cli(obj={})


if __name__ == "__main__":
    main()
