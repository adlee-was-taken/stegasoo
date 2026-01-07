#!/bin/bash
#
# Stegasoo Pi Test Kickoff Script
# Automates: flash -> wait for boot -> setup -> test
#
# Usage: ./kickoff-pi-test.sh <image.img.zst> </dev/sdX>
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pi connection settings
PI_HOST="stegasoo.local"
PI_USER="admin"
PI_PASS="stegasoo"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

# Wait for Pi to be reachable
wait_for_pi() {
    local attempt=1
    ssh-keygen -R "$PI_HOST" 2>/dev/null

    echo "Waiting for $PI_USER@$PI_HOST..."
    while ! sshpass -p "$PI_PASS" ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no -o BatchMode=no -o UserKnownHostsFile=/dev/null "$PI_USER@$PI_HOST" "exit" 2>/dev/null; do
        printf "\rAttempt %d..." "$attempt"
        ((attempt++))
        sleep 2
    done

    printf "\r${GREEN}✓ Ready after %d attempts${NC}\n" "$attempt"
    printf '\a'  # Terminal bell
}

# Run command on Pi (non-interactive)
run_on_pi() {
    sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$PI_USER@$PI_HOST" "$@"
}

# Run command on Pi (interactive/PTY)
run_on_pi_interactive() {
    sshpass -p "$PI_PASS" ssh -t -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$PI_USER@$PI_HOST" "$@"
}

# Copy file to Pi
scp_to_pi() {
    local src="$1"
    local dst="$2"
    sshpass -p "$PI_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$src" "$PI_USER@$PI_HOST:$dst"
}

# Interactive SSH session
ssh_pi() {
    ssh-keygen -R "$PI_HOST" 2>/dev/null
    sshpass -p "$PI_PASS" ssh -t -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$PI_USER@$PI_HOST" "$@"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

if [[ $# -lt 2 ]]; then
    echo "Usage: $0 <image.img.zst> </dev/sdX>"
    echo ""
    echo "Example: $0 stegasoo-v4.1.img.zst /dev/sda"
    exit 1
fi

IMAGE="$1"
DEVICE="$2"

if [[ ! -f "$IMAGE" ]]; then
    echo -e "${RED}Error: Image file not found: $IMAGE${NC}"
    exit 1
fi

if [[ ! -b "$DEVICE" ]]; then
    echo -e "${RED}Error: Device not found: $DEVICE${NC}"
    exit 1
fi

echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              Stegasoo Pi Test Kickoff                         ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Image:  ${YELLOW}$IMAGE${NC}"
echo -e "Device: ${YELLOW}$DEVICE${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Flash the image
# -----------------------------------------------------------------------------
echo -e "${GREEN}[1/8]${NC} Flashing image..."
echo ""

# Auto-answer: "yes" for confirm, "y" for wipe, "y" for resize
printf 'yes\ny\ny\n' | "$SCRIPT_DIR/flash-stock-img.sh" "$IMAGE" "$DEVICE"

echo ""
echo -e "${GREEN}[2/8]${NC} Flash complete! Waiting for SD card insertion..."
echo ""

# -----------------------------------------------------------------------------
# Step 2: Wait for user to insert SD card
# -----------------------------------------------------------------------------
echo -e "${YELLOW}════════════════════════════════════════════════════════════════${NC}"
echo -e "${YELLOW}  Insert SD card into Pi and power on${NC}"
echo -e "${YELLOW}════════════════════════════════════════════════════════════════${NC}"
echo ""
read -p "Press ENTER when Pi is booting..."

echo ""

# -----------------------------------------------------------------------------
# Step 3: Wait for Pi to be ready
# -----------------------------------------------------------------------------
echo -e "${GREEN}[3/8]${NC} Waiting for Pi to boot..."
echo ""

wait_for_pi

# -----------------------------------------------------------------------------
# Step 4: Pre-setup (install dependencies)
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}[4/8]${NC} Installing dependencies on Pi..."
echo ""

run_on_pi "sudo chown admin:admin /opt && sudo apt-get update && sudo apt-get install -y git zstd jq"

# -----------------------------------------------------------------------------
# Step 5: Clone repo
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}[5/8]${NC} Cloning Stegasoo repo..."
echo ""

run_on_pi "cd /opt && git clone -b 4.1 https://github.com/adlee-was-taken/stegasoo.git stegasoo"

# -----------------------------------------------------------------------------
# Step 6: Copy pre-built tarball
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}[6/8]${NC} Copying pre-built tarball to Pi..."
echo ""

TARBALL="$SCRIPT_DIR/stegasoo-rpi-runtime-env-arm64.tar.zst"
if [[ -f "$TARBALL" ]]; then
    scp_to_pi "$TARBALL" "/opt/stegasoo/rpi/"
    echo -e "  ${GREEN}✓${NC} Tarball copied"
else
    echo -e "  ${YELLOW}⚠${NC} Tarball not found at $TARBALL"
    echo -e "  ${YELLOW}⚠${NC} Setup will build from source (takes longer)"
fi

# -----------------------------------------------------------------------------
# Step 7: Run setup
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}[7/8]${NC} Running setup.sh on Pi..."
echo ""

run_on_pi_interactive "cd /opt/stegasoo && ./rpi/setup.sh"

# -----------------------------------------------------------------------------
# Step 8: Test it works
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}[8/8]${NC} Testing Stegasoo..."
echo ""

run_on_pi "sudo systemctl start stegasoo && sleep 2 && curl -sk https://localhost:5000 | head -5"

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Build complete! Pi is ready for testing.${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Access: ${YELLOW}https://stegasoo.local:5000${NC}"
echo ""
read -p "Press ENTER to SSH into Pi for manual testing..."

ssh_pi
