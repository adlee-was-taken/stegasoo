# Changelog

All notable changes to Stegasoo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org).

## [4.1.0] - 2026-01-04

### Added
- **Admin Recovery System**: Password reset for locked-out admins
  - Recovery key generated during setup (32-char alphanumeric)
  - Multiple backup options: text file, QR code, stego image
  - QR codes obfuscated (XOR'd with magic header hash)
  - Stego backups hide key in an image using Stegasoo itself
  - CLI: `stegasoo admin recover --db path/to/db`
- **EXIF Editor**: Full metadata editing in Tools page
  - View all EXIF fields from uploaded image
  - Inline editing of individual fields
  - Clear all metadata with one click
  - Download cleaned image
  - CLI: `stegasoo tools exif image.jpg [--clear] [--set Field=Value]`
- **Multi-User Support**: Admin can create up to 16 additional users
  - Role-based access control (admin/user)
  - Admin user management page
  - Temp password generation for new users
- **Saved Channel Keys**: Users can save/manage channel keys in account page

### Changed
- **Architecture**: Consolidated `resolve_channel_key()` to library layer
  - Single source of truth in `src/stegasoo/channel.py`
  - CLI, API, WebUI now use thin wrappers
- **DCT Pre-Check**: Fail fast with helpful error before expensive encoding
- **Toast Notifications**: Auto-dismiss after 20 seconds with fade animation
- `RECOVERY_OBFUSCATION_KEY` constant added to `constants.py`

### Fixed
- DCT payload size error now caught early with clear message

## [4.0.2] - 2026-01-02

### Added
- **Web UI Authentication**: Single-admin login with SQLite3 user storage
  - First-run setup wizard for admin account creation
  - Account management page for password changes
  - `@login_required` decorator protects encode/decode/generate routes
  - Argon2id password hashing (lighter 64MB for fast login)
- **Optional HTTPS**: Auto-generated self-signed certificates for home network deployment
  - Configurable via `STEGASOO_HTTPS_ENABLED` environment variable
  - Certificates stored in `frontends/web/certs/`
- New environment variables: `STEGASOO_AUTH_ENABLED`, `STEGASOO_HTTPS_ENABLED`, `STEGASOO_HOSTNAME`

### Changed
- PIN entry column widened in encode/decode forms (col-md-4 → col-md-6)
- Channel options column narrowed (col-md-8 → col-md-6)
- QR preview panels enlarged for better text readability
- Consistent font sizing across all preview panel banners (0.7rem filename, 0.6rem data, 0.65rem badges)

### Fixed
- QR preview text too small to read in encode/decode templates
- Inconsistent label sizes between reference/carrier/stego panels

## [4.0.1] - 2025-01-02

### Fixed
- Fixed numpy binary incompatibility on Python 3.10 (jpegio/scipy)
- Fixed BatchCredentials test failures with missing `reference_photo` parameter
- Graceful handling when DCT dependencies have version mismatches

### Changed
- Applied `ruff` linter fixes across entire codebase (~400 issues)
- Applied `black` formatter to all Python files
- Modernized type hints: `Optional[X]` → `X | None`
- Updated ruff config to use `[tool.ruff.lint]` section
- Moved documentation files to repository root

### Removed
- Removed obsolete debug/diagnostic scripts
- Cleaned up backup files and dev scripts

## [4.0.0] - 2024-12-29

### Added
- Refreshed Web UI with modern, snazzy interface
- Improved user experience across all pages

### Changed
- Major version bump for breaking API changes
- Simplified passphrase handling (single passphrase instead of day-based)
- Removed date_str parameter from encoding

### Fixed
- Various bug fixes for Web UI
- CLI updates and improvements

## [3.2.0] - 2024-12-28

### Added
- Big revamp of the encoding system
- Home and about page improvements
- UNDER_THE_HOOD.md documentation

### Changed
- Renamed `phrase` → `passphrase` in API
- Updated Web UI styling

## [3.0.2] - 2024-12-27

### Added
- Full experimental DCT steganography support
- jpegio integration for better JPEG manipulation
- DCT/LSB mode selector in Web UI

## [3.0.0] - 2024-12-25

### Added
- DCT (Discrete Cosine Transform) steganography mode
- Support for JPEG carriers without quality loss
- Channel key feature for private messaging

### Changed
- Complete rewrite of steganography engine
- New hybrid authentication system

## [2.0.0] - 2024-12-20

### Added
- Web UI frontend
- REST API (FastAPI)
- Batch processing support
- RSA key authentication option

### Changed
- Migrated to hybrid photo + passphrase + PIN authentication

## [1.0.0] - 2024-12-15

### Added
- Initial release
- LSB steganography
- AES-256-GCM encryption
- CLI interface
- Basic PIN authentication

[4.0.2]: https://github.com/adlee-was-taken/stegasoo/compare/v4.0.1...v4.0.2
[4.0.1]: https://github.com/adlee-was-taken/stegasoo/compare/v4.0.0...v4.0.1
[4.0.0]: https://github.com/adlee-was-taken/stegasoo/compare/v3.2.0...v4.0.0
[3.2.0]: https://github.com/adlee-was-taken/stegasoo/compare/v3.0.2...v3.2.0
[3.0.2]: https://github.com/adlee-was-taken/stegasoo/compare/v3.0.0...v3.0.2
[3.0.0]: https://github.com/adlee-was-taken/stegasoo/compare/v2.0.0...v3.0.0
[2.0.0]: https://github.com/adlee-was-taken/stegasoo/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/adlee-was-taken/stegasoo/releases/tag/v1.0.0
