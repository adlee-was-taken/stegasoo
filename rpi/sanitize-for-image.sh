#!/bin/bash
#
# Sanitize Raspberry Pi for SD Card Image Distribution
# Run this BEFORE creating an image with dd
#
# This script removes:
#   - WiFi credentials (unless --soft)
#   - SSH host keys (will regenerate on boot)
#   - SSH authorized keys
#   - User-specific data
#   - Bash history
#   - Logs
#   - Stegasoo auth database (users will create their own admin)
#
# Usage:
#   sudo ./sanitize-for-image.sh                 # Full sanitize for image distribution
#   sudo ./sanitize-for-image.sh --soft          # Soft reset (keeps WiFi for testing)
#   sudo ./sanitize-for-image.sh --soft --reboot # Soft reset and auto-reboot
#   sudo ./sanitize-for-image.sh --reboot        # Full sanitize and auto-shutdown
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m'

# Show help
show_help() {
    echo "Stegasoo Sanitize Script - Prepare Pi for SD Card Imaging"
    echo ""
    echo "Usage: sudo $0 [options]"
    echo ""
    echo "Options:"
    echo "  -h, --help     Show this help message"
    echo "  -s, --soft     Soft reset (keeps WiFi for testing)"
    echo "  -r, --reboot   Auto-reboot/shutdown when done"
    echo ""
    echo "Examples:"
    echo "  sudo $0                 # Full sanitize, prompts for shutdown"
    echo "  sudo $0 --soft          # Keep WiFi, reset everything else"
    echo "  sudo $0 --soft --reboot # Soft reset, auto-reboot"
    echo "  sudo $0 --reboot        # Full sanitize, auto-shutdown"
    echo ""
    echo "Config override:"
    echo "  Set STEGASOO_DIR to specify a custom install location:"
    echo "    export STEGASOO_DIR=\"/home/pi/stegasoo\""
    echo "    sudo -E $0"
    echo ""
    exit 0
}

SOFT_RESET=false
AUTO_REBOOT=false
for arg in "$@"; do
    case $arg in
        -h|--help) show_help ;;
        --soft|-s) SOFT_RESET=true ;;
        --reboot|-r) AUTO_REBOOT=true ;;
    esac
done

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Must run as root (sudo)${NC}"
    exit 1
fi

clear
echo ""
echo -e "${GRAY} . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · .${NC}"
echo -e "${GRAY} · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . ·${NC}"
echo -e "${GRAY} . · . · . · . · . · . ${CYAN}/\\\\${GRAY} · . · ${CYAN}/\\\\${GRAY} · . · ${CYAN}/\\\\${GRAY} · . · ${CYAN}/\\\\${GRAY} · . · . · . .${NC}"
echo -e "${GRAY} · . · . · . · . · . · ${CYAN}\\\\/${GRAY} · . · ${CYAN}\\\\/${GRAY} · . · ${CYAN}\\\\/${GRAY} · . · ${CYAN}\\\\/${GRAY} · . · . · . ·${NC}"
echo -e "${GRAY} . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · .${NC}"
echo -e "${GRAY} · .   ${CYAN}___  _____  ___    ___    _    ___    ___    ___${GRAY}    . · . ·${NC}"
echo -e "${GRAY} . ·  ${CYAN}/ __||_   _|| __|  / __|  /_\\\\  / __|  / _ \\\\  / _ \\\\${GRAY}   · . · ·${NC}"
echo -e "${GRAY} · .  ${CYAN}/ __||_   _|| __|  / __|  /_\\\\  / __|  / _ \\\\  / _ \\\\${GRAY}   . · . ·${NC}"
echo -e "${GRAY} . ·  ${CYAN}\\\\__ \\\\  | |  | _|  | (_ | / _ \\\\ \\\\__ \\\\ | (_) || (_) |${GRAY}  · . · ·${NC}"
echo -e "${GRAY} · .  ${CYAN}\\\\__ \\\\  | |  | _|  | (_ | / _ \\\\ \\\\__ \\\\ | (_) || (_) |${GRAY}  . · . ·${NC}"
echo -e "${GRAY} . ·  ${CYAN}|___/  |_|  |___|  \\___|/_/ \\_\\\\|___/  \\\\___/  \\\\___/${GRAY}   · . · ·${NC}"
echo -e "${GRAY} · .  ${CYAN}|___/  |_|  |___|  \\___|/_/ \\_\\\\|___/  \\\\___/  \\\\___/${GRAY}   . · . ·${NC}"
echo -e "${GRAY} · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . ·${NC}"
echo -e "${GRAY} . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · .${NC}"
if [ "$SOFT_RESET" = true ]; then
    echo -e "${GRAY} · . · ${CYAN}~~~~${GRAY} · . · . · ${CYAN}Soft Reset (Factory)${GRAY} · . · . ${CYAN}~~~~${GRAY} · . · . ·${NC}"
