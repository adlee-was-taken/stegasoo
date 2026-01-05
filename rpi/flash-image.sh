#!/bin/bash
#
# Flash Stegasoo image to SD card
# Auto-detects SD card, decompresses and writes with progress
#
# Usage: ./flash-image.sh <image> [device]
#
# Supports: .img, .img.zst, .img.xz, .img.gz, .img.zst.zip (GitHub release format)
# If device is specified, skips auto-detection (useful for NVMe/large drives)
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Check for required tools
for cmd in dd pv lsblk; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}Error: $cmd is required but not installed.${NC}"
        exit 1
    fi
done

# Check for root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Must run as root (sudo)${NC}"
    exit 1
fi

# Check for image argument
if [ -z "$1" ]; then
    echo -e "${RED}Usage: $0 <image> [device]${NC}"
    echo ""
    echo "Supported formats: .img, .img.zst, .img.xz, .img.gz, .img.zst.zip"
    echo ""
    echo "Examples:"
    echo "  $0 stegasoo-rpi-4.1.1.img.zst             # auto-detect SD card"
    echo "  $0 stegasoo-rpi-4.1.1.img.zst.zip         # from GitHub release"
    echo "  $0 stegasoo-rpi-4.1.1.img.zst /dev/sdb    # specify device"
    exit 1
fi

IMAGE="$1"
MANUAL_DEVICE="$2"

if [ ! -f "$IMAGE" ]; then
    echo -e "${RED}Error: Image file not found: $IMAGE${NC}"
    exit 1
fi

# Handle .zst.zip wrapper (GitHub releases workaround)
if [[ "$IMAGE" == *.zst.zip ]]; then
    echo -e "${YELLOW}Extracting .zst from zip wrapper...${NC}"
    if ! command -v unzip &> /dev/null; then
        echo -e "${RED}Error: unzip is required for .zst.zip files but not installed.${NC}"
        exit 1
    fi
    TEMP_DIR=$(mktemp -d)
    trap "rm -rf $TEMP_DIR" EXIT
    unzip -q "$IMAGE" -d "$TEMP_DIR"
    IMAGE=$(find "$TEMP_DIR" -name "*.zst" | head -1)
    if [ -z "$IMAGE" ]; then
        echo -e "${RED}Error: No .zst file found in zip archive${NC}"
        exit 1
    fi
    echo -e "${GREEN}Found: $(basename "$IMAGE")${NC}"
    echo ""
fi

# Detect compression
COMPRESSED=false
COMP_TYPE=""
if [[ "$IMAGE" == *.xz ]]; then
    COMPRESSED=true
    COMP_TYPE="xz"
    if ! command -v xzcat &> /dev/null; then
        echo -e "${RED}Error: xz is required for .xz files but not installed.${NC}"
        exit 1
    fi
elif [[ "$IMAGE" == *.zst ]]; then
    COMPRESSED=true
    COMP_TYPE="zst"
    if ! command -v zstdcat &> /dev/null; then
        echo -e "${RED}Error: zstd is required for .zst files but not installed.${NC}"
        exit 1
    fi
elif [[ "$IMAGE" == *.gz ]]; then
    COMPRESSED=true
    COMP_TYPE="gz"
    if ! command -v zcat &> /dev/null; then
        echo -e "${RED}Error: gzip is required for .gz files but not installed.${NC}"
        exit 1
    fi
fi

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              Stegasoo SD Card Flasher                         ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo -e "Image: ${YELLOW}$IMAGE${NC}"
echo -e "Size:  ${YELLOW}$(du -h "$IMAGE" | awk '{print $1}')${NC}"
if [ "$COMPRESSED" = true ]; then
    echo -e "Type:  ${YELLOW}Compressed (will decompress on-the-fly)${NC}"
fi
echo ""

# Use manual device or auto-detect
if [ -n "$MANUAL_DEVICE" ]; then
    # Manual device specified
    if [ ! -b "$MANUAL_DEVICE" ]; then
        echo -e "${RED}Error: $MANUAL_DEVICE is not a block device${NC}"
        exit 1
    fi
    SELECTED="$MANUAL_DEVICE"
    echo -e "Using specified device: ${YELLOW}$SELECTED${NC}"
    echo ""
    lsblk "$SELECTED" -o NAME,SIZE,TYPE,MODEL
    echo ""
