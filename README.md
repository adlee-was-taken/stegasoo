# Stegasoo

A secure steganography system for hiding encrypted messages in images using hybrid authentication.

![Python](https://img.shields.io/badge/Python-3.10--3.12-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Security](https://img.shields.io/badge/Security-AES--256--GCM-red)
![Version](https://img.shields.io/badge/Version-4.0.1-purple)

## Features

- 🔐 **AES-256-GCM** authenticated encryption
- 🧠 **Argon2id** memory-hard key derivation (256MB RAM requirement)
- 🎲 **Pseudo-random pixel selection** defeats steganalysis
- 🔑 **Multi-factor authentication**: PIN, RSA key, or both
- 🖼️ **Reference photo** as "something you have"
- 🌐 **Multiple interfaces**: CLI, Web UI, REST API
- 📁 **File embedding** - Hide any file type (PDF, ZIP, documents)
- 📱 **QR code support** - Encode/decode RSA keys via QR codes
- 🆕 **DCT steganography** - JPEG-resilient embedding for social media
- 🆕 **Large image support** - Process images up to 14MB+

## What's New in v4.0.0

| Feature | Description |
|---------|-------------|
| **Simplified Auth** | Removed date dependency - encode/decode anytime without tracking dates |
| **Passphrase** | Renamed from "day phrase" to "passphrase" (no more daily rotation) |
| **Python 3.12** | Requires Python 3.10-3.12 (jpegio incompatible with 3.13) |
| **Large Image Fix** | JPEG normalization prevents crashes with quality=100 images |
| **Subprocess Isolation** | WebUI runs encode/decode in subprocesses for stability |
| **4-Word Default** | Default passphrase increased from 3 to 4 words |

### Breaking Changes from v3.x

- `day_phrase` parameter renamed to `passphrase` in all APIs
- `date_str` parameter removed from encode/decode functions
- Python 3.13 not supported (jpegio C extension incompatibility)

### Embedding Mode Comparison

| Mode | Capacity (1080p) | JPEG Resilient | Best For |
|------|------------------|----------------|----------|
| **DCT** (default) | ~150 KB | ✅ Yes | Social media, messaging apps |
| **LSB** | ~750 KB | ❌ No | Email, file transfer |

## WebUI Preview

| Front Page | Encode | Decode | Generate |
|:----------:|:------:|:------:|:--------:|
| ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI.webp) | ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI_Encode.webp) | ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI_Decode.webp) | ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI_Generate.webp) |

## Quick Start

```bash
# Install with all features (requires Python 3.10-3.12)
pip install -e ".[all]"

# Generate credentials (memorize these!)
stegasoo generate --pin --words 4

# Encode a message (DCT mode - default, best for social media)
stegasoo encode \
  --ref photo.jpg \
  --carrier meme.jpg \
  --passphrase "apple forest thunder mountain" \
  --pin 123456 \
  --message "Secret message"

# Encode with LSB mode (higher capacity, for email/file transfer)
stegasoo encode \
  --ref photo.jpg \
  --carrier meme.png \
  --passphrase "apple forest thunder mountain" \
  --pin 123456 \
  --message "Secret message" \
  --mode lsb

# Decode (auto-detects mode)
stegasoo decode \
  --ref photo.jpg \
  --stego stego.png \
  --passphrase "apple forest thunder mountain" \
  --pin 123456
```

For detailed installation instructions, see **[INSTALL.md](INSTALL.md)**.

---

## Security Model

Stegasoo uses multiple authentication factors combined with strong cryptography:

