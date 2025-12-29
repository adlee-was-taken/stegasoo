# Stegasoo

A secure steganography system for hiding encrypted messages in images using hybrid authentication.

![Python](https://img.shields.io/badge/Python-3.10+-blue)
![License](https://img.shields.io/badge/License-MIT-green)
![Security](https://img.shields.io/badge/Security-AES--256--GCM-red)

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


## WebUI Preview

Front Page                 |  Encode                   |  Decode                  | Generate |
:-------------------------:|:-------------------------:|:-------------------------:---------:|
![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI.webp)  |  ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI_Encode.webp)   | ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI_Decode.webp) ![Screenshot](https://github.com/adlee-was-taken/stegasoo/blob/main/data/WebUI_Generate.webp)


## Installation

### From Source

```bash
# Clone the repository
git clone https://github.com/adlee-was-taken/stegasoo.git
cd stegasoo

# Install core library
pip install -e .

# Install with CLI
pip install -e ".[cli]"

# Install with Web UI
pip install -e ".[web]"

# Install with REST API
pip install -e ".[api]"

# Install everything
pip install -e ".[all]"
```

### CLI Usage

```bash
# Generate credentials
stegasoo generate --pin --words 3

# With RSA key
stegasoo generate --rsa --rsa-bits 4096 -o mykey.pem -p "secretpassword"

# Encode
stegasoo encode \
  --ref photo.jpg \
  --carrier meme.png \
  --phrase "apple forest thunder" \
  --pin 123456 \
  --message "Secret message"

# Decode
stegasoo decode \
  --ref photo.jpg \
  --stego stego.png \
  --phrase "apple forest thunder" \
  --pin 123456

# Pipe-friendly
echo "secret" | stegasoo encode -r photo.jpg -c meme.png -p "words" --pin 123456 > stego.png
stegasoo decode -r photo.jpg -s stego.png -p "words" --pin 123456 -q
```

### Web UI

```bash
# Development
cd frontends/web
python app.py

# Production
gunicorn --bind 0.0.0.0:5000 app:app
```

Visit http://localhost:5000

### REST API

```bash
# Development
cd frontends/api
python main.py

# Production
uvicorn main:app --host 0.0.0.0 --port 8000
```

API docs at http://localhost:8000/docs

#### Example API Calls

```bash
# Generate credentials
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"use_pin": true, "use_rsa": false}'

# Encode (multipart)
curl -X POST http://localhost:8000/encode/multipart \
  -F "message=Secret" \
  -F "day_phrase=apple forest thunder" \
  -F "pin=123456" \
  -F "reference_photo=@photo.jpg" \
  -F "carrier=@meme.png" \
  --output stego.png

# Decode (multipart)
curl -X POST http://localhost:8000/decode/multipart \
  -F "day_phrase=apple forest thunder" \
  -F "pin=123456" \
  -F "reference_photo=@photo.jpg" \
  -F "stego_image=@stego.png"
```

## Security Model

| Component | Entropy | Purpose |
|-----------|---------|---------|
| Reference Photo | ~80-256 bits | Something you have |
| Day Phrase (3-12 words) | ~33-100+ bits | Something you know (rotates daily) |
| PIN (6-9 digits) | ~20+ bits | Something you know (static) |
| RSA Key (2048-bit) | ~128 bits | Something you have |
| **Combined** | **~133-400+ bits** | **Beyond brute force** |

### Attack Resistance

| Attack | Protection |
|--------|------------|
| Brute force | 2^133+ combinations |
| Rainbow tables | Random salt per message |
| Steganalysis | Random pixel selection |
| GPU cracking | Argon2id requires 256MB RAM per attempt |
| Side-channel | Constant-time operations in crypto |

## Project Structure

```
stegasoo/
├── src/stegasoo/           # Core library
│   ├── __init__.py         # Public API
│   ├── constants.py        # Configuration
│   ├── crypto.py           # Encryption/decryption
│   ├── steganography.py    # Image embedding
│   ├── keygen.py           # Credential generation
│   ├── validation.py       # Input validation
│   ├── models.py           # Data classes
│   ├── exceptions.py       # Custom exceptions
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
└── docker-compose.yml      # Container orchestration
```

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | production | Flask environment |
| `PYTHONPATH` | - | Include src/ for development |

### Limits

| Limit | Value |
|-------|-------|
| Max image size | 4 megapixels |
| Max message size | 50 KB |
| Max file upload | 5 MB |
| PIN length | 6-9 digits |
| Phrase length | 3-12 words |
| RSA key sizes | 2048, 3072, 4096 bits |

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
```

## License

MIT License - Use responsibly.

## ⚠️ Disclaimer

This tool is for educational and legitimate privacy purposes only. Users are responsible for complying with applicable laws in their jurisdiction.