else
    echo -e "${GRAY} · . · ${CYAN}~~~~${GRAY} · . · . ${CYAN}Sanitize for Imaging${GRAY} · . · . · ${CYAN}~~~~${GRAY} · . · . ·${NC}"
fi
echo -e "${GRAY} . · . ${CYAN}~~~~${GRAY} · . · . · . · . · . · . · . · . · . · . ${CYAN}~~~~${GRAY} · . · . .${NC}"
echo -e "${GRAY} · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . ·${NC}"
echo ""

if [ "$SOFT_RESET" = true ]; then
    echo "  WiFi credentials will be KEPT for continued testing."
    echo "  Everything else will be reset to first-boot state."
else
    echo "  This will remove ALL personal data for imaging."
    echo "  The system will shut down when complete."
fi
echo ""

if [ "$AUTO_REBOOT" = false ]; then
    # Flush input buffer before prompt
    read -t 0.1 -n 10000 discard </dev/tty 2>/dev/null || true
    read -p "Continue? This cannot be undone! [y/N] " -n 1 -r </dev/tty
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Aborted."
        exit 1
    fi
fi

# Track validation results
VALIDATION_ERRORS=0

# =============================================================================
# Step 1: WiFi Credentials
# =============================================================================
if [ "$SOFT_RESET" = true ]; then
    echo -e "${GREEN}[1/10]${NC} Keeping WiFi credentials (soft reset)..."
    echo "  WiFi config preserved"
else
    echo -e "${GREEN}[1/10]${NC} Removing WiFi credentials..."

    # Remove from rootfs
    if [ -f /etc/wpa_supplicant/wpa_supplicant.conf ]; then
        cat > /etc/wpa_supplicant/wpa_supplicant.conf << 'EOF'
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1
country=US

