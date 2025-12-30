# Changelog

All notable changes to Stegasoo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [2.2.0] - 2025-12-30

### Added

- **Compression Module** (`stegasoo.compression`)
  - Zlib compression for payloads (enabled by default)
  - Optional LZ4 support for faster compression (`pip install lz4`)
  - Automatic algorithm detection on decompression
  - `--compress/--no-compress` CLI flags
  - `--algorithm` flag to choose compression method
  - `estimate_compressed_size()` for capacity planning

- **Batch Processing** (`stegasoo.batch`)
  - `stegasoo batch encode` - encode message into multiple images
  - `stegasoo batch decode` - decode from multiple images
  - `stegasoo batch check` - check capacity of multiple images
  - Parallel processing with configurable workers (`-j/--jobs`)
  - Recursive directory scanning (`-r/--recursive`)
  - Progress callbacks for UI integration
  - JSON output for all batch operations

- **CLI Improvements**
  - `--json` global flag for machine-readable output
  - `--dry-run` flag for encode (preview capacity usage)
  - `stegasoo info` command to show version and features
  - JSON output for `generate` command

- **New Constants**
  - `MIN_COMPRESS_SIZE` - minimum size to attempt compression
  - `ZLIB_COMPRESSION_LEVEL` - compression level setting
  - `BATCH_DEFAULT_WORKERS` - default parallel workers
  - `BATCH_MAX_WORKERS` - maximum parallel workers

### Changed

- Version bumped to 2.2.0
- Payloads are now compressed by default before encryption
- Updated `pyproject.toml` with `compression` optional dependency group

### Dependencies

- Added optional dependency: `lz4>=4.0.0` (in `[compression]` extra)

## [2.1.4] - 2025-12-29

### Changed

- Centralized all configuration values to `constants.py`
- Added version injection to Flask templates via context processor
- Synchronized version across `constants.py` and `pyproject.toml`

## [2.1.3] - 2025-12-28

### Added

- Initial public release
- Core steganography encoding/decoding
- Hybrid authentication (passphrase + PIN)
- RSA key support
- QR code credential sharing
- CLI interface
- REST API (FastAPI)
- Web frontend (Flask)
- File payload embedding
- Temporary file auto-expiry

---

## Version History Summary

| Version | Date | Highlights |
|---------|------|------------|
| 2.2.0 | 2025-12-30 | Batch processing, compression |
| 2.1.4 | 2025-12-29 | Constants centralization |
| 2.1.3 | 2025-12-28 | Initial release |
