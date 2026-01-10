# Stegasoo AUR Package

> **Note:** Uses Python 3.12 via `python312` AUR package (jpegio not yet compatible with 3.13)

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

- `/opt/stegasoo/venv/` - Self-contained Python 3.12 venv with all dependencies
- `/usr/bin/stegasoo` - CLI symlink
- `/usr/lib/systemd/system/stegasoo-web.service` - Web UI service
- `/usr/lib/systemd/system/stegasoo-api.service` - REST API service

## Optional Dependencies

```bash
# QR code reading from webcam/images
sudo pacman -S zbar
```

All other dependencies are bundled in the venv.

## Usage

### CLI
```bash
stegasoo --help
stegasoo generate --rsa --qr-ascii
stegasoo encode -i carrier.jpg -r reference.jpg -m "secret" -P passphrase -p 123456
```

### Web UI (systemd)
```bash
# Create service user (first time)
sudo useradd -r -s /usr/bin/nologin stegasoo

# Start service
sudo systemctl enable --now stegasoo-web

# Access at http://localhost:5000
```

### REST API (systemd)
```bash
# Start service
sudo systemctl enable --now stegasoo-api

# Access at http://localhost:8000/docs
```

### Manual run (without systemd)
```bash
# Web UI
/opt/stegasoo/venv/bin/python -m gunicorn -b 0.0.0.0:5000 \
    --chdir /opt/stegasoo/venv/lib/python3.12/site-packages/frontends/web app:app

# REST API
/opt/stegasoo/venv/bin/uvicorn \
    --app-dir /opt/stegasoo/venv/lib/python3.12/site-packages/frontends/api \
    main:app --host 0.0.0.0 --port 8000
```

## Maintainer

Aaron D. Lee
