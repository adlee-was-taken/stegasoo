# Stegasoo Release Checklist

Pre-release validation checklist. Complete all items before tagging a release.

## Code Quality

- [ ] All tests pass: `./venv/bin/pytest tests/ -v`
- [ ] No lint errors: `./venv/bin/ruff check src/`
- [ ] Version bumped in `pyproject.toml`
- [ ] CHANGELOG.md updated

## Pi Image Validation

- [ ] Fresh Pi OS install with setup.sh works
- [ ] First-boot wizard completes successfully
- [ ] MOTD shows correct URL on SSH login
- [ ] Smoke test passes: `./rpi/smoke-test.sh --443 <PI_IP>`
- [ ] Encode/decode works on large image (10MB+)
- [ ] Sanitize script runs cleanly
- [ ] Image created and compressed

## Docker Validation

- [ ] Base image builds: `docker build -f Dockerfile.base -t stegasoo-base:latest .`
- [ ] Web image builds: `docker-compose build web`
- [ ] Container starts: `docker-compose up -d web`
- [ ] Web UI accessible at http://localhost:5000
- [ ] Encode/decode works in container
- [ ] Container stops cleanly: `docker-compose down`

## Release Process

- [ ] Merge feature branch to main
- [ ] Create annotated tag: `git tag -a vX.Y.Z -m "message"`
- [ ] Push tag: `git push origin vX.Y.Z`
- [ ] Create GitHub Release with release notes
- [ ] Upload Pi image (.img.zst.zip)
- [ ] Verify download links work

## Post-Release

- [ ] Delete old/obsolete releases if needed
- [ ] Update any external documentation
- [ ] Announce release (if applicable)