# Add your WiFi network here on first boot:
# network={
#     ssid="YourNetworkName"
#     psk="YourPassword"
# }
EOF
        echo "  Cleared /etc/wpa_supplicant/wpa_supplicant.conf"
    fi

    # Remove from boot partition (headless setup file)
    BOOT_PART=$(findmnt -n -o SOURCE /boot/firmware 2>/dev/null || findmnt -n -o SOURCE /boot 2>/dev/null || echo "")
    if [ -n "$BOOT_PART" ]; then
        BOOT_MOUNT=$(findmnt -n -o TARGET "$BOOT_PART" 2>/dev/null || echo "/boot")
        rm -f "$BOOT_MOUNT/wpa_supplicant.conf" 2>/dev/null || true
        echo "  Removed boot partition WiFi config"
    fi

    # Remove NetworkManager connections (RPi OS Bookworm+)
    if [ -d /etc/NetworkManager/system-connections ]; then
        # Remove all WiFi connections (files containing type=wifi)
        for conn in /etc/NetworkManager/system-connections/*; do
            if [ -f "$conn" ] && grep -q "type=wifi" "$conn" 2>/dev/null; then
                rm -f "$conn"
                echo "  Removed NetworkManager: $(basename "$conn")"
            fi
        done
    fi

    # Remove netplan WiFi configs (Ubuntu-based systems)
    if [ -d /etc/netplan ]; then
        for np in /etc/netplan/*.yaml; do
            if [ -f "$np" ] && grep -q "wifis:" "$np" 2>/dev/null; then
                rm -f "$np"
                echo "  Removed netplan: $(basename "$np")"
            fi
        done
        # Also remove NM-generated netplan files (contain WiFi SSIDs)
        rm -f /etc/netplan/90-NM-*.yaml 2>/dev/null && echo "  Removed netplan NM configs"
    fi
fi

# =============================================================================
# Step 2: SSH Authorized Keys
# =============================================================================
echo -e "${GREEN}[2/10]${NC} Removing SSH authorized keys..."
for user_home in /home/*; do
    if [ -d "$user_home/.ssh" ]; then
        rm -f "$user_home/.ssh/authorized_keys"
        rm -f "$user_home/.ssh/known_hosts"
        echo "  Cleared $user_home/.ssh/"
    fi
done
rm -f /root/.ssh/authorized_keys /root/.ssh/known_hosts 2>/dev/null || true

# =============================================================================
# Step 3: SSH Host Keys
# =============================================================================
echo -e "${GREEN}[3/10]${NC} Removing SSH host keys (will regenerate on first boot)..."
rm -f /etc/ssh/ssh_host_*

# Create a first-boot service to regenerate SSH keys
cat > /etc/systemd/system/regenerate-ssh-keys.service <<'SSHEOF'
[Unit]
Description=Regenerate SSH host keys on first boot
Before=ssh.service
ConditionPathExists=!/etc/ssh/ssh_host_ed25519_key

[Service]
Type=oneshot
ExecStart=/usr/bin/ssh-keygen -A

[Install]
WantedBy=multi-user.target
SSHEOF

systemctl enable regenerate-ssh-keys.service 2>/dev/null || true
echo "  SSH host keys removed (will regenerate on first boot)"

# =============================================================================
# Step 4: Bash History
# =============================================================================
echo -e "${GREEN}[4/10]${NC} Clearing bash history..."
for user_home in /home/*; do
    rm -f "$user_home/.bash_history"
    rm -f "$user_home/.python_history"
done
rm -f /root/.bash_history /root/.python_history 2>/dev/null || true
history -c 2>/dev/null || true

# =============================================================================
# Step 5: Stegasoo User Data
# =============================================================================
echo -e "${GREEN}[5/10]${NC} Removing Stegasoo user data..."
# Remove auth database (users create their own admin on first run)
rm -rf /opt/stegasoo/frontends/web/instance/ 2>/dev/null
rm -rf /home/*/stegasoo/frontends/web/instance/
# Remove SSL certs (will be regenerated)
rm -rf /opt/stegasoo/frontends/web/certs/ 2>/dev/null
rm -rf /home/*/stegasoo/frontends/web/certs/
# Remove any .env files with channel keys
rm -f /opt/stegasoo/frontends/web/.env 2>/dev/null
rm -f /home/*/stegasoo/frontends/web/.env
echo "  Stegasoo instance data cleared"

# =============================================================================
# Step 6: First-Boot Wizard Setup
# =============================================================================
echo -e "${GREEN}[6/10]${NC} Setting up first-boot wizard..."

# Find stegasoo install directory (prefer /opt/stegasoo)
STEGASOO_DIR=""
if [ -d /opt/stegasoo ]; then
    STEGASOO_DIR="/opt/stegasoo"
