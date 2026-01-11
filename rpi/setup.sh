#!/bin/bash
#
# Stegasoo Raspberry Pi Setup Script
# Tested on: Raspberry Pi 4/5 with Raspberry Pi OS (64-bit)
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/adlee-was-taken/stegasoo/4.2/rpi/setup.sh | bash
#   # or
#   wget -qO- https://raw.githubusercontent.com/adlee-was-taken/stegasoo/4.2/rpi/setup.sh | bash
#
# What this script does:
#   1. Installs system dependencies
#   2. Verifies Python 3.11+ (uses system Python)
#   3. Installs jpeglib for DCT steganography (Python 3.11-3.14 compatible)
#   4. Installs Stegasoo with web UI
#   5. Creates systemd service for auto-start
#   6. Enables the service
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Source banner.sh if available (for local runs), otherwise define inline
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" 2>/dev/null && pwd)"
if [ -f "$SCRIPT_DIR/banner.sh" ]; then
    source "$SCRIPT_DIR/banner.sh"
else
    # Inline banner functions for curl-pipe execution
    print_gradient_line() {
        echo -e "\033[38;5;93m══════════════\033[38;5;99m══════════════\033[38;5;105m══════════════\033[38;5;117m══════════════\033[0m"
    }
    print_banner() {
        local subtitle="$1"
        echo ""
        print_gradient_line
        echo -e "\033[0;90m · .  · .  *  · .  *  · .  *  · .  *  · .  *  · .  ·\033[0m"
        echo -e "\033[38;5;220m    ___  _____  ___    ___    _    ___    ___    ___\033[0m"
        echo -e "\033[38;5;220m   / __||_   _|| __|  / __|  /_\\  / __|  / _ \\  / _ \\\\\033[0m"
        echo -e "\033[38;5;220m   \\__ \\  | |  | _|  | (_ | / _ \\ \\__ \\ | (_) || (_) |\033[0m"
        echo -e "\033[38;5;220m   |___/  |_|  |___|  \\___//_/ \\_\\|___/  \\___/  \\___/\033[0m"
        echo -e "\033[0;90m · .  · .  *  · .  *  · .  *  · .  *  · .  *  · .  ·\033[0m"
        print_gradient_line
        if [ -n "$subtitle" ]; then
            echo -e "\033[1;37m                    ${subtitle}\033[0m"
            print_gradient_line
        fi
    }
fi

# Show help
show_help() {
    echo "Stegasoo Raspberry Pi Setup Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help      Show this help message"
    echo "  --no-prebuilt   Build from source instead of using pre-built venv"
    echo "  --from-source   Same as --no-prebuilt"
    echo ""
    echo "Configuration:"
    echo "  Config files are loaded in order (later overrides earlier):"
    echo "    1. /etc/stegasoo.conf"
    echo "    2. ~/.config/stegasoo/stegasoo.conf"
    echo "    3. Environment variables"
    echo ""
    echo "  Available variables:"
    echo "    INSTALL_DIR       Install location (default: /opt/stegasoo)"
    echo "    STEGASOO_REPO     Git repo URL"
    echo "    STEGASOO_BRANCH   Git branch (default: 4.2)"
    echo ""
    echo "  Example:"
    echo "    export INSTALL_DIR=\"/home/pi/stegasoo\""
    echo "    ./setup.sh"
    echo ""
    exit 0
}

# Parse args
for arg in "$@"; do
    case $arg in
        -h|--help) show_help ;;
    esac
done

# Default configuration
INSTALL_DIR="${INSTALL_DIR:-/opt/stegasoo}"
STEGASOO_REPO="${STEGASOO_REPO:-https://github.com/adlee-was-taken/stegasoo.git}"
STEGASOO_BRANCH="${STEGASOO_BRANCH:-4.2}"

# Load config files (system, then user - user overrides system)
for config_file in "/etc/stegasoo.conf" "$HOME/.config/stegasoo/stegasoo.conf"; do
    if [ -f "$config_file" ]; then
        # shellcheck source=/dev/null
        source "$config_file"
    fi
done

clear
print_banner "Raspberry Pi Setup"
echo ""
echo "  This will install Stegasoo with full DCT support"
echo "  Estimated time: ~2 minutes (pre-built) or 5-10 min (from source)"
echo ""