```
┌─────────────────────────────────────────────────────────────────┐
│                    AUTHENTICATION LAYERS                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   Reference Photo ──┐                                           │
│   (~80-256 bits)    │                                           │
│                     ├──► Argon2id KDF ──► AES-256-GCM Key       │
│   Passphrase ───────┤    (256MB RAM)                            │
│   (~43-132 bits)    │                                           │
│                     │                                           │
│   Static PIN ───────┤                                           │
│   (~20-30 bits)     │                                           │
│                     │                                           │
│   RSA Key ──────────┘                                           │
│   (~128 bits)       (optional, adds another factor)             │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Entropy Summary

| Component | Entropy | Purpose |
|-----------|---------|---------|
| Reference Photo | ~80-256 bits | Something you have |
| Passphrase (3-12 words) | ~33-132 bits | Something you know |
| PIN (6-9 digits) | ~20-30 bits | Something you know |
| RSA Key (2048-4096 bit) | ~112-128 bits | Something you have (optional) |
| **Combined** | **133-400+ bits** | **Beyond brute force** |

### Attack Resistance

| Attack | Protection |
|--------|------------|
| Brute force | 2^133+ combinations minimum |
| Rainbow tables | Random 16-byte salt per message |
| Steganalysis | Pseudo-random pixel/coefficient selection |
| GPU cracking | Argon2id requires 256MB RAM per attempt |
| Side-channel | Constant-time operations in cryptography library |
| JPEG recompression | DCT mode embeds in frequency domain |

### Security Configurations

| Configuration | Entropy | Use Case |
|--------------|---------|----------|
| 3-word passphrase + 6-digit PIN | ~133 bits | Casual private messaging |
| 4-word passphrase + 9-digit PIN | ~176 bits | Standard security (recommended) |
| 4-word passphrase + RSA 2048 | ~241 bits | File-based authentication |
| 6-word passphrase + PIN + RSA 4096 | ~304 bits | Maximum security |

---

## Interfaces

### Command-Line Interface (CLI)

Full-featured CLI with piping support:

```bash
# Generate with RSA key
stegasoo generate --rsa --rsa-bits 4096 -o mykey.pem -p "password"

# Encode (DCT mode is now default)
stegasoo encode -r ref.jpg -c carrier.jpg -p "passphrase words here" --pin 123456 -m "Message"

# Encode with LSB mode for higher capacity
stegasoo encode -r ref.jpg -c carrier.png -p "passphrase words here" --pin 123456 \
  -m "Message" --mode lsb

# Encode a file
stegasoo encode -r ref.jpg -c carrier.png -p "passphrase words here" --pin 123456 -f secret.txt

# Decode to stdout (quiet mode)
stegasoo decode -r ref.jpg -s stego.png -p "passphrase words here" --pin 123456 -q

# Compare LSB vs DCT capacity for an image
stegasoo compare carrier.png

# Check available modes
stegasoo modes
```

📖 Full documentation: **[CLI.md](CLI.md)**

### Web UI

Browser-based interface with drag-and-drop uploads:

```bash
# Start the server
cd frontends/web
python app.py
# Visit http://localhost:5000
```

Features:
- Drag-and-drop image uploads with scan animations
- Real-time entropy calculator
- Native mobile sharing (Web Share API)
- DCT mode default with compact mode selector
- Subprocess isolation for stability
- Large image support (14MB+ tested)
- Streamlined form flow (v3.3.0)

📖 Full documentation: **[WEB_UI.md](WEB_UI.md)**

### REST API

FastAPI-powered REST API with OpenAPI documentation:

```bash
# Start the server
cd frontends/api
uvicorn main:app --host 0.0.0.0 --port 8000
# Docs at http://localhost:8000/docs
```

Example API calls:

```bash
# Generate credentials
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"use_pin": true, "passphrase_words": 4}'

# Encode (DCT mode is default)
curl -X POST http://localhost:8000/encode/multipart \
  -F "message=Secret" \
  -F "passphrase=apple forest thunder mountain" \
  -F "pin=123456" \
  -F "reference_photo=@photo.jpg" \
  -F "carrier=@meme.jpg" \
  --output stego.jpg

# Encode with LSB mode
curl -X POST http://localhost:8000/encode/multipart \
  -F "message=Secret" \
  -F "passphrase=apple forest thunder mountain" \
  -F "pin=123456" \
  -F "embed_mode=lsb" \
  -F "reference_photo=@photo.jpg" \
  -F "carrier=@meme.png" \
  --output stego.png

# Decode (auto-detects mode)
curl -X POST http://localhost:8000/decode/multipart \
  -F "passphrase=apple forest thunder mountain" \
  -F "pin=123456" \
  -F "reference_photo=@photo.jpg" \
  -F "stego_image=@stego.jpg"
