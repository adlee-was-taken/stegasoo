#!/bin/bash
#
# Stegasoo First Boot Wizard
# Runs on first SSH login to configure the pre-installed Stegasoo image
#
# This script is triggered by /etc/profile.d/stegasoo-wizard.sh
# After completion, it removes itself to prevent re-running
#

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
GRAY='\033[0;90m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
INSTALL_DIR="/opt/stegasoo"
FLAG_FILE="/etc/stegasoo-first-boot"
PROFILE_HOOK="/etc/profile.d/stegasoo-wizard.sh"

# Check if this is first boot
if [ ! -f "$FLAG_FILE" ]; then
  exit 0
fi

clear

echo ""
echo -e "${GRAY} . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · .${NC}"
echo -e "${GRAY} · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . ·${NC}"
echo -e "${GRAY} . · . · . · . · . · . ${CYAN}/\\\\${GRAY} · . · ${CYAN}/\\\\${GRAY} · . · ${CYAN}/\\\\${GRAY} · . · ${CYAN}/\\\\${GRAY} · . · . · . .${NC}"
echo -e "${GRAY} · . · . · . · . · . · ${CYAN}\\\\/${GRAY} · . · ${CYAN}\\\\/${GRAY} · . · ${CYAN}\\\\/${GRAY} · . · ${CYAN}\\\\/${GRAY} · . · . · . ·${NC}"
echo -e "${GRAY} . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · .${NC}"
echo -e "${GRAY} · .  ${CYAN} ___  _____  ___    ___    _    ___    ___    ___  ${GRAY}  . · . ·${NC}"
echo -e "${GRAY} . ·  ${CYAN}/ __||_   _|| __|  / __|  /_\\\\  / __|  / _ \\\\  / _ \\\\${GRAY}   · . · ·${NC}"
echo -e "${GRAY} · .  ${CYAN}/ __||_   _|| __|  / __|  /_\\\\  / __|  / _ \\\\  / _ \\\\${GRAY}   . · . ·${NC}"
echo -e "${GRAY} . ·  ${CYAN}\\\\__ \\\\  | |  | _|  | (_ | / _ \\\\ \\\\__ \\\\ | (_) || (_) |${GRAY}  · . · ·${NC}"
echo -e "${GRAY} · .  ${CYAN}\\\\__ \\\\  | |  | _|  | (_ | / _ \\\\ \\\\__ \\\\ | (_) || (_) |${GRAY}  . · . ·${NC}"
echo -e "${GRAY} . ·  ${CYAN}|___/  |_|  |___|  \\\\___|/_/ \\\\_\\\\|___/  \\\\___/  \\\\___/${GRAY}   · . · ·${NC}"
echo -e "${GRAY} · .  ${CYAN}|___/  |_|  |___|  \\\\___|/_/ \\\\_\\\\|___/  \\\\___/  \\\\___/${GRAY}   . · . ·${NC}"
echo -e "${GRAY} · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . ·${NC}"
echo -e "${GRAY} . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · .${NC}"
echo -e "${GRAY} · . · ${CYAN}~~~~${NC} ${GRAY}· . · . · .${NC} ${CYAN}First Boot Wizard${NC} ${GRAY}· . · . · ${CYAN}~~~~${NC} ${GRAY}· . · . ·${NC}"
echo -e "${GRAY} . · . ${CYAN}~~~~${NC} ${GRAY}· . · . · . · . · . · . · . · . · . · . ${CYAN}~~~~${NC} ${GRAY}· . · . .${NC}"
echo -e "${GRAY} · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . · . ·${NC}"
echo ""

echo -e "${BOLD}Welcome to Stegasoo!${NC}"
echo ""
echo "This wizard will help you configure your Stegasoo server."
echo "You can reconfigure later by editing /etc/systemd/system/stegasoo.service"
echo ""
echo -e "${YELLOW}Press Enter to begin setup...${NC}"
read

# =============================================================================
# Configuration Variables
# =============================================================================

ENABLE_HTTPS="false"
USE_PORT_443="false"
CHANNEL_KEY=""

# =============================================================================
# Step 1: HTTPS Configuration
# =============================================================================

clear
echo -e "${BOLD}Step 1 of 3: HTTPS Configuration${NC}"
echo -e "${BLUE}-------------------------------------------------------${NC}"
echo ""
echo "HTTPS encrypts all traffic between your browser and this server"
echo "using a self-signed certificate."
echo ""
echo -e "${YELLOW}Note:${NC} Your browser will show a security warning because the"
echo "certificate is self-signed. This is normal for home networks."
echo ""
echo "  [Y] Enable HTTPS (recommended for home network security)"
echo "  [n] Use HTTP only (unencrypted, not recommended)"
echo ""
# Flush input buffer to prevent stray keystrokes from auto-answering
read -t 0.1 -n 10000 discard 2>/dev/null || true
read -p "Enable HTTPS? [Y/n] " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Nn]$ ]]; then
  ENABLE_HTTPS="true"
  echo ""
  echo -e "  ${GREEN}✓${NC} HTTPS will be enabled"
  sleep 1
