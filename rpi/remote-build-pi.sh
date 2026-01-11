#!/bin/bash
#
# Stegasoo Remote Pi Build Script
# Waits for Pi to be reachable, then sets up Stegasoo
#
# Usage: ./remote-build-pi.sh [host] [user] [pass]
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Pi connection settings (defaults)
PI_HOST="${1:-stegasoo.local}"
PI_USER="${2:-admin}"
PI_PASS="${3:-stegasoo}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

wait_for_pi() {
    local attempt=1
    ssh-keygen -R "$PI_HOST" 2>/dev/null || true

    echo "Waiting for $PI_USER@$PI_HOST..."
    while ! sshpass -p "$PI_PASS" ssh -o ConnectTimeout=2 -o StrictHostKeyChecking=no -o BatchMode=no -o UserKnownHostsFile=/dev/null "$PI_USER@$PI_HOST" "exit" 2>/dev/null; do
        printf "\rAttempt %d..." "$attempt"
        ((attempt++))
        sleep 2
    done

    printf "\r${GREEN}✓ Ready after %d attempts${NC}\n" "$attempt"
    printf '\a'
}

run_on_pi() {
    sshpass -p "$PI_PASS" ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$PI_USER@$PI_HOST" "$@"
}

run_on_pi_interactive() {
    sshpass -p "$PI_PASS" ssh -t -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$PI_USER@$PI_HOST" "$@"
}

scp_to_pi() {
    local src="$1"
    local dst="$2"
    sshpass -p "$PI_PASS" scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$src" "$PI_USER@$PI_HOST:$dst"
}

ssh_pi() {
    ssh-keygen -R "$PI_HOST" 2>/dev/null || true
    sshpass -p "$PI_PASS" ssh -t -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$PI_USER@$PI_HOST" "$@"
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              Stegasoo Remote Pi Build                         ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Host: ${YELLOW}$PI_HOST${NC}"
echo -e "User: ${YELLOW}$PI_USER${NC}"
echo ""

# -----------------------------------------------------------------------------
# Step 1: Wait for Pi to be ready
# -----------------------------------------------------------------------------
echo -e "${GREEN}[1/6]${NC} Waiting for Pi..."
echo ""

wait_for_pi

# -----------------------------------------------------------------------------
# Step 2: Install dependencies
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}[2/6]${NC} Installing dependencies on Pi..."
echo ""

run_on_pi "sudo chown admin:admin /opt && sudo apt-get update && sudo apt-get install -y git zstd jq ca-certificates && sudo update-ca-certificates"

# -----------------------------------------------------------------------------
# Step 3: Clone repo
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}[3/6]${NC} Cloning Stegasoo repo..."
echo ""

run_on_pi "cd /opt && rm -rf stegasoo && git clone https://github.com/adlee-was-taken/stegasoo.git stegasoo"

# -----------------------------------------------------------------------------
# Step 4: Copy pre-built tarball
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}[4/6]${NC} Copying pre-built tarball to Pi..."
echo ""

TARBALL="$SCRIPT_DIR/stegasoo-rpi-venv-arm64.tar.zst"
if [[ -f "$TARBALL" ]]; then
    scp_to_pi "$TARBALL" "/opt/stegasoo/rpi/"
    echo -e "  ${GREEN}✓${NC} Tarball copied"
else
    echo -e "  ${YELLOW}⚠${NC} Tarball not found at $TARBALL"
    echo -e "  ${YELLOW}⚠${NC} Setup will build from source (takes longer)"
fi

# -----------------------------------------------------------------------------
# Step 5: Run setup
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}[5/6]${NC} Running setup.sh on Pi..."
echo ""

run_on_pi_interactive "cd /opt/stegasoo && ./rpi/setup.sh"

# -----------------------------------------------------------------------------
# Step 6: Test it works
# -----------------------------------------------------------------------------
echo ""
echo -e "${GREEN}[6/6]${NC} Testing Stegasoo..."
echo ""

run_on_pi "sudo systemctl start stegasoo && sleep 2 && curl -sk https://localhost:5000 | head -5"

echo ""
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Build complete! Pi is ready for testing.${NC}"
echo -e "${GREEN}════════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Access: ${YELLOW}https://$PI_HOST:5000${NC}"
echo ""
read -p "Press ENTER to SSH into Pi for manual testing..."

ssh_pi
