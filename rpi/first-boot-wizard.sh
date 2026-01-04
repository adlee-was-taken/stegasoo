#!/bin/bash
#
# Stegasoo First Boot Wizard
# Runs on first SSH login to configure the pre-installed Stegasoo image
#
# This script is triggered by /etc/profile.d/stegasoo-wizard.sh
# After completion, it removes itself to prevent re-running
#
# Uses whiptail for reliable TUI dialogs (pre-installed on Pi OS)
#

# Configuration
INSTALL_DIR="/opt/stegasoo"
FLAG_FILE="/etc/stegasoo-first-boot"
PROFILE_HOOK="/etc/profile.d/stegasoo-wizard.sh"

# Terminal dimensions
TERM_HEIGHT=$(tput lines 2>/dev/null || echo 24)
TERM_WIDTH=$(tput cols 2>/dev/null || echo 80)
BOX_HEIGHT=$((TERM_HEIGHT - 4))
BOX_WIDTH=$((TERM_WIDTH - 4))
[ $BOX_HEIGHT -gt 20 ] && BOX_HEIGHT=20
[ $BOX_WIDTH -gt 70 ] && BOX_WIDTH=70

# Check if this is first boot
if [ ! -f "$FLAG_FILE" ]; then
    exit 0
fi

# =============================================================================
# Welcome
# =============================================================================

whiptail --title "Stegasoo First Boot Wizard" --msgbox "\
Welcome to Stegasoo!

This wizard will help you configure your Stegasoo server.

You can reconfigure later by editing:
/etc/systemd/system/stegasoo.service

Press OK to begin setup..." $BOX_HEIGHT $BOX_WIDTH

# =============================================================================
# Configuration Variables
# =============================================================================

ENABLE_HTTPS="false"
USE_PORT_443="false"
CHANNEL_KEY=""

# =============================================================================
# Step 1: HTTPS Configuration
# =============================================================================

if whiptail --title "Step 1 of 3: HTTPS Configuration" --yesno "\
HTTPS encrypts all traffic between your browser and this server using a self-signed certificate.

NOTE: Your browser will show a security warning because the certificate is self-signed. This is normal for home networks.

Enable HTTPS? (Recommended)" $BOX_HEIGHT $BOX_WIDTH; then
    ENABLE_HTTPS="true"
fi

# =============================================================================
# Step 2: Port Configuration (only if HTTPS)
# =============================================================================

if [ "$ENABLE_HTTPS" = "true" ]; then
    if whiptail --title "Step 2 of 3: Port Configuration" --yesno "\
The standard HTTPS port is 443, which means you can access Stegasoo without specifying a port in the URL.

  Port 443:  https://stegasoo.local
  Port 5000: https://stegasoo.local:5000

NOTE: Port 443 requires an iptables redirect rule.

Use standard port 443? (Cleaner URLs)" $BOX_HEIGHT $BOX_WIDTH; then
        USE_PORT_443="true"
    fi
fi

# =============================================================================
# Step 3: Channel Key Configuration
# =============================================================================

if whiptail --title "Step 3 of 3: Channel Key" --yesno "\
A channel key creates a private encoding channel.

WITHOUT a key: Anyone with Stegasoo can decode your images
WITH a key:    Only people with YOUR key can decode

This is useful if you want to share encoded images only with specific people (family, team, etc).

Generate a private channel key?" $BOX_HEIGHT $BOX_WIDTH --defaultno; then

    # Generate key (use temp file to preserve across subshell)
    KEY_FILE=$(mktemp)
    {
        echo 50
        source "$INSTALL_DIR/venv/bin/activate" 2>/dev/null
        python -c "from stegasoo.channel import generate_channel_key; print(generate_channel_key())" > "$KEY_FILE" 2>/dev/null
        echo 100
    } | whiptail --title "Generating Key" --gauge "Generating channel key..." 6 50 0

    CHANNEL_KEY=$(cat "$KEY_FILE" 2>/dev/null)
    rm -f "$KEY_FILE"

    if [ -n "$CHANNEL_KEY" ]; then
        whiptail --title "Channel Key Generated" --msgbox "\
Your private channel key:

    $CHANNEL_KEY

