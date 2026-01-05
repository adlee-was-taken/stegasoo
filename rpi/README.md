# Stegasoo Raspberry Pi

Scripts and resources for deploying Stegasoo on Raspberry Pi.

## Quick Install

On a fresh Raspberry Pi OS Lite (64-bit) installation:

```bash
# Pre-setup (git not included in Lite image)
sudo chown $USER:$USER /opt
sudo apt-get update && sudo apt-get install -y git

# Clone and run setup
cd /opt
git clone -b 4.1 https://github.com/adlee-was-taken/stegasoo.git stegasoo
cd stegasoo
./rpi/setup.sh
```

## What the Setup Script Does

1. **Installs system dependencies** - build tools, libraries
2. **Installs Python 3.12** - via pyenv (Pi OS ships with 3.13 which is incompatible)
3. **Builds jpegio for ARM** - patches x86-specific flags
4. **Installs Stegasoo** - with web UI and all dependencies
5. **Creates systemd service** - auto-starts on boot
6. **Enables the service** - ready to start

## Requirements

- Raspberry Pi 4 or 5
- Raspberry Pi OS Lite (64-bit) - Bookworm or later
- 4GB+ RAM recommended (2GB minimum)
- ~2GB free disk space
- Internet connection

### Performance

On a Pi 4 at 2GHz with USB 3.0 NVMe, expect ~60 seconds to encode/decode a 10MB JPEG with full encryption (passphrase + PIN + reference photo).

## Pre-built Image Defaults

If using a pre-built image from GitHub Releases:

- **Default login**: `admin` / `stegasoo`
- **Hostname**: `stegasoo.local`
- **First boot**: A setup wizard runs on first SSH login

> **Security note**: Change the default password after setup with `passwd`

## After Installation

### Start the Service

```bash
sudo systemctl start stegasoo
```

### Check Status

```bash
sudo systemctl status stegasoo
```

### View Logs

```bash
journalctl -u stegasoo -f
```

### Access Web UI

Open in browser: `http://<pi-ip>:5000`

On first access, you'll create an admin account.

## Configuration

Edit the systemd service to change settings:

```bash
sudo systemctl edit stegasoo
```

Add overrides:

```ini
[Service]
Environment="STEGASOO_AUTH_ENABLED=true"
Environment="STEGASOO_HTTPS_ENABLED=true"
Environment="STEGASOO_HOSTNAME=stegasoo.local"
```

Then reload:

```bash
sudo systemctl daemon-reload
sudo systemctl restart stegasoo
```

## Uninstall

```bash
sudo systemctl stop stegasoo
sudo systemctl disable stegasoo
sudo rm /etc/systemd/system/stegasoo.service
rm -rf /opt/stegasoo
```

## Pre-built Images

Check [GitHub Releases](https://github.com/adlee-was-taken/stegasoo/releases) for pre-built SD card images.

---

## Building Your Own Image

To create a distributable SD card image:

### 1. Flash Fresh Raspberry Pi OS

Use rpi-imager to flash Raspberry Pi OS (64-bit) to an SD card.

In advanced settings, set:
- Hostname: `stegasoo`
- Enable SSH (password auth for initial setup)
- Username/password (temporary, will work for any user)
- Skip WiFi for distributable image

### 2. Boot and Run Setup

```bash
# SSH into the Pi
ssh admin@stegasoo.local

# Pre-setup
sudo chown admin:admin /opt
sudo apt-get update && sudo apt-get install -y git

# Clone and run setup
cd /opt
git clone -b 4.1 https://github.com/adlee-was-taken/stegasoo.git stegasoo
cd stegasoo
./rpi/setup.sh
```

### 3. Test It Works

```bash
sudo systemctl start stegasoo
curl -k https://localhost:5000  # Should return HTML
```

### 4. Sanitize for Distribution

```bash
# Full sanitize (removes WiFi, shuts down for imaging)
sudo /opt/stegasoo/rpi/sanitize-for-image.sh

# Or soft reset (keeps WiFi for testing, reboots)
sudo /opt/stegasoo/rpi/sanitize-for-image.sh --soft
```

This removes:
- WiFi credentials (unless `--soft`)
- SSH host keys (regenerate on boot)
- SSH authorized keys
- Bash history
- Stegasoo auth database (users create their own admin)
- Logs and temp files

The script validates cleanup and reports any issues.

### 5. Create the Image

After Pi shuts down, remove SD card and on another Linux machine:

```bash
# Find SD card device (BE CAREFUL - wrong device = data loss!)
lsblk

# Copy (replace sdX with your SD card)
sudo dd if=/dev/sdX of=stegasoo-rpi-$(date +%Y%m%d).img bs=4M status=progress

# Shrink the image (optional but recommended)
wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
chmod +x pishrink.sh
sudo ./pishrink.sh stegasoo-rpi-*.img

# Compress (zstd is faster than xz with similar compression)
zstd -19 -T0 stegasoo-rpi-*.img
```

### 6. Distribute

Upload the `.img.zst` file to GitHub Releases.

Users flash with:
```bash
zstdcat stegasoo-rpi-*.img.zst | sudo dd of=/dev/sdX bs=4M status=progress
```

Or use rpi-imager's "Use custom" option.
