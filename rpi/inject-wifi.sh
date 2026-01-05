#!/bin/bash
#
# Inject WiFi credentials into SD card for Raspberry Pi
# Supports both Bookworm (NetworkManager) and older (wpa_supplicant)
#
# First-time setup:
#   ./inject-wifi.sh --setup
#
# Then after flashing:
#   sudo ./inject-wifi.sh              # auto-detect partitions
#   sudo ./inject-wifi.sh /dev/sdb     # specify device (finds partitions)
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

CONFIG_DIR="$HOME/.config/stegasoo"
CONFIG_FILE="$CONFIG_DIR/wifi.conf"

# Setup mode - save credentials
if [ "$1" == "--setup" ]; then
    echo -e "${BLUE}Stegasoo WiFi Config Setup${NC}"
    echo ""

    read -p "WiFi SSID: " WIFI_SSID
    read -s -p "WiFi Password: " WIFI_PASS
    echo ""
    read -p "Country code [US]: " WIFI_COUNTRY
    WIFI_COUNTRY=${WIFI_COUNTRY:-US}

    # Generate hashed PSK for wpa_supplicant (legacy)
    if command -v wpa_passphrase &> /dev/null; then
        HASHED_PSK=$(wpa_passphrase "$WIFI_SSID" "$WIFI_PASS" | grep -E "^\s+psk=" | tr -d '\t' | cut -d= -f2)
    else
        HASHED_PSK=""
        echo -e "${YELLOW}Note: wpa_passphrase not found, legacy mode disabled${NC}"
    fi

    # Save config (includes plaintext for NetworkManager)
    mkdir -p "$CONFIG_DIR"
    chmod 700 "$CONFIG_DIR"

    cat > "$CONFIG_FILE" << EOF
# Stegasoo WiFi config
WIFI_SSID="$WIFI_SSID"
WIFI_PASS="$WIFI_PASS"
WIFI_PSK_HASH="$HASHED_PSK"
WIFI_COUNTRY="$WIFI_COUNTRY"
EOF
    chmod 600 "$CONFIG_FILE"

    echo ""
    echo -e "${GREEN}Config saved to $CONFIG_FILE${NC}"
    exit 0
fi

# Normal mode - inject credentials
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Must run as root (sudo)${NC}"
    echo "Usage: sudo $0 [/dev/sdX]"
    echo ""
    echo "First-time setup (no sudo): $0 --setup"
    exit 1
fi

# Load config
if [ -n "$SUDO_USER" ]; then
    USER_HOME=$(getent passwd "$SUDO_USER" | cut -d: -f6)
    CONFIG_FILE="$USER_HOME/.config/stegasoo/wifi.conf"
fi

if [ ! -f "$CONFIG_FILE" ]; then
    echo -e "${RED}Config not found: $CONFIG_FILE${NC}"
    echo ""
    echo "Run setup first (without sudo):"
    echo "  ./inject-wifi.sh --setup"
    exit 1
fi

source "$CONFIG_FILE"

if [ -z "$WIFI_SSID" ] || [ -z "$WIFI_PASS" ]; then
    echo -e "${RED}Invalid config. Run --setup again.${NC}"
    exit 1
fi

# Find partitions
MANUAL_DEV="$1"

if [ -n "$MANUAL_DEV" ]; then
    # Strip partition number if given (e.g., /dev/sdb1 -> /dev/sdb)
    BASE_DEV=$(echo "$MANUAL_DEV" | sed 's/[0-9]*$//')
    BOOT_DEV="${BASE_DEV}1"
    ROOT_DEV="${BASE_DEV}2"
else
    # Auto-detect by label
    BOOT_PART=$(lsblk -o NAME,FSTYPE,LABEL -rn | grep -E "vfat.*(bootfs|boot)" | head -1 | awk '{print $1}')
    ROOT_PART=$(lsblk -o NAME,FSTYPE,LABEL -rn | grep -E "ext4.*rootfs" | head -1 | awk '{print $1}')

    if [ -z "$BOOT_PART" ] || [ -z "$ROOT_PART" ]; then
        echo -e "${RED}Could not find boot/root partitions. Is the SD card inserted?${NC}"
        echo ""
        lsblk -o NAME,SIZE,FSTYPE,LABEL
        echo ""
        echo -e "${YELLOW}Tip: Specify device manually: sudo $0 /dev/sdX${NC}"
        exit 1
    fi

    BOOT_DEV="/dev/$BOOT_PART"
    ROOT_DEV="/dev/$ROOT_PART"
fi

echo -e "${GREEN}Found partitions:${NC}"
echo -e "  Boot: ${YELLOW}$BOOT_DEV${NC}"
echo -e "  Root: ${YELLOW}$ROOT_DEV${NC}"

# Mount points
BOOT_MNT="/tmp/stegasoo-boot-$$"
ROOT_MNT="/tmp/stegasoo-root-$$"

cleanup() {
    umount "$BOOT_MNT" 2>/dev/null || true
    umount "$ROOT_MNT" 2>/dev/null || true
    rmdir "$BOOT_MNT" "$ROOT_MNT" 2>/dev/null || true
}
trap cleanup EXIT

mkdir -p "$BOOT_MNT" "$ROOT_MNT"

# Mount partitions
mount "$BOOT_DEV" "$BOOT_MNT"
mount "$ROOT_DEV" "$ROOT_MNT"

echo ""

# 1. Write NetworkManager config (Bookworm+)
NM_DIR="$ROOT_MNT/etc/NetworkManager/system-connections"
if [ -d "$ROOT_MNT/etc/NetworkManager" ]; then
    mkdir -p "$NM_DIR"

    # NetworkManager connection file
    NM_FILE="$NM_DIR/stegasoo-wifi.nmconnection"
    cat > "$NM_FILE" << EOF
[connection]
id=$WIFI_SSID
type=wifi
autoconnect=true

[wifi]
mode=infrastructure
ssid=$WIFI_SSID

[wifi-security]
auth-alg=open
key-mgmt=wpa-psk
psk=$WIFI_PASS

[ipv4]
method=auto

[ipv6]
method=auto
EOF
    chmod 600 "$NM_FILE"
    echo -e "${GREEN}Created NetworkManager config (Bookworm)${NC}"
fi

# 2. Write wpa_supplicant.conf (legacy, boot partition)
if [ -n "$WIFI_PSK_HASH" ]; then
    cat > "$BOOT_MNT/wpa_supplicant.conf" << EOF
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=$WIFI_COUNTRY

network={
    ssid="$WIFI_SSID"
    psk=$WIFI_PSK_HASH
}
EOF
    echo -e "${GREEN}Created wpa_supplicant.conf (legacy)${NC}"
fi

# 3. Set WiFi country in boot config
if [ -f "$BOOT_MNT/config.txt" ]; then
    if ! grep -q "^dtparam=cfg80211" "$BOOT_MNT/config.txt"; then
        echo "" >> "$BOOT_MNT/config.txt"
        echo "# WiFi country" >> "$BOOT_MNT/config.txt"
        echo "dtparam=cfg80211" >> "$BOOT_MNT/config.txt"
    fi
fi

echo -e "  SSID: ${YELLOW}$WIFI_SSID${NC}"

echo ""
echo -e "${GREEN}Done! WiFi credentials injected for Bookworm + legacy.${NC}"
