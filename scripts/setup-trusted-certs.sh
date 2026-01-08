#!/bin/bash
#
# Setup trusted HTTPS certificates for Stegasoo
# Uses mkcert to create browser-trusted certs (no warning screens!)
#
# Usage: ./setup-trusted-certs.sh [hostname]
#
# This script:
#   1. Installs mkcert if needed
#   2. Creates a local CA (one-time)
#   3. Generates certs for your hostname
#   4. Shows how to trust the CA on other devices
#

set -e

HOSTNAME="${1:-stegasoo.local}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$SCRIPT_DIR/.."
CERT_DIR="$PROJECT_ROOT/frontends/web/certs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         Stegasoo Trusted Certificate Setup                    ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check/install mkcert
install_mkcert() {
    if command -v mkcert &> /dev/null; then
        echo -e "${GREEN}✓${NC} mkcert already installed"
        return
    fi

    echo -e "${YELLOW}Installing mkcert...${NC}"

    # Detect OS and install
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command -v brew &> /dev/null; then
            brew install mkcert
        else
            echo -e "${RED}Please install Homebrew first: https://brew.sh${NC}"
            exit 1
        fi
    elif [[ -f /etc/debian_version ]]; then
        # Debian/Ubuntu/Raspberry Pi OS
        sudo apt-get update
        sudo apt-get install -y libnss3-tools

        # Download mkcert binary
        ARCH=$(dpkg --print-architecture)
        if [[ "$ARCH" == "arm64" ]] || [[ "$ARCH" == "aarch64" ]]; then
            MKCERT_URL="https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-linux-arm64"
        else
            MKCERT_URL="https://github.com/FiloSottile/mkcert/releases/latest/download/mkcert-linux-amd64"
        fi

        sudo curl -L "$MKCERT_URL" -o /usr/local/bin/mkcert
        sudo chmod +x /usr/local/bin/mkcert
    elif [[ -f /etc/arch-release ]]; then
        # Arch Linux
        sudo pacman -S mkcert
    else
        echo -e "${RED}Unsupported OS. Please install mkcert manually:${NC}"
        echo "  https://github.com/FiloSottile/mkcert#installation"
        exit 1
    fi

    echo -e "${GREEN}✓${NC} mkcert installed"
}

# Install local CA
setup_ca() {
    echo ""
    echo -e "${CYAN}Setting up local Certificate Authority...${NC}"

    if mkcert -install 2>/dev/null; then
        echo -e "${GREEN}✓${NC} Local CA installed in system trust store"
    else
        echo -e "${YELLOW}!${NC} Could not auto-install CA (may need manual browser import)"
    fi
}

# Generate certificates
generate_certs() {
    echo ""
    echo -e "${CYAN}Generating trusted certificate for: ${YELLOW}$HOSTNAME${NC}"

    mkdir -p "$CERT_DIR"
    cd "$CERT_DIR"

    # Generate cert for hostname + common local names
    mkcert -key-file key.pem -cert-file cert.pem \
        "$HOSTNAME" \
        localhost \
        127.0.0.1 \
        ::1

    echo -e "${GREEN}✓${NC} Certificates generated in: $CERT_DIR"
}

# Show CA location for other devices
show_ca_info() {
    CA_ROOT=$(mkcert -CAROOT)
    CA_FILE="$CA_ROOT/rootCA.pem"

    echo ""
    echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Setup Complete!${NC}"
    echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
    echo ""
    echo "Your certificates are ready. Browsers on THIS machine will trust them."
    echo ""
    echo -e "${YELLOW}To trust on OTHER devices (phones, tablets, other computers):${NC}"
    echo ""
    echo "  1. Copy the CA certificate to that device:"
    echo -e "     ${CYAN}$CA_FILE${NC}"
    echo ""
    echo "  2. Import it as a trusted CA:"
    echo "     - iOS: AirDrop/email the file, Settings > Profile Downloaded > Install"
    echo "     - Android: Settings > Security > Install from storage"
    echo "     - Windows: Double-click > Install > Trusted Root CAs"
    echo "     - macOS: Double-click > Keychain Access > Trust Always"
    echo "     - Linux: Copy to /usr/local/share/ca-certificates/ && update-ca-certificates"
    echo ""
    echo -e "${YELLOW}Quick copy command:${NC}"
    echo "  scp $CA_FILE user@device:/path/"
    echo ""

    # Offer to serve CA file via HTTP for easy phone download
    echo -e "${YELLOW}Or serve the CA for easy phone download:${NC}"
    echo "  python3 -m http.server 8080 -d $CA_ROOT"
    echo "  Then visit: http://$(hostname -I | awk '{print $1}'):8080/rootCA.pem"
    echo ""
}

# Main
install_mkcert
setup_ca
generate_certs
show_ca_info
