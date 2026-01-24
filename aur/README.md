# Stegasoo AUR Package

Full package with CLI, Web UI, and REST API. Supports Python 3.11-3.14.

## Installation

### From AUR (once published)
```bash
yay -S stegasoo-git
# or
paru -S stegasoo-git
```

### Manual build
```bash
git clone https://aur.archlinux.org/stegasoo-git.git
cd stegasoo-git
makepkg -si
```

## What Gets Installed

- `/opt/stegasoo/venv/` - Self-contained Python venv with all dependencies
- `/usr/bin/stegasoo` - CLI symlink
- `/usr/lib/systemd/system/stegasoo-web.service` - Web UI service (port 5000)
- `/usr/lib/systemd/system/stegasoo-api.service` - REST API service (port 8000, HTTPS)

## Optional Dependencies

```bash
# QR code reading from webcam/images (recommended)
sudo pacman -S zbar
```

All other dependencies are bundled in the venv.

## Usage

### CLI
```bash
stegasoo --help
stegasoo generate                    # Generate passphrase + PIN
stegasoo generate --rsa --qr-ascii   # With RSA keys and QR codes
stegasoo encode -i carrier.jpg -r reference.jpg -m "secret" -P "word1 word2 word3 word4" -p 123456
stegasoo decode -i encoded.png -r reference.jpg -P "word1 word2 word3 word4" -p 123456
```

### Web UI
```bash
# Start service (user created automatically on install)
sudo systemctl enable --now stegasoo-web

# Access at http://localhost:5000
```

### REST API
```bash
# Create an API key first
sudo -u stegasoo stegasoo api keys create mykey

# Start service (HTTPS with auto-generated self-signed cert)
sudo systemctl enable --now stegasoo-api

# Access docs at https://localhost:8000/docs
curl -k -H "X-API-Key: YOUR_KEY" https://localhost:8000/
```

### HTTPS Configuration

The API uses HTTPS by default with auto-generated self-signed certificates.

```bash
# View certificate info
stegasoo api tls info

# Generate new self-signed cert
sudo -u stegasoo stegasoo api tls generate

# Use custom certs (edit service file)
sudo systemctl edit stegasoo-api
```

## Alternative Packages

- `stegasoo-cli-git` - CLI only, minimal dependencies
- `stegasoo-api-git` - CLI + REST API, no web UI

## Maintainer

Aaron D. Lee