# Check if running on ARM
ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
    echo -e "${RED}Error: This script is for ARM64 systems (Raspberry Pi).${NC}"
    echo "Detected architecture: $ARCH"
    exit 1
fi

# =============================================================================
# Python Version Check
# =============================================================================
echo -e "${GREEN}Checking Python version...${NC}"

# Find system Python
SYSTEM_PYTHON=""
for py in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$py" &>/dev/null; then
        SYSTEM_PYTHON=$(command -v "$py")
        break
    fi
done

if [ -z "$SYSTEM_PYTHON" ]; then
    echo -e "${RED}Error: Python 3 not found.${NC}"
    echo "Please install Python 3.11 or later:"
    echo "  sudo apt-get install python3"
    exit 1
fi

# Get version numbers
PY_VERSION=$("$SYSTEM_PYTHON" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PY_MAJOR=$("$SYSTEM_PYTHON" -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$("$SYSTEM_PYTHON" -c 'import sys; print(sys.version_info.minor)')

echo "  Found: $SYSTEM_PYTHON (Python $PY_VERSION)"

# Check version range (3.11 <= version <= 3.14)
if [ "$PY_MAJOR" -ne 3 ]; then
    echo -e "${RED}Error: Python 3 required, found Python $PY_MAJOR${NC}"
    exit 1
fi

if [ "$PY_MINOR" -lt 11 ]; then
    echo -e "${RED}Error: Python 3.11+ required, found Python $PY_VERSION${NC}"
    echo ""
    echo "Raspberry Pi OS Bookworm ships with Python 3.11."
    echo "Raspberry Pi OS Trixie ships with Python 3.13."
    echo ""
    echo "Please upgrade your Raspberry Pi OS or install Python 3.11+."
    exit 1
fi

if [ "$PY_MINOR" -gt 14 ]; then
    echo -e "${YELLOW}Warning: Python $PY_VERSION detected.${NC}"
    echo "Stegasoo is tested with Python 3.11-3.14."
    echo "Newer versions may work but are not officially supported."
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

echo -e "  ${GREEN}✓${NC} Python $PY_VERSION supported"

# Check available memory
TOTAL_MEM=$(free -m | awk '/^Mem:/{print $2}')
if [ "$TOTAL_MEM" -lt 2000 ]; then
    echo -e "${YELLOW}Warning: Less than 2GB RAM detected ($TOTAL_MEM MB).${NC}"
    echo "Stegasoo Web UI requires ~768MB for Argon2 operations."
    echo "Consider using a Pi with more RAM for best results."
    read -p "Continue anyway? [y/N] " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# =============================================================================
# Installation
# =============================================================================

echo -e "${GREEN}[1/9]${NC} Setting up install directory..."
if [ ! -d "$INSTALL_DIR" ]; then
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$USER:$USER" "$INSTALL_DIR"
    echo "  Created $INSTALL_DIR"
else
    # Ensure current user owns it
    sudo chown "$USER:$USER" "$INSTALL_DIR"
    echo "  $INSTALL_DIR exists, updated ownership"
fi

echo -e "${GREEN}[2/9]${NC} Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    git \
    curl \
    zstd \
    libssl-dev \
    zlib1g-dev \
    libbz2-dev \
    libreadline-dev \
    libsqlite3-dev \
    libncursesw5-dev \
    xz-utils \
    tk-dev \
    libxml2-dev \
    libxmlsec1-dev \
    libffi-dev \
    liblzma-dev \
    libzbar0 \
    libjpeg-dev \
    python3-dev \
    python3-venv \
    python3-pip \
    btop

echo -e "${GREEN}[3/9]${NC} Installing gum (TUI toolkit)..."
# Add Charm repo for gum
if ! command -v gum &>/dev/null; then
    sudo mkdir -p /etc/apt/keyrings
    curl -fsSL https://repo.charm.sh/apt/gpg.key | sudo gpg --dearmor -o /etc/apt/keyrings/charm.gpg
    echo "deb [signed-by=/etc/apt/keyrings/charm.gpg] https://repo.charm.sh/apt/ * *" | sudo tee /etc/apt/sources.list.d/charm.list
    sudo apt-get update
    sudo apt-get install -y gum
else
    echo "  gum already installed"
fi

# Install mkcert for browser-trusted certificates (no warning screen!)
echo "  Installing mkcert for trusted HTTPS certificates..."
if ! command -v mkcert &>/dev/null; then
    sudo apt-get install -y libnss3-tools
    # Download mkcert for ARM64
    sudo curl -sL "https://github.com/FiloSottile/mkcert/releases/download/v1.4.4/mkcert-v1.4.4-linux-arm64" -o /usr/local/bin/mkcert
    sudo chmod +x /usr/local/bin/mkcert
    # Install local CA (makes certs trusted on this Pi)
    mkcert -install 2>/dev/null || true
    echo "  mkcert installed"
else
    echo "  mkcert already installed"
fi

echo -e "${GREEN}[4/9]${NC} Cloning Stegasoo..."

# Clone Stegasoo first (needed to check for pre-built tarball)
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "  Stegasoo directory exists, updating..."
    cd "$INSTALL_DIR"
    git fetch origin
    git checkout "$STEGASOO_BRANCH"
    git pull origin "$STEGASOO_BRANCH"
else
    git clone -b "$STEGASOO_BRANCH" "$STEGASOO_REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Pre-built venv tarball (skips pip compile time)
PREBUILT_TARBALL="$INSTALL_DIR/rpi/stegasoo-rpi-venv-arm64.tar.zst"
PREBUILT_URL="${PREBUILT_URL:-https://github.com/adlee-was-taken/stegasoo/releases/download/v4.2.0/stegasoo-rpi-venv-arm64.tar.zst}"
USE_PREBUILT=true

# Use local tarball if present, otherwise will download
if [ -f "$PREBUILT_TARBALL" ]; then
    echo -e "${GREEN}Found local pre-built venv - fast install mode${NC}"
else
    echo -e "${GREEN}Will download pre-built venv - fast install mode${NC}"
fi

# Allow --no-prebuilt flag to force from-source build
if [[ " $* " =~ " --no-prebuilt " ]] || [[ " $* " =~ " --from-source " ]]; then
    USE_PREBUILT=false
    echo -e "${YELLOW}Building from source (--no-prebuilt specified)${NC}"
fi

echo -e "${GREEN}[5/9]${NC} Setting up Python environment..."

if [ "$USE_PREBUILT" = true ]; then
    # Fast path: use pre-built venv

    # Download if local file doesn't exist
    if [ ! -f "$PREBUILT_TARBALL" ]; then
        echo "  Downloading pre-built venv (~50MB)..."
        curl -L -o "$PREBUILT_TARBALL" "$PREBUILT_URL"
    fi

    # Extract pre-built venv
    echo "  Extracting pre-built venv..."
    zstd -d "$PREBUILT_TARBALL" --stdout | tar -xf - -C "$INSTALL_DIR"

    # Fix venv Python symlinks to point to system Python
    echo "  Updating venv to use system Python..."
    rm -f "$INSTALL_DIR/venv/bin/python" "$INSTALL_DIR/venv/bin/python3"
    ln -s "$SYSTEM_PYTHON" "$INSTALL_DIR/venv/bin/python"
    ln -s "$SYSTEM_PYTHON" "$INSTALL_DIR/venv/bin/python3"

    # Update pip shebang if needed
    if [ -f "$INSTALL_DIR/venv/bin/pip" ]; then
        sed -i "1s|^#!.*|#!$INSTALL_DIR/venv/bin/python|" "$INSTALL_DIR/venv/bin/pip" 2>/dev/null || true
    fi

    # Activate and verify
    source "$INSTALL_DIR/venv/bin/activate"
    VENV_PY=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo -e "  ${GREEN}✓${NC} venv Python: $VENV_PY"

    # Install stegasoo package in editable mode (quick, no compile)
    echo "  Installing Stegasoo package..."
    pip install -e "." --quiet
else
    # Build from source
    echo -e "  ${YELLOW}Building from source (this takes 5-10 minutes)${NC}"

    # Create venv with system Python
    if [ ! -d "$INSTALL_DIR/venv" ]; then
        "$SYSTEM_PYTHON" -m venv "$INSTALL_DIR/venv"
    fi
    source "$INSTALL_DIR/venv/bin/activate"

    # Verify we're using the right Python
    VENV_PY=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo "  venv Python: $VENV_PY"

    # Upgrade pip and install build tools
    pip install --upgrade pip setuptools wheel

    # Install jpeglib (has no ARM64 wheel, needs headers fix)
    echo "  Installing jpeglib for ARM64..."
    if [ -f "$INSTALL_DIR/rpi/patches/jpeglib/install-jpeglib-arm64.sh" ]; then
        bash "$INSTALL_DIR/rpi/patches/jpeglib/install-jpeglib-arm64.sh"
    else
        # Inline fix: download headers and build
        JPEGLIB_WORKDIR=$(mktemp -d)
        cd "$JPEGLIB_WORKDIR"
        pip download jpeglib==1.0.2 --no-binary :all: --no-deps -d . -q
        tar -xzf jpeglib-1.0.2.tar.gz
        cd jpeglib-1.0.2
        CJPEGLIB="src/jpeglib/cjpeglib"

        # Download and copy libjpeg 6b headers
        curl -sL "https://www.ijg.org/files/jpegsrc.v6b.tar.gz" | tar -xzf -
        cp jpeg-6b/*.h "$CJPEGLIB/6b/"

        # Download and copy libjpeg 9f headers (works for 7-9f)
        curl -sL "https://www.ijg.org/files/jpegsrc.v9f.tar.gz" | tar -xzf -
        for v in 7 8 8a 8b 8c 8d 9 9a 9b 9c 9d 9e 9f; do
            cp jpeg-9f/*.h "$CJPEGLIB/$v/"
        done

        # Download and copy libjpeg-turbo headers
        curl -sL "https://github.com/libjpeg-turbo/libjpeg-turbo/archive/refs/tags/2.1.0.tar.gz" | tar -xzf -
        for v in turbo120 turbo130 turbo140 turbo150 turbo200 turbo210; do
            cp libjpeg-turbo-2.1.0/*.h "$CJPEGLIB/$v/" 2>/dev/null || true
        done

        # Download and copy mozjpeg headers
        curl -sL "https://github.com/mozilla/mozjpeg/archive/refs/tags/v4.0.3.tar.gz" | tar -xzf -
        for v in mozjpeg101 mozjpeg201 mozjpeg300 mozjpeg403; do
            cp mozjpeg-4.0.3/*.h "$CJPEGLIB/$v/" 2>/dev/null || true
        done

        # Build and install
        pip install .
        cd "$INSTALL_DIR"
        rm -rf "$JPEGLIB_WORKDIR"
    fi

    # Install remaining dependencies
    echo "  Installing remaining dependencies..."
    pip install -e ".[web]"
fi

echo -e "  ${GREEN}✓${NC} Stegasoo installed"

echo -e "${GREEN}[6/9]${NC} Creating systemd services..."

# Create systemd service file for Web UI
sudo tee /etc/systemd/system/stegasoo.service > /dev/null <<EOF
[Unit]
Description=Stegasoo Web UI
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR/frontends/web
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/bin"
Environment="STEGASOO_AUTH_ENABLED=true"
Environment="STEGASOO_HTTPS_ENABLED=false"
Environment="STEGASOO_PORT=5000"
ExecStart=$INSTALL_DIR/venv/bin/python app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create systemd service file for REST API (optional)
sudo tee /etc/systemd/system/stegasoo-api.service > /dev/null <<EOF
[Unit]
Description=Stegasoo REST API
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR/frontends/api
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/bin"
Environment="PYTHONPATH=$INSTALL_DIR/src"
ExecStart=$INSTALL_DIR/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8000
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo -e "${GREEN}[7/9]${NC} Enabling services..."

sudo systemctl daemon-reload
sudo systemctl enable stegasoo.service

# Prompt for REST API service (optional, with security warning)
echo ""
echo -e "${CYAN}Would you like to enable the REST API service? (port 8000)${NC}"
echo ""
echo -e "  ${RED}⚠ WARNING: The REST API has NO AUTHENTICATION${NC}"
echo "  Anyone on your network can use it to encode/decode messages."
echo "  Only enable if you understand the security implications."
echo ""
echo "  The Web UI (port 5000) has authentication and works independently."
echo ""
read -p "Enable REST API (no auth)? [y/N]: " ENABLE_API
if [[ "$ENABLE_API" =~ ^[Yy]$ ]]; then
    sudo systemctl enable stegasoo-api.service
    STEGASOO_API_ENABLED=true
    echo -e "  ${YELLOW}⚠${NC} REST API enabled on port 8000 ${RED}(no authentication)${NC}"
else
    STEGASOO_API_ENABLED=false
    echo -e "  ${GREEN}✓${NC} REST API not enabled (recommended)"
    echo "    Can enable later with: sudo systemctl enable --now stegasoo-api"
fi

echo -e "${GREEN}[8/9]${NC} Setting up user environment..."

# Add stegasoo venv and rpi scripts to PATH for all users
sudo tee /etc/profile.d/stegasoo-path.sh > /dev/null <<'PATHEOF'
# Stegasoo CLI and scripts
if [ -d /opt/stegasoo/venv/bin ]; then
    export PATH="/opt/stegasoo/venv/bin:$PATH"
fi
if [ -d /opt/stegasoo/rpi ]; then
    export PATH="/opt/stegasoo/rpi:$PATH"
fi
PATHEOF
sudo chmod 644 /etc/profile.d/stegasoo-path.sh
echo "  Added stegasoo to PATH"

# Install custom bashrc if not already customized
if [ -f "$INSTALL_DIR/rpi/skel/.bashrc" ]; then
    if ! grep -q "Stegasoo Pi" ~/.bashrc 2>/dev/null; then
        cp "$INSTALL_DIR/rpi/skel/.bashrc" ~/.bashrc
        source ~/.bashrc 2>/dev/null || true
        echo "  Installed custom .bashrc"
    else
        echo "  Custom .bashrc already installed"
    fi
fi

# Install man page
if [ -f "$INSTALL_DIR/docs/stegasoo.1" ]; then
    sudo mkdir -p /usr/local/share/man/man1
    sudo cp "$INSTALL_DIR/docs/stegasoo.1" /usr/local/share/man/man1/
    sudo mandb -q 2>/dev/null || true
    echo "  Installed man page (man stegasoo)"
fi

echo -e "${GREEN}[9/9]${NC} Setting up login banner..."

# Create dynamic MOTD script
sudo tee /etc/profile.d/stegasoo-motd.sh > /dev/null <<'MOTDEOF'
# Stegasoo login banner
if systemctl is-active --quiet stegasoo 2>/dev/null; then
    PI_IP=$(hostname -I | awk '{print $1}')
    # Check if HTTPS and port 443 are configured
    if systemctl show stegasoo -p Environment 2>/dev/null | grep -q "STEGASOO_HTTPS_ENABLED=true"; then
        # Check for port 443 redirect (iptables-restore service means 443 is configured)
        if systemctl is-enabled --quiet iptables-restore 2>/dev/null; then
            STEGASOO_URL="https://$PI_IP"
        else
            STEGASOO_URL="https://$PI_IP:5000"
        fi
    else
        STEGASOO_URL="http://$PI_IP:5000"
    fi
    echo ""
    echo -e "\033[38;5;93m══════════════\033[38;5;99m══════════════\033[38;5;105m══════════════\033[38;5;117m══════════════\033[0m"
    echo -e "\033[0;90m · .  · .  *  · .  *  · .  *  · .  *  · .  *  · .  ·\033[0m"
    echo -e "\033[38;5;220m    ___  _____  ___    ___    _    ___    ___    ___\033[0m"
    echo -e "\033[38;5;220m   / __||_   _|| __|  / __|  /_\\  / __|  / _ \\  / _ \\\\\033[0m"
    echo -e "\033[38;5;220m   \\__ \\  | |  | _|  | (_ | / _ \\ \\__ \\ | (_) || (_) |\033[0m"
    echo -e "\033[38;5;220m   |___/  |_|  |___|  \\___//_/ \\_\\|___/  \\___/  \\___/\033[0m"
    echo -e "\033[0;90m · .  · .  *  · .  *  · .  *  · .  *  · .  *  · .  ·\033[0m"
    echo -e "\033[38;5;93m══════════════\033[38;5;99m══════════════\033[38;5;105m══════════════\033[38;5;117m══════════════\033[0m"
    # Show CPU stats if overclocked (read configured freq, not current idle freq)
    CONFIG_FILE=""
    if [ -f /boot/firmware/config.txt ]; then CONFIG_FILE="/boot/firmware/config.txt"
    elif [ -f /boot/config.txt ]; then CONFIG_FILE="/boot/config.txt"; fi
    CPU_MHZ=""
    CPU_TEMP=""
    if [ -n "$CONFIG_FILE" ] && grep -qE "^arm_freq=" "$CONFIG_FILE" 2>/dev/null; then
        CPU_MHZ=$(grep "^arm_freq=" "$CONFIG_FILE" | cut -d= -f2)
        CPU_TEMP=$(vcgencmd measure_temp 2>/dev/null | cut -d= -f2)
    fi
    # Compact two-column layout
    echo -e " 🚀 Stegasoo running     🌐 \033[0;33m$STEGASOO_URL\033[0m"
    if [ -n "$CPU_MHZ" ] && [ -n "$CPU_TEMP" ]; then
        # Temp emoji: ice<50, cool 50-70, fire>70
        TEMP_NUM=$(echo "$CPU_TEMP" | grep -oE "[0-9]+" | head -1)
        if [ -n "$TEMP_NUM" ]; then
            if [ "$TEMP_NUM" -ge 70 ]; then
                TEMP_EMOJI="🔥"
            elif [ "$TEMP_NUM" -ge 50 ]; then
                TEMP_EMOJI="😎"
            else
                TEMP_EMOJI="🧊"
            fi
        else
            TEMP_EMOJI="🌡"
        fi
        echo -e " \033[0;35m⚡\033[0m ${CPU_MHZ} MHz             ${TEMP_EMOJI} ${CPU_TEMP}"
    fi
    echo -e "\033[38;5;93m══════════════\033[38;5;99m══════════════\033[38;5;105m══════════════\033[38;5;117m══════════════\033[0m"
    echo ""
else
    echo ""
    echo -e " \033[0;31m●\033[0m Stegasoo is not running"
    echo -e "   Start with: sudo systemctl start stegasoo"
    echo ""
fi
MOTDEOF
sudo chmod 644 /etc/profile.d/stegasoo-motd.sh
echo "  Created login banner"

# Shorten the default Debian MOTD boilerplate
echo "Debian GNU/Linux · License: /usr/share/doc/*/copyright" | sudo tee /etc/motd > /dev/null
echo "  Shortened system MOTD"

echo ""
echo -e "${BOLD}Installation Complete!${NC}"
echo -e "${BLUE}-------------------------------------------------------${NC}"
echo ""
echo -e "Stegasoo installed to: ${YELLOW}$INSTALL_DIR${NC}"
echo ""

# =============================================================================
# Interactive Configuration
# =============================================================================

echo -e "${BOLD}Configuration${NC}"
echo -e "${BLUE}-------------------------------------------------------${NC}"
echo ""

# Track configuration choices
ENABLE_HTTPS="false"
USE_PORT_443="false"
CHANNEL_KEY=""

# --- HTTPS Configuration ---
echo -e "${GREEN}HTTPS Configuration${NC}"
echo "  HTTPS encrypts traffic with a self-signed certificate."
echo "  (Browser will show a security warning - this is normal for self-signed certs)"
echo ""
read -p "Enable HTTPS? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    ENABLE_HTTPS="true"
    echo -e "  ${GREEN}✓${NC} HTTPS will be enabled"

    # --- Port 443 Configuration ---
    echo ""
    echo -e "${GREEN}Port Configuration${NC}"
    echo "  Standard HTTPS port is 443 (no port needed in URL)."
    echo "  This requires iptables to redirect 443 → 5000."
    echo ""
    read -p "Use standard port 443? [y/N] " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        USE_PORT_443="true"
        echo -e "  ${GREEN}✓${NC} Port 443 will be configured"
    else
        echo -e "  ${YELLOW}→${NC} Using default port 5000"
    fi
else
    echo -e "  ${YELLOW}→${NC} Using HTTP (unencrypted)"
fi

# --- Channel Key Configuration ---
echo ""
echo -e "${GREEN}Channel Key Configuration${NC}"
echo "  A channel key creates a private encoding channel."
echo "  Only users with the same key can decode each other's images."
echo ""
read -p "Generate a private channel key? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Generate channel key and save encrypted to config
    CHANNEL_KEY=$($INSTALL_DIR/venv/bin/python -c "
from stegasoo.channel import generate_channel_key, set_channel_key
key = generate_channel_key()
set_channel_key(key, 'user')  # Saves encrypted to ~/.stegasoo/channel.key
print(key)
")
    echo -e "  ${GREEN}✓${NC} Channel key generated: ${YELLOW}$CHANNEL_KEY${NC}"
    echo -e "  ${GREEN}✓${NC} Key saved (encrypted) to ~/.stegasoo/channel.key"
    echo ""
    echo -e "  ${RED}IMPORTANT: Save this key!${NC} You'll need to share it with anyone"
    echo "  who should be able to decode your images."
else
    echo -e "  ${YELLOW}→${NC} Using public mode (no channel isolation)"
fi

# =============================================================================
# Apply Configuration
# =============================================================================

echo ""
echo -e "${BLUE}Applying configuration...${NC}"

# Update systemd service with configuration
sudo tee /etc/systemd/system/stegasoo.service > /dev/null <<EOF
[Unit]
Description=Stegasoo Web UI
After=network.target

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR/frontends/web
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/bin"
Environment="STEGASOO_AUTH_ENABLED=true"
Environment="STEGASOO_HTTPS_ENABLED=$ENABLE_HTTPS"
Environment="STEGASOO_PORT=5000"
Environment="STEGASOO_CHANNEL_KEY=$CHANNEL_KEY"
ExecStart=$INSTALL_DIR/venv/bin/python app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Generate SSL certificates if HTTPS enabled
if [ "$ENABLE_HTTPS" = "true" ]; then
    echo "  Generating SSL certificates..."
    CERT_DIR="$INSTALL_DIR/frontends/web/certs"
    mkdir -p "$CERT_DIR"

    # Get local IP for SAN
    LOCAL_IP=$(hostname -I | awk '{print $1}')
    PI_HOSTNAME=$(hostname)

    # Try mkcert first (creates browser-trusted certs - no warning screen!)
    if command -v mkcert &> /dev/null; then
        echo "  Using mkcert for browser-trusted certificates..."
        cd "$CERT_DIR"
        mkcert -key-file server.key -cert-file server.crt \
            "$PI_HOSTNAME" "$PI_HOSTNAME.local" localhost "$LOCAL_IP" 127.0.0.1 ::1

        # Copy CA to web-accessible location for easy device setup
        CA_ROOT=$(mkcert -CAROOT)
        CA_DIR="$INSTALL_DIR/frontends/web/static/ca"
        mkdir -p "$CA_DIR"
        cp "$CA_ROOT/rootCA.pem" "$CA_DIR/"

        echo -e "  ${GREEN}✓${NC} Trusted certificates generated with mkcert"
        echo -e "  ${CYAN}Tip:${NC} New devices can get the CA from: http://$PI_HOSTNAME.local/static/ca/rootCA.pem"
    else
        # Fallback to self-signed (shows browser warning)
        echo "  Using self-signed certificate (browser will show warning)"
        echo "  Tip: Install mkcert for trusted certs without warnings"

        openssl req -x509 -newkey rsa:2048 \
          -keyout "$CERT_DIR/server.key" \
          -out "$CERT_DIR/server.crt" \
          -days 365 -nodes \
          -subj "/O=Stegasoo/CN=$PI_HOSTNAME" \
          -addext "subjectAltName=DNS:$PI_HOSTNAME,DNS:$PI_HOSTNAME.local,DNS:localhost,IP:$LOCAL_IP,IP:127.0.0.1" \
          2>/dev/null

        echo -e "  ${GREEN}✓${NC} Self-signed certificates generated"
    fi

    # Fix permissions
    chmod 600 "$CERT_DIR/server.key"
    chown -R "$USER:$USER" "$CERT_DIR"
fi

# Setup port 443 redirect if requested
if [ "$USE_PORT_443" = "true" ]; then
    echo "  Setting up port 443 redirect..."

    # Install iptables if needed
    if ! command -v iptables &> /dev/null; then
        sudo apt-get install -y iptables
    fi

    # Add redirect rule
    sudo iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 5000
    sudo sh -c 'iptables-save > /etc/iptables.rules'

    # Create systemd service to restore rules on boot
    sudo tee /etc/systemd/system/iptables-restore.service > /dev/null <<EOF
[Unit]
Description=Restore iptables rules
Before=network-pre.target

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables.rules

[Install]
WantedBy=multi-user.target
EOF
    sudo systemctl enable iptables-restore.service
    echo -e "  ${GREEN}✓${NC} Port 443 redirect configured"
fi

sudo systemctl daemon-reload

# =============================================================================
# Final Summary
# =============================================================================

echo ""
echo -e "${BOLD}Setup Complete!${NC}"
echo -e "${BLUE}-------------------------------------------------------${NC}"
echo ""

PI_IP=$(hostname -I | awk '{print $1}')
PI_HOST=$(hostname)

echo -e "${GREEN}Create your admin account:${NC}"
if [ "$ENABLE_HTTPS" = "true" ]; then
    if [ "$USE_PORT_443" = "true" ]; then
        echo -e "  ${YELLOW}https://$PI_HOST.local/setup${NC}"
        echo -e "  ${YELLOW}https://$PI_IP/setup${NC}"
    else
        echo -e "  ${YELLOW}https://$PI_HOST.local:5000/setup${NC}"
        echo -e "  ${YELLOW}https://$PI_IP:5000/setup${NC}"
    fi
else
    echo -e "  ${YELLOW}http://$PI_HOST.local:5000/setup${NC}"
    echo -e "  ${YELLOW}http://$PI_IP:5000/setup${NC}"
fi

echo ""
if [ -n "$CHANNEL_KEY" ]; then
    echo -e "${GREEN}Channel Key:${NC}"
    echo -e "  ${YELLOW}$CHANNEL_KEY${NC}"
    echo ""
fi

echo -e "${GREEN}Commands:${NC}"
echo "  Start:   sudo systemctl start stegasoo"
echo "  Stop:    sudo systemctl stop stegasoo"
echo "  Status:  sudo systemctl status stegasoo"
echo "  Logs:    journalctl -u stegasoo -f"
if [ "$STEGASOO_API_ENABLED" = "true" ]; then
    echo ""
    echo -e "${GREEN}REST API Commands:${NC}"
    echo "  Start:   sudo systemctl start stegasoo-api"
    echo "  Stop:    sudo systemctl stop stegasoo-api"
    echo "  Status:  sudo systemctl status stegasoo-api"
    echo "  Logs:    journalctl -u stegasoo-api -f"
fi
echo ""

# Offer to start now
read -p "Start Stegasoo now? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    sudo systemctl start stegasoo
    if [ "$STEGASOO_API_ENABLED" = "true" ]; then
        sudo systemctl start stegasoo-api
    fi
    sleep 2
    if systemctl is-active --quiet stegasoo; then
        echo -e "${GREEN}✓ Stegasoo Web UI is running!${NC}"
        if [ "$ENABLE_HTTPS" = "true" ]; then
            if [ "$USE_PORT_443" = "true" ]; then
                echo -e "  Create admin: ${YELLOW}https://$PI_HOST.local/setup${NC} or ${YELLOW}https://$PI_IP/setup${NC}"
            else
                echo -e "  Create admin: ${YELLOW}https://$PI_HOST.local:5000/setup${NC} or ${YELLOW}https://$PI_IP:5000/setup${NC}"
            fi
        else
            echo -e "  Create admin: ${YELLOW}http://$PI_HOST.local:5000/setup${NC} or ${YELLOW}http://$PI_IP:5000/setup${NC}"
        fi
        if [ "$STEGASOO_API_ENABLED" = "true" ]; then
            if systemctl is-active --quiet stegasoo-api; then
                echo -e "${GREEN}✓ Stegasoo REST API is running on port 8000${NC}"
            else
                echo -e "${YELLOW}⚠ REST API failed to start. Check logs:${NC} journalctl -u stegasoo-api -f"
            fi
        fi
    else
        echo -e "${RED}✗ Failed to start. Check logs:${NC} journalctl -u stegasoo -f"
    fi
fi