*** IMPORTANT: Write down or copy this key NOW! ***

You'll need to share it with anyone who should decode your images. This key won't be shown again after you press OK." $BOX_HEIGHT $BOX_WIDTH
    else
        whiptail --title "Error" --msgbox "Failed to generate channel key. Using public mode." 8 50
        CHANNEL_KEY=""
    fi
fi

# =============================================================================
# Apply Configuration
# =============================================================================

{
    echo 10
    echo "XXX"
    echo "Updating systemd service..."
    echo "XXX"

    # Find the stegasoo user (whoever owns the install dir)
    STEGASOO_USER=$(stat -c '%U' "$INSTALL_DIR" 2>/dev/null || echo "pi")

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

    echo 30

    # Setup port 443 if requested
    if [ "$USE_PORT_443" = "true" ]; then
        echo "XXX"
        echo "Setting up port 443 redirect..."
        echo "XXX"

        if ! command -v iptables &>/dev/null; then
            sudo apt-get install -y iptables >/dev/null 2>&1
        fi

        if ! sudo iptables -t nat -C PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 5000 2>/dev/null; then
            sudo iptables -t nat -A PREROUTING -p tcp --dport 443 -j REDIRECT --to-port 5000
        fi
        sudo sh -c 'iptables-save > /etc/iptables.rules'

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
    fi

    echo 50
    echo "XXX"
    echo "Reloading systemd..."
    echo "XXX"
    sudo systemctl daemon-reload

    echo 70
    echo "XXX"
    echo "Starting Stegasoo..."
    echo "XXX"
    sudo systemctl restart stegasoo
    sleep 2

    echo 90
    echo "XXX"
    echo "Cleaning up wizard..."
    echo "XXX"
    sudo rm -f "$FLAG_FILE"
    sudo rm -f "$PROFILE_HOOK"

    echo 100
} | whiptail --title "Applying Configuration" --gauge "Starting..." 6 50 0

# =============================================================================
# Final Summary
# =============================================================================

PI_IP=$(hostname -I | awk '{print $1}')
HOSTNAME=$(hostname)

# Build the access URL
if [ "$ENABLE_HTTPS" = "true" ]; then
    if [ "$USE_PORT_443" = "true" ]; then
        ACCESS_URL="https://$PI_IP"
        ACCESS_URL_LOCAL="https://$HOSTNAME.local"
    else
        ACCESS_URL="https://$PI_IP:5000"
        ACCESS_URL_LOCAL="https://$HOSTNAME.local:5000"
    fi
else
    ACCESS_URL="http://$PI_IP:5000"
    ACCESS_URL_LOCAL="http://$HOSTNAME.local:5000"
fi

# Build channel key message
CHANNEL_MSG=""
if [ -n "$CHANNEL_KEY" ]; then
    CHANNEL_MSG="
Channel Key: $CHANNEL_KEY"
fi

# Check if service started
if systemctl is-active --quiet stegasoo; then
    SERVICE_STATUS="Running"
else
    SERVICE_STATUS="Failed to start (check: journalctl -u stegasoo)"
fi

whiptail --title "Setup Complete!" --msgbox "\
Your Stegasoo server is ready!

Access URL:
  $ACCESS_URL
  $ACCESS_URL_LOCAL (if mDNS works)

Service Status: $SERVICE_STATUS
$CHANNEL_MSG

First Steps:
  1. Open the URL above in your browser
  2. Accept the security warning (self-signed cert)
  3. Create your admin account
  4. Start encoding secret messages!

Useful Commands:
  sudo systemctl status stegasoo   # Check status
  sudo systemctl restart stegasoo  # Restart
  journalctl -u stegasoo -f        # View logs

Enjoy Stegasoo!" $((BOX_HEIGHT + 4)) $BOX_WIDTH

clear
echo ""
echo "Stegasoo setup complete!"
echo ""
echo "Access your server at: $ACCESS_URL"
if [ -n "$CHANNEL_KEY" ]; then
    echo "Channel Key: $CHANNEL_KEY"
fi
echo ""
