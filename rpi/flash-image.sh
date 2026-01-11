#!/bin/bash
#
# Flash Stegasoo image to SD card
# Uses rpi-imager if available, falls back to dd
#
# Usage: ./flash-image.sh <image> [device]
#
# Supports: .img, .img.zst, .img.xz, .img.gz, .img.zst.zip (GitHub release format)
# If device is specified, skips auto-detection (useful for NVMe/large drives)
#
# Optional: Place config.json in same directory for headless WiFi setup
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m'

# Load config if present (optional - for headless WiFi setup)
HAS_CONFIG=false
if [ -f "$CONFIG_FILE" ] && command -v jq &> /dev/null; then
    WIFI_SSID=$(jq -r '.wifiSSID // empty' "$CONFIG_FILE")
    WIFI_PASS=$(jq -r '.wifiPassword // empty' "$CONFIG_FILE")
    WIFI_COUNTRY=$(jq -r '.wifiCountry // "US"' "$CONFIG_FILE")
    PI_HOSTNAME=$(jq -r '.hostname // empty' "$CONFIG_FILE")
    if [ -n "$WIFI_SSID" ] && [ -n "$WIFI_PASS" ]; then
        HAS_CONFIG=true
        echo -e "${GREEN}Found config.json - will configure WiFi after flash${NC}"
        echo -e "  WiFi: ${YELLOW}$WIFI_SSID${NC}"
        if [ -n "$PI_HOSTNAME" ]; then
            echo -e "  Hostname: ${YELLOW}$PI_HOSTNAME${NC}"
        fi
        echo ""
    fi
elif [ -f "$CONFIG_FILE" ]; then
    echo -e "${YELLOW}Note: config.json found but jq not installed (apt install jq)${NC}"
    echo -e "${YELLOW}      WiFi will need to be configured manually after boot${NC}"
    echo ""
fi

# Check for required tools
for cmd in dd lsblk; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}Error: $cmd is required but not installed.${NC}"
        exit 1
    fi
done

# Check for optional tools
HAS_RPI_IMAGER=false
HAS_PV=false
if command -v rpi-imager &> /dev/null; then
    HAS_RPI_IMAGER=true
fi
if command -v pv &> /dev/null; then
    HAS_PV=true
fi

if [ "$HAS_RPI_IMAGER" = false ] && [ "$HAS_PV" = false ]; then
    echo -e "${YELLOW}Warning: Neither rpi-imager nor pv found. Progress will not be shown.${NC}"
fi

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
    echo "  $0 stegasoo-rpi-4.2.1.img.zst             # auto-detect SD card"
    echo "  $0 stegasoo-rpi-4.2.1.img.zst.zip         # from GitHub release"
    echo "  $0 stegasoo-rpi-4.2.1.img.zst /dev/sdb    # specify device"
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

# Ask about wiping (defer actual wipe until after final confirmation)
echo
read -p "Wipe partition table first? (recommended if having issues) [y/N] " wipe_confirm

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

# Now wipe if requested
if [[ "$wipe_confirm" =~ ^[Yy]$ ]]; then
    echo "Wiping partition table..."
    sudo wipefs -af "$SELECTED" 2>/dev/null || true
    sync
    echo "  Wiped"
fi

echo ""
echo -e "${GREEN}Flashing image to $SELECTED...${NC}"
echo ""

# Flash with dd (status=progress shows actual write progress)
echo -e "${YELLOW}Flashing (this may take several minutes for SD cards)...${NC}"
if [ "$COMPRESSED" = true ]; then
    case "$COMP_TYPE" in
        xz)  xzcat "$IMAGE" | sudo dd of="$SELECTED" bs=1M status=progress ;;
        zst) zstdcat "$IMAGE" | sudo dd of="$SELECTED" bs=1M status=progress ;;
        gz)  zcat "$IMAGE" | sudo dd of="$SELECTED" bs=1M status=progress ;;
    esac
else
    sudo dd if="$IMAGE" of="$SELECTED" bs=1M status=progress
fi

echo ""
echo -e "${GREEN}Syncing...${NC}"
sync

# Wait for partitions to appear
sleep 2
partprobe "$SELECTED" 2>/dev/null || true
sleep 1

# Determine partition names
if [[ "$SELECTED" == *"nvme"* ]] || [[ "$SELECTED" == *"mmcblk"* ]]; then
    BOOT_PART="${SELECTED}p1"
    ROOT_PART="${SELECTED}p2"
else
    BOOT_PART="${SELECTED}1"
    ROOT_PART="${SELECTED}2"
fi

# Validate and repair filesystems
echo ""
echo -e "${YELLOW}Validating filesystems...${NC}"

echo "  Checking boot partition ($BOOT_PART)..."
sudo fsck.vfat -a "$BOOT_PART" 2>&1 | grep -v "^$" || true

echo "  Checking root partition ($ROOT_PART)..."
sudo e2fsck -f -y "$ROOT_PART" 2>&1 | tail -5 || true

