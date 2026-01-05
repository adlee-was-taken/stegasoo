# Stegasoo Pi Image Build Workflow

Quick reference for building a distributable SD card image.

## Step 1: Flash Fresh Raspbian

Use rpi-imager with these settings:
- **OS**: Raspberry Pi OS Lite (64-bit)
- **Hostname**: `stegasoo`
- **Enable SSH**: Yes (password auth)
- **Username**: `admin`
- **Password**: `stegasoo`
- **WiFi**: Configure for your network (sanitize script removes it later)

## Step 2: Boot & SSH In

```bash
# Wait for Pi to boot (~60 seconds), then:
ssh admin@stegasoo.local
# or use IP from router DHCP list
```

## Step 3: Pre-Setup

```bash
# Take ownership of /opt (for pyenv, jpegio builds)
sudo chown admin:admin /opt

# Install git (not included in Lite image)
sudo apt-get update && sudo apt-get install -y git
```

## Step 4: Clone & Run Setup

```bash
cd /opt
git clone -b 4.1 https://github.com/adlee-was-taken/stegasoo.git stegasoo
cd stegasoo
./rpi/setup.sh
```

This takes ~15-20 minutes and installs:
- Python 3.12 via pyenv
- jpegio (patched for ARM)
- Stegasoo with web UI
- Systemd service

## Step 5: Test It Works

```bash
sudo systemctl start stegasoo
curl -k https://localhost:5000
# Should return HTML
```

## Step 6: Sanitize for Distribution

```bash
# Full sanitize (for final image - removes WiFi, shuts down)
sudo /opt/stegasoo/rpi/sanitize-for-image.sh

# Or soft reset (for testing - keeps WiFi, reboots)
sudo /opt/stegasoo/rpi/sanitize-for-image.sh --soft
```

This removes:
- WiFi credentials (unless `--soft`)
- SSH host keys (regenerate on boot)
- SSH authorized keys
- Bash history
- Stegasoo auth database
- Logs and temp files

The script validates all cleanup steps before finishing.

## Step 7: Copy the Image

Remove SD card, insert into your Linux machine:

```bash
# Find the SD card device (CAREFUL!)
lsblk

# Copy (replace sdX with actual device, e.g., sda)
sudo dd if=/dev/sdX of=stegasoo-rpi-$(date +%Y%m%d).img bs=4M status=progress
```

## Step 8: Shrink & Compress

```bash
# Optional: Shrink image (saves space)
wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
chmod +x pishrink.sh
sudo ./pishrink.sh stegasoo-rpi-*.img

# Compress (zstd is faster than xz with similar ratio)
zstd -19 -T0 stegasoo-rpi-*.img
```

## Step 9: Distribute

Upload `.img.zst` to GitHub Releases.

Users can flash with:
```bash
# Linux
zstdcat stegasoo-rpi-*.img.zst | sudo dd of=/dev/sdX bs=4M status=progress

# Or use rpi-imager "Use custom" option
```

---

## Quick Command Summary

```bash
# On Pi (after SSH):
sudo chown admin:admin /opt
sudo apt-get update && sudo apt-get install -y git
cd /opt && git clone -b 4.1 https://github.com/adlee-was-taken/stegasoo.git stegasoo
cd stegasoo && ./rpi/setup.sh
sudo systemctl start stegasoo
curl -k https://localhost:5000
sudo /opt/stegasoo/rpi/sanitize-for-image.sh

# On your machine:
sudo dd if=/dev/sdX of=stegasoo-rpi-$(date +%Y%m%d).img bs=4M status=progress
zstd -19 -T0 stegasoo-rpi-*.img
```
