#!/bin/bash
# Flash Raspberry Pi image with headless config (Trixie/Bookworm compatible)
# Usage: ./flash-stock-img.sh <image.img.xz> <device>
# Reads settings from config.json in same directory
#
# Uses the same firstrun.sh approach as rpi-imager for compatibility

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
WIFI_COUNTRY=$(jq -r '.wifiCountry // "US"' "$CONFIG_FILE")
PI_HOSTNAME=$(jq -r '.hostname' "$CONFIG_FILE")
PI_TIMEZONE=$(jq -r '.timezone // "America/New_York"' "$CONFIG_FILE")
PI_KEYMAP=$(jq -r '.keyboardLayout // "us"' "$CONFIG_FILE")

echo "Loaded config from $CONFIG_FILE"
echo "  Hostname: $PI_HOSTNAME"
echo "  User: $PI_USER"
echo "  WiFi: $WIFI_SSID"
echo "  Timezone: $PI_TIMEZONE"
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

# Ask about wiping
echo
read -p "Wipe partition table first? (recommended if having issues) [y/N] " wipe_confirm
if [[ "$wipe_confirm" =~ ^[Yy]$ ]]; then
    echo "Wiping partition table..."
    sudo wipefs -a "$DEVICE"
    sudo dd if=/dev/zero of="$DEVICE" bs=1M count=10 status=none
    sync
    echo "  Wiped clean"
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

# Wait for partitions
sleep 2
sudo partprobe "$DEVICE" 2>/dev/null || true
sleep 1

# ============================================================================
# Find partitions
# ============================================================================
if [ -b "${DEVICE}1" ]; then
    BOOT_PART="${DEVICE}1"
    ROOT_PART="${DEVICE}2"
elif [ -b "${DEVICE}p1" ]; then
    BOOT_PART="${DEVICE}p1"
    ROOT_PART="${DEVICE}p2"
else
    echo "Error: Could not find boot partition"
    exit 1
fi

# ============================================================================
# Resize rootfs to 16GB (faster imaging)
# ============================================================================
echo
read -p "Resize rootfs to 16GB for faster imaging? [Y/n] " resize_confirm
if [[ ! "$resize_confirm" =~ ^[Nn]$ ]]; then
    echo "Resizing rootfs partition to 16GB..."

    # Get current partition size in bytes
    CURRENT_SIZE=$(sudo blockdev --getsize64 "$ROOT_PART")
    TARGET_BYTES=$((16 * 1024 * 1024 * 1024))  # 16GB in bytes

    # Get boot partition end in sectors
    BOOT_END=$(sudo parted -s "$DEVICE" unit s print | grep "^ 1" | awk '{print $3}' | tr -d 's')

    # Calculate 16GB in sectors (512 byte sectors)
    ROOT_SIZE_SECTORS=33554432
    ROOT_END=$((BOOT_END + ROOT_SIZE_SECTORS))

    if [ "$CURRENT_SIZE" -lt "$TARGET_BYTES" ]; then
        # EXPANDING: partition first, then filesystem
        echo "Current partition is smaller than 16GB - expanding..."

        # Delete and recreate partition 2 with 16GB size
        echo "Expanding partition to 16GB..."
        sudo parted -s "$DEVICE" rm 2
        sudo parted -s "$DEVICE" mkpart primary ext4 $((BOOT_END + 1))s ${ROOT_END}s

        # Refresh partition table
        sudo partprobe "$DEVICE"
        sleep 2

        # Expand filesystem to fill the new partition
        echo "Expanding filesystem to fill partition..."
        sudo e2fsck -f -y "$ROOT_PART" 2>/dev/null || true
        sudo resize2fs "$ROOT_PART"
    else
        # SHRINKING: filesystem first, then partition
        echo "Current partition is larger than 16GB - shrinking..."

        # Check and shrink filesystem first
        echo "Checking filesystem..."
        sudo e2fsck -f -y "$ROOT_PART" 2>/dev/null || true

        # Shrink filesystem to 15.5GB (leave room for partition overhead)
        echo "Shrinking filesystem to 15500M..."
        sudo resize2fs "$ROOT_PART" 15500M

        # Delete and recreate partition 2 with 16GB size
        echo "Shrinking partition to 16GB..."
        sudo parted -s "$DEVICE" rm 2
        sudo parted -s "$DEVICE" mkpart primary ext4 $((BOOT_END + 1))s ${ROOT_END}s

        # Refresh partition table
        sudo partprobe "$DEVICE"
        sleep 2

        # Expand filesystem to fill the partition exactly
        echo "Expanding filesystem to fill partition..."
        sudo e2fsck -f -y "$ROOT_PART" 2>/dev/null || true
        sudo resize2fs "$ROOT_PART"
    fi

    # Verify and show result
    echo "Verifying partition size..."
    sudo parted -s "$DEVICE" unit GB print | grep "^ 2"

    # Disable Pi OS auto-expand on first boot
    echo "Disabling auto-expand..."
    TEMP_ROOT=$(mktemp -d)
    sudo mount "$ROOT_PART" "$TEMP_ROOT"

    # Remove resize2fs_once service if it exists
    sudo rm -f "$TEMP_ROOT/etc/init.d/resize2fs_once"
    sudo rm -f "$TEMP_ROOT/etc/rc3.d/S01resize2fs_once"

    # Disable the systemd resize service
    sudo rm -f "$TEMP_ROOT/etc/systemd/system/multi-user.target.wants/rpi-resizerootfs.service"

    sudo umount "$TEMP_ROOT"
    rmdir "$TEMP_ROOT"

    echo "  Rootfs set to 16GB (auto-expand disabled)"
