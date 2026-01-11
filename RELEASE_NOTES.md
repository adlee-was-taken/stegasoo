## Stegasoo v4.2.1

### API Security

#### API Key Authentication
- All protected endpoints now require `X-API-Key` header
- Keys stored hashed (SHA-256) in `~/.stegasoo/api_keys.json`
- Auth disabled when no keys configured (easy onboarding)
- Public endpoints remain open: `/`, `/docs`, `/modes`, `/auth/status`

#### TLS Support
- Self-signed certificates auto-generated on first run
- Certs valid for localhost, all local IPs, hostname.local
- Stored in `~/.stegasoo/certs/`
- CLI: `stegasoo api tls generate` to pre-generate

### CLI Improvements

#### New API Management Commands
```bash
stegasoo api keys list           # List API keys
stegasoo api keys create NAME    # Create new key (shown once!)
stegasoo api keys delete NAME    # Delete key
stegasoo api tls generate        # Generate TLS cert
stegasoo api tls info            # Show cert info
stegasoo api serve               # Start with TLS (default)
```

#### New Image Tools
```bash
stegasoo tools compress IMG -q 75   # JPEG compression
stegasoo tools rotate IMG -r 90     # Rotation (jpegtran for JPEGs)
stegasoo tools rotate IMG --flip-h  # Flip-only
stegasoo tools convert IMG -f png   # Format conversion
```

### Bug Fixes

- **DCT rotation**: Portrait photos no longer export rotated 90 degrees
- **jpegtran**: Removed `-trim` flag that destroyed DCT stego data
- **CLI encode**: Now outputs JPEG when carrier is JPEG (was always PNG)
- **EXIF viewer**: Redesigned with card-based grid layout

### AUR Packages

Three package options now available:

| Package | Size | Contents |
|---------|------|----------|
| `stegasoo-git` | 79MB | Full (Web UI + API + CLI) |
| `stegasoo-api-git` | 74MB | REST API + CLI only |
| `stegasoo-cli-git` | 68MB | CLI only |

### Quick Start

```bash
# Create API key
stegasoo api keys create mykey

# Start API server (TLS by default)
stegasoo api serve

# Use API
curl -k -H "X-API-Key: stegasoo_xxxx_..." https://localhost:8000/
```

### Raspberry Pi Image
Download `stegasoo-rpi-4.2.1.img.zst` from Releases.

```bash
# Flash (auto-detects SD card)
sudo ./rpi/flash-image.sh stegasoo-rpi-4.2.1.img.zst
```

Default login: `admin` / `stegasoo`

### Docker
```bash
docker-compose -f docker/docker-compose.yml up -d
```

---

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

### Compression

#### Zstd Default Compression
- `zstandard` is now a core dependency (always installed)
- Better compression ratio than zlib for QR code RSA keys
- New `STEGASOO-ZS:` prefix for zstd, backward compatible with `STEGASOO-Z:` (zlib)

### QR Code Generation

#### CLI Support
- `stegasoo generate --rsa --qr key.png` - save RSA key as QR image (PNG/JPG)
- `stegasoo generate --rsa --qr-ascii` - print ASCII QR to terminal

#### API Support
- `POST /generate-key-qr` - generate QR from RSA key
- Supports `png`, `jpg`, and `ascii` output formats
- Uses zstd compression by default

### Other Changes

- RSA key size capped at 3072 bits (4096 too large for QR codes)
- File auto-expire increased to 10 minutes
- Progress bar "candy cane" animation during Argon2 key derivation
- Optional API service in Pi setup (with security warning)

### Summary

| Metric | v4.1.7 | v4.2.0 | Improvement |
|--------|--------|--------|-------------|
| Decode (1MB) | ~2.6s | ~0.8s | **70% faster** |
| Peak RAM | 211 MB | 107 MB | **50% less** |
| Concurrent API | No | Yes | check |
| QR Compression | zlib | zstd | **~15% smaller** |

### Full Changelog
See [CHANGELOG.md](CHANGELOG.md) for complete version history.
