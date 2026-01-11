# RPi Patches

This directory contains patches for dependencies that need modifications to build on ARM64.

## Current Status (v4.2+)

As of Stegasoo 4.2, we use **jpeglib** instead of jpegio. The jpeglib build process is handled inline in `setup.sh` and includes:

- Cloning from GitHub (PyPI tarball missing headers)
- Downloading libjpeg headers for each version (6b through 9f)
- Patching setup.py to skip turbo/mozjpeg (need cmake-generated headers)

See `setup.sh` for the full implementation.

## Legacy: jpegio Patches (v4.1 and earlier)

The `jpegio/` directory contains patches for the old jpegio dependency, which required removing x86-specific `-m64` compiler flags. These are no longer used but kept for reference.

## jpeglib Helper Script

The `jpeglib/install-jpeglib-arm64.sh` script is a standalone version of the jpeglib build process. It's not used by setup.sh (which has the logic inline) but can be useful for manual testing or debugging.

## Structure

```
patches/
  jpegio/           # Legacy (v4.1) - not used in v4.2+
    arm64.patch
    apply-patch.sh
  jpeglib/          # Reference script for manual builds
    install-jpeglib-arm64.sh
```

## Adding New Patches

If a new dependency needs ARM64 patches:

1. Create a directory: `patches/<package>/`
2. Add patch files or helper scripts
3. Update `setup.sh` to apply the patch during installation
