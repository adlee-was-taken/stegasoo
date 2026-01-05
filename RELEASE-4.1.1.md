# Stegasoo 4.1.1 Release Notes

**Release Date:** January 5, 2026

## Highlights

- **Reed-Solomon Error Correction** - DCT steganography now includes RS error correction, making encoded images more resilient to minor corruption and compression artifacts
- **Completely Rewritten Pi Setup** - Fresh install tested and validated, works reliably from scratch
- **SSH Login Banner** - See your Stegasoo URL immediately on SSH login

## New Features

### Reed-Solomon Error Correction
DCT-encoded images now include Reed-Solomon error correction codes, allowing recovery from minor image corruption. This significantly improves reliability when images are shared through platforms that may slightly modify them.

### SSH Login Banner (MOTD)
When you SSH into your Stegasoo Pi, you'll now see:
```
  ___  _____  ___    ___    _    ___    ___    ___
 / __||_   _|| __|  / __|  /_\  / __|  / _ \  / _ \
 \__ \  | |  | _|  | (_ | / _ \ \__ \ | (_) || (_) |
 |___/  |_|  |___|  \___//_/ \_\|___/  \___/  \___/

 ● Stegasoo is running
   https://192.168.0.4
```

### Elapsed Time Counter
Encode/decode buttons now show elapsed time during operations.

### Click-to-Copy Decoded Message
Click the decoded message box to copy to clipboard (no button needed).

### Overclock Wizard Option
First-boot wizard now offers optional CPU overclocking for Pi 4/5 with active cooling.

## Improvements

### Setup Script (setup.sh)
- Fixed pyenv Python path resolution (handles 3.12 → 3.12.12 mapping)
- Changed default install location to `/opt/stegasoo`
- Fixed jpegio build order (clone stegasoo first, then build jpegio into venv)
- Added python3-dev to dependencies
- Added btop for system monitoring
- Shows `/setup` URL at completion for admin account creation

### Sanitize Script
- Now clears port 443 iptables redirect (clean slate for wizard)
- Removes overclock settings before imaging

### Documentation
- Updated all docs to reference `/opt/stegasoo` path
- Added pre-setup steps (chown /opt, install git)
- Added Pi 4 performance baseline (~60s for 10MB JPEG)

### About Page
- Redesigned "Limits & Specs" section with key stats cards and accordion

## Bug Fixes

- Fixed DCT steganography for non-8-aligned images
- Fixed MOTD port detection (was using iptables which requires root)
- Fixed smoke test `--443` flag parsing

## Performance

On a Raspberry Pi 4 at 2GHz with USB 3.0 NVMe:
- ~50 seconds to encode a 10MB JPEG
- ~60 seconds to decode a 10MB JPEG
- Full encryption: passphrase + PIN + reference photo

## Upgrade Notes

If upgrading from 4.1.0:
```bash
cd /opt/stegasoo  # or ~/stegasoo
git pull origin 4.1
```

For fresh installs, see the [Pi README](rpi/README.md).

## Pre-built Images

- `stegasoo-rpi-4.1.1_20260105-2.img.zst` - Raspberry Pi 4/5 image

Flash with:
```bash
zstdcat stegasoo-rpi-4.1.1_20260105-2.img.zst | sudo dd of=/dev/sdX bs=4M status=progress
```

---

Full changelog: [v4.1.0...v4.1.1](https://github.com/adlee-was-taken/stegasoo/compare/v4.1.0...v4.1.1)