fi

# =============================================================================
# Step 2: Port Configuration (only if HTTPS)
# =============================================================================

if [ "$ENABLE_HTTPS" = "true" ]; then
  clear
  echo -e "${BOLD}Step 2 of 3: Port Configuration${NC}"
  echo -e "${BLUE}-------------------------------------------------------${NC}"
  echo ""
  echo "The standard HTTPS port is 443, which means you can access"
  echo "Stegasoo without specifying a port in the URL."
  echo ""
  echo "  Port 443:  https://stegasoo.local"
  echo "  Port 5000: https://stegasoo.local:5000"
  echo ""
  echo -e "${YELLOW}Note:${NC} Port 443 requires an iptables redirect rule."
  echo ""
  echo "  [Y] Use port 443 (cleaner URLs)"
  echo "  [n] Use port 5000 (default, no extra config)"
  echo ""
  # Flush input buffer to prevent stray keystrokes from auto-answering
  read -t 0.1 -n 10000 discard 2>/dev/null || true
  read -p "Use standard port 443? [Y/n] " -n 1 -r
  echo
  if [[ ! $REPLY =~ ^[Nn]$ ]]; then
    USE_PORT_443="true"
    echo ""
    echo -e "  ${GREEN}✓${NC} Port 443 will be configured"
    sleep 1
  fi
fi

# =============================================================================
# Step 3: Channel Key Configuration
# =============================================================================

clear
echo -e "${BOLD}Step 3 of 3: Channel Key Configuration${NC}"
echo -e "${BLUE}-------------------------------------------------------${NC}"
echo ""
echo "A channel key creates a private encoding channel."
echo ""
echo -e "  ${BOLD}Without a key:${NC} Anyone with Stegasoo can decode your images"
echo -e "  ${BOLD}With a key:${NC}    Only people with YOUR key can decode your images"
echo ""
echo "This is useful if you want to share encoded images only with"
echo "specific people (family, team, etc)."
echo ""
echo "  [y] Generate a private channel key"
echo "  [N] Use public mode (anyone can decode)"
echo ""
# Flush input buffer to prevent stray keystrokes from auto-answering
read -t 0.1 -n 10000 discard 2>/dev/null || true
read -p "Generate a private channel key? [y/N] " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
  echo ""
  echo "Generating channel key..."

  # Source the venv and generate key
  source "$INSTALL_DIR/venv/bin/activate" 2>/dev/null
  CHANNEL_KEY=$(python -c "from stegasoo.channel import generate_channel_key; print(generate_channel_key())" 2>/dev/null)

  if [ -n "$CHANNEL_KEY" ]; then
    echo ""
    echo -e "  ${GREEN}✓${NC} Channel key generated!"
    echo ""
    echo -e "  ${BOLD}${YELLOW}$CHANNEL_KEY${NC}"
    echo ""
    echo -e "  ${RED}*** IMPORTANT: Write down or copy this key NOW! ***${NC}"
    echo -e "  ${RED}You'll need to share it with anyone who should decode${NC}"
    echo -e "  ${RED}your images. This key won't be shown again.${NC}"
    echo ""
    # Flush input buffer before waiting
    read -t 0.1 -n 10000 discard 2>/dev/null || true
    sleep 0.3
    read -p "Press Enter when you've saved the key..."
  else
    echo -e "  ${RED}✗${NC} Failed to generate key. Using public mode."
    CHANNEL_KEY=""
  fi
else
  echo ""
  echo -e "  ${YELLOW}→${NC} Using public mode"
  sleep 1
fi

# =============================================================================
# Apply Configuration
# =============================================================================

clear
echo -e "${BOLD}Applying Configuration...${NC}"
echo -e "${BLUE}-------------------------------------------------------${NC}"
echo ""

# Find the stegasoo user (whoever owns the install dir)
STEGASOO_USER=$(stat -c '%U' "$INSTALL_DIR" 2>/dev/null || echo "pi")

echo "  Updating systemd service..."

sudo tee /etc/systemd/system/stegasoo.service >/dev/null <<EOF
[Unit]
Description=Stegasoo Web UI
After=network.target