else
    STEGASOO_DIR=$(ls -d /home/*/stegasoo 2>/dev/null | head -1)
fi

if [ -z "$STEGASOO_DIR" ]; then
    # Last resort fallback
    if [ -d /root/stegasoo ]; then
        STEGASOO_DIR="/root/stegasoo"
    fi
fi

STEGASOO_USER=$(stat -c '%U' "$STEGASOO_DIR" 2>/dev/null || echo "pi")
echo "  Stegasoo directory: $STEGASOO_DIR"
echo "  Stegasoo user: $STEGASOO_USER"

# Check and repair venv if needed (paths break when moving directories)
if [ -n "$STEGASOO_DIR" ] && [ -d "$STEGASOO_DIR/venv" ]; then
    VENV_PYTHON="$STEGASOO_DIR/venv/bin/python"
    # Check if venv python works and has stegasoo installed
    if ! "$VENV_PYTHON" -c "import stegasoo" 2>/dev/null; then
        echo "  Venv broken or stegasoo not installed, rebuilding..."
        rm -rf "$STEGASOO_DIR/venv"
        sudo -u "$STEGASOO_USER" python3 -m venv "$STEGASOO_DIR/venv"
        sudo -u "$STEGASOO_USER" "$STEGASOO_DIR/venv/bin/pip" install --quiet -e "$STEGASOO_DIR[web]"
        echo "  Venv rebuilt and stegasoo installed"
    else
        echo "  Venv OK"
    fi
fi

if [ -n "$STEGASOO_DIR" ] && [ -f "$STEGASOO_DIR/rpi/stegasoo-wizard.sh" ]; then
    # Install the profile.d hook
    cp "$STEGASOO_DIR/rpi/stegasoo-wizard.sh" /etc/profile.d/stegasoo-wizard.sh
    chmod 644 /etc/profile.d/stegasoo-wizard.sh
    echo "  Installed wizard hook to /etc/profile.d/"

    # Create the first-boot flag
    touch /etc/stegasoo-first-boot
    echo "  Created /etc/stegasoo-first-boot flag"

    # Reset systemd service to defaults (wizard will reconfigure)
    cat > /etc/systemd/system/stegasoo.service <<EOF
[Unit]
Description=Stegasoo Web UI
After=network.target

[Service]
Type=simple
User=$STEGASOO_USER
WorkingDirectory=$STEGASOO_DIR/frontends/web
Environment="PATH=$STEGASOO_DIR/venv/bin:/usr/bin"
Environment="STEGASOO_AUTH_ENABLED=true"
Environment="STEGASOO_HTTPS_ENABLED=false"
Environment="STEGASOO_PORT=5000"
Environment="STEGASOO_CHANNEL_KEY="
ExecStart=$STEGASOO_DIR/venv/bin/python app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
    systemctl daemon-reload
    echo "  Reset systemd service to defaults"
else
    echo -e "  ${RED}ERROR: Could not find wizard script${NC}"
    echo "  STEGASOO_DIR: $STEGASOO_DIR"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
fi

# =============================================================================
# Step 7: Logs
# =============================================================================
echo -e "${GREEN}[7/10]${NC} Clearing logs..."
journalctl --rotate 2>/dev/null || true
journalctl --vacuum-time=1s 2>/dev/null || true
rm -rf /var/log/*.log /var/log/*.gz /var/log/*.[0-9] 2>/dev/null || true
rm -rf /var/log/apt/* 2>/dev/null || true
rm -rf /var/log/journal/* 2>/dev/null || true
find /var/log -type f -name "*.log" -delete 2>/dev/null || true
echo "  Logs cleared"

# =============================================================================
# Step 8: Temporary Files
# =============================================================================
echo -e "${GREEN}[8/10]${NC} Clearing temporary files..."
rm -rf /tmp/* 2>/dev/null || true
rm -rf /var/tmp/* 2>/dev/null || true
echo "  Temp files cleared"

# =============================================================================
# Step 9: Package Cache
# =============================================================================
echo -e "${GREEN}[9/10]${NC} Clearing package cache..."
apt-get clean 2>/dev/null || true
rm -rf /var/cache/apt/archives/* 2>/dev/null || true
echo "  Package cache cleared"

# =============================================================================
# Step 10: Final Sync
# =============================================================================
echo -e "${GREEN}[10/10]${NC} Final sync..."
rm -f /root/.bash_history 2>/dev/null || true
sync
echo "  Filesystem synced"

# =============================================================================
# Validation
# =============================================================================
echo ""
echo -e "${CYAN}Validating sanitization...${NC}"

# Check first-boot flag
if [ -f /etc/stegasoo-first-boot ]; then
    echo -e "  ${GREEN}[PASS]${NC} First-boot flag exists"
else
    echo -e "  ${RED}[FAIL]${NC} First-boot flag missing"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
fi

# Check profile.d hook
if [ -f /etc/profile.d/stegasoo-wizard.sh ]; then
    echo -e "  ${GREEN}[PASS]${NC} Wizard hook installed"
else
    echo -e "  ${RED}[FAIL]${NC} Wizard hook missing"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
fi

# Check SSH host keys removed
if ls /etc/ssh/ssh_host_* 1>/dev/null 2>&1; then
    echo -e "  ${RED}[FAIL]${NC} SSH host keys still present"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
else
    echo -e "  ${GREEN}[PASS]${NC} SSH host keys removed"
fi

# Check Stegasoo instance data removed
DB_FOUND=false
if ls /opt/stegasoo/frontends/web/instance/*.db 1>/dev/null 2>&1; then
    DB_FOUND=true
fi
if ls /home/*/stegasoo/frontends/web/instance/*.db 1>/dev/null 2>&1; then
    DB_FOUND=true
fi
if [ "$DB_FOUND" = true ]; then
    echo -e "  ${RED}[FAIL]${NC} Stegasoo database still present"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
else
    echo -e "  ${GREEN}[PASS]${NC} Stegasoo database removed"
fi

# Check WiFi (only for full sanitize)
if [ "$SOFT_RESET" = false ]; then
    WIFI_FOUND=false

    # Check wpa_supplicant
    if grep -q "psk=" /etc/wpa_supplicant/wpa_supplicant.conf 2>/dev/null; then
        WIFI_FOUND=true
    fi

    # Check NetworkManager
    for conn in /etc/NetworkManager/system-connections/*; do
        if [ -f "$conn" ] && grep -q "type=wifi" "$conn" 2>/dev/null; then
            WIFI_FOUND=true
            break
        fi
    done

    # Check netplan
    for np in /etc/netplan/*.yaml; do
        if [ -f "$np" ] && grep -q "wifis:" "$np" 2>/dev/null; then
            WIFI_FOUND=true
            break
        fi
    done
    # Check NM-generated netplan
    if ls /etc/netplan/90-NM-*.yaml 1>/dev/null 2>&1; then
        WIFI_FOUND=true
    fi

    if [ "$WIFI_FOUND" = true ]; then
        echo -e "  ${RED}[FAIL]${NC} WiFi credentials still present"
        VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
    else
        echo -e "  ${GREEN}[PASS]${NC} WiFi credentials cleared"
    fi
else
    echo -e "  ${YELLOW}[SKIP]${NC} WiFi check (soft reset mode)"
fi

# Check authorized_keys removed
AUTH_KEYS_FOUND=false
for user_home in /home/*; do
    if [ -f "$user_home/.ssh/authorized_keys" ]; then
        AUTH_KEYS_FOUND=true
        break
    fi
done
if [ "$AUTH_KEYS_FOUND" = true ]; then
    echo -e "  ${RED}[FAIL]${NC} SSH authorized_keys still present"
    VALIDATION_ERRORS=$((VALIDATION_ERRORS + 1))
else
    echo -e "  ${GREEN}[PASS]${NC} SSH authorized_keys removed"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
if [ $VALIDATION_ERRORS -eq 0 ]; then
    echo -e "${BOLD}Sanitization Complete!${NC}"
    echo -e "${GREEN}-------------------------------------------------------${NC}"
    echo -e "  ${GREEN}All validation checks passed.${NC}"
else
    echo -e "${BOLD}Sanitization Complete with Errors${NC}"
    echo -e "${RED}-------------------------------------------------------${NC}"
    echo -e "  ${RED}$VALIDATION_ERRORS validation check(s) failed${NC}"
fi
echo ""

if [ "$SOFT_RESET" = true ]; then
    echo -e "${CYAN}Soft reset complete.${NC}"
    echo "You can now reboot to test the first-boot wizard."
    echo ""
    if [ "$AUTO_REBOOT" = true ]; then
        echo "Rebooting..."
        exec reboot
    fi
    # Flush input buffer and pause before prompt
    read -t 0.1 -n 10000 discard </dev/tty 2>/dev/null || true
    sleep 0.3
    read -p "Reboot now? [y/N] " -n 1 -r </dev/tty
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        exec reboot
    fi
else
    echo "The system is ready for imaging."
    echo ""
    echo -e "${YELLOW}Next steps:${NC}"
    echo "  1. Shut down: sudo shutdown -h now"
    echo "  2. Remove SD card"
    echo "  3. On another machine, copy with:"
    echo "     sudo dd if=/dev/sdX of=stegasoo-rpi.img bs=4M status=progress"
    echo "  4. Compress: zstd -19 stegasoo-rpi.img"
    echo ""
    if [ "$AUTO_REBOOT" = true ]; then
        echo "Shutting down..."
        exec shutdown -h now
    fi
    # Flush input buffer and pause before prompt
    read -t 0.1 -n 10000 discard </dev/tty 2>/dev/null || true
    sleep 0.3
    read -p "Shut down now? [y/N] " -n 1 -r </dev/tty
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        exec shutdown -h now
    fi
fi