fi

MOUNT_DIR=$(mktemp -d)

# ============================================================================
# Configure boot partition with firstrun.sh (rpi-imager method)
# ============================================================================
echo "Mounting boot partition..."
sudo mount "$BOOT_PART" "$MOUNT_DIR"

# Enable SSH
echo "Enabling SSH..."
sudo touch "$MOUNT_DIR/ssh"

# Generate password hash
PASS_HASH=$(echo "$PI_PASS" | openssl passwd -6 -stdin)

# Create firstrun.sh - this is exactly what rpi-imager generates
echo "Creating firstrun.sh..."
sudo tee "$MOUNT_DIR/firstrun.sh" > /dev/null << 'EOFSCRIPT'
#!/bin/bash
set +e

CURRENT_HOSTNAME=$(cat /etc/hostname | tr -d " \t\n\r")
if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_hostname PLACEHOLDER_HOSTNAME
else
   echo PLACEHOLDER_HOSTNAME >/etc/hostname
   sed -i "s/127.0.1.1.*$CURRENT_HOSTNAME/127.0.1.1\tPLACEHOLDER_HOSTNAME/g" /etc/hosts
fi

FIRSTUSER=$(getent passwd 1000 | cut -d: -f1)
FIRSTUSERHOME=$(getent passwd 1000 | cut -d: -f6)

if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom enable_ssh
else
   systemctl enable ssh
fi

if [ -f /usr/lib/userconf-pi/userconf ]; then
   /usr/lib/userconf-pi/userconf 'PLACEHOLDER_USER' 'PLACEHOLDER_HASH'
else
   echo "$FIRSTUSER:"'PLACEHOLDER_HASH' | chpasswd -e
   if [ "$FIRSTUSER" != "PLACEHOLDER_USER" ]; then
      usermod -l "PLACEHOLDER_USER" "$FIRSTUSER"
      usermod -m -d "/home/PLACEHOLDER_USER" "PLACEHOLDER_USER"
      groupmod -n "PLACEHOLDER_USER" "$FIRSTUSER"
      if grep -q "^autologin-user=" /etc/lightdm/lightdm.conf 2>/dev/null; then
         sed -i "s/^autologin-user=.*/autologin-user=PLACEHOLDER_USER/" /etc/lightdm/lightdm.conf
      fi
      if [ -f /etc/systemd/system/getty@tty1.service.d/autologin.conf ]; then
         sed -i "s/$FIRSTUSER/PLACEHOLDER_USER/" /etc/systemd/system/getty@tty1.service.d/autologin.conf
      fi
   fi
fi

