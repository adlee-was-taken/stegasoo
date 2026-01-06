## Stegasoo v4.1.3

### Fixes
- **SSL Certificate Generation**: First-boot wizard now properly generates self-signed certs when HTTPS is enabled
- **Download Bug Fixed**: No more "File expired or not found" errors - fixed multi-worker temp file sharing
- **Docker Build**: Reduced build context from 2.3GB to ~900KB

### Improvements
- Docker memory limits increased to 2GB (prevents OOM on large DCT operations)
- Decode button now shows loading spinner during processing
- Headless Pi flash script with Trixie/NetworkManager support

### Docker
```bash
docker-compose up -d web  # Web UI on :5000
docker-compose up -d api  # REST API on :8000
```

### Raspberry Pi Image
Download `stegasoo-rpi-4.1.3.img.zst`, flash to SD card, and boot. The first-boot wizard will guide you through WiFi, HTTPS, and channel key setup.

```bash
# Flash with included script
./rpi/flash-image.sh stegasoo-rpi-4.1.3.img.zst /dev/sdX

# First time: save your WiFi credentials
./rpi/inject-wifi.sh --setup

# Then inject WiFi after flashing
sudo ./rpi/inject-wifi.sh /dev/sdX
```

### Full Changelog
See [CHANGELOG.md](CHANGELOG.md) for complete details.