else
    # Auto-detect SD card candidates
    echo -e "${BOLD}Scanning for SD cards...${NC}"
    echo ""

    declare -a CANDIDATES
    declare -a CANDIDATE_INFO

    while IFS= read -r line; do
        DEV=$(echo "$line" | awk '{print $1}')
        SIZE=$(echo "$line" | awk '{print $2}')
        TYPE=$(echo "$line" | awk '{print $3}')
        TRAN=$(echo "$line" | awk '{print $4}')
        MODEL=$(echo "$line" | awk '{print $5" "$6" "$7}' | xargs)

        # Skip if it's the root filesystem
        if mount | grep -q "^/dev/${DEV}[0-9]* on / "; then
            continue
        fi

        # Skip if any partition is mounted as root
        ROOT_DEV=$(mount | grep " on / " | awk '{print $1}' | sed 's/[0-9]*$//')
        if [[ "/dev/$DEV" == "$ROOT_DEV" ]]; then
            continue
        fi

        # Get size in bytes for reliable comparison
        SIZE_BYTES=$(lsblk -b -d -o SIZE -n "/dev/$DEV" 2>/dev/null | tr -d ' ')
        SIZE_GB_INT=$((SIZE_BYTES / 1073741824))  # 1024^3

        # Check if size is in SD card range (8GB - 128GB)
        if [ "$SIZE_GB_INT" -ge 8 ] && [ "$SIZE_GB_INT" -le 128 ]; then
            CANDIDATES+=("/dev/$DEV")
            CANDIDATE_INFO+=("$SIZE $TYPE ${TRAN:-???} $MODEL")
        fi
    done < <(lsblk -d -o NAME,SIZE,TYPE,TRAN,MODEL -n | grep "disk")

    if [ ${#CANDIDATES[@]} -eq 0 ]; then
        echo -e "${RED}No SD card candidates found.${NC}"
        echo "Looking for USB/removable disks between 8GB and 128GB."
        echo ""
        echo "Available disks:"
        lsblk -d -o NAME,SIZE,TYPE,TRAN,MODEL
        echo ""
        echo -e "${YELLOW}Tip: Specify device manually: $0 $IMAGE /dev/sdX${NC}"
        exit 1
    fi

    echo -e "${GREEN}Found ${#CANDIDATES[@]} candidate(s):${NC}"
    echo ""

    for i in "${!CANDIDATES[@]}"; do
        echo -e "  ${BOLD}[$((i+1))]${NC} ${CANDIDATES[$i]} - ${CANDIDATE_INFO[$i]}"
    done

    echo ""

    if [ ${#CANDIDATES[@]} -eq 1 ]; then
        SELECTED="${CANDIDATES[0]}"
        echo -e "Auto-selected: ${YELLOW}$SELECTED${NC}"
    else
        read -p "Select device [1-${#CANDIDATES[@]}]: " -r
        if [[ ! $REPLY =~ ^[0-9]+$ ]] || [ "$REPLY" -lt 1 ] || [ "$REPLY" -gt ${#CANDIDATES[@]} ]; then
            echo -e "${RED}Invalid selection.${NC}"
            exit 1
        fi
        SELECTED="${CANDIDATES[$((REPLY-1))]}"
    fi
fi

# Show current partitions
echo ""
echo -e "${BOLD}Current partitions on $SELECTED:${NC}"
lsblk "$SELECTED" -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT
echo ""

# Unmount any mounted partitions
MOUNTED=$(mount | grep "^${SELECTED}" | awk '{print $1}' || true)
if [ -n "$MOUNTED" ]; then
    echo -e "${YELLOW}Unmounting partitions...${NC}"
    for part in $MOUNTED; do
        umount "$part" 2>/dev/null || true
    done
fi

# Final confirmation
echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║  WARNING: ALL DATA ON THIS DEVICE WILL BE DESTROYED!          ║${NC}"
echo -e "${RED}║  $SELECTED                                                  ║${NC}"
echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
read -p "Type 'yes' to continue: " -r
if [[ ! $REPLY == "yes" ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo -e "${GREEN}Flashing image to $SELECTED...${NC}"
echo ""

if [ "$COMPRESSED" = true ]; then
    case "$COMP_TYPE" in
        xz)  pv "$IMAGE" | xzcat | dd of="$SELECTED" bs=4M conv=fsync 2>/dev/null ;;
        zst) pv "$IMAGE" | zstdcat | dd of="$SELECTED" bs=4M conv=fsync 2>/dev/null ;;
        gz)  pv "$IMAGE" | zcat | dd of="$SELECTED" bs=4M conv=fsync 2>/dev/null ;;
    esac
else
    pv "$IMAGE" | dd of="$SELECTED" bs=4M conv=fsync 2>/dev/null
fi

echo ""
echo -e "${GREEN}Syncing...${NC}"
sync

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Flash Complete!                            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "You can now remove the SD card and boot your Raspberry Pi."
echo ""
echo -e "${YELLOW}Tip:${NC} On first boot, SSH in and the setup wizard will run automatically."
echo ""
