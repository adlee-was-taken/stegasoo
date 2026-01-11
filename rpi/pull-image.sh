#!/bin/bash
# Pull Raspberry Pi image from SD card (after setup)
# Resizes rootfs to 16GB for consistent image size, then pulls
#
# Usage: ./pull-image.sh <device> <output.img.zst>
# Example: ./pull-image.sh /dev/sdb stegasoo-rpi-4.2.1.img.zst

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

if [ $# -ne 2 ]; then
    echo "Usage: $0 <device> <output.img.zst>"
    echo "Example: $0 /dev/sdb stegasoo-rpi-4.2.1.img.zst"
    exit 1
fi

DEVICE="$1"
OUTPUT="$2"

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Must run as root (sudo)${NC}"
    exit 1
fi

if [ ! -b "$DEVICE" ]; then
    echo -e "${RED}Error: Device not found: $DEVICE${NC}"
    exit 1
fi

echo -e "${BOLD}Device info:${NC}"
lsblk "$DEVICE"
echo

# Find partitions
if [ -b "${DEVICE}1" ]; then
    BOOT_PART="${DEVICE}1"
    ROOT_PART="${DEVICE}2"
elif [ -b "${DEVICE}p1" ]; then
    BOOT_PART="${DEVICE}p1"
    ROOT_PART="${DEVICE}p2"
else
    echo -e "${RED}Error: Could not find partitions${NC}"
    exit 1
fi

# Unmount any mounted partitions
echo -e "${YELLOW}Unmounting partitions...${NC}"
umount "$BOOT_PART" 2>/dev/null || true
umount "$ROOT_PART" 2>/dev/null || true

# ============================================================================
# Resize rootfs to 16GB
# ============================================================================
echo
echo -e "${BOLD}Checking partition size...${NC}"

# Get current partition size in bytes
CURRENT_SIZE=$(blockdev --getsize64 "$ROOT_PART")
TARGET_BYTES=$((16 * 1024 * 1024 * 1024))  # 16GB in bytes
CURRENT_GB=$(echo "scale=2; $CURRENT_SIZE / 1073741824" | bc)

echo "  Current rootfs size: ${CURRENT_GB}GB"

if [ "$CURRENT_SIZE" -gt "$TARGET_BYTES" ]; then
    echo -e "${YELLOW}Resizing rootfs to 16GB...${NC}"

    # Get boot partition end in sectors
    BOOT_END=$(parted -s "$DEVICE" unit s print | grep "^ 1" | awk '{print $3}' | tr -d 's')

    # Calculate 16GB in sectors (512 byte sectors)
    ROOT_SIZE_SECTORS=33554432
    ROOT_END=$((BOOT_END + ROOT_SIZE_SECTORS))

    # SHRINKING: filesystem first, then partition
    echo "  Checking filesystem..."
    e2fsck -f -y "$ROOT_PART" 2>/dev/null || true

    # Shrink filesystem to 15.5GB (leave room for partition overhead)
    echo "  Shrinking filesystem to 15500M..."
    resize2fs "$ROOT_PART" 15500M

    # Delete and recreate partition 2 with 16GB size
    echo "  Shrinking partition to 16GB..."
    parted -s "$DEVICE" rm 2
    parted -s "$DEVICE" mkpart primary ext4 $((BOOT_END + 1))s ${ROOT_END}s

    # Refresh partition table
    partprobe "$DEVICE"
    sleep 2

    # Expand filesystem to fill the partition exactly
    echo "  Expanding filesystem to fill partition..."
    e2fsck -f -y "$ROOT_PART" 2>/dev/null || true
    resize2fs "$ROOT_PART"

    echo -e "${GREEN}  Rootfs resized to 16GB${NC}"
elif [ "$CURRENT_SIZE" -lt "$TARGET_BYTES" ]; then
    echo -e "${YELLOW}  Rootfs is smaller than 16GB - expanding...${NC}"

    # Get boot partition end in sectors
    BOOT_END=$(parted -s "$DEVICE" unit s print | grep "^ 1" | awk '{print $3}' | tr -d 's')
    ROOT_SIZE_SECTORS=33554432
    ROOT_END=$((BOOT_END + ROOT_SIZE_SECTORS))

    # EXPANDING: partition first, then filesystem
    parted -s "$DEVICE" rm 2
    parted -s "$DEVICE" mkpart primary ext4 $((BOOT_END + 1))s ${ROOT_END}s

    partprobe "$DEVICE"
    sleep 2

    e2fsck -f -y "$ROOT_PART" 2>/dev/null || true
    resize2fs "$ROOT_PART"

    echo -e "${GREEN}  Rootfs expanded to 16GB${NC}"
else
    echo -e "${GREEN}  Rootfs already ~16GB${NC}"
fi

# ============================================================================
# Pull image
# ============================================================================
echo
echo -e "${BOLD}Partition table:${NC}"
parted -s "$DEVICE" unit s print
echo

# Get the end of the last partition (partition 2 = rootfs)
END_SECTOR=$(parted -s "$DEVICE" unit s print | grep "^ 2" | awk '{print $3}' | tr -d 's')

if [ -z "$END_SECTOR" ]; then
    echo -e "${RED}Error: Could not determine partition 2 end sector${NC}"
    exit 1
fi

# Add a small buffer (1MB = 2048 sectors) for safety
TOTAL_SECTORS=$((END_SECTOR + 2048))
TOTAL_BYTES=$((TOTAL_SECTORS * 512))
TOTAL_GB=$(echo "scale=2; $TOTAL_BYTES / 1073741824" | bc)

echo -e "Image size: ${YELLOW}~${TOTAL_GB}GB${NC} (${TOTAL_SECTORS} sectors)"
echo -e "Output: ${YELLOW}$OUTPUT${NC}"
echo

read -p "Proceed with image pull? [Y/n] " confirm
if [[ "$confirm" =~ ^[Nn]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo
echo -e "${GREEN}Pulling image...${NC}"
echo

# Use pv if available for progress, otherwise fallback to dd status
if command -v pv &> /dev/null; then
    dd if="$DEVICE" bs=512 count=$TOTAL_SECTORS 2>/dev/null | \
        pv -s $TOTAL_BYTES | \
        zstd -T0 -3 > "$OUTPUT"
else
    dd if="$DEVICE" bs=512 count=$TOTAL_SECTORS status=progress | \
        zstd -T0 -3 > "$OUTPUT"
fi

echo
echo -e "${GREEN}Done!${NC} Image saved to: $OUTPUT"
ls -lh "$OUTPUT"

# ============================================================================
# Optional: Zip-wrap for GitHub releases
# ============================================================================
echo
read -p "Create .zst.zip wrapper for GitHub? [y/N] " zip_confirm
if [[ "$zip_confirm" =~ ^[Yy]$ ]]; then
    ZIP_OUTPUT="${OUTPUT}.zip"
    echo -e "${YELLOW}Creating zip wrapper (store mode, no compression)...${NC}"
    zip -0 "$ZIP_OUTPUT" "$OUTPUT"
    echo -e "${GREEN}Done!${NC} Upload this to GitHub Releases:"
    ls -lh "$ZIP_OUTPUT"
    echo
    echo "Users can flash with:"
    echo "  sudo ./rpi/flash-image.sh $ZIP_OUTPUT"
else
    echo
    echo "To verify:"
    echo "  zstdcat $OUTPUT | fdisk -l /dev/stdin"
fi
