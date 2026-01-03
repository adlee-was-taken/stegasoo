# Stegasoo Pi Image Build Workflow

Quick reference for building a distributable SD card image.

## Step 1: Flash Fresh Raspbian

Use rpi-imager with these settings:
- **OS**: Raspberry Pi OS (64-bit)
- **Hostname**: `stegasoo`
- **Enable SSH**: Yes (password auth)
- **Username**: `pi` (or any)
- **Password**: `raspberry` (temporary)
- **WiFi**: Skip (use ethernet for clean image)

## Step 2: Boot & SSH In

```bash
# Wait for Pi to boot (~60 seconds), then:
ssh pi@stegasoo.local
# or use IP from router DHCP list
```

## Step 3: Run Setup Script

```bash
curl -sSL https://raw.githubusercontent.com/adlee-was-taken/stegasoo/main/rpi/setup.sh | bash
```

This takes ~15-20 minutes and installs:
- Python 3.12 via pyenv
- jpegio (patched for ARM)
- Stegasoo with web UI
- Systemd service

## Step 4: Test It Works

```bash
sudo systemctl start stegasoo
curl -k https://localhost:5000
# Should return HTML
```

## Step 5: Sanitize for Distribution

```bash
curl -sSL https://raw.githubusercontent.com/adlee-was-taken/stegasoo/main/rpi/sanitize-for-image.sh | sudo bash
```

This removes:
- WiFi credentials
- SSH authorized keys
- Bash history
- Stegasoo auth database
- Logs and temp files

The Pi will shut down when complete.

## Step 6: Copy the Image

Remove SD card, insert into your Linux machine:

```bash
# Find the SD card device (CAREFUL!)
lsblk

# Copy (replace sdX with actual device, e.g., sda)
sudo dd if=/dev/sdX of=stegasoo-rpi-$(date +%Y%m%d).img bs=4M status=progress
```

## Step 7: Shrink & Compress

```bash
# Optional: Shrink image (saves space)
wget https://raw.githubusercontent.com/Drewsif/PiShrink/master/pishrink.sh
chmod +x pishrink.sh
sudo ./pishrink.sh stegasoo-rpi-*.img

# Compress
xz -9 -T0 stegasoo-rpi-*.img
```

## Step 8: Distribute

Upload `.img.xz` to GitHub Releases.

Users can flash with:
```bash
# Linux
xzcat stegasoo-rpi-*.img.xz | sudo dd of=/dev/sdX bs=4M status=progress

# Or use rpi-imager "Use custom" option
```

---

## Quick Command Summary

```bash
# On Pi:
curl -sSL https://raw.githubusercontent.com/adlee-was-taken/stegasoo/main/rpi/setup.sh | bash
sudo systemctl start stegasoo
curl -k https://localhost:5000
curl -sSL https://raw.githubusercontent.com/adlee-was-taken/stegasoo/main/rpi/sanitize-for-image.sh | sudo bash

# On your machine:
sudo dd if=/dev/sdX of=stegasoo-rpi-$(date +%Y%m%d).img bs=4M status=progress
xz -9 -T0 stegasoo-rpi-*.img
```