[Service]
Type=simple
User=$STEGASOO_USER
WorkingDirectory=$INSTALL_DIR/frontends/web
Environment="PATH=$INSTALL_DIR/venv/bin:/usr/bin"
Environment="STEGASOO_AUTH_ENABLED=true"
Environment="STEGASOO_HTTPS_ENABLED=$ENABLE_HTTPS"
Environment="STEGASOO_PORT=5000"
Environment="STEGASOO_CHANNEL_KEY=$CHANNEL_KEY"
ExecStart=$INSTALL_DIR/venv/bin/python app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

echo -e "  ${GREEN}✓${NC} Service configured"

# Setup port 443 if requested
if [ "$USE_PORT_443" = "true" ]; then
  echo "  Setting up port 443 redirect..."

  # Install iptables if needed
  if ! command -v iptables &>/dev/null; then
    sudo apt-get install -y iptables >/dev/null 2>&1
  fi

  # Add redirect rule (check if it already exists)
  if ! sudo iptables -t nat -C PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 5000 2>/dev/null; then
    sudo iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 5000
  fi
  sudo sh -c 'iptables-save > /etc/iptables.rules'

  # Create/update persistence service
  sudo tee /etc/systemd/system/iptables-restore.service >/dev/null <<EOF
[Unit]
Description=Restore iptables rules
Before=network-pre.target

[Service]
Type=oneshot
ExecStart=/sbin/iptables-restore /etc/iptables.rules

[Install]
WantedBy=multi-user.target
EOF
  sudo systemctl enable iptables-restore.service >/dev/null 2>&1
  echo -e "  ${GREEN}✓${NC} Port 443 redirect configured"
fi

echo "  Reloading systemd..."
sudo systemctl daemon-reload
echo -e "  ${GREEN}✓${NC} Systemd reloaded"

echo "  Starting Stegasoo..."
sudo systemctl restart stegasoo
sleep 2

if systemctl is-active --quiet stegasoo; then
  echo -e "  ${GREEN}✓${NC} Stegasoo started successfully"
else
  echo -e "  ${RED}✗${NC} Failed to start (check: journalctl -u stegasoo)"
fi

# Remove first-boot flag and profile hook
echo "  Cleaning up first-boot wizard..."
sudo rm -f "$FLAG_FILE"
sudo rm -f "$PROFILE_HOOK"
echo -e "  ${GREEN}✓${NC} Wizard complete"

# =============================================================================
# Final Summary
# =============================================================================

clear
PI_IP=$(hostname -I | awk '{print $1}')
HOSTNAME=$(hostname)

echo -e "${GREEN}"
cat <<'BANNER'
   _____ _
  / ____| |
 | (___ | |_ ___  __ _  __ _ ___  ___   ___
  \___ \| __/ _ \/ _` |/ _` / __|/ _ \ / _ \
  ____) | ||  __/ (_| | (_| \__ \ (_) | (_) |
 |_____/ \__\___|\__, |\__,_|___/\___/ \___/
                  __/ |
                 |___/   Setup Complete!
BANNER
echo -e "${NC}"

echo -e "${BOLD}Your Stegasoo server is ready!${NC}"
echo ""

echo -e "${GREEN}Access URL:${NC}"
if [ "$ENABLE_HTTPS" = "true" ]; then
  if [ "$USE_PORT_443" = "true" ]; then
    echo -e "  ${BOLD}${YELLOW}https://$PI_IP${NC}"
    echo -e "  ${BOLD}${YELLOW}https://$HOSTNAME.local${NC} (if mDNS works)"
  else
    echo -e "  ${BOLD}${YELLOW}https://$PI_IP:5000${NC}"
    echo -e "  ${BOLD}${YELLOW}https://$HOSTNAME.local:5000${NC} (if mDNS works)"
  fi
else
  echo -e "  ${BOLD}${YELLOW}http://$PI_IP:5000${NC}"
fi
echo ""

if [ -n "$CHANNEL_KEY" ]; then
  echo -e "${GREEN}Channel Key:${NC}"
  echo -e "  ${YELLOW}$CHANNEL_KEY${NC}"
  echo ""
fi

echo -e "${GREEN}First Steps:${NC}"
echo "  1. Open the URL above in your browser"
echo "  2. Accept the security warning (self-signed cert)"
echo "  3. Create your admin account"
echo "  4. Start encoding secret messages!"
echo ""

echo -e "${GREEN}Useful Commands:${NC}"
echo "  sudo systemctl status stegasoo   # Check status"
echo "  sudo systemctl restart stegasoo  # Restart"
echo "  journalctl -u stegasoo -f        # View logs"
echo ""

echo -e "${CYAN}Enjoy Stegasoo!${NC}"
echo ""
