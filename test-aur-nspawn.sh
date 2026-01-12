#!/bin/bash
# Test AUR package builds using systemd-nspawn
#
# Usage: sudo ./test-aur-nspawn.sh [package]
#   package: all (default), full, cli, api
#
# First run creates Arch root at /tmp/arch-build-root

set -e

PACKAGE="${1:-all}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
ARCH_ROOT="/tmp/arch-build-root"

echo "=== Stegasoo AUR Build Test (nspawn) ==="
echo "Package: $PACKAGE"
echo "Arch root: $ARCH_ROOT"
echo ""

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo "Please run as root (sudo)"
    exit 1
fi

# Create Arch root if it doesn't exist
if [ ! -d "$ARCH_ROOT/usr" ]; then
    echo "Creating Arch root (first time setup)..."
    mkdir -p "$ARCH_ROOT"
    pacstrap -c "$ARCH_ROOT" base base-devel git python python-build python-hatchling zbar
    echo "Arch root created."
else
    echo "Using existing Arch root."
    # Update packages
    arch-chroot "$ARCH_ROOT" pacman -Syu --noconfirm
fi

# Create build user if needed
if ! arch-chroot "$ARCH_ROOT" id builder &>/dev/null; then
    arch-chroot "$ARCH_ROOT" useradd -m builder
    echo "builder ALL=(ALL) NOPASSWD: ALL" >> "$ARCH_ROOT/etc/sudoers"
fi

# Copy source
rm -rf "$ARCH_ROOT/home/builder/stegasoo"
cp -r "$SCRIPT_DIR" "$ARCH_ROOT/home/builder/stegasoo"
arch-chroot "$ARCH_ROOT" chown -R builder:builder /home/builder/stegasoo

# Create build script
cat > "$ARCH_ROOT/tmp/build.sh" << 'BUILDSCRIPT'
#!/bin/bash
set -e

build_package() {
    local pkg_dir="$1"
    local pkg_name="$2"

    echo ""
    echo "=========================================="
    echo "Building: $pkg_name"
    echo "=========================================="

    cd "/home/builder/stegasoo/$pkg_dir"

    # Clean previous builds
    rm -rf src pkg *.pkg.tar.zst "${pkg_name}" 2>/dev/null || true

    # Build as non-root user
    sudo -u builder makepkg -sf --noconfirm

    # Show result
    ls -lh *.pkg.tar.zst

    # Test install
    echo "Installing $pkg_name..."
    pacman -U --noconfirm *.pkg.tar.zst

    # Quick test
    echo "Testing $pkg_name..."
    /usr/bin/stegasoo --version

    # More tests for API package
    if [[ "$pkg_name" == *"api"* ]]; then
        /usr/bin/stegasoo api --help
        /usr/bin/stegasoo api keys list
    fi

    # Uninstall for next test
    pacman -Rns --noconfirm $(pacman -Qq | grep stegasoo) 2>/dev/null || true

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
        build_package "aur-cli" "stegasoo-cli-git"
        build_package "aur-api" "stegasoo-api-git"
        build_package "aur" "stegasoo-git"
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
BUILDSCRIPT

chmod +x "$ARCH_ROOT/tmp/build.sh"

# Run build in nspawn container
echo "Starting nspawn container..."
systemd-nspawn -D "$ARCH_ROOT" --bind-ro="$SCRIPT_DIR:/home/builder/stegasoo" /tmp/build.sh "$PACKAGE"

echo ""
echo "=== Build test complete ==="
echo "Arch root preserved at: $ARCH_ROOT"
echo "To clean up: sudo rm -rf $ARCH_ROOT"
