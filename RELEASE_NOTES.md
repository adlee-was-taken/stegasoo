## Stegasoo v4.2.0

### Performance Optimizations

Major performance improvements for Raspberry Pi and resource-constrained deployments.

#### DCT Vectorization (~14x faster)
- Batch DCT processing using `scipy.fft.dctn` with `axes=(1,2)`
- Processes 500 blocks at once instead of one-by-one
- Decode time reduced from ~2.6s to ~0.8s on 1MB images

#### Memory Optimization (50% reduction)
- Switched from `float64` to `float32` for all DCT operations
- Peak RAM: 211 MB → 107 MB for encode, 104 MB → 52 MB for decode
- Critical for Pi 3/4 avoiding swap thrashing

#### Progress Callbacks for Decode
- `progress_file` parameter added to `decode()` and extraction functions
- UI can now show decode progress (phases: loading, extracting, decoding, complete)
- JSON format: `{"current": 80, "total": 100, "percent": 80.0, "phase": "decoding"}`

#### Async API Endpoints
- Encode/decode operations now run in thread pool via `asyncio.to_thread()`
- API server can handle concurrent requests without blocking
- Essential for multi-user Pi deployments

### Summary

| Metric | v4.1.7 | v4.2.0 | Improvement |
|--------|--------|--------|-------------|
| Decode (1MB) | ~2.6s | ~0.8s | **70% faster** |
| Peak RAM | 211 MB | 107 MB | **50% less** |
| Concurrent API | No | Yes | ✓ |

### Raspberry Pi Image
Download `stegasoo-rpi-4.2.0_final.img.zst` from Releases.

```bash
# Flash (auto-detects SD card)
sudo ./rpi/flash-image.sh stegasoo-rpi-4.2.0_final.img.zst

# Or manual
zstdcat stegasoo-rpi-4.2.0_final.img.zst | sudo dd of=/dev/sdX bs=4M status=progress
```

Default login: `admin` / `stegasoo`

### Docker
```bash
# Build and run
docker build -f docker/Dockerfile.base -t stegasoo-base:latest .
docker-compose -f docker/docker-compose.yml up -d

# Or individual services
docker-compose -f docker/docker-compose.yml up -d web  # Web UI on :5000
docker-compose -f docker/docker-compose.yml up -d api  # REST API on :8000
```

### Full Changelog
See [CHANGELOG.md](CHANGELOG.md) for complete version history.
