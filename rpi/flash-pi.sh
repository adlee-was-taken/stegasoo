#!/bin/bash
# Flash Raspberry Pi image with headless config
# Usage: ./flash-pi.sh <image.img.xz> <device>
# Reads settings from config.json in same directory

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/config.json"

# ============================================================================
# Load config
# ============================================================================
if [ ! -f "$CONFIG_FILE" ]; then
    echo "Error: config.json not found at $CONFIG_FILE"
    exit 1
fi

PI_USER=$(jq -r '.username' "$CONFIG_FILE")
PI_PASS=$(jq -r '.password' "$CONFIG_FILE")
WIFI_SSID=$(jq -r '.wifiSSID' "$CONFIG_FILE")
WIFI_PASS=$(jq -r '.wifiPassword' "$CONFIG_FILE")
WIFI_COUNTRY=$(jq -r '.wifiCountry' "$CONFIG_FILE")
HOSTNAME=$(jq -r '.hostname' "$CONFIG_FILE")

echo "Loaded config from $CONFIG_FILE"
echo "  Hostname: $HOSTNAME"
echo "  User: $PI_USER"
echo "  WiFi: $WIFI_SSID"
echo

# ============================================================================
# Validate args
# ============================================================================
if [ $# -ne 2 ]; then
    echo "Usage: $0 <image.img.xz> <device>"
    echo "Example: $0 2025-12-04-raspios-trixie-arm64-lite.img.xz /dev/sdb"
    exit 1
fi

IMAGE="$1"
DEVICE="$2"

if [ ! -f "$IMAGE" ]; then
    echo "Error: Image file not found: $IMAGE"
    exit 1
fi

if [ ! -b "$DEVICE" ]; then
    echo "Error: Device not found: $DEVICE"
    exit 1
fi

# Safety check
echo "WARNING: This will ERASE all data on $DEVICE"
echo "Device info:"
lsblk "$DEVICE"
echo
read -p "Type 'yes' to continue: " confirm
if [ "$confirm" != "yes" ]; then
    echo "Aborted."
    exit 1
fi

# ============================================================================
# Flash image
# ============================================================================
echo "Flashing $IMAGE to $DEVICE..."
if [[ "$IMAGE" == *.xz ]]; then
    xzcat "$IMAGE" | sudo dd of="$DEVICE" bs=4M status=progress conv=fsync
elif [[ "$IMAGE" == *.zst ]]; then
    zstdcat "$IMAGE" | sudo dd of="$DEVICE" bs=4M status=progress conv=fsync
else
    sudo dd if="$IMAGE" of="$DEVICE" bs=4M status=progress conv=fsync
fi

echo "Syncing..."
sync

# ============================================================================
# Configure boot partition
# ============================================================================
BOOT_MOUNT=$(mktemp -d)
echo "Mounting boot partition to $BOOT_MOUNT..."

# Wait for partition to appear
sleep 2
sudo partprobe "$DEVICE" 2>/dev/null || true
sleep 1

# Try both partition naming schemes
if [ -b "${DEVICE}1" ]; then
    BOOT_PART="${DEVICE}1"
elif [ -b "${DEVICE}p1" ]; then
    BOOT_PART="${DEVICE}p1"
else
    echo "Error: Could not find boot partition"
    exit 1
fi

sudo mount "$BOOT_PART" "$BOOT_MOUNT"

# Enable SSH
echo "Enabling SSH..."
sudo touch "$BOOT_MOUNT/ssh"

# Set user/password
echo "Setting user credentials..."
PASS_HASH=$(echo "$PI_PASS" | openssl passwd -6 -stdin)
echo "${PI_USER}:${PASS_HASH}" | sudo tee "$BOOT_MOUNT/userconf.txt" > /dev/null

# Set hostname
echo "Setting hostname to $HOSTNAME..."
echo "$HOSTNAME" | sudo tee "$BOOT_MOUNT/hostname" > /dev/null

# Cleanup boot partition
echo "Unmounting boot..."
sudo umount "$BOOT_MOUNT"

# ============================================================================
# Configure rootfs partition (for NetworkManager WiFi)
# ============================================================================
if [ -n "$WIFI_SSID" ]; then
    echo "Configuring WiFi on rootfs..."

    # Find rootfs partition
    if [ -b "${DEVICE}2" ]; then
        ROOT_PART="${DEVICE}2"
    elif [ -b "${DEVICE}p2" ]; then
        ROOT_PART="${DEVICE}p2"
    else
        echo "Warning: Could not find rootfs partition, skipping WiFi config"
        rmdir "$BOOT_MOUNT"
        exit 0
    fi

    sudo mount "$ROOT_PART" "$BOOT_MOUNT"

    # Create NetworkManager connection file
    NM_DIR="$BOOT_MOUNT/etc/NetworkManager/system-connections"
    sudo mkdir -p "$NM_DIR"

    sudo tee "$NM_DIR/$WIFI_SSID.nmconnection" > /dev/null << EOF
[connection]
id=$WIFI_SSID
type=wifi
autoconnect=true

[wifi]
mode=infra
ssid=$WIFI_SSID

[wifi-security]
key-mgmt=wpa-psk
psk=$WIFI_PASS

[ipv4]
method=auto

[ipv6]
method=auto
EOF

    sudo chmod 600 "$NM_DIR/$WIFI_SSID.nmconnection"

    echo "Unmounting rootfs..."
    sudo umount "$BOOT_MOUNT"
fi

rmdir "$BOOT_MOUNT"

echo
echo "Done! SD card is ready."
echo "  Hostname: $HOSTNAME"
echo "  User: $PI_USER"
echo "  SSH: enabled"
echo "  WiFi: $WIFI_SSID"
echo
echo "Insert into Pi and boot. Find it with: ping $HOSTNAME.local"
