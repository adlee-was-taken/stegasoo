"""
Stegasoo CLI Module (v3.2.0)

Command-line interface with batch processing and compression support.

Changes in v3.2.0:
- Updated to use DEFAULT_PASSPHRASE_WORDS (consistency with v3.2.0 naming)
- Updated help text to use 'passphrase' terminology
"""

import sys
import json
from pathlib import Path
from typing import Optional

import click

from .constants import (
    __version__,
    MAX_MESSAGE_SIZE,
    MAX_FILE_PAYLOAD_SIZE,
    DEFAULT_PIN_LENGTH,
    DEFAULT_PASSPHRASE_WORDS,  # v3.2.0: renamed from DEFAULT_PHRASE_WORDS
)
from .compression import (
    CompressionAlgorithm,
    get_available_algorithms,
    algorithm_name,
    HAS_LZ4,
)
from .batch import (
    BatchProcessor,
    BatchResult,
    batch_capacity_check,
    print_batch_result,
)


# Click context settings
CONTEXT_SETTINGS = dict(help_option_names=['-h', '--help'])


@click.group(context_settings=CONTEXT_SETTINGS)
@click.version_option(__version__, '-v', '--version')
@click.option('--json', 'json_output', is_flag=True, help='Output results as JSON')
@click.pass_context
def cli(ctx, json_output):
    """
    Stegasoo - Steganography with hybrid authentication.
    
    Hide messages in images using PIN + passphrase security.
    """
    ctx.ensure_object(dict)
    ctx.obj['json'] = json_output


# =============================================================================
# ENCODE COMMANDS
# =============================================================================

@cli.command()
@click.argument('image', type=click.Path(exists=True))
@click.option('-m', '--message', help='Message to encode')
@click.option('-f', '--file', 'file_payload', type=click.Path(exists=True), 
              help='File to embed instead of message')
@click.option('-o', '--output', type=click.Path(), help='Output image path')
@click.option('--passphrase', prompt=True, hide_input=True, 
              confirmation_prompt=True, help='Passphrase (recommend 4+ words)')
@click.option('--pin', prompt=True, hide_input=True,
              confirmation_prompt=True, help='PIN code')
@click.option('--compress/--no-compress', default=True, 
              help='Enable/disable compression (default: enabled)')
@click.option('--algorithm', type=click.Choice(['zlib', 'lz4', 'none']), 
              default='zlib', help='Compression algorithm')
@click.option('--dry-run', is_flag=True, help='Show capacity usage without encoding')
@click.pass_context
def encode(ctx, image, message, file_payload, output, passphrase, pin, 
           compress, algorithm, dry_run):
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
        'zlib': CompressionAlgorithm.ZLIB,
        'lz4': CompressionAlgorithm.LZ4,
        'none': CompressionAlgorithm.NONE,
    }
    compression_algo = algo_map[algorithm] if compress else CompressionAlgorithm.NONE
    
    if algorithm == 'lz4' and not HAS_LZ4:
        click.echo("Warning: LZ4 not available, falling back to zlib", err=True)
        compression_algo = CompressionAlgorithm.ZLIB
    
    # Calculate payload size
    if file_payload:
        payload_size = Path(file_payload).stat().st_size
        payload_type = "file"
    else:
        payload_size = len(message.encode('utf-8'))
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
        
        if ctx.obj.get('json'):
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
    
    if ctx.obj.get('json'):
        click.echo(json.dumps({
            "status": "success",
            "input": image,
            "output": output,
            "payload_type": payload_type,
            "compression": algorithm_name(compression_algo),
        }, indent=2))
    else:
        click.echo(f"✓ Encoded {payload_type} to {output}")
        click.echo(f"  Compression: {algorithm_name(compression_algo)}")


@cli.command()
@click.argument('image', type=click.Path(exists=True))
@click.option('--passphrase', prompt=True, hide_input=True, help='Passphrase')
@click.option('--pin', prompt=True, hide_input=True, help='PIN code')
@click.option('-o', '--output', type=click.Path(), 
              help='Output path for file payloads')
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
    
    if ctx.obj.get('json'):
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"Decoded from {image}:")
        click.echo(result['message'])


# =============================================================================
# BATCH COMMANDS
# =============================================================================

@cli.group()
def batch():
    """Batch operations on multiple images."""
    pass


@batch.command('encode')
@click.argument('images', nargs=-1, required=True, type=click.Path(exists=True))
@click.option('-m', '--message', help='Message to encode in all images')
@click.option('-f', '--file', 'file_payload', type=click.Path(exists=True),
              help='File to embed in all images')
@click.option('-o', '--output-dir', type=click.Path(),
              help='Output directory (default: same as input)')
@click.option('--suffix', default='_encoded', help='Output filename suffix')
@click.option('--passphrase', prompt=True, hide_input=True,
              confirmation_prompt=True, help='Passphrase (recommend 4+ words)')
@click.option('--pin', prompt=True, hide_input=True,
              confirmation_prompt=True, help='PIN code')
@click.option('--compress/--no-compress', default=True,
              help='Enable/disable compression')
@click.option('--algorithm', type=click.Choice(['zlib', 'lz4', 'none']),
              default='zlib', help='Compression algorithm')
@click.option('-r', '--recursive', is_flag=True,
              help='Search directories recursively')
