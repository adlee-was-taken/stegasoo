#!/bin/bash
#
# Stegasoo Raspberry Pi Setup Script
# Tested on: Raspberry Pi 4/5 with Raspberry Pi OS (64-bit)
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/adlee-was-taken/stegasoo/4.1/rpi/setup.sh | bash
#   # or
#   wget -qO- https://raw.githubusercontent.com/adlee-was-taken/stegasoo/4.1/rpi/setup.sh | bash
#
# What this script does:
#   1. Installs system dependencies
#   2. Installs Python 3.12 via pyenv (Pi OS ships with 3.13 which is incompatible)
#   3. Patches and builds jpegio for ARM
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
    echo "    PYTHON_VERSION    Python version (default: 3.12)"
    echo "    STEGASOO_REPO     Git repo URL"
    echo "    STEGASOO_BRANCH   Git branch (default: 4.1)"
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
PYTHON_VERSION="${PYTHON_VERSION:-3.12}"
STEGASOO_REPO="${STEGASOO_REPO:-https://github.com/adlee-was-taken/stegasoo.git}"
STEGASOO_BRANCH="${STEGASOO_BRANCH:-4.1}"
JPEGIO_REPO="https://github.com/dwgoon/jpegio.git"

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
echo "  Estimated time: ~2 minutes (pre-built) or 15-20 min (from source)"
echo ""

# Check if running on ARM
ARCH=$(uname -m)
if [[ "$ARCH" != "aarch64" && "$ARCH" != "arm64" ]]; then
    echo -e "${RED}Error: This script is for ARM64 systems (Raspberry Pi).${NC}"
    echo "Detected architecture: $ARCH"
    exit 1
fi

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

# Create /opt/stegasoo with proper permissions
echo -e "${GREEN}[1/12]${NC} Setting up install directory..."
if [ ! -d "$INSTALL_DIR" ]; then
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$USER:$USER" "$INSTALL_DIR"
    echo "  Created $INSTALL_DIR"
else
    # Ensure current user owns it
    sudo chown "$USER:$USER" "$INSTALL_DIR"
    echo "  $INSTALL_DIR exists, updated ownership"
fi

echo -e "${GREEN}[2/12]${NC} Installing system dependencies..."
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
    btop

echo -e "${GREEN}[3/12]${NC} Installing gum (TUI toolkit)..."
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

echo -e "${GREEN}[4/12]${NC} Cloning Stegasoo..."

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

# Pre-built environment tarball (skips 20+ min compile time)
# Includes both pyenv Python 3.12 AND venv with all dependencies
PREBUILT_TARBALL="$INSTALL_DIR/rpi/stegasoo-pi-arm64.tar.zst"
PREBUILT_URL="${PREBUILT_URL:-https://github.com/adlee-was-taken/stegasoo/releases/download/v4.1.3/stegasoo-pi-arm64.tar.zst}"
USE_PREBUILT=true

# Use local tarball if present, otherwise will download
if [ -f "$PREBUILT_TARBALL" ]; then
    echo -e "${GREEN}Found local pre-built environment - fast install mode${NC}"
else
    echo -e "${GREEN}Will download pre-built environment - fast install mode${NC}"
fi

# Allow --no-prebuilt flag to force from-source build
if [[ " $* " =~ " --no-prebuilt " ]] || [[ " $* " =~ " --from-source " ]]; then
    USE_PREBUILT=false
    echo -e "${YELLOW}Building from source (--no-prebuilt specified)${NC}"
fi

