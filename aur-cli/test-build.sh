#!/bin/bash
# Test build the AUR CLI package locally

set -e

cd "$(dirname "$0")"

echo "=== Cleaning previous builds ==="
rm -rf stegasoo-cli-git pkg src *.pkg.tar.zst *.whl 2>/dev/null || true

echo "=== Generating .SRCINFO ==="
makepkg --printsrcinfo > .SRCINFO

echo "=== Building package ==="
makepkg -sf

echo "=== Package built ==="
ls -la *.pkg.tar.zst

echo ""
echo "To install: sudo pacman -U stegasoo-cli-git-*.pkg.tar.zst"
echo "To test:    makepkg -si"
