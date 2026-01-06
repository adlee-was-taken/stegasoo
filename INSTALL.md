# Stegasoo Installation Guide

Complete installation instructions for all platforms and deployment methods.

## Table of Contents

- [Requirements](#requirements)
- [Quick Install](#quick-install)
- [Installation Methods](#installation-methods)
  - [From Source (Development)](#from-source-development)
  - [From PyPI](#from-pypi)
  - [Docker](#docker)
  - [Docker Compose](#docker-compose)
- [Optional Dependencies](#optional-dependencies)
- [Platform-Specific Notes](#platform-specific-notes)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Requirements

### ⚠️ Python Version Requirements

| Python Version | Status | Notes |
|----------------|--------|-------|
| 3.10 | ✅ Supported | |
| 3.11 | ✅ Supported | Recommended |
| 3.12 | ✅ Supported | Recommended |
| 3.13 | ❌ **Not Supported** | jpegio C extension incompatible |

**Important:** Python 3.13 (released October 2024) is **not compatible** with jpegio due to C extension ABI changes. Use Python 3.12 or earlier.

### Minimum Requirements

| Requirement | Value |
|-------------|-------|
| Python | 3.10-3.12 |
| RAM | 512 MB minimum (256MB for Argon2) |
| Disk | ~100 MB |

### System Dependencies

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install -y \
  python3.12 \
  python3.12-venv \
  python3-pip \
  python3-dev \
  libzbar0 \
  libjpeg-dev \
  build-essential
```

**Linux (Arch):**
```bash
# Use pyenv for Python version management
curl https://pyenv.run | bash
pyenv install 3.12
pyenv local 3.12

sudo pacman -S zbar libjpeg-turbo base-devel
```

**macOS:**
```bash
brew install python@3.12 zbar jpeg
xcode-select --install  # For compilation
```

**Windows:**
- Install Python 3.12 from [python.org](https://python.org)
- Install Visual Studio Build Tools for compilation

---

## Quick Install

```bash
# Clone and install everything
git clone https://github.com/adlee-was-taken/stegasoo.git
cd stegasoo

# Create venv with Python 3.12 (critical!)
python3.12 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Install all dependencies
pip install -e ".[all]"

# Verify
stegasoo --version
python -c "from stegasoo import has_dct_support; print(f'DCT: {has_dct_support()}')"
```

---

## Installation Methods

### From Source (Development)

Best for development or customization.

```bash
# Clone the repository
git clone https://github.com/adlee-was-taken/stegasoo.git
cd stegasoo

# Create virtual environment with Python 3.12 (recommended)
python3.12 -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

# Verify Python version
python -V  # Should show 3.12.x

# Install core library only
pip install -e .

# Install with specific extras
pip install -e ".[cli]"       # Command-line interface
pip install -e ".[web]"       # Flask web UI + DCT support
pip install -e ".[api]"       # FastAPI REST API + DCT support
pip install -e ".[dct]"       # DCT steganography only
pip install -e ".[compression]"  # LZ4 compression

# Install everything
pip install -e ".[all]"

# Install with development tools
pip install -e ".[dev]"
```

### From PyPI

```bash
# Core only
pip install stegasoo

# With extras
pip install stegasoo[cli]
pip install stegasoo[web]
pip install stegasoo[api]
pip install stegasoo[all]
```

### Docker

Build and run individual containers.

#### Build Images

```bash
# Build all targets
docker build -t stegasoo-web --target web .
docker build -t stegasoo-api --target api .
docker build -t stegasoo-cli --target cli .
```

#### Run Web UI

```bash
docker run -d \
  --name stegasoo-web \
  -p 5000:5000 \
  --memory=768m \
  stegasoo-web

# Visit http://localhost:5000
```

#### Run REST API

```bash
docker run -d \
  --name stegasoo-api \
  -p 8000:8000 \
  --memory=768m \
  stegasoo-api

# Docs at http://localhost:8000/docs
```

#### Run CLI

```bash
# Interactive shell
docker run -it --rm stegasoo-cli /bin/bash

# Run commands directly
docker run --rm stegasoo-cli --help
docker run --rm stegasoo-cli generate --pin --words 4

# With volume for files
docker run --rm \
  -v $(pwd)/images:/data \
  stegasoo-cli encode \
    -r /data/ref.jpg \
    -c /data/carrier.png \
    -p "passphrase words here more" \
    --pin 123456 \
    -m "Secret message" \
    -o /data/stego.png
```

### Docker Compose

The easiest way to run all services.

#### Start All Services

```bash
# Start in background
docker-compose up -d

# Start specific service
docker-compose up -d web
docker-compose up -d api

# View logs
docker-compose logs -f

# Stop all
docker-compose down
```

#### Authentication Configuration (v4.0.2)

The Web UI supports optional authentication. Configure via environment variables:

```bash
# .env file (create in project root)
STEGASOO_AUTH_ENABLED=true      # Enable login (default: true)
STEGASOO_HTTPS_ENABLED=false    # Enable HTTPS (default: false)
STEGASOO_HOSTNAME=localhost     # Hostname for SSL cert
STEGASOO_CHANNEL_KEY=           # Optional channel key

# Then run
docker-compose up -d web
```

On first access, you'll be prompted to create an admin account. The database and SSL certs are persisted in Docker volumes.

#### Services

| Service | URL | Description |
|---------|-----|-------------|
| `web` | http://localhost:5000 | Flask Web UI |
| `api` | http://localhost:8000 | FastAPI REST API |

#### Build and Start

```bash
# Build images and start
docker-compose up -d --build

# Force rebuild (no cache)
docker-compose build --no-cache
docker-compose up -d
```

#### Resource Configuration

The `docker-compose.yml` includes resource limits:

```yaml
services:
  web:
    deploy:
      resources:
        limits:
          memory: 768M    # For Argon2 + scipy
        reservations:
          memory: 384M
```

Adjust based on your available RAM:

| Available RAM | Recommended Limit | Workers |
|---------------|-------------------|---------|
| 2 GB | 768M | 2 |
| 4 GB | 1G | 3 |
| 8 GB+ | 1.5G | 4 |

---

## Optional Dependencies

### DCT Steganography (scipy + jpegio)

DCT mode enables JPEG-resilient steganography. It's automatically included with `[web]`, `[api]`, and `[all]` extras.

#### Install via pip

```bash
# scipy is straightforward
pip install scipy numpy

# jpegio - MUST use Python 3.12 or earlier!
pip install jpegio

# If pip fails, build from source
pip install cython numpy
git clone https://github.com/dwgoon/jpegio.git
cd jpegio
python setup.py install
```

#### Linux Build Dependencies

```bash
sudo apt-get install -y \
  build-essential \
  python3-dev \
  libjpeg-dev \
  cython3
```

#### macOS Build Dependencies

```bash
brew install jpeg cython
```

#### Verify DCT Support

```python
from stegasoo import has_dct_support
from stegasoo.dct_steganography import has_jpegio_support

print(f"DCT support (scipy): {has_dct_support()}")
print(f"JPEG native (jpegio): {has_jpegio_support()}")
```

Expected output:
```
DCT support (scipy): True
JPEG native (jpegio): True
```

### Compression (lz4)

Optional LZ4 compression for messages:

```bash
pip install lz4
```

---

## Platform-Specific Notes

### Linux

Most straightforward installation. Use your package manager for system dependencies.

**Ubuntu/Debian:**
```bash
sudo apt-get install python3.12 python3.12-venv python3-dev libzbar0 libjpeg-dev
python3.12 -m venv venv
source venv/bin/activate
pip install stegasoo[all]
```

**Fedora/RHEL:**
```bash
sudo dnf install python3.12 python3-devel zbar libjpeg-devel
python3.12 -m venv venv
source venv/bin/activate
pip install stegasoo[all]
```

**Arch (using pyenv):**
```bash
# Install pyenv
curl https://pyenv.run | bash

# Add to ~/.bashrc or ~/.zshrc
export PATH="$HOME/.pyenv/bin:$PATH"
eval "$(pyenv init -)"

# Install Python 3.12
pyenv install 3.12
cd ~/Sources/stegasoo
pyenv local 3.12

# Create venv and install
python -m venv venv
source venv/bin/activate
pip install stegasoo[all]
```

### macOS

```bash
# Install Homebrew if needed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.12 zbar jpeg

# Create venv
python3.12 -m venv venv
source venv/bin/activate

# Install Stegasoo
pip install stegasoo[all]
```

**Apple Silicon (M1/M2/M3):**

jpegio may need native compilation:
```bash
# Ensure you have native Python
arch -arm64 brew install python@3.12
arch -arm64 python3.12 -m venv venv
source venv/bin/activate
pip install jpegio
```

### Windows

1. Install Python 3.12 from [python.org](https://python.org) (NOT 3.13!)
2. Install Visual Studio Build Tools
3. Install from pip:

```powershell
python -m venv venv
.\venv\Scripts\activate
pip install stegasoo[all]
```

### Raspberry Pi

Stegasoo works on Raspberry Pi 4/5 (4GB+ RAM recommended for Web UI).

#### Step 1: Install System Dependencies

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential \
  git \
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
```

#### Step 2: Install Python 3.12 via pyenv

Raspberry Pi OS ships with Python 3.13, which is **not compatible** with jpegio. Install Python 3.12:

```bash
# Install pyenv
curl https://pyenv.run | bash

# Add to ~/.bashrc
echo 'export PYENV_ROOT="$HOME/.pyenv"' >> ~/.bashrc
echo '[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"' >> ~/.bashrc
echo 'eval "$(pyenv init - bash)"' >> ~/.bashrc
source ~/.bashrc

# Install Python 3.12 (takes ~10 minutes on Pi 5)
pyenv install 3.12
pyenv global 3.12
```

#### Step 3: Build jpegio for ARM

The upstream jpegio has x86-specific build flags. Patch and build from source:

```bash
# Clone jpegio
git clone https://github.com/dwgoon/jpegio.git
cd jpegio

# Patch for ARM (removes x86-specific -m64 flag)
sed -i "s/cargs.append('-m64')/pass  # ARM fix/" setup.py

# Build and install
pip install .
cd ..
```

#### Step 4: Install Stegasoo

```bash
# Clone Stegasoo
git clone https://github.com/adlee-was-taken/stegasoo.git
cd stegasoo

# Create venv with Python 3.12
~/.pyenv/versions/3.12.*/bin/python -m venv venv
source venv/bin/activate

# Install (jpegio already installed, skip it)
pip install -e ".[web]" --no-deps
pip install argon2-cffi cryptography pillow flask gunicorn scipy numpy pyzbar qrcode
```

#### Step 5: Run the Web UI

```bash
cd frontends/web

# Optional: Enable authentication
export STEGASOO_AUTH_ENABLED=true

# Optional: Enable HTTPS for local network security
export STEGASOO_HTTPS_ENABLED=true
export STEGASOO_HOSTNAME=raspberrypi.local

# Start server
python app.py
# Access at http://<pi-ip>:5000
```

#### Verify Installation

```bash
python -c "
import stegasoo
from stegasoo.dct_steganography import has_jpegio_support
print(f'Stegasoo: {stegasoo.__version__}')
print(f'Argon2: {stegasoo.has_argon2()}')
print(f'DCT: {stegasoo.has_dct_support()}')
print(f'jpegio: {has_jpegio_support()}')
"
# Expected: All True
```

#### Notes

- **RAM**: Web UI needs ~768MB free for Argon2 + scipy operations
- **Performance**: Argon2 operations take 3-5 seconds on Pi 5 (vs ~2s on desktop)
- **Python 3.13**: Not supported due to jpegio C extension incompatibility
- **First run**: Will prompt you to create an admin account
- **HTTPS**: Generates self-signed certificate (browsers will warn)

---

## Custom SSL Certificates

By default, Stegasoo generates a self-signed certificate for HTTPS. To use your own certificate (e.g., from Let's Encrypt or your organization's CA):

### Replace Self-Signed Certificates

```bash
# Stop the service
sudo systemctl stop stegasoo

# Backup existing certs (optional)
mv /opt/stegasoo/frontends/web/certs /opt/stegasoo/frontends/web/certs.bak

# Create new certs directory
mkdir -p /opt/stegasoo/frontends/web/certs

# Copy your certificates (adjust paths as needed)
cp /path/to/your/certificate.crt /opt/stegasoo/frontends/web/certs/server.crt
cp /path/to/your/private.key /opt/stegasoo/frontends/web/certs/server.key

# Set permissions (key must be readable by service user)
chmod 600 /opt/stegasoo/frontends/web/certs/server.key
chown -R $(whoami):$(whoami) /opt/stegasoo/frontends/web/certs

# Start the service
sudo systemctl start stegasoo
```

### Generate New Self-Signed Certificate

If your certificate expires or you need to regenerate:

```bash
# Stop service
sudo systemctl stop stegasoo

# Generate new cert with SANs
CERT_DIR="/opt/stegasoo/frontends/web/certs"
LOCAL_IP=$(hostname -I | awk '{print $1}')
HOSTNAME=$(hostname)

openssl req -x509 -newkey rsa:2048 \
  -keyout "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.crt" \
  -days 365 -nodes \
  -subj "/O=Stegasoo/CN=$HOSTNAME" \
  -addext "subjectAltName=DNS:$HOSTNAME,DNS:$HOSTNAME.local,DNS:localhost,IP:$LOCAL_IP,IP:127.0.0.1"

chmod 600 "$CERT_DIR/server.key"

# Start service
sudo systemctl start stegasoo
```

### Let's Encrypt with Certbot

For publicly accessible servers:

```bash
# Install certbot
sudo apt install certbot

# Get certificate (standalone mode)
sudo certbot certonly --standalone -d yourdomain.com

# Copy to Stegasoo
sudo cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /opt/stegasoo/frontends/web/certs/server.crt
sudo cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /opt/stegasoo/frontends/web/certs/server.key
sudo chown $(whoami):$(whoami) /opt/stegasoo/frontends/web/certs/*
sudo chmod 600 /opt/stegasoo/frontends/web/certs/server.key

# Restart
sudo systemctl restart stegasoo
```

**Note:** Set up a cron job or systemd timer to copy renewed certificates and restart Stegasoo.

---

## Verification

### Check Installation

```bash
# CLI version
stegasoo --version

# Python import
python -c "import stegasoo; print(stegasoo.__version__)"

# Check Python version (must be 3.10-3.12)
python -V
```

### Check All Features

```python
#!/usr/bin/env python3
"""Verify Stegasoo installation."""

import sys

def check_feature(name, check_fn):
    try:
        result = check_fn()
        status = "✓" if result else "✗"
        print(f"  {status} {name}: {result}")
        return result
    except Exception as e:
        print(f"  ✗ {name}: Error - {e}")
        return False

print("Stegasoo Installation Check")
print("=" * 40)

# Python version check
py_version = sys.version_info
print(f"\nPython: {py_version.major}.{py_version.minor}.{py_version.micro}")
if py_version >= (3, 13):
    print("  ⚠️  WARNING: Python 3.13+ not supported!")
    print("      jpegio will not work. Use Python 3.12.")
elif py_version >= (3, 10):
    print("  ✓ Python version OK")
else:
    print("  ✗ Python 3.10+ required")

# Core
import stegasoo
print(f"\nStegasoo Version: {stegasoo.__version__}")

print("\nCore Features:")
check_feature("Argon2", lambda: stegasoo.has_argon2())
check_feature("Pillow", lambda: True)  # Required, would fail import

print("\nOptional Features:")
check_feature("DCT (scipy)", stegasoo.has_dct_support)

try:
    from stegasoo.dct_steganography import has_jpegio_support
    check_feature("JPEG native (jpegio)", has_jpegio_support)
except ImportError:
    print("  ✗ JPEG native (jpegio): Not installed")

try:
    import lz4
    check_feature("Compression (lz4)", lambda: True)
except ImportError:
    print("  - Compression (lz4): Not installed (optional)")

try:
    import pyzbar
    check_feature("QR codes (pyzbar)", lambda: True)
except ImportError:
    print("  - QR codes (pyzbar): Not installed (optional)")

print("\nInterfaces:")
try:
    import click
    check_feature("CLI", lambda: True)
except ImportError:
    print("  ✗ CLI: Not installed")

try:
    import flask
    check_feature("Web UI", lambda: True)
except ImportError:
    print("  - Web UI: Not installed")

try:
    import fastapi
    check_feature("REST API", lambda: True)
except ImportError:
    print("  - REST API: Not installed")

print("\n" + "=" * 40)
print("Installation check complete!")
```

Save as `check_install.py` and run:
```bash
python check_install.py
```

### Test Encoding/Decoding

```bash
# Quick test with CLI
stegasoo generate --pin --words 4 --json > /tmp/creds.json

# Create test image
python -c "
from PIL import Image
img = Image.new('RGB', (256, 256), 'blue')
img.save('/tmp/test_carrier.png')
img.save('/tmp/test_ref.jpg')
"

# Encode
stegasoo encode \
  -r /tmp/test_ref.jpg \
  -c /tmp/test_carrier.png \
  -p "test phrase words here" \
  --pin 123456 \
  -m "Hello, Stegasoo!" \
  -o /tmp/test_stego.png

# Decode
stegasoo decode \
  -r /tmp/test_ref.jpg \
  -s /tmp/test_stego.png \
  -p "test phrase words here" \
  --pin 123456
```

---

## Troubleshooting

### Common Issues

#### "jpegio crashes" / "free(): invalid size" / Core dump

**This is the #1 issue!** You're using Python 3.13.

```bash
# Check your Python version
python -V

# If it shows 3.13, you need to use 3.12
# Option 1: Use pyenv
pyenv install 3.12
pyenv local 3.12

# Option 2: Use system Python 3.12
python3.12 -m venv venv
source venv/bin/activate
pip install -e ".[all]"
```

#### "No module named 'stegasoo'"

```bash
# Ensure you're in the right environment
which python
pip list | grep stegasoo

# Reinstall
pip install -e ".[all]"
```

#### "Argon2 not available"

```bash
# Install argon2-cffi
pip install argon2-cffi

# On Linux, may need:
sudo apt-get install libffi-dev
pip install --force-reinstall argon2-cffi
```

#### "jpegio not available" (not crash, just missing)

```bash
# Install build dependencies first
sudo apt-get install libjpeg-dev  # Linux
brew install jpeg                  # macOS

# Then install jpegio
pip install cython numpy
pip install jpegio

# If still fails, build from source
git clone https://github.com/dwgoon/jpegio.git
cd jpegio
python setup.py install
```

#### "libzbar not found" (QR codes)

```bash
# Linux
sudo apt-get install libzbar0

# macOS
brew install zbar

# Then reinstall pyzbar
pip install --force-reinstall pyzbar
```

#### Docker: "Cannot allocate memory"

Argon2 needs 256MB per operation. Increase container memory:

```bash
# Docker run
docker run --memory=768m ...

# Docker Compose - edit docker-compose.yml
deploy:
  resources:
    limits:
      memory: 768M
```

#### Slow performance

- **Argon2 is intentionally slow** - This is a security feature
- Expected encode/decode time: 2-5 seconds
- DCT mode adds ~1-2 seconds for transforms
- Large images (10MB+) may take 15-30 seconds

#### "Carrier image too small"

- LSB needs ~3 bits per pixel
- DCT needs ~0.25 bits per pixel
- For 50KB message: LSB needs ~136K pixels, DCT needs ~1.6M pixels
- Use larger carrier images or shorter messages

### Getting Help

1. Check the documentation:
   - [README.md](README.md)
   - [CLI.md](CLI.md)
   - [API.md](API.md)
   - [WEB_UI.md](WEB_UI.md)

2. Check existing issues on GitHub

3. Open a new issue with:
   - Python version (`python --version`)
   - OS and version
   - Installation method
   - Full error message
   - Steps to reproduce

---

## Next Steps

After installation:

1. **Generate credentials**: `stegasoo generate --pin --words 4`
2. **Read the CLI docs**: [CLI.md](CLI.md)
3. **Try the Web UI**: `cd frontends/web && python app.py`
4. **Explore the API**: `cd frontends/api && python main.py`

Happy steganography! 🦕
