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
- [ ] CLI tools - full shakedown and fixes

## AUR Packages
- [ ] `stegasoo-cli` - standalone CLI package (no web dependencies)
- [ ] `stegasoo-api` - REST API package (needs auth overhaul first)

## API Auth Work (blocking stegasoo-api)
- [ ] Implement OAuth2 authentication
- [ ] TLS 1.3 support with self-signed certificates
- [ ] Figure out cert trust/distribution for clients

## API Documentation
- [ ] Postman collection
- [ ] Environment variable templates
