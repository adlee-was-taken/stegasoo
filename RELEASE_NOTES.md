## Stegasoo v4.1.7

### Mobile UI Polish
- **PIN Entry**: Shrunk digit boxes for 9-digit PIN support on mobile
- **Mode Selectors**: DCT/LSB buttons now use consistent button-group styling with icons
- **Navbar**: Left-aligned collapsed menu, shortened channel fingerprint display (`ABCD-••••-3456`)
- **Text Wrapping**: Fixed button text wrapping issues on narrow screens

### Docker Improvements
- **Reorganized**: Docker files moved to `docker/` directory
  - `docker/Dockerfile`
  - `docker/Dockerfile.base`
  - `docker/docker-compose.yml`
- **DCT Fix**: Added Reed-Solomon (`reedsolo`) to Docker images - fixes DCT decode failures
- **Quick Start**: New `docs/DOCKER_QUICKSTART.md` guide

```bash
# Build and run
docker build -f docker/Dockerfile.base -t stegasoo-base:latest .
docker-compose -f docker/docker-compose.yml up -d
```

### Raspberry Pi
- **First-Boot Wizard**: Can now load existing channel key (for joining team deployments)
- **Project Cleanup**: Moved `pishrink.sh` to `rpi/tools/`

### UI Copy
- Changed "Undetectable" to "Covertly Embedded" on encode page (more accurate)

### Raspberry Pi Image
Download `stegasoo-rpi-4.1.7.img.zst.zip` from Releases.

```bash
# Flash (auto-detects SD card)
sudo ./rpi/flash-image.sh stegasoo-rpi-4.1.7.img.zst.zip

# Or manual
unzip -p stegasoo-rpi-4.1.7.img.zst.zip | zstdcat | sudo dd of=/dev/sdX bs=4M status=progress
```

Default login: `admin` / `stegasoo`

First boot runs the setup wizard for WiFi, HTTPS, and channel key configuration.

### Docker
```bash
docker-compose -f docker/docker-compose.yml up -d web  # Web UI on :5000
docker-compose -f docker/docker-compose.yml up -d api  # REST API on :8000
```

### Full Changelog
See [CHANGELOG.md](CHANGELOG.md) for complete version history.
