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
NC='\033[0m' # No Color

# Configuration
INSTALL_DIR="$HOME/stegasoo"
PYTHON_VERSION="3.12"
STEGASOO_REPO="https://github.com/adlee-was-taken/stegasoo.git"
JPEGIO_REPO="https://github.com/dwgoon/jpegio.git"

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║           Stegasoo Raspberry Pi Setup Script                  ║"
echo "║                                                               ║"
echo "║   This will install Stegasoo with full DCT support            ║"
echo "║   Estimated time: 15-20 minutes on Pi 5                       ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

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

echo -e "${GREEN}[1/6]${NC} Installing system dependencies..."
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

echo -e "${GREEN}[2/6]${NC} Installing pyenv and Python $PYTHON_VERSION..."

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

echo -e "${GREEN}[3/6]${NC} Building jpegio for ARM..."

# Clone and patch jpegio
JPEGIO_DIR="/tmp/jpegio-build"
rm -rf "$JPEGIO_DIR"
git clone "$JPEGIO_REPO" "$JPEGIO_DIR"
cd "$JPEGIO_DIR"

# Patch for ARM (remove x86-specific -m64 flag)
sed -i "s/cargs.append('-m64')/pass  # ARM fix/" setup.py

# Build jpegio
pip install --upgrade pip setuptools wheel cython numpy
pip install .

cd "$HOME"
rm -rf "$JPEGIO_DIR"

echo -e "${GREEN}[4/6]${NC} Installing Stegasoo..."

# Clone Stegasoo
if [ -d "$INSTALL_DIR" ]; then
    echo "Stegasoo directory exists, updating..."
    cd "$INSTALL_DIR"
    git pull
else
    git clone "$STEGASOO_REPO" "$INSTALL_DIR"
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

echo -e "${GREEN}[5/6]${NC} Creating systemd service..."

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

echo -e "${GREEN}[6/6]${NC} Enabling service..."

sudo systemctl daemon-reload
sudo systemctl enable stegasoo.service

echo ""
echo -e "${BLUE}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║${NC}           ${GREEN}Installation Complete!${NC}                              ${BLUE}║${NC}"
echo -e "${BLUE}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Stegasoo installed to: ${YELLOW}$INSTALL_DIR${NC}"
echo ""
echo -e "${GREEN}Verify installation:${NC}"
echo "  source $INSTALL_DIR/venv/bin/activate"
echo "  python -c \"import stegasoo; print(stegasoo.__version__)\""
echo ""
echo -e "${GREEN}Start the service:${NC}"
echo "  sudo systemctl start stegasoo"
echo ""
echo -e "${GREEN}Check status:${NC}"
echo "  sudo systemctl status stegasoo"
echo ""
echo -e "${GREEN}View logs:${NC}"
echo "  journalctl -u stegasoo -f"
echo ""
echo -e "${GREEN}Access Web UI:${NC}"
PI_IP=$(hostname -I | awk '{print $1}')
echo "  http://$PI_IP:5000  (default port, configurable via STEGASOO_PORT)"
echo ""
echo -e "${YELLOW}Note: On first access, you'll be prompted to create an admin account.${NC}"
echo ""
echo -e "${GREEN}Enable HTTPS:${NC}"
echo "  sudo nano /etc/systemd/system/stegasoo.service"
echo ""
echo "  Change: Environment=\"STEGASOO_HTTPS_ENABLED=false\""
echo "  To:     Environment=\"STEGASOO_HTTPS_ENABLED=true\""
echo ""
echo "  Save (Ctrl+O, Enter, Ctrl+X), then:"
echo "    sudo systemctl daemon-reload"
echo "    sudo systemctl restart stegasoo"
echo ""
echo -e "${GREEN}Private Channel Key (optional):${NC}"
echo "  Generate a key:"
echo "    source $INSTALL_DIR/venv/bin/activate"
echo "    stegasoo generate --channel-key"
echo ""
echo "  Add to the service file (same nano command above):"
echo "    Environment=\"STEGASOO_CHANNEL_KEY=XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX\""
echo ""
echo "  This ensures only users with the same key can decode your images."
echo ""
echo -e "To start now: ${YELLOW}sudo systemctl start stegasoo${NC}"
