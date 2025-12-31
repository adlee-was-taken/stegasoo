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
  - [DCT Steganography (scipy + jpegio)](#dct-steganography-scipy--jpegio)
  - [Compression (lz4)](#compression-lz4)
- [Platform-Specific Notes](#platform-specific-notes)
- [Verification](#verification)
- [Troubleshooting](#troubleshooting)

---

## Requirements

### Minimum Requirements

| Requirement | Version |
|-------------|---------|
| Python | 3.10+ |
| RAM | 512 MB minimum (256MB for Argon2) |
| Disk | ~100 MB |

### System Dependencies

**Linux (Debian/Ubuntu):**
```bash
sudo apt-get update
sudo apt-get install -y \
  python3 \
  python3-pip \
  python3-dev \
  libzbar0 \
  libjpeg-dev \
  build-essential
```

**macOS:**
```bash
brew install python@3.11 zbar jpeg
xcode-select --install  # For compilation
```

**Windows:**
- Install Python 3.10+ from [python.org](https://python.org)
- Install Visual Studio Build Tools for compilation

---

## Quick Install

```bash
# Clone and install everything
git clone https://github.com/adlee-was-taken/stegasoo.git
cd stegasoo
pip install -e ".[all]"

# Verify
stegasoo --version
```

---

## Installation Methods

### From Source (Development)

Best for development or customization.

```bash
# Clone the repository
git clone https://github.com/adlee-was-taken/stegasoo.git
cd stegasoo

# Create virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # Linux/macOS
# or: venv\Scripts\activate  # Windows

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
docker run --rm stegasoo-cli generate --pin --words 3

# With volume for files
docker run --rm \
  -v $(pwd)/images:/data \
  stegasoo-cli encode \
    -r /data/ref.jpg \
    -c /data/carrier.png \
    -p "phrase words here" \
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

#### Development Mode

For development with hot-reload:

```bash
# Create docker-compose.override.yml
cat > docker-compose.override.yml << 'EOF'
version: '3.8'
services:
  web:
    volumes:
      - ./src:/app/src:ro
      - ./frontends/web:/app/frontends/web:ro
    environment:
      - FLASK_ENV=development
    command: ["python", "app.py"]
  api:
    volumes:
      - ./src:/app/src:ro
      - ./frontends/api:/app/frontends/api:ro
    command: ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]
EOF

# Start with override
docker-compose up
```

#### Production with Nginx

For production deployment with SSL:

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  web:
    build:
      context: .
      target: web
    expose:
      - "5000"
    restart: always

  api:
    build:
      context: .
      target: api
    expose:
      - "8000"
    restart: always

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf:ro
      - ./certs:/etc/nginx/certs:ro
    depends_on:
      - web
      - api
    restart: always
```

Run with:
```bash
docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
```

---

## Optional Dependencies

### DCT Steganography (scipy + jpegio)

DCT mode enables JPEG-resilient steganography. It's automatically included with `[web]`, `[api]`, and `[all]` extras.

#### Install via pip

```bash
# scipy is straightforward
pip install scipy

# jpegio - try pip first
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
sudo apt-get install python3-dev libzbar0 libjpeg-dev
pip install stegasoo[all]
```

**Fedora/RHEL:**
```bash
sudo dnf install python3-devel zbar libjpeg-devel
pip install stegasoo[all]
```

**Arch:**
```bash
sudo pacman -S python zbar libjpeg-turbo
pip install stegasoo[all]
```

### macOS

```bash
# Install Homebrew if needed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install python@3.11 zbar jpeg

# Install Stegasoo
pip3 install stegasoo[all]
```

**Apple Silicon (M1/M2/M3):**

jpegio may need Rosetta or native compilation:
```bash
# Try native first
pip install jpegio

# If fails, ensure you have native Python
arch -arm64 brew install python@3.11
arch -arm64 pip3 install jpegio
```

### Windows

1. Install Python 3.10+ from [python.org](https://python.org)
2. Install Visual Studio Build Tools
3. Install from pip:

```powershell
pip install stegasoo[all]
```

**For jpegio on Windows:**
```powershell
# May need pre-built wheel
pip install jpegio

# If fails, install build tools and compile
pip install cython numpy
git clone https://github.com/dwgoon/jpegio.git
cd jpegio
python setup.py install
```

### Raspberry Pi

Stegasoo works on Raspberry Pi 4 (2GB+ RAM recommended):

```bash
# System dependencies
sudo apt-get install python3-dev libzbar0 libjpeg-dev

# Install (may take a while to compile)
pip install stegasoo[cli]

# For web/api, ensure enough RAM
pip install stegasoo[web]  # Needs ~768MB free
```

**Note:** Argon2 operations will be slower on Pi due to memory-hardness.

---

## Verification

### Check Installation

```bash
# CLI version
stegasoo --version

# Python import
python -c "import stegasoo; print(stegasoo.__version__)"
```

### Check All Features

```python
#!/usr/bin/env python3
"""Verify Stegasoo installation."""

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

# Core
import stegasoo
print(f"\nVersion: {stegasoo.__version__}")

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
stegasoo generate --pin --words 3 --json > /tmp/creds.json

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
  -p "test phrase words" \
  --pin 123456 \
  -m "Hello, Stegasoo!" \
  -o /tmp/test_stego.png

# Decode
stegasoo decode \
  -r /tmp/test_ref.jpg \
  -s /tmp/test_stego.png \
  -p "test phrase words" \
  --pin 123456
```

---

## Troubleshooting

### Common Issues

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

#### "jpegio not available" / DCT JPEG fails

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

#### Docker: Build fails on jpegio

The Dockerfile includes jpegio build dependencies. If still failing:

```bash
# Rebuild without cache
docker-compose build --no-cache

# Or build manually
docker build --no-cache -t stegasoo-web --target web .
```

#### Slow performance

- **Argon2 is intentionally slow** - This is a security feature
- Expected encode/decode time: 2-5 seconds
- DCT mode adds ~1-2 seconds for transforms

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

1. **Generate credentials**: `stegasoo generate --pin --words 3`
2. **Read the CLI docs**: [CLI.md](CLI.md)
3. **Try the Web UI**: `cd frontends/web && python app.py`
4. **Explore the API**: `cd frontends/api && python main.py`

Happy steganography! 🦕
