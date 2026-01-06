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

# Gum styling - terminal green buttons with bold dark text
export GUM_CONFIRM_SELECTED_BACKGROUND="46"
export GUM_CONFIRM_SELECTED_FOREGROUND="232"
export GUM_CONFIRM_SELECTED_BOLD="true"
export GUM_CONFIRM_UNSELECTED_BACKGROUND="238"
export GUM_CONFIRM_UNSELECTED_FOREGROUND="255"

clear

# =============================================================================
# Welcome
# =============================================================================

echo ""
echo -e "\033[38;5;218m════════════════════════════════════════════════════════\033[0m"
echo -e "\033[0;90m · .  · .  *  · .  *  · .  *  · .  *  · .  *  · .  ·\033[0m"
echo -e "\033[0;36m    ___  _____  ___    ___    _    ___    ___    ___\033[0m"
echo -e "\033[0;36m   / __||_   _|| __|  / __|  /_\\  / __|  / _ \\  / _ \\\\\033[0m"
echo -e "\033[0;36m   \\__ \\  | |  | _|  | (_ | / _ \\ \\__ \\ | (_) || (_) |\033[0m"
echo -e "\033[0;36m   |___/  |_|  |___|  \\___//_/ \\_\\|___/  \\___/  \\___/\033[0m"
echo -e "\033[0;90m · .  · .  *  · .  *  · .  *  · .  *  · .  *  · .  ·\033[0m"
echo -e "\033[38;5;218m════════════════════════════════════════════════════════\033[0m"
echo -e "\033[1;37m                    First Boot Wizard\033[0m"
echo -e "\033[38;5;218m════════════════════════════════════════════════════════\033[0m"

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
  "Step 1 of 4: HTTPS Configuration"
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
    "Step 2 of 4: Port Configuration"
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
  "Step 3 of 4: Channel Key Configuration"
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
# Step 4: Overclock Configuration
# =============================================================================

ENABLE_OVERCLOCK="false"
NEEDS_RESTART="false"

# Detect Pi model
PI_MODEL=$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')

if [[ "$PI_MODEL" == *"Raspberry Pi 4"* ]] || [[ "$PI_MODEL" == *"Raspberry Pi 5"* ]]; then
  clear
  gum style \
    --foreground 212 --bold \
    "Step 4 of 4: Performance Tuning"
  echo ""

  gum style --foreground 245 "\
Detected: $PI_MODEL

Overclocking can improve DCT encode/decode performance.
This is ONLY recommended if you have active cooling:
  • Heatsink + Fan
  • Active cooler case

Without cooling, the Pi may throttle or become unstable."
  echo ""

  if gum confirm "Do you have active cooling (heatsink + fan)?" --default=false; then
    echo ""
    gum style --foreground 245 "\
Recommended overclock settings:
  • Pi 4: 2.0 GHz (stock 1.5 GHz) - ~33% faster
  • Pi 5: 2.8 GHz (stock 2.4 GHz) - ~17% faster"
    echo ""

    if gum confirm "Enable overclock?" --default=true; then
      ENABLE_OVERCLOCK="true"
      NEEDS_RESTART="true"
      gum style --foreground 82 "✓ Overclock will be enabled (restart required)"
    else
      gum style --foreground 214 "→ Running at stock speed"
    fi
  else
    gum style --foreground 214 "→ Skipping overclock (no active cooling)"
  fi
  sleep 0.5
else
  # Not a Pi 4/5, skip overclock
  :
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

