# Changelog

All notable changes to Stegasoo will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org).

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

[4.0.1]: https://github.com/adlee-was-taken/stegasoo/compare/v4.0.0...v4.0.1
[4.0.0]: https://github.com/adlee-was-taken/stegasoo/compare/v3.2.0...v4.0.0
[3.2.0]: https://github.com/adlee-was-taken/stegasoo/compare/v3.0.2...v3.2.0
[3.0.2]: https://github.com/adlee-was-taken/stegasoo/compare/v3.0.0...v3.0.2
[3.0.0]: https://github.com/adlee-was-taken/stegasoo/compare/v2.0.0...v3.0.0
[2.0.0]: https://github.com/adlee-was-taken/stegasoo/compare/v1.0.0...v2.0.0
[1.0.0]: https://github.com/adlee-was-taken/stegasoo/releases/tag/v1.0.0
