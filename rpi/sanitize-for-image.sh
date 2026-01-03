#!/bin/bash
#
# Sanitize Raspberry Pi for SD Card Image Distribution
# Run this BEFORE creating an image with dd
#
# This script removes:
#   - WiFi credentials
#   - SSH authorized keys
#   - User-specific data
#   - Bash history
#   - Logs
#   - Stegasoo auth database (users will create their own admin)
#
# Usage: sudo ./sanitize-for-image.sh
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: Must run as root (sudo)${NC}"
    exit 1
fi

echo -e "${YELLOW}"
echo "╔═══════════════════════════════════════════════════════════════╗"
echo "║         Sanitize Pi for Image Distribution                    ║"
echo "║                                                               ║"
echo "║   This will remove personal data and prepare for imaging.     ║"
echo "║   The system will shut down when complete.                    ║"
echo "╚═══════════════════════════════════════════════════════════════╝"
echo -e "${NC}"

read -p "Continue? This cannot be undone! [y/N] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo -e "${GREEN}[1/9]${NC} Removing WiFi credentials..."
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
    echo "  WiFi credentials cleared"
else
    echo "  No wpa_supplicant.conf found"
fi

echo -e "${GREEN}[2/9]${NC} Removing SSH authorized keys..."
for user_home in /home/*; do
    if [ -d "$user_home/.ssh" ]; then
        rm -f "$user_home/.ssh/authorized_keys"
        rm -f "$user_home/.ssh/known_hosts"
        echo "  Cleared $user_home/.ssh/"
    fi
done
rm -f /root/.ssh/authorized_keys /root/.ssh/known_hosts 2>/dev/null || true

echo -e "${GREEN}[3/9]${NC} Clearing bash history..."
for user_home in /home/*; do
    rm -f "$user_home/.bash_history"
    rm -f "$user_home/.python_history"
done
rm -f /root/.bash_history /root/.python_history 2>/dev/null || true
history -c

echo -e "${GREEN}[4/9]${NC} Removing Stegasoo user data..."
# Remove auth database (users create their own admin on first run)
rm -rf /home/*/stegasoo/frontends/web/instance/
# Remove SSL certs (will be regenerated)
rm -rf /home/*/stegasoo/frontends/web/certs/
# Remove any .env files with channel keys
rm -f /home/*/stegasoo/frontends/web/.env
echo "  Stegasoo instance data cleared"

echo -e "${GREEN}[5/9]${NC} Setting up first-boot wizard..."
# Find stegasoo install directory
STEGASOO_DIR=$(ls -d /home/*/stegasoo 2>/dev/null | head -1)
STEGASOO_USER=$(stat -c '%U' "$STEGASOO_DIR" 2>/dev/null || echo "pi")

if [ -n "$STEGASOO_DIR" ] && [ -f "$STEGASOO_DIR/rpi/stegasoo-wizard.sh" ]; then
    # Install the profile.d hook
    cp "$STEGASOO_DIR/rpi/stegasoo-wizard.sh" /etc/profile.d/stegasoo-wizard.sh
    chmod 755 /etc/profile.d/stegasoo-wizard.sh
    echo "  Installed first-boot wizard hook"

    # Create the first-boot flag
    touch /etc/stegasoo-first-boot
    echo "  Created first-boot flag"

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
    echo "  Reset service to defaults"
else
    echo "  ${YELLOW}Warning: Stegasoo not found, skipping wizard setup${NC}"
fi

echo -e "${GREEN}[6/9]${NC} Clearing logs..."
journalctl --rotate
journalctl --vacuum-time=1s
rm -rf /var/log/*.log /var/log/*.gz /var/log/*.[0-9]
rm -rf /var/log/apt/*
rm -rf /var/log/journal/*
find /var/log -type f -name "*.log" -delete 2>/dev/null || true
echo "  Logs cleared"

echo -e "${GREEN}[7/9]${NC} Clearing temporary files..."
rm -rf /tmp/*
rm -rf /var/tmp/*
echo "  Temp files cleared"

echo -e "${GREEN}[8/9]${NC} Clearing package cache..."
apt-get clean
rm -rf /var/cache/apt/archives/*
echo "  Package cache cleared"

echo -e "${GREEN}[9/9]${NC} Final cleanup..."
# Remove this script's evidence
rm -f /root/.bash_history
sync

echo ""
echo -e "${GREEN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║                    Sanitization Complete!                     ║${NC}"
echo -e "${GREEN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo "The system is ready for imaging."
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "  1. Shut down: sudo shutdown -h now"
echo "  2. Remove SD card"
echo "  3. On another machine, copy with:"
echo "     sudo dd if=/dev/sdX of=stegasoo-rpi.img bs=4M status=progress"
echo "  4. Compress: xz -9 stegasoo-rpi.img"
echo ""
read -p "Shut down now? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    shutdown -h now
fi
