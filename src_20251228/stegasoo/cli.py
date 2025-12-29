"""
Stegasoo CLI - Command-line interface for steganography operations.

This is the package entry point. For full CLI, install with: pip install stegasoo[cli]
"""

def main():
    """Main entry point for the CLI."""
    try:
        import click
    except ImportError:
        print("CLI requires click. Install with: pip install stegasoo[cli]")
        return 1
    
    # Import the CLI from frontends
    import sys
    from pathlib import Path
    
    # Add frontends to path for development
    root = Path(__file__).parent.parent.parent
    cli_path = root / 'frontends' / 'cli'
    if cli_path.exists():
        sys.path.insert(0, str(cli_path))
    
    try:
        from main import cli
        cli()
    except ImportError:
        # Minimal fallback CLI
        _minimal_cli()


def _minimal_cli():
    """Minimal CLI when full CLI is not available."""
    import sys
    from . import __version__, generate_credentials, DAY_NAMES
    
    if len(sys.argv) < 2 or sys.argv[1] in ['-h', '--help']:
        print(f"Stegasoo v{__version__} - Secure Steganography")
        print()
        print("Usage: stegasoo <command>")
        print()
        print("Commands:")
        print("  generate  Generate credentials")
        print("  encode    Encode a message (requires full CLI)")
        print("  decode    Decode a message (requires full CLI)")
        print()
        print("For full CLI functionality:")
        print("  pip install stegasoo[cli]")
        return
    
    if sys.argv[1] == 'generate':
        creds = generate_credentials(use_pin=True, use_rsa=False)
        print("\n=== STEGASOO CREDENTIALS ===\n")
        print(f"PIN: {creds.pin}\n")
        print("Daily Phrases:")
        for day in DAY_NAMES:
            print(f"  {day:9} | {creds.phrases[day]}")
        print(f"\nEntropy: {creds.total_entropy} bits (+ photo)")
    else:
        print(f"Command '{sys.argv[1]}' requires full CLI.")
        print("Install with: pip install stegasoo[cli]")


if __name__ == '__main__':
    main()
