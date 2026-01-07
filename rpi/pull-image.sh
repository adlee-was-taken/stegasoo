#!/bin/bash
# Pull Raspberry Pi image from SD card (after setup)
# Only pulls the actual used partition space, not the entire SD card
#
# Usage: ./pull-image.sh <device> <output.img.zst>
# Example: ./pull-image.sh /dev/sdb stegasoo-rpi-4.1.5.img.zst

set -e

if [ $# -ne 2 ]; then
    echo "Usage: $0 <device> <output.img.zst>"
    echo "Example: $0 /dev/sdb stegasoo-rpi-4.1.5.img.zst"
    exit 1
fi

DEVICE="$1"
OUTPUT="$2"

if [ ! -b "$DEVICE" ]; then
    echo "Error: Device not found: $DEVICE"
    exit 1
fi

echo "Device info:"
lsblk "$DEVICE"
echo

# Get partition info
echo "Partition table:"
sudo parted -s "$DEVICE" unit s print
echo

# Get the end of the last partition (partition 2 = rootfs)
END_SECTOR=$(sudo parted -s "$DEVICE" unit s print | grep "^ 2" | awk '{print $3}' | tr -d 's')

if [ -z "$END_SECTOR" ]; then
    echo "Error: Could not determine partition 2 end sector"
    exit 1
fi

# Add a small buffer (1MB = 2048 sectors) for safety
TOTAL_SECTORS=$((END_SECTOR + 2048))
TOTAL_BYTES=$((TOTAL_SECTORS * 512))
TOTAL_GB=$(echo "scale=2; $TOTAL_BYTES / 1073741824" | bc)

echo "Image will be approximately ${TOTAL_GB}GB (${TOTAL_SECTORS} sectors)"
echo "Output file: $OUTPUT"
echo

read -p "Proceed with image pull? [Y/n] " confirm
if [[ "$confirm" =~ ^[Nn]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo "Pulling image..."
echo

# Use pv if available for progress, otherwise fallback to dd status
if command -v pv &> /dev/null; then
    sudo dd if="$DEVICE" bs=512 count=$TOTAL_SECTORS 2>/dev/null | \
        pv -s $TOTAL_BYTES | \
        zstd -T0 -3 > "$OUTPUT"
else
    sudo dd if="$DEVICE" bs=512 count=$TOTAL_SECTORS status=progress | \
        zstd -T0 -3 > "$OUTPUT"
fi

echo
echo "Done! Image saved to: $OUTPUT"
ls -lh "$OUTPUT"

# Show verification info
echo
echo "To verify, you can check the image with:"
echo "  zstdcat $OUTPUT | fdisk -l /dev/stdin"