if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_keymap 'PLACEHOLDER_KEYMAP'
   /usr/lib/raspberrypi-sys-mods/imager_custom set_timezone 'PLACEHOLDER_TIMEZONE'
fi

if [ -f /usr/lib/raspberrypi-sys-mods/imager_custom ]; then
   /usr/lib/raspberrypi-sys-mods/imager_custom set_wlan 'PLACEHOLDER_SSID' 'PLACEHOLDER_WIFIPASS' 'PLACEHOLDER_COUNTRY'
else
cat >/etc/wpa_supplicant/wpa_supplicant.conf <<'WPAEOF'
country=PLACEHOLDER_COUNTRY
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
ap_scan=1
update_config=1
network={
	ssid="PLACEHOLDER_SSID"
	psk="PLACEHOLDER_WIFIPASS"
}
WPAEOF
   chmod 600 /etc/wpa_supplicant/wpa_supplicant.conf
   rfkill unblock wifi
   for filename in /var/lib/systemd/rfkill/*:wlan ; do
      echo 0 > "$filename"
   done
fi

rm -f /boot/firstrun.sh
rm -f /boot/firmware/firstrun.sh
sed -i 's| systemd.run.*||g' /boot/cmdline.txt 2>/dev/null
sed -i 's| systemd.run.*||g' /boot/firmware/cmdline.txt 2>/dev/null
exit 0
EOFSCRIPT

# Replace placeholders with actual values
sudo sed -i "s/PLACEHOLDER_HOSTNAME/$PI_HOSTNAME/g" "$MOUNT_DIR/firstrun.sh"
sudo sed -i "s/PLACEHOLDER_USER/$PI_USER/g" "$MOUNT_DIR/firstrun.sh"
sudo sed -i "s|PLACEHOLDER_HASH|$PASS_HASH|g" "$MOUNT_DIR/firstrun.sh"
sudo sed -i "s/PLACEHOLDER_KEYMAP/$PI_KEYMAP/g" "$MOUNT_DIR/firstrun.sh"
sudo sed -i "s|PLACEHOLDER_TIMEZONE|$PI_TIMEZONE|g" "$MOUNT_DIR/firstrun.sh"
sudo sed -i "s/PLACEHOLDER_SSID/$WIFI_SSID/g" "$MOUNT_DIR/firstrun.sh"
sudo sed -i "s/PLACEHOLDER_WIFIPASS/$WIFI_PASS/g" "$MOUNT_DIR/firstrun.sh"
sudo sed -i "s/PLACEHOLDER_COUNTRY/$WIFI_COUNTRY/g" "$MOUNT_DIR/firstrun.sh"

sudo chmod +x "$MOUNT_DIR/firstrun.sh"

# Update cmdline.txt to run firstrun.sh on boot
echo "Updating cmdline.txt..."
CMDLINE="$MOUNT_DIR/cmdline.txt"
if [ -f "$CMDLINE" ]; then
    # Read current cmdline, strip existing systemd.run and init= (auto-expand)
    CURRENT=$(cat "$CMDLINE" | tr -d '\n' | sed 's| systemd.run.*||g' | sed 's| init=[^ ]*||g')
    echo "$CURRENT systemd.run=/boot/firmware/firstrun.sh systemd.run_success_action=reboot systemd.unit=kernel-command-line.target" | sudo tee "$CMDLINE" > /dev/null
    echo "  cmdline.txt updated"
fi

sudo umount "$MOUNT_DIR"
rmdir "$MOUNT_DIR"

echo
echo "Done! SD card is ready."
echo "  Hostname: $PI_HOSTNAME"
echo "  User: $PI_USER"
echo "  SSH: enabled"
echo "  WiFi: $WIFI_SSID"
echo
echo "Insert into Pi and boot. Find it with: ping $PI_HOSTNAME.local"

# If we resized, remind about pull-image.sh
if [[ ! "$resize_confirm" =~ ^[Nn]$ ]]; then
    echo
    echo "=== After setup, use pull-image.sh to create distributable image ==="
    echo "  ./pull-image.sh $DEVICE stegasoo-rpi-VERSION.img.zst"
    echo
    echo "This will only pull the 16GB partition, not the entire SD card."
fi
