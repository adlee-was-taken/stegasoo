#!/bin/bash
#
# Stegasoo First Boot Wizard
# Runs on first SSH login to configure the pre-installed Stegasoo image
#
# This script is triggered by /etc/profile.d/stegasoo-wizard.sh
# After completion, it removes itself to prevent re-running
#
# Uses gum (Charm.sh) for beautiful TUI - install with:
#   sudo apt install gum  OR  go install github.com/charmbracelet/gum@latest
#

# Configuration
INSTALL_DIR="/opt/stegasoo"
FLAG_FILE="/etc/stegasoo-first-boot"
PROFILE_HOOK="/etc/profile.d/stegasoo-wizard.sh"

# Check if this is first boot
if [ ! -f "$FLAG_FILE" ]; then
    exit 0
fi

# Check for gum, fall back to basic prompts if not available
if ! command -v gum &>/dev/null; then
    echo "Error: gum not found. Install with: sudo apt install gum"
    exit 1
fi

# Gum styling - lime green buttons
export GUM_CONFIRM_SELECTED_BACKGROUND="82"
export GUM_CONFIRM_SELECTED_FOREGROUND="0"
export GUM_CONFIRM_UNSELECTED_BACKGROUND=""
export GUM_CONFIRM_UNSELECTED_FOREGROUND="245"

clear

# =============================================================================
# Welcome
# =============================================================================

gum style \
    --border double \
    --border-foreground 212 \
    --padding "1 2" \
    --margin "1" \
    --align center \
    "  ___  _____  ___    ___    _    ___    ___    ___  " \
    " / __||_   _|| __|  / __|  /_\\  / __|  / _ \\  / _ \\ " \
    " \\__ \\  | |  | _|  | (_ | / _ \\ \\__ \\ | (_) || (_) |" \
    " |___/  |_|  |___|  \\___//_/ \\_\\|___/  \\___/  \\___/ " \
    "" \
    "First Boot Wizard"

echo ""
gum style --foreground 245 "This wizard will help you configure your Stegasoo server."
gum style --foreground 245 "You can reconfigure later by editing /etc/systemd/system/stegasoo.service"
echo ""

gum confirm "Ready to begin setup?" || exit 0

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
gum style \
    --foreground 212 --bold \
    "Step 1 of 3: HTTPS Configuration"
echo ""

gum style --foreground 245 "\
HTTPS encrypts all traffic between your browser and this server
using a self-signed certificate.

NOTE: Your browser will show a security warning because the
certificate is self-signed. This is normal for home networks."
echo ""

if gum confirm "Enable HTTPS?" --default=true; then
    ENABLE_HTTPS="true"
    gum style --foreground 82 "✓ HTTPS will be enabled"
else
    gum style --foreground 214 "→ Using HTTP (unencrypted)"
fi
sleep 0.5

# =============================================================================
# Step 2: Port Configuration (only if HTTPS)
# =============================================================================

if [ "$ENABLE_HTTPS" = "true" ]; then
    clear
    gum style \
        --foreground 212 --bold \
        "Step 2 of 3: Port Configuration"
    echo ""

    gum style --foreground 245 "\
The standard HTTPS port is 443, which means you can access
Stegasoo without specifying a port in the URL.

  Port 443:  https://stegasoo.local
  Port 5000: https://stegasoo.local:5000

NOTE: Port 443 requires an iptables redirect rule."
    echo ""

    if gum confirm "Use standard port 443?" --default=true; then
        USE_PORT_443="true"
        gum style --foreground 82 "✓ Port 443 will be configured"
    else
        gum style --foreground 214 "→ Using port 5000"
    fi
    sleep 0.5
fi

# =============================================================================
# Step 3: Channel Key Configuration
# =============================================================================

clear
gum style \
    --foreground 212 --bold \
    "Step 3 of 3: Channel Key Configuration"
echo ""

gum style --foreground 245 "\
A channel key creates a private encoding channel.

  WITHOUT a key: Anyone with Stegasoo can decode your images
  WITH a key:    Only people with YOUR key can decode

This is useful if you want to share encoded images only with
specific people (family, team, etc)."
echo ""