# Apply overclock if requested
if [ "$ENABLE_OVERCLOCK" = "true" ]; then
  gum spin --spinner dot --title "Configuring overclock..." -- bash -c "
    CONFIG_FILE='/boot/firmware/config.txt'
    # Fallback for older Pi OS
    if [ ! -f \"\$CONFIG_FILE\" ]; then
      CONFIG_FILE='/boot/config.txt'
    fi

    # Check if overclock already configured
    if ! grep -q '^over_voltage=' \"\$CONFIG_FILE\" 2>/dev/null; then
      # Detect Pi model for appropriate settings
      PI_MODEL=\$(cat /proc/device-tree/model 2>/dev/null | tr -d '\0')

      echo '' | sudo tee -a \"\$CONFIG_FILE\" >/dev/null
      echo '# Overclock (configured by Stegasoo wizard)' | sudo tee -a \"\$CONFIG_FILE\" >/dev/null

      if [[ \"\$PI_MODEL\" == *'Raspberry Pi 5'* ]]; then
        # Pi 5 overclock
        echo 'over_voltage=4' | sudo tee -a \"\$CONFIG_FILE\" >/dev/null
        echo 'arm_freq=2800' | sudo tee -a \"\$CONFIG_FILE\" >/dev/null
      else
        # Pi 4 overclock
        echo 'over_voltage=6' | sudo tee -a \"\$CONFIG_FILE\" >/dev/null
        echo 'arm_freq=2000' | sudo tee -a \"\$CONFIG_FILE\" >/dev/null
        echo 'gpu_freq=700' | sudo tee -a \"\$CONFIG_FILE\" >/dev/null
      fi
    fi
  "
  gum style --foreground 82 "✓ Overclock configured"
fi

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
    ACCESS_URL="https://$PI_IP/setup"
    ACCESS_URL_LOCAL="https://$HOSTNAME.local/setup"
  else
    ACCESS_URL="https://$PI_IP:5000/setup"
    ACCESS_URL_LOCAL="https://$HOSTNAME.local:5000/setup"
  fi
else
  ACCESS_URL="http://$PI_IP:5000/setup"
  ACCESS_URL_LOCAL="http://$HOSTNAME.local:5000/setup"
fi

echo ""
echo ""
echo -e "\033[38;5;218m════════════════════════════════════════════════════════\033[0m"
echo -e "\033[0;90m · .  · .  *  · .  *  · .  *  · .  *  · .  *  · .  ·\033[0m"
echo -e "\033[0;36m    ___  _____  ___    ___    _    ___    ___    ___\033[0m"
echo -e "\033[0;36m   / __||_   _|| __|  / __|  /_\\  / __|  / _ \\  / _ \\\\\033[0m"
echo -e "\033[0;36m   \\__ \\  | |  | _|  | (_ | / _ \\ \\__ \\ | (_) || (_) |\033[0m"
echo -e "\033[0;36m   |___/  |_|  |___|  \\___//_/ \\_\\|___/  \\___/  \\___/\033[0m"
echo -e "\033[0;90m · .  · .  *  · .  *  · .  *  · .  *  · .  *  · .  ·\033[0m"
echo -e "\033[38;5;218m════════════════════════════════════════════════════════\033[0m"
echo -e "\033[1;32m                      Setup Complete!\033[0m"
echo -e "\033[38;5;218m════════════════════════════════════════════════════════\033[0m"

echo ""
gum style --foreground 82 --bold "Create your admin account:"
gum style --foreground 226 "  $ACCESS_URL"
gum style --foreground 245 "  $ACCESS_URL_LOCAL (if mDNS works)"

if [ -n "$CHANNEL_KEY" ]; then
  echo ""
  echo -e "\033[1;32mChannel Key:\033[0m \033[0;33m$CHANNEL_KEY\033[0m"
fi

echo ""
gum style --foreground 82 --bold "First Steps:"
gum style --foreground 255 "  1. Open URL → 2. Accept cert → 3. Create admin → 4. Encode!"

echo ""
gum style --foreground 245 "Commands: systemctl {status|restart} stegasoo, journalctl -u stegasoo -f"

# Prompt for restart if overclock was enabled
if [ "$NEEDS_RESTART" = "true" ]; then
  echo ""
  gum style --foreground 226 --bold "⚠ Restart required for overclock settings"
  if gum confirm "Restart now?" --default=true; then
    gum style --foreground 82 "Restarting in 3 seconds..."
    sleep 3
    sudo reboot
  else
    gum style --foreground 214 "Run 'sudo reboot' later to apply overclock."
  fi
fi

echo ""
gum style --foreground 212 --bold "Enjoy Stegasoo!"
echo ""