# Fast path: use pre-built environment if available
if [ "$USE_PREBUILT" = true ]; then
    echo -e "${GREEN}[5/8]${NC} Installing pre-built Python environment..."

    # Download if local file doesn't exist
    if [ ! -f "$PREBUILT_TARBALL" ]; then
        echo "  Downloading pre-built environment (~50MB)..."
        curl -L -o "$PREBUILT_TARBALL" "$PREBUILT_URL"
    fi

    # Extract pre-built environment (includes pyenv Python + venv)
    echo "  Extracting pre-built environment..."
    zstd -d "$PREBUILT_TARBALL" --stdout | tar -xf - -C "$HOME"

    # Setup pyenv in current shell
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
    pyenv global $PYTHON_VERSION

    # Add to .bashrc if not already there
    if ! grep -q 'PYENV_ROOT' ~/.bashrc; then
        echo '' >> ~/.bashrc
        echo '# pyenv' >> ~/.bashrc
        echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
        echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
        echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc
    fi

    # Verify Python
    INSTALLED_PY=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo -e "  ${GREEN}✓${NC} Python: $INSTALLED_PY"

    # Extract venv to install dir
    echo -e "${GREEN}[6/8]${NC} Setting up virtual environment..."
    if [ -f "$HOME/stegasoo-venv.tar.zst" ]; then
        zstd -d "$HOME/stegasoo-venv.tar.zst" --stdout | tar -xf - -C "$INSTALL_DIR"
        rm "$HOME/stegasoo-venv.tar.zst"
    fi

    # Activate and verify
    source "$INSTALL_DIR/venv/bin/activate"
    VENV_PY=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo -e "  ${GREEN}✓${NC} venv Python: $VENV_PY"

    # Install stegasoo package in editable mode (quick, no compile)
    echo -e "${GREEN}[7/8]${NC} Installing Stegasoo package..."
    pip install -e "." --quiet

    # Adjust step numbers for rest of script
    STEP_OFFSET=-4
else
    echo -e "${GREEN}[5/12]${NC} Installing pyenv and Python $PYTHON_VERSION..."

    # Install pyenv if not present
    if [ ! -d "$HOME/.pyenv" ]; then
        curl https://pyenv.run | bash

        # Add pyenv to current shell
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"

        # Add to .bashrc if not already there
        if ! grep -q 'PYENV_ROOT' ~/.bashrc; then
            echo '' >> ~/.bashrc
            echo '# pyenv' >> ~/.bashrc
            echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
            echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
            echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc
        fi
    else
        echo "  pyenv already installed"
        export PYENV_ROOT="$HOME/.pyenv"
        export PATH="$PYENV_ROOT/bin:$PATH"
        eval "$(pyenv init -)"
    fi

    # Install Python 3.12 if not present
    if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
        echo "  Building Python $PYTHON_VERSION (this takes ~10 minutes)..."
        pyenv install $PYTHON_VERSION
    else
        echo "  Python $PYTHON_VERSION already installed"
    fi
    pyenv global $PYTHON_VERSION

    # Verify Python version
    INSTALLED_PY=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    if [ "$INSTALLED_PY" != "$PYTHON_VERSION" ]; then
        echo -e "${RED}Error: Python $PYTHON_VERSION not active. Got: $INSTALLED_PY${NC}"
        exit 1
    fi
    echo -e "${GREEN}[6/12]${NC} Creating Python virtual environment..."
    echo -e "  ${YELLOW}Note: No pre-built venv found. Building from source (20+ min)${NC}"
    echo -e "  ${YELLOW}To speed up future installs, add stegasoo-venv-pi-arm64.tar.gz to rpi/${NC}"

    # Create venv with pyenv Python (not system Python)
    # Use pyenv which to get actual path (handles 3.12 -> 3.12.12 mapping)
    PYENV_PYTHON=$(pyenv which python)
    echo "  Using Python: $PYENV_PYTHON"
    if [ ! -d "venv" ]; then
        "$PYENV_PYTHON" -m venv venv
    fi
    source venv/bin/activate

    # Verify we're using the right Python
    VENV_PY=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
    echo "  venv Python: $VENV_PY"

    echo -e "${GREEN}[7/12]${NC} Building jpegio for ARM..."

    # Clone jpegio
    JPEGIO_DIR="/tmp/jpegio-build"
    rm -rf "$JPEGIO_DIR"
    git clone "$JPEGIO_REPO" "$JPEGIO_DIR"

    # Apply ARM64 patch
    if [ -f "$INSTALL_DIR/rpi/patches/jpegio/apply-patch.sh" ]; then
        bash "$INSTALL_DIR/rpi/patches/jpegio/apply-patch.sh" "$JPEGIO_DIR"
    else
        echo "  Applying inline ARM64 patch..."
        sed -i "s/cargs.append('-m64')/pass  # ARM64 fix/g" "$JPEGIO_DIR/setup.py"
    fi

    cd "$JPEGIO_DIR"

    # Build jpegio into venv
    pip install --upgrade pip setuptools wheel cython numpy
    pip install .

    cd "$INSTALL_DIR"
    rm -rf "$JPEGIO_DIR"

    echo -e "${GREEN}[8/12]${NC} Installing Stegasoo..."

    # Install dependencies (jpegio already in venv, won't re-download)
    pip install -e ".[web]"

    STEP_OFFSET=0
