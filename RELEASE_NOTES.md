## Stegasoo v4.1.5

### Developer Experience
- **Educational Code Comments**: Core modules now include detailed explanations
  - DCT: zig-zag coefficient diagrams, QIM embedding math, Reed-Solomon "Voyager" reference
  - LSB: visual bit manipulation examples, ChaCha20 pixel selection
  - Crypto: multi-factor KDF flow diagrams, Argon2id memory-hardness reasoning
  - CLI/Web: architectural patterns for future contributors

### Raspberry Pi Improvements
- **Streamlined Image Creation**: `pull-image.sh` now handles everything
  - Auto-resizes rootfs to exactly 16GB (for smaller download)
  - Preserves auto-expand (image fills SD card on first boot)
  - Compresses with zstd
  - Optional .zst.zip wrapper for GitHub releases
- **16GB Minimum**: Pre-built images are now 16GB (was variable)
- **Host Requirements**: `rpi/host-requirements.txt` documents all dependencies
- **Test Automation**: `kickoff-pi-test.sh` for one-command flash+test cycles

### MOTD Polish
- Dynamic temperature emoji (ice/cool/fire based on CPU temp)
- Rocket emoji for service status
- Cleaner formatting

### Raspberry Pi Image
Download `stegasoo-rpi-4.1.5.img.zst.zip` from Releases.

```bash
# Flash (auto-detects SD card)
sudo ./rpi/flash-image.sh stegasoo-rpi-4.1.5.img.zst.zip

# Or manual
zstdcat stegasoo-rpi-4.1.5.img.zst | sudo dd of=/dev/sdX bs=4M status=progress
```

Default login: `admin` / `stegasoo`

First boot runs the setup wizard for WiFi, HTTPS, and channel key configuration.

### Docker
```bash
docker-compose up -d web  # Web UI on :5000
docker-compose up -d api  # REST API on :8000
```

### Full Changelog
See [CHANGELOG.md](CHANGELOG.md) for complete version history.