```

📖 Full documentation: **[API.md](API.md)**

---

## Project Structure

```
stegasoo/
├── src/stegasoo/           # Core library
│   ├── __init__.py         # Public API
│   ├── constants.py        # Configuration
│   ├── crypto.py           # Encryption/decryption
│   ├── steganography.py    # LSB image embedding
│   ├── dct_steganography.py # DCT embedding
│   ├── keygen.py           # Credential generation
│   ├── validation.py       # Input validation
│   ├── models.py           # Data classes
│   ├── exceptions.py       # Custom exceptions
│   ├── qr_utils.py         # QR code utilities
│   └── utils.py            # Utilities
│
├── frontends/
│   ├── web/                # Flask web UI
│   │   ├── app.py
│   │   ├── subprocess_stego.py  # Subprocess isolation
│   │   └── stego_worker.py      # Worker script
│   ├── cli/                # Command-line interface
│   └── api/                # FastAPI REST API
│
├── data/
│   └── bip39-words.txt     # BIP-39 wordlist
│
├── pyproject.toml          # Package configuration
├── requirements.txt        # Dependencies
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Container orchestration
│
├── README.md               # This file
├── INSTALL.md              # Installation guide
├── CLI.md                  # CLI documentation
├── API.md                  # API documentation
├── WEB_UI.md               # Web UI documentation
├── SECURITY.md             # Security documentation
└── UNDER_THE_HOOD.md       # Technical deep-dive
```

---

## Requirements

| Requirement | Version | Notes |
|-------------|---------|-------|
| Python | 3.10-3.12 | **3.13 not supported** (jpegio incompatibility) |
| RAM | 512 MB+ | 256MB for Argon2 operations |
| Disk | ~100 MB | |

### Key Dependencies

| Package | Purpose |
|---------|---------|
| `cryptography` | AES-256-GCM encryption |
| `Pillow` | Image processing |
| `argon2-cffi` | Memory-hard key derivation |
| `scipy` | DCT transforms |
| `jpegio` | JPEG coefficient manipulation |
| `numpy` | Array operations |

---

## Configuration

### Limits

| Limit | Value |
|-------|-------|
| Max image size | Tested up to 14MB |
| Max message size | 50 KB |
| Max file upload | 5 MB |
| PIN length | 6-9 digits |
| Passphrase length | 3-12 words |
| RSA key sizes | 2048, 3072, 4096 bits |

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | production | Flask environment |
| `PYTHONPATH` | - | Include `src/` for development |

---

## Development

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/ frontends/
ruff check src/ frontends/

# Type checking
mypy src/

# Check DCT support
python -c "from stegasoo import has_dct_support; print(f'DCT: {has_dct_support()}')"
python -c "from stegasoo.dct_steganography import has_jpegio_support; print(f'jpegio: {has_jpegio_support()}')"
```

---

## Version History

| Version | Changes |
|---------|---------|
| **4.0.1** | Lint cleanup, test fixes, Web UI improvements (channel key dropdown, LED indicators) |
| **4.0.0** | Channel key support for deployment isolation, removed date dependency, renamed day_phrase→passphrase, Python 3.12 requirement, JPEG normalization fix, subprocess isolation, large image support |
| **3.2.x** | DCT color mode, JPEG output fixes |
| **3.0.x** | Added DCT steganography mode |
| **2.2.x** | QR code support, file embedding |
| **2.0.x** | Web UI, REST API, RSA keys |
| **1.0.x** | Initial release, CLI only |

---

## Upgrading from v3.x

### Code Changes Required

```python
# Old (v3.x)
result = encode(
    message="secret",
    day_phrase="apple forest thunder",
    date_str="2024-01-15",
    ...
)

# New (v4.0)
result = encode(
    message="secret",
    passphrase="apple forest thunder mountain",
    # No date_str needed!
    ...
)
```

### CLI Changes

```bash
# Old (v3.x)
stegasoo encode --phrase "words" --date 2024-01-15 ...

# New (v4.0)
stegasoo encode --passphrase "words here more" ...
# or short form
stegasoo encode -p "words here more" ...
```

---

## License

MIT License - Use responsibly.

---

## ⚠️ Disclaimer

This tool is for educational and legitimate privacy purposes only. Users are responsible for complying with applicable laws in their jurisdiction.

---

## See Also

- **[INSTALL.md](INSTALL.md)** - Detailed installation instructions
- **[CLI.md](CLI.md)** - Command-line interface reference
- **[API.md](API.md)** - REST API documentation
- **[WEB_UI.md](WEB_UI.md)** - Web interface guide
- **[SECURITY.md](SECURITY.md)** - Security model and threat analysis
- **[UNDER_THE_HOOD.md](UNDER_THE_HOOD.md)** - Technical implementation details