fi

echo -e "${GREEN}[9/12]${NC} Creating systemd service..."

# Create systemd service file
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

echo -e "${GREEN}[10/12]${NC} Enabling service..."

sudo systemctl daemon-reload
sudo systemctl enable stegasoo.service

echo -e "${GREEN}[11/12]${NC} Setting up user environment..."

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

echo -e "${GREEN}[12/12]${NC} Setting up login banner..."

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
    echo -e " 🚀 Stegasoo running    🔗 \033[0;33m$STEGASOO_URL\033[0m"
    if [ -n "$CPU_MHZ" ] && [ -n "$CPU_TEMP" ]; then
        echo -e " \033[0;35m⚡\033[0m ${CPU_MHZ} MHz             \033[0;35m🌡\033[0m ${CPU_TEMP}"
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
    # Generate channel key using the CLI
    CHANNEL_KEY=$($INSTALL_DIR/venv/bin/python -c "from stegasoo.channel import generate_channel_key; print(generate_channel_key())")
    echo -e "  ${GREEN}✓${NC} Channel key generated: ${YELLOW}$CHANNEL_KEY${NC}"
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

    # Generate cert with SANs for IP, hostname, and localhost
    openssl req -x509 -newkey rsa:2048 \
      -keyout "$CERT_DIR/server.key" \
      -out "$CERT_DIR/server.crt" \
      -days 365 -nodes \
      -subj "/O=Stegasoo/CN=$PI_HOSTNAME" \
      -addext "subjectAltName=DNS:$PI_HOSTNAME,DNS:$PI_HOSTNAME.local,DNS:localhost,IP:$LOCAL_IP,IP:127.0.0.1" \
      2>/dev/null

    # Fix permissions
    chmod 600 "$CERT_DIR/server.key"
    chown -R "$USER:$USER" "$CERT_DIR"
    echo -e "  ${GREEN}✓${NC} SSL certificates generated"
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
echo ""

# Offer to start now
read -p "Start Stegasoo now? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    sudo systemctl start stegasoo
    sleep 2
    if systemctl is-active --quiet stegasoo; then
        echo -e "${GREEN}✓ Stegasoo is running!${NC}"
        if [ "$ENABLE_HTTPS" = "true" ]; then
            if [ "$USE_PORT_443" = "true" ]; then
                echo -e "  Create admin: ${YELLOW}https://$PI_HOST.local/setup${NC} or ${YELLOW}https://$PI_IP/setup${NC}"
            else
                echo -e "  Create admin: ${YELLOW}https://$PI_HOST.local:5000/setup${NC} or ${YELLOW}https://$PI_IP:5000/setup${NC}"
            fi
        else
            echo -e "  Create admin: ${YELLOW}http://$PI_HOST.local:5000/setup${NC} or ${YELLOW}http://$PI_IP:5000/setup${NC}"
        fi
    else
        echo -e "${RED}✗ Failed to start. Check logs:${NC} journalctl -u stegasoo -f"
    fi
fi
