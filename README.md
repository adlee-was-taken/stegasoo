# StegoCrypt Web Service

A containerized Flask + Bootstrap web UI for hybrid Photo + Day-Phrase + PIN steganography.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![Flask](https://img.shields.io/badge/Flask-3.0+-green)
![Docker](https://img.shields.io/badge/Docker-Ready-blue)
![Security](https://img.shields.io/badge/Security-AES--256--GCM-red)

## Features

- 🔐 **AES-256-GCM** authenticated encryption
- 🧠 **Argon2id** memory-hard key derivation (256MB)
- 🎲 **Pseudo-random pixel selection** defeats steganalysis
- 📅 **Daily key rotation** with 3-word phrases
- 🔢 **Static PIN** for additional entropy
- 🖼️ **Reference photo** as "something you have"
- 🌐 **Web UI** with Bootstrap 5 dark theme

## Quick Start

### Docker (Recommended)

```bash
# Build and run
docker-compose up -d

# Access at http://localhost:5000
```

### Manual Installation

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Run development server
python app.py

# Or production with gunicorn
gunicorn --bind 0.0.0.0:5000 app:app
```

## Usage

### 1. Generate Credentials

Visit `/generate` to create:
- **7 three-word phrases** (one per day of week)
- **1 six-digit PIN** (same every day)

Memorize these! Don't save them.

### 2. Encode a Message

Visit `/encode` and provide:
- **Reference photo** - A photo both parties have (NOT transmitted)
- **Carrier image** - The image to hide your message in
- **Message** - Your secret text
- **Day phrase** - Today's 3-word phrase
- **PIN** - Your static 6-digit PIN

Download the stego image and share it through any channel.

### 3. Decode a Message

Visit `/decode` and provide:
- **Reference photo** - Same photo used for encoding
- **Stego image** - The image containing the hidden message
- **Day phrase** - The phrase for the day it was encoded
- **PIN** - Your static PIN

## Security Model

| Component | Entropy | Purpose |
|-----------|---------|---------|
| Reference Photo | ~80-256 bits | Something you have |
| 3-Word Phrase | ~33 bits | Something you know (rotates daily) |
| 6-Digit PIN | ~20 bits | Something you know (static) |
| **Combined** | **133+ bits** | **Beyond brute force** |

### Attack Resistance

| Attack | Result |
|--------|--------|
| Brute force | 2^133 combinations = impossible |
| Rainbow tables | Random salt per message |
| Steganalysis | Random pixel selection defeats detection |
| GPU cracking | Argon2 requires 256MB RAM per attempt |

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Home page |
| `/generate` | GET/POST | Generate phrase card + PIN |
| `/encode` | GET/POST | Encode message in image |
| `/decode` | GET/POST | Decode message from image |
| `/about` | GET | Security information |

## Configuration

Environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | production | Flask environment |
| `SECRET_KEY` | random | Session secret (auto-generated) |

## Production Deployment

For production, consider:

1. **HTTPS** - Use nginx reverse proxy with SSL
2. **Rate limiting** - Prevent abuse
3. **Logging** - Monitor for security events
4. **Memory** - Allocate at least 512MB (Argon2 needs 256MB)

Example nginx config:

```nginx
server {
    listen 443 ssl;
    server_name stegocrypt.example.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location / {
        proxy_pass http://stegocrypt:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        client_max_body_size 50M;
    }
}
```

## License

MIT License - Use responsibly.

## ⚠️ Disclaimer

This tool is for educational and legitimate privacy purposes only. Users are responsible for complying with applicable laws in their jurisdiction.
