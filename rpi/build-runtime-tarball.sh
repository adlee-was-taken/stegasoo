#!/bin/bash
#
# Build Stegasoo Pi venv Tarball
# Run this ON THE PI after a successful from-source build
#
# Creates: stegasoo-rpi-venv-arm64.tar.zst (~40-50MB)
# Contains: venv with all dependencies (uses system Python 3.11+)
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

INSTALL_DIR="${INSTALL_DIR:-/opt/stegasoo}"
OUTPUT_FILE="${1:-$HOME/stegasoo-rpi-venv-arm64.tar.zst}"

echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║         Stegasoo Pi venv Tarball Builder                      ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Verify we're on ARM64
ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" ]]; then
    echo -e "${RED}Error: This script must be run on ARM64 (aarch64)${NC}"
    echo "Current architecture: $ARCH"
    exit 1
fi

# Verify venv exists
if [[ ! -d "$INSTALL_DIR/venv" ]]; then
    echo -e "${RED}Error: venv not found at $INSTALL_DIR/venv${NC}"
    echo "Run a from-source build first: ./rpi/setup.sh --no-prebuilt"
    exit 1
fi

# Step 1: Clean caches from venv
echo -e "${GREEN}[1/2]${NC} Cleaning caches from venv..."
VENV_SIZE_BEFORE=$(du -sh "$INSTALL_DIR/venv" | cut -f1)
find "$INSTALL_DIR/venv/" -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null || true
find "$INSTALL_DIR/venv/" -type d -name 'tests' -exec rm -rf {} + 2>/dev/null || true
find "$INSTALL_DIR/venv/" -type d -name 'test' -exec rm -rf {} + 2>/dev/null || true
find "$INSTALL_DIR/venv/" -type f -name '*.pyc' -delete 2>/dev/null || true
VENV_SIZE_AFTER=$(du -sh "$INSTALL_DIR/venv" | cut -f1)
echo "  venv: $VENV_SIZE_BEFORE -> $VENV_SIZE_AFTER"

# Step 2: Create tarball
echo -e "${GREEN}[2/2]${NC} Creating tarball..."
cd "$INSTALL_DIR"
tar -cf - venv/ | zstd -19 -T0 > "$OUTPUT_FILE"

# Summary
FINAL_SIZE=$(ls -lh "$OUTPUT_FILE" | awk '{print $5}')
echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "  Output: ${YELLOW}$OUTPUT_FILE${NC}"
echo -e "  Size:   ${YELLOW}$FINAL_SIZE${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo "To pull to your host machine:"
echo "  scp $(whoami)@$(hostname).local:$OUTPUT_FILE ./"
echo ""
echo "To use in setup.sh, place at:"
echo "  rpi/stegasoo-rpi-venv-arm64.tar.zst"
echo ""
echo "Or upload to GitHub releases for automatic download."