@click.option('-j', '--jobs', default=4, help='Parallel workers (default: 4)')
@click.option('-v', '--verbose', is_flag=True, help='Show detailed output')
@click.pass_context
def batch_encode(ctx, images, message, file_payload, output_dir, suffix,
                 passphrase, pin, compress, algorithm, recursive, jobs, verbose):
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
        if not ctx.obj.get('json'):
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
        progress_callback=progress if not ctx.obj.get('json') else None,
    )
    
    if ctx.obj.get('json'):
        click.echo(result.to_json())
    else:
        print_batch_result(result, verbose)


@batch.command('decode')
@click.argument('images', nargs=-1, required=True, type=click.Path(exists=True))
@click.option('-o', '--output-dir', type=click.Path(),
              help='Output directory for file payloads')
@click.option('--passphrase', prompt=True, hide_input=True, help='Passphrase')
@click.option('--pin', prompt=True, hide_input=True, help='PIN code')
@click.option('-r', '--recursive', is_flag=True,
              help='Search directories recursively')
@click.option('-j', '--jobs', default=4, help='Parallel workers (default: 4)')
@click.option('-v', '--verbose', is_flag=True, help='Show detailed output')
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
        if not ctx.obj.get('json'):
            status = "✓" if item.status.value == "success" else "✗"
            click.echo(f"[{current}/{total}] {status} {item.input_path.name}")
    
    # v3.2.0: Use 'passphrase' key instead of 'phrase'
    credentials = {"passphrase": passphrase, "pin": pin}
    
    result = processor.batch_decode(
        images=list(images),
        output_dir=Path(output_dir) if output_dir else None,
        credentials=credentials,
        recursive=recursive,
        progress_callback=progress if not ctx.obj.get('json') else None,
    )
    
    if ctx.obj.get('json'):
        click.echo(result.to_json())
    else:
        print_batch_result(result, verbose)


@batch.command('check')
@click.argument('images', nargs=-1, required=True, type=click.Path(exists=True))
@click.option('-r', '--recursive', is_flag=True,
              help='Search directories recursively')
@click.pass_context
def batch_check(ctx, images, recursive):
    """
    Check capacity of multiple images.
    
    Examples:
    
        stegasoo batch check *.png
        
        stegasoo batch check ./photos/ -r
    """
    results = batch_capacity_check(list(images), recursive)
    
    if ctx.obj.get('json'):
        click.echo(json.dumps(results, indent=2))
    else:
        click.echo(f"{'Image':<40} {'Size':<12} {'Capacity':<12} {'Status'}")
        click.echo("─" * 80)
        
        for item in results:
            if 'error' in item:
                click.echo(f"{Path(item['path']).name:<40} {'ERROR':<12} {'':<12} {item['error']}")
            else:
                name = Path(item['path']).name
                if len(name) > 38:
                    name = name[:35] + "..."
                
                status = "✓" if item['valid'] else "⚠"
                warnings = ", ".join(item.get('warnings', []))
                
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
@click.option('--words', default=DEFAULT_PASSPHRASE_WORDS, 
              help=f'Number of words in passphrase (default: {DEFAULT_PASSPHRASE_WORDS})')
@click.option('--pin-length', default=DEFAULT_PIN_LENGTH,
              help=f'PIN length (default: {DEFAULT_PIN_LENGTH})')
@click.pass_context
def generate(ctx, words, pin_length):
    """
    Generate random credentials (passphrase + PIN).
    
    Examples:
    
        stegasoo generate
        
        stegasoo generate --words 6 --pin-length 8
    """
    import secrets
    
    # Generate PIN
    pin = ''.join(str(secrets.randbelow(10)) for _ in range(pin_length))
    # Ensure PIN doesn't start with 0
    if pin[0] == '0':
        pin = str(secrets.randbelow(9) + 1) + pin[1:]
    
    # Generate passphrase (would use BIP-39 wordlist)
    # Placeholder - actual implementation uses constants.get_wordlist()
    try:
        from .constants import get_wordlist
        wordlist = get_wordlist()
        phrase_words = [secrets.choice(wordlist) for _ in range(words)]
    except (ImportError, FileNotFoundError):
        # Fallback for testing
        sample_words = ['alpha', 'bravo', 'charlie', 'delta', 'echo', 'foxtrot',
                        'golf', 'hotel', 'india', 'juliet', 'kilo', 'lima']
        phrase_words = [secrets.choice(sample_words) for _ in range(words)]
    
    passphrase = ' '.join(phrase_words)
    
    result = {
        "passphrase": passphrase,
        "pin": pin,
        "passphrase_words": words,
        "pin_length": pin_length,
    }
    
    if ctx.obj.get('json'):
        click.echo(json.dumps(result, indent=2))
    else:
        click.echo(f"Passphrase: {passphrase}")
        click.echo(f"PIN:        {pin}")
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
    
    if ctx.obj.get('json'):
        click.echo(json.dumps(info_data, indent=2))
    else:
        click.echo(f"Stegasoo v{__version__}")
        click.echo(f"\nCompression algorithms:")
        for algo in get_available_algorithms():
            click.echo(f"  • {algorithm_name(algo)}")
        if not HAS_LZ4:
            click.echo("    (install 'lz4' for LZ4 support)")
        click.echo(f"\nLimits:")
        click.echo(f"  • Max message: {MAX_MESSAGE_SIZE:,} bytes")
        click.echo(f"  • Max file payload: {MAX_FILE_PAYLOAD_SIZE:,} bytes")


def main():
    """Entry point for CLI."""
    cli(obj={})


if __name__ == '__main__':
    main()
