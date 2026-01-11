# Stegasoo 4.2.1 Plan

## Bugs
- [x] Fix EXIF viewer panel not loading metadata in Web UI
  - Redesigned with card-based grid layout and categories
  - Compact styling for better space usage
- [x] DCT mode: portrait photos export rotated 90° (EXIF orientation not handled)
  - Added `_apply_exif_orientation()` to apply EXIF rotation before embedding
- [x] DCT mode: add rotation fallback (try as-is, rotate 90°, retry on failure)
  - Added rotation fallback in `extract_from_dct()` with quick header validation
- [x] Rotate tool: use jpegtran for lossless JPEG rotation (preserves DCT stego!)
  - Web UI rotate tool now uses jpegtran for JPEGs
  - DCT decode rotation fallback now uses jpegtran for JPEGs
  - Dynamic UI shows "DCT Safe" for JPEGs, warning for other formats

## Tools Audit
- [x] Web UI tools - full shakedown and fixes
  - Compress, Rotate, Strip, EXIF viewer all working
  - Rotate uses jpegtran for lossless JPEG rotation
  - Compact UI styling
- [x] CLI tools - full shakedown and fixes
  - Fixed encode to output JPEG when carrier is JPEG (was always PNG)
  - Fixed jpegtran -trim flag destroying DCT stego data
  - Added compress, rotate, convert tools (matching Web UI)
  - Rotate uses jpegtran for JPEGs, supports flip-only operations

## AUR Packages
- [x] `stegasoo-cli` - standalone CLI package (no web dependencies)
  - Created aur-cli/PKGBUILD with [cli,dct,compression] extras only
  - No flask/gunicorn/fastapi/uvicorn/pyzbar deps
  - 68MB vs 79MB for full package
- [x] `stegasoo-api` - REST API package
  - Created aur-api/PKGBUILD with [api,cli,compression] extras
  - Has fastapi/uvicorn, no flask/gunicorn
  - 74MB package size
  - Includes systemd service with TLS

## API Auth Work
- [x] API key authentication (simpler than OAuth2 for personal use)
  - `frontends/api/auth.py` - key generation, hashing, validation
  - Keys stored in `~/.stegasoo/api_keys.json` (hashed)
  - `X-API-Key` header for authentication
  - Auth disabled when no keys configured
- [x] TLS with self-signed certificates
  - Auto-generates certs on first run
  - CLI: `stegasoo api tls generate`
  - Certs stored in `~/.stegasoo/certs/`
- [x] CLI commands for API management
  - `stegasoo api keys list/create/delete`
  - `stegasoo api tls generate/info`
  - `stegasoo api serve` (starts with TLS by default)

## API Documentation
- [ ] Postman collection (with environment templates)