if gum confirm "Generate a private channel key?" --default=false; then
    echo ""
    # Generate key to temp file (gum spin doesn't capture stdout well)
    KEY_FILE=$(mktemp)
    ERR_FILE=$(mktemp)
    VENV_PYTHON="$INSTALL_DIR/venv/bin/python"
    gum spin --spinner dot --title "Generating channel key..." -- \
        bash -c "'$VENV_PYTHON' -c 'from stegasoo.channel import generate_channel_key; print(generate_channel_key())' > '$KEY_FILE' 2>'$ERR_FILE'"

    CHANNEL_KEY=$(cat "$KEY_FILE" 2>/dev/null | head -1)
    KEY_ERROR=$(cat "$ERR_FILE" 2>/dev/null)
    rm -f "$KEY_FILE" "$ERR_FILE"

    if [ -n "$CHANNEL_KEY" ] && [[ "$CHANNEL_KEY" =~ ^[A-Za-z0-9] ]]; then
        echo ""
        gum style --foreground 82 "✓ Channel key generated!"
        echo ""
        gum style \
            --border rounded \
            --border-foreground 226 \
            --padding "1 2" \
            --foreground 226 --bold \
            "$CHANNEL_KEY"
        echo ""
        gum style --foreground 196 --bold \
            "*** IMPORTANT: Write down or copy this key NOW! ***"
        gum style --foreground 196 \
            "You'll need to share it with anyone who should decode" \
            "your images. This key won't be shown again."
        echo ""
        gum confirm "I've saved the key" --default=true --affirmative="Continue" --negative=""
    else
        gum style --foreground 196 "Failed to generate key. Using public mode."
        if [ -n "$KEY_ERROR" ]; then
            echo ""
            gum style --foreground 245 "Error details:"
            echo "$KEY_ERROR"
        fi
        CHANNEL_KEY=""
        echo ""
        gum confirm "Continue" --default=true --affirmative="OK" --negative=""
    fi
else
    gum style --foreground 214 "→ Using public mode"
    sleep 0.5
fi

# =============================================================================
# Apply Configuration
# =============================================================================

clear
gum style \
    --foreground 212 --bold \
    "Applying Configuration..."
echo ""

# Find the stegasoo user (whoever owns the install dir)
STEGASOO_USER=$(stat -c '%U' "$INSTALL_DIR" 2>/dev/null || echo "pi")

gum spin --spinner dot --title "Updating systemd service..." -- bash -c "
sudo tee /etc/systemd/system/stegasoo.service >/dev/null <<EOF
[Unit]
Description=Stegasoo Web UI
After=network.target

[Service]
Type=simple
User=$STEGASOO_USER
WorkingDirectory=$INSTALL_DIR/frontends/web
Environment=\"PATH=$INSTALL_DIR/venv/bin:/usr/bin\"
Environment=\"STEGASOO_AUTH_ENABLED=true\"
Environment=\"STEGASOO_HTTPS_ENABLED=$ENABLE_HTTPS\"
Environment=\"STEGASOO_PORT=5000\"
Environment=\"STEGASOO_CHANNEL_KEY=$CHANNEL_KEY\"
ExecStart=$INSTALL_DIR/venv/bin/python app.py
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF
"
gum style --foreground 82 "✓ Service configured"

# Setup port 443 if requested
if [ "$USE_PORT_443" = "true" ]; then
    gum spin --spinner dot --title "Setting up port 443 redirect..." -- bash -c "
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
    "
    gum style --foreground 82 "✓ Port 443 redirect configured"
fi

gum spin --spinner dot --title "Reloading systemd..." -- sudo systemctl daemon-reload
gum style --foreground 82 "✓ Systemd reloaded"

gum spin --spinner dot --title "Starting Stegasoo..." -- bash -c "sudo systemctl restart stegasoo && sleep 2"

if systemctl is-active --quiet stegasoo; then
    gum style --foreground 82 "✓ Stegasoo started successfully"
else
    gum style --foreground 196 "✗ Failed to start (check: journalctl -u stegasoo)"
fi

gum spin --spinner dot --title "Cleaning up wizard..." -- bash -c "
    sudo rm -f '$FLAG_FILE'
    sudo rm -f '$PROFILE_HOOK'
"
gum style --foreground 82 "✓ Wizard complete"

sleep 1

# =============================================================================
# Final Summary
# =============================================================================

clear

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

gum style \
    --border double \
    --border-foreground 82 \
    --padding "1 2" \
    --margin "1" \
    --align center \
    "  ___  _____  ___    ___    _    ___    ___    ___  " \
    " / __||_   _|| __|  / __|  /_\\  / __|  / _ \\  / _ \\ " \
    " \\__ \\  | |  | _|  | (_ | / _ \\ \\__ \\ | (_) || (_) |" \
    " |___/  |_|  |___|  \\___//_/ \\_\\|___/  \\___/  \\___/ " \
    "" \
    "Setup Complete!"

echo ""
gum style --foreground 82 --bold "Access URL:"
gum style --foreground 226 "  $ACCESS_URL"
gum style --foreground 245 "  $ACCESS_URL_LOCAL (if mDNS works)"
echo ""

if [ -n "$CHANNEL_KEY" ]; then
    gum style --foreground 82 --bold "Channel Key:"
    gum style --foreground 226 "  $CHANNEL_KEY"
    echo ""
fi

gum style --foreground 82 --bold "First Steps:"
gum style --foreground 255 \
    "  1. Open the URL above in your browser" \
    "  2. Accept the security warning (self-signed cert)" \
    "  3. Create your admin account" \
    "  4. Start encoding secret messages!"
echo ""

gum style --foreground 82 --bold "Useful Commands:"
gum style --foreground 245 \
    "  sudo systemctl status stegasoo   # Check status" \
    "  sudo systemctl restart stegasoo  # Restart" \
    "  journalctl -u stegasoo -f        # View logs"
echo ""

gum style --foreground 212 --bold "Enjoy Stegasoo!"
echo ""
