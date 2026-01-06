# Stegasoo 4.1.4 Plan

## Build / Deploy
- [ ] Pre-built Python 3.12 venv tarball for Pi (skip 20+ min compile)
- [ ] Fixed partition sizing in flash script (8-16GB rootfs for faster imaging)
- [ ] Rename `flash-pi.sh` → `flash-stock-img.sh` for clarity
- [ ] pip-audit integration in release validation

## Features
- [ ] QR channel key sharing (needs UI thought - avoid crowding encode/decode pages)
- [ ] Role-based permissions: admin / mod / user
- [ ] `stegasoo info` fastfetch-style command (version, service status, channel, CPU, temp, etc.)
- [ ] Better capacity estimates / pre-flight check before encode fails

## Security
- [ ] Optional encryption for temp file storage (paranoid mode, config toggle)

## Docs
- [ ] Update UNDER_THE_HOOD.md
- [ ] General docs refresh

## Ideas (maybe later)
- [ ] Stego detection tool
- [ ] Browser extension
- [ ] Pi snapshot/backup feature
