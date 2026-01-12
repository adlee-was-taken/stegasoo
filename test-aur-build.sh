#!/bin/bash
# Test AUR package builds in a clean Arch container
#
# Usage: sudo ./test-aur-build.sh [package]
#   package: all (default), full, cli, api

set -e

PACKAGE="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== Stegasoo AUR Build Test ==="
echo "Package: $PACKAGE"
echo ""

# Create a test script to run inside container
cat > /tmp/aur-build-test.sh << 'INNERSCRIPT'
#!/bin/bash
set -e

# Update system
pacman -Syu --noconfirm

# Install build dependencies
pacman -S --noconfirm --needed \
    base-devel git python python-build python-hatchling \
    zbar

# Create build user (makepkg won't run as root)
useradd -m builder
echo "builder ALL=(ALL) NOPASSWD: ALL" >> /etc/sudoers

# Copy source to build location
cp -r /src /home/builder/stegasoo
chown -R builder:builder /home/builder/stegasoo

build_package() {
    local pkg_dir="$1"
    local pkg_name="$2"

    echo ""
    echo "=========================================="
    echo "Building: $pkg_name"
    echo "=========================================="

    cd "/home/builder/stegasoo/$pkg_dir"

    # Build as non-root user
    sudo -u builder makepkg -sf --noconfirm

    # Show result
    ls -lh *.pkg.tar.zst

    # Test install
    echo "Installing $pkg_name..."
    pacman -U --noconfirm *.pkg.tar.zst

    # Quick test
    echo "Testing $pkg_name..."
    stegasoo --version
    stegasoo --help | head -20

    # Uninstall for next test
    pacman -R --noconfirm "${pkg_name%-git}" 2>/dev/null || pacman -R --noconfirm "$pkg_name" 2>/dev/null || true

    echo "$pkg_name: SUCCESS"
}

case "$1" in
    full)
        build_package "aur" "stegasoo-git"
        ;;
    cli)
        build_package "aur-cli" "stegasoo-cli-git"
        ;;
    api)
        build_package "aur-api" "stegasoo-api-git"
        ;;
    all)
        build_package "aur" "stegasoo-git"
        build_package "aur-cli" "stegasoo-cli-git"
        build_package "aur-api" "stegasoo-api-git"
        ;;
    *)
        echo "Unknown package: $1"
        exit 1
        ;;
esac

echo ""
echo "=========================================="
echo "All builds completed successfully!"
echo "=========================================="
INNERSCRIPT

chmod +x /tmp/aur-build-test.sh

# Run in Arch container
echo "Starting Arch container..."
docker run --rm -it \
    -v "$SCRIPT_DIR:/src:ro" \
    -v "/tmp/aur-build-test.sh:/build.sh:ro" \
    archlinux:latest \
    /bin/bash -c "chmod +x /build.sh && /build.sh $PACKAGE"

echo ""
echo "=== Build test complete ==="
