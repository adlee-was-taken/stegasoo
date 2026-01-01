#!/usr/bin/env python3
"""
Stegasoo - Main Entry Point

This module provides the main entry point for the stegasoo package.
It can be run directly or via the installed console script.

Usage:
    python -m stegasoo --help
    python src/main.py --help
    stegasoo --help  (if installed via pip)
"""

import sys


def main():
    """
    Main entry point for Stegasoo CLI.
    
    Delegates to the CLI module for command parsing and execution.
    """
    try:
        from stegasoo.cli import main as cli_main
        cli_main()
    except ImportError as e:
        # Provide helpful error if dependencies are missing
        print(f"Error: Could not import stegasoo package: {e}", file=sys.stderr)
        print("\nMake sure stegasoo is installed:", file=sys.stderr)
        print("  pip install -e .", file=sys.stderr)
        print("\nOr run from the src directory:", file=sys.stderr)
        print("  PYTHONPATH=src python -m stegasoo", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        sys.exit(130)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


def version():
    """Print version and exit."""
    try:
        from stegasoo import __version__
        print(f"stegasoo {__version__}")
    except ImportError:
        print("stegasoo (version unknown)")


if __name__ == "__main__":
    main()
