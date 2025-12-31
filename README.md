# Stegasoo

A secure steganography system for hiding encrypted messages in images using hybrid authentication.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Security](https://img.shields.io/badge/Security-AES--256--GCM-red)
![Version](https://img.shields.io/badge/Version-3.0.2-purple)

## Features

- 🔐 **AES-256-GCM** authenticated encryption
- 🧠 **Argon2id** memory-hard key derivation (256MB RAM requirement)
- 🎲 **Pseudo-random pixel selection** defeats steganalysis
- 📅 **Daily key rotation** with BIP-39 passphrases
- 🔑 **Multi-factor authentication**: PIN, RSA key, or both
- 🖼️ **Reference photo** as "something you have"
- 🌐 **Multiple interfaces**: CLI, Web UI, REST API
- 📁 **File embedding** - Hide any file type (PDF, ZIP, documents)
- 📱 **QR code support** - Encode/decode RSA keys via QR codes
- 🆕 **DCT steganography** - JPEG-resilient embedding for social media (v3.0+)

## What's New in v3.0.2

| Feature | Description |
|---------|-------------|
| **DCT Mode** | Frequency-domain embedding survives JPEG recompression |
| **JPEG Output** | Native JPEG output using jpegio library |
| **Color Preservation** | DCT color mode preserves carrier image colors |
| **Auto-Detection** | Decoder automatically detects LSB vs DCT mode |

### Embedding Mode Comparison

| Mode | Capacity (1080p) | JPEG Resilient | Best For |
|------|------------------|----------------|----------|
| **LSB** (default) | ~770 KB | ❌ No | Email, file transfer |
| **DCT** (experimental) | ~65 KB | ✅ Yes | Social media, messaging apps |

## WebUI Preview

| Front Page | Encode | Decode | Generate |
|:----------:|:------:|:------:|:--------:|
| ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI.webp) | ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI_Encode.webp) | ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI_Decode.webp) | ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI_Generate.webp) |

## Quick Start

```bash
# Install with all features
pip install -e ".[all]"

# Generate credentials (memorize these!)
stegasoo generate --pin --words 3

# Encode a message (LSB mode - default)
stegasoo encode \
  --ref photo.jpg \
  --carrier meme.png \
  --phrase "apple forest thunder" \
  --pin 123456 \
  --message "Secret message"

# Encode for social media (DCT mode)
stegasoo encode \
  --ref photo.jpg \
  --carrier meme.png \
  --phrase "apple forest thunder" \
  --pin 123456 \
  --message "Secret message" \
  --mode dct \
  --format jpeg

# Decode (auto-detects mode)
stegasoo decode \
  --ref photo.jpg \
  --stego stego.png \
  --phrase "apple forest thunder" \
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
│   Day Phrase ───────┤    (256MB RAM)                            │
│   (~33-132 bits)    │                                           │
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
| Day Phrase (3-12 words) | ~33-132 bits | Something you know (rotates daily) |
| PIN (6-9 digits) | ~20-30 bits | Something you know (static) |
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
| JPEG recompression | DCT mode embeds in frequency domain (v3.0+) |

### Security Configurations

| Configuration | Entropy | Use Case |
|--------------|---------|----------|
| 3-word phrase + 6-digit PIN | ~133 bits | Casual private messaging |
| 6-word phrase + 9-digit PIN | ~176 bits | Standard security |
| 3-word phrase + RSA 2048 | ~241 bits | File-based authentication |
| 6-word phrase + PIN + RSA 4096 | ~304 bits | Maximum security |

---

## Interfaces

### Command-Line Interface (CLI)

Full-featured CLI with piping support:

```bash
# Generate with RSA key
stegasoo generate --rsa --rsa-bits 4096 -o mykey.pem -p "password"

# Encode from file
stegasoo encode -r ref.jpg -c carrier.png -p "phrase" --pin 123456 -f secret.txt

# Encode for social media (DCT + JPEG)
stegasoo encode -r ref.jpg -c carrier.png -p "phrase" --pin 123456 \
  -m "Message" --mode dct --format jpeg

# Decode to stdout (quiet mode)
stegasoo decode -r ref.jpg -s stego.png -p "phrase" --pin 123456 -q

# Check image capacity (shows both LSB and DCT)
stegasoo info carrier.png
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
- Drag-and-drop image uploads
- Real-time entropy calculator
- Native mobile sharing (Web Share API)
- DCT mode with advanced options panel
- Automatic day-of-week detection

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
  -d '{"use_pin": true, "words_per_phrase": 3}'

# Encode with DCT mode
curl -X POST http://localhost:8000/encode/multipart \
  -F "message=Secret" \
  -F "day_phrase=apple forest thunder" \
  -F "pin=123456" \
  -F "embedding_mode=dct" \
  -F "output_format=jpeg" \
  -F "reference_photo=@photo.jpg" \
  -F "carrier=@meme.png" \
  --output stego.jpg

# Decode (auto-detects mode)
curl -X POST http://localhost:8000/decode/multipart \
  -F "day_phrase=apple forest thunder" \
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
│   ├── dct_steganography.py # DCT embedding (v3.0+)
│   ├── keygen.py           # Credential generation
│   ├── validation.py       # Input validation
│   ├── models.py           # Data classes
│   ├── exceptions.py       # Custom exceptions
│   ├── qr_utils.py         # QR code utilities
│   └── utils.py            # Utilities
│
├── frontends/
│   ├── web/                # Flask web UI
│   ├── cli/                # Command-line interface
│   └── api/                # FastAPI REST API
│
├── data/
│   └── bip39-words.txt     # BIP-39 wordlist
│
├── pyproject.toml          # Package configuration
├── Dockerfile              # Multi-stage Docker build
├── docker-compose.yml      # Container orchestration
│
├── README.md               # This file
├── INSTALL.md              # Installation guide
├── CLI.md                  # CLI documentation
├── API.md                  # API documentation
└── WEB_UI.md               # Web UI documentation
```

---

## Configuration

### Limits

| Limit | Value |
|-------|-------|
| Max image size | 4 megapixels |
| Max message size | 50 KB |
| Max file upload | 5 MB |
| PIN length | 6-9 digits |
| Phrase length | 3-12 words |
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
python -c "from stegasoo import has_dct_support; print(has_dct_support())"
python -c "from stegasoo.dct_steganography import has_jpegio_support; print(has_jpegio_support())"
```

---

## Version History

| Version | Changes |
|---------|---------|
| **3.0.2** | Fixed JPEG output with jpegio integration |
| **3.0.1** | Added DCT color mode, JPEG output (broken) |
| **3.0.0** | Added DCT steganography mode |
| **2.2.x** | QR code support, file embedding |
| **2.0.x** | Web UI, REST API, RSA keys |
| **1.0.x** | Initial release, CLI only |

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
