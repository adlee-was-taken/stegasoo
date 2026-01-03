#!/bin/bash
#
# Pull Stegasoo image from SD card
# Auto-detects SD card, copies with progress, shrinks, and compresses
#
# Usage: ./pull-image.sh [output-name]
#        Output will be: stegasoo-rpi-YYYYMMDD.img.zst (or custom name)
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Check for required tools
for cmd in dd pv zstd lsblk; do
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

# Output filename
if [ -n "$1" ]; then
    OUTPUT="$1"
else
    OUTPUT="stegasoo-rpi-$(date +%Y%m%d).img.zst"
fi

# Remove .zst extension for intermediate file
IMG_FILE="${OUTPUT%.zst}"
if [[ "$IMG_FILE" == "$OUTPUT" ]]; then
    IMG_FILE="${OUTPUT}.img"
    OUTPUT="${OUTPUT}.img.zst"
fi

echo -e "${BLUE}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║              Stegasoo SD Card Image Puller                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

# Auto-detect SD card candidates
# Looking for: USB/removable, 8-128GB, not mounted as root filesystem
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

    # Parse size to bytes for comparison
    SIZE_NUM=$(echo "$SIZE" | sed 's/[^0-9.]//g')
    SIZE_UNIT=$(echo "$SIZE" | sed 's/[0-9.]//g')

    case $SIZE_UNIT in
        G) SIZE_GB=$SIZE_NUM ;;
        T) SIZE_GB=$(echo "$SIZE_NUM * 1024" | bc) ;;
        M) SIZE_GB=$(echo "scale=2; $SIZE_NUM / 1024" | bc) ;;
        *) SIZE_GB=0 ;;
    esac

    # Check if size is in SD card range (8GB - 128GB)
    if (( $(echo "$SIZE_GB >= 8" | bc -l) )) && (( $(echo "$SIZE_GB <= 128" | bc -l) )); then
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

# Show partitions
echo ""
echo -e "${BOLD}Partitions on $SELECTED:${NC}"
lsblk "$SELECTED" -o NAME,SIZE,FSTYPE,LABEL,MOUNTPOINT
echo ""

# Final confirmation
echo -e "${RED}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${RED}║  WARNING: This will read the ENTIRE device:                   ║${NC}"
echo -e "${RED}║  $SELECTED                                                  ║${NC}"
echo -e "${RED}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Output: ${YELLOW}$OUTPUT${NC}"
echo ""
read -p "Continue? [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

# Get device size for pv
DEV_SIZE=$(blockdev --getsize64 "$SELECTED")

echo ""
echo -e "${GREEN}[1/3]${NC} Copying image from $SELECTED..."
dd if="$SELECTED" bs=4M status=none | pv -s "$DEV_SIZE" > "$IMG_FILE"
sync

echo ""
echo -e "${GREEN}[2/3]${NC} Shrinking image..."
if command -v pishrink.sh &> /dev/null; then
    pishrink.sh "$IMG_FILE"
elif [ -f "./pishrink.sh" ]; then
    bash ./pishrink.sh "$IMG_FILE"
elif [ -f "../pishrink.sh" ]; then
    bash ../pishrink.sh "$IMG_FILE"
else
    echo -e "${YELLOW}pishrink.sh not found, skipping shrink step.${NC}"
    echo "Download from: https://github.com/Drewsif/PiShrink"
fi

echo ""
echo -e "${GREEN}[3/3]${NC} Compressing with zstd..."
pv "$IMG_FILE" | zstd -19 -T0 -q > "$OUTPUT"
rm -f "$IMG_FILE"

echo ""
FINAL_SIZE=$(du -h "$OUTPUT" | awk '{print $1}')
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Image Complete!                            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Output: ${YELLOW}$OUTPUT${NC}"
echo -e "Size:   ${YELLOW}$FINAL_SIZE${NC}"
echo ""