echo -e "${GREEN}  ✓ Filesystems validated${NC}"

# Inject WiFi config if config.json was loaded
if [ "$HAS_CONFIG" = true ]; then
    echo ""
    echo -e "${GREEN}Configuring WiFi from config.json...${NC}"

    if [ -b "$BOOT_PART" ]; then
        MOUNT_DIR=$(mktemp -d)
        if mount "$BOOT_PART" "$MOUNT_DIR" 2>/dev/null; then
            # Create firstrun.sh for WiFi setup
            cat > "$MOUNT_DIR/firstrun.sh" << 'EOFSCRIPT'
#!/bin/bash
set +e

# Set hostname if provided
if [ -n "PLACEHOLDER_HOSTNAME" ] && [ "PLACEHOLDER_HOSTNAME" != "" ]; then
    CURRENT_HOSTNAME=$(cat /etc/hostname | tr -d " \t\n\r")
    if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
        /usr/lib/raspberrypi-sys-mods/imager_custom set_hostname PLACEHOLDER_HOSTNAME
    else
        echo PLACEHOLDER_HOSTNAME >/etc/hostname
        sed -i "s/127.0.1.1.*$CURRENT_HOSTNAME/127.0.1.1\tPLACEHOLDER_HOSTNAME/g" /etc/hosts
    fi
fi

# Configure WiFi
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
    /usr/lib/raspberrypi-sys-mods/imager_custom set_wlan 'PLACEHOLDER_SSID' 'PLACEHOLDER_WIFIPASS' 'PLACEHOLDER_COUNTRY'
else
    # NetworkManager method (Trixie)
    cat >/etc/NetworkManager/system-connections/preconfigured.nmconnection <<'NMEOF'
[connection]
id=preconfigured
type=wifi
autoconnect=true

[wifi]
mode=infrastructure
ssid=PLACEHOLDER_SSID

[wifi-security]
auth-alg=open
key-mgmt=wpa-psk
psk=PLACEHOLDER_WIFIPASS

[ipv4]
method=auto

[ipv6]
method=auto
NMEOF
    chmod 600 /etc/NetworkManager/system-connections/preconfigured.nmconnection
    rfkill unblock wifi
fi

# Cleanup
rm -f /boot/firstrun.sh
rm -f /boot/firmware/firstrun.sh
sed -i 's| systemd.run.*||g' /boot/cmdline.txt 2>/dev/null
sed -i 's| systemd.run.*||g' /boot/firmware/cmdline.txt 2>/dev/null
exit 0
EOFSCRIPT

            # Replace placeholders
            sed -i "s/PLACEHOLDER_SSID/$WIFI_SSID/g" "$MOUNT_DIR/firstrun.sh"
            sed -i "s/PLACEHOLDER_WIFIPASS/$WIFI_PASS/g" "$MOUNT_DIR/firstrun.sh"
            sed -i "s/PLACEHOLDER_COUNTRY/$WIFI_COUNTRY/g" "$MOUNT_DIR/firstrun.sh"
            if [ -n "$PI_HOSTNAME" ]; then
                sed -i "s/PLACEHOLDER_HOSTNAME/$PI_HOSTNAME/g" "$MOUNT_DIR/firstrun.sh"
            else
                sed -i "s/PLACEHOLDER_HOSTNAME//g" "$MOUNT_DIR/firstrun.sh"
            fi
            chmod +x "$MOUNT_DIR/firstrun.sh"

            # Update cmdline.txt to run firstrun.sh
            CMDLINE="$MOUNT_DIR/cmdline.txt"
            if [ -f "$CMDLINE" ]; then
                CURRENT=$(cat "$CMDLINE" | tr -d '\n' | sed 's| systemd.run.*||g')
                echo "$CURRENT systemd.run=/boot/firmware/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target" > "$CMDLINE"
            fi

            umount "$MOUNT_DIR"
            echo -e "  ${GREEN}✓${NC} WiFi configured for: $WIFI_SSID"
        else
            echo -e "  ${YELLOW}⚠${NC} Could not mount boot partition"
        fi
        rmdir "$MOUNT_DIR" 2>/dev/null || true
    else
        echo -e "  ${YELLOW}⚠${NC} Boot partition not found"
    fi
fi

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Flash Complete!                            ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "You can now remove the SD card and boot your Raspberry Pi."
echo ""
if [ "$HAS_CONFIG" = true ]; then
    echo -e "${GREEN}WiFi pre-configured${NC} - Pi will connect to $WIFI_SSID on boot"
    echo -e "SSH: ${YELLOW}ssh admin@${PI_HOSTNAME:-stegasoo}.local${NC} (password: stegasoo)"
else
    echo -e "${YELLOW}Tip:${NC} On first boot, the setup wizard will help configure WiFi."
    echo -e "${YELLOW}Tip:${NC} Or place config.json in rpi/ for headless setup next time."
fi
echo ""
