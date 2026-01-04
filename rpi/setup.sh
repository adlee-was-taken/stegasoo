#!/bin/bash
#
# Stegasoo Raspberry Pi Setup Script
# Tested on: Raspberry Pi 4/5 with Raspberry Pi OS (64-bit)
#
# Usage:
#   curl -sSL https://raw.githubusercontent.com/adlee-was-taken/stegasoo/main/rpi/setup.sh | bash
#   # or
#   wget -qO- https://raw.githubusercontent.com/adlee-was-taken/stegasoo/main/rpi/setup.sh | bash
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

# Show help
show_help() {
    echo "Stegasoo Raspberry Pi Setup Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help    Show this help message"
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
    echo "    STEGASOO_BRANCH   Git branch (default: main)"
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
STEGASOO_BRANCH="${STEGASOO_BRANCH:-main}"
JPEGIO_REPO="https://github.com/dwgoon/jpegio.git"

# Load config files (system, then user - user overrides system)
for config_file in "/etc/stegasoo.conf" "$HOME/.config/stegasoo/stegasoo.conf"; do
    if [ -f "$config_file" ]; then
        # shellcheck source=/dev/null
        source "$config_file"
    fi
done

clear
echo ""
echo -e "${GRAY} . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · .${NC}"
echo -e "${GRAY} · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . ·${NC}"
echo -e "${GRAY} . · . · . · . · . · . ${CYAN}/\\\\${GRAY} · . · ${CYAN}/\\\\${GRAY} · . · ${CYAN}/\\\\${GRAY} · . · ${CYAN}/\\\\${GRAY} · . · . · . .${NC}"
echo -e "${GRAY} · . · . · . · . · . · ${CYAN}\\\\/${GRAY} · . · ${CYAN}\\\\/${GRAY} · . · ${CYAN}\\\\/${GRAY} · . · ${CYAN}\\\\/${GRAY} · . · . · . ·${NC}"
echo -e "${GRAY} . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · .${NC}"
echo -e "${GRAY} · .   ${CYAN}___  _____  ___    ___    _    ___    ___    ___${GRAY}    . · . ·${NC}"
echo -e "${GRAY} . ·  ${CYAN}/ __||_   _|| __|  / __|  /_\\\\  / __|  / _ \\\\  / _ \\\\${GRAY}   · . · ·${NC}"
echo -e "${GRAY} · .  ${CYAN}/ __||_   _|| __|  / __|  /_\\\\  / __|  / _ \\\\  / _ \\\\${GRAY}   . · . ·${NC}"
echo -e "${GRAY} . ·  ${CYAN}\\\\__ \\\\  | |  | _|  | (_ | / _ \\\\ \\\\__ \\\\ | (_) || (_) |${GRAY}  · . · ·${NC}"
echo -e "${GRAY} · .  ${CYAN}\\\\__ \\\\  | |  | _|  | (_ | / _ \\\\ \\\\__ \\\\ | (_) || (_) |${GRAY}  . · . ·${NC}"
echo -e "${GRAY} . ·  ${CYAN}|___/  |_|  |___|  \\___|/_/ \\_\\\\|___/  \\\\___/  \\\\___/${GRAY}   · . · ·${NC}"
echo -e "${GRAY} · .  ${CYAN}|___/  |_|  |___|  \\___|/_/ \\_\\\\|___/  \\\\___/  \\\\___/${GRAY}   . · . ·${NC}"
echo -e "${GRAY} · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . ·${NC}"
echo -e "${GRAY} . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · .${NC}"
echo -e "${GRAY} · . · ${CYAN}~~~~${GRAY} · . · . · . ${CYAN}Raspberry Pi Setup${GRAY} · . · . · ${CYAN}~~~~${GRAY} · . · . ·${NC}"
echo -e "${GRAY} . · . ${CYAN}~~~~${GRAY} · . · . · . · . · . · . · . · . · . · . ${CYAN}~~~~${GRAY} · . · . .${NC}"
echo -e "${GRAY} · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . ·${NC}"
echo ""
echo "  This will install Stegasoo with full DCT support"
echo "  Estimated time: 15-20 minutes on Pi 5"
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
echo -e "${GREEN}[1/7]${NC} Setting up install directory..."
if [ ! -d "$INSTALL_DIR" ]; then
    sudo mkdir -p "$INSTALL_DIR"
    sudo chown "$USER:$USER" "$INSTALL_DIR"
    echo "  Created $INSTALL_DIR"
else
    # Ensure current user owns it
    sudo chown "$USER:$USER" "$INSTALL_DIR"
    echo "  $INSTALL_DIR exists, updated ownership"
fi

echo -e "${GREEN}[2/7]${NC} Installing system dependencies..."
sudo apt-get update
sudo apt-get install -y \
    build-essential \
    git \
    curl \
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
    libjpeg-dev

echo -e "${GREEN}[3/7]${NC} Installing pyenv and Python $PYTHON_VERSION..."

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
    echo "pyenv already installed, skipping..."
    export PYENV_ROOT="$HOME/.pyenv"
    export PATH="$PYENV_ROOT/bin:$PATH"
    eval "$(pyenv init -)"
fi

# Install Python 3.12 if not present
if ! pyenv versions | grep -q "$PYTHON_VERSION"; then
    echo "Building Python $PYTHON_VERSION (this takes ~10 minutes)..."
    pyenv install $PYTHON_VERSION
fi
pyenv global $PYTHON_VERSION

# Verify Python version
INSTALLED_PY=$(python --version 2>&1 | cut -d' ' -f2 | cut -d'.' -f1,2)
if [ "$INSTALLED_PY" != "$PYTHON_VERSION" ]; then
    echo -e "${RED}Error: Python $PYTHON_VERSION not active. Got: $INSTALLED_PY${NC}"
    exit 1
fi

echo -e "${GREEN}[4/7]${NC} Building jpegio for ARM..."

# Clone jpegio
JPEGIO_DIR="/tmp/jpegio-build"
rm -rf "$JPEGIO_DIR"
git clone "$JPEGIO_REPO" "$JPEGIO_DIR"

# Apply ARM64 patch using robust patching system
# The patch script tries: 1) patch file, 2) sed, 3) python regex
if [ -f "$INSTALL_DIR/rpi/patches/jpegio/apply-patch.sh" ]; then
    bash "$INSTALL_DIR/rpi/patches/jpegio/apply-patch.sh" "$JPEGIO_DIR"
else
    # Fallback if running before stegasoo is cloned (curl install)
    echo "  Using inline patch fallback..."
    cd "$JPEGIO_DIR"
    sed -i "s/cargs.append('-m64')/pass  # ARM64 fix/g" setup.py
fi

cd "$JPEGIO_DIR"

# Build jpegio
pip install --upgrade pip setuptools wheel cython numpy
pip install .

cd "$HOME"
rm -rf "$JPEGIO_DIR"

echo -e "${GREEN}[5/7]${NC} Installing Stegasoo..."

# Clone Stegasoo
if [ -d "$INSTALL_DIR/.git" ]; then
    echo "Stegasoo directory exists, updating..."
    cd "$INSTALL_DIR"
    git fetch origin
    git checkout "$STEGASOO_BRANCH"
    git pull origin "$STEGASOO_BRANCH"
else
    git clone -b "$STEGASOO_BRANCH" "$STEGASOO_REPO" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
fi

# Create venv if needed
if [ ! -d "venv" ]; then
    python -m venv venv
fi
source venv/bin/activate

# Install dependencies (jpegio already installed globally, will be available)
pip install --upgrade pip
pip install -e ".[web]" || {
    # If full install fails (jpegio conflict), install deps manually
    pip install -e . --no-deps
    pip install argon2-cffi cryptography pillow flask gunicorn scipy numpy pyzbar qrcode
}

echo -e "${GREEN}[6/7]${NC} Creating systemd service..."

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

echo -e "${GREEN}[7/7]${NC} Enabling service..."

sudo systemctl daemon-reload
sudo systemctl enable stegasoo.service

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

echo -e "${GREEN}Your Stegasoo server:${NC}"
if [ "$ENABLE_HTTPS" = "true" ]; then
    if [ "$USE_PORT_443" = "true" ]; then
        echo -e "  ${YELLOW}https://$PI_IP${NC}"
    else
        echo -e "  ${YELLOW}https://$PI_IP:5000${NC}"
    fi
else
    echo -e "  ${YELLOW}http://$PI_IP:5000${NC}"
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
echo -e "${YELLOW}Note: On first access, you'll create an admin account.${NC}"
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
                echo -e "  Visit: ${YELLOW}https://$PI_IP${NC}"
            else
                echo -e "  Visit: ${YELLOW}https://$PI_IP:5000${NC}"
            fi
        else
            echo -e "  Visit: ${YELLOW}http://$PI_IP:5000${NC}"
        fi
    else
        echo -e "${RED}✗ Failed to start. Check logs:${NC} journalctl -u stegasoo -f"
    fi
fi
