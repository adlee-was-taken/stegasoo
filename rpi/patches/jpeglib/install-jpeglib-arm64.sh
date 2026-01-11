#!/bin/bash
#
# Install jpeglib on ARM64 Linux (Raspberry Pi)
# Works around missing headers in the source tarball
#
# Usage: ./install-jpeglib-arm64.sh
#

set -e

echo "Installing jpeglib for ARM64..."

# Create temp directory
WORKDIR=$(mktemp -d)
cd "$WORKDIR"

# Download jpeglib source
echo "  Downloading jpeglib source..."
pip download jpeglib==1.0.2 --no-binary :all: --no-deps -d . -q
tar -xzf jpeglib-1.0.2.tar.gz
cd jpeglib-1.0.2

# Download official libjpeg sources and copy headers
echo "  Downloading libjpeg headers..."
CJPEGLIB="src/jpeglib/cjpeglib"

# libjpeg 6b
curl -sL "https://www.ijg.org/files/jpegsrc.v6b.tar.gz" | tar -xzf -
cp jpeg-6b/*.h "$CJPEGLIB/6b/"

# libjpeg 7-9f (all use similar headers from 9e)
curl -sL "https://www.ijg.org/files/jpegsrc.v9f.tar.gz" | tar -xzf -
for v in 7 8 8a 8b 8c 8d 9 9a 9b 9c 9d 9e 9f; do
    cp jpeg-9f/*.h "$CJPEGLIB/$v/"
done

# libjpeg-turbo versions
curl -sL "https://github.com/libjpeg-turbo/libjpeg-turbo/archive/refs/tags/2.1.0.tar.gz" | tar -xzf -
for v in turbo120 turbo130 turbo140 turbo150 turbo200 turbo210; do
    cp libjpeg-turbo-2.1.0/*.h "$CJPEGLIB/$v/" 2>/dev/null || true
done

# mozjpeg versions
curl -sL "https://github.com/mozilla/mozjpeg/archive/refs/tags/v4.0.3.tar.gz" | tar -xzf -
for v in mozjpeg101 mozjpeg201 mozjpeg300 mozjpeg403; do
    cp mozjpeg-4.0.3/*.h "$CJPEGLIB/$v/" 2>/dev/null || true
done

# Build and install
echo "  Building jpeglib..."
pip install . -q

# Cleanup
cd /
rm -rf "$WORKDIR"

echo "  Done! jpeglib installed successfully."
