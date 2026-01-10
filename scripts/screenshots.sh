#!/bin/bash
# Capture Web UI screenshots for documentation
# Requires: chromium, imagemagick
# Usage: ./scripts/screenshots.sh [base_url]
#
# Modes:
#   Default (auth disabled): Captures main UI pages
#   With auth: Also captures login/setup/account pages
#
# Start server with: STEGASOO_AUTH_ENABLED=false python frontends/web/app.py

set -e

BASE_URL="${1:-http://localhost:5000}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
OUTPUT_DIR="$PROJECT_DIR/data"
WINDOW_SIZE="1280,900"

echo "╔══════════════════════════════════════════╗"
echo "║     Stegasoo Screenshot Capture          ║"
echo "╚══════════════════════════════════════════╝"
echo ""
echo "Base URL: $BASE_URL"
echo "Output:   $OUTPUT_DIR"
echo ""

# Check dependencies
for cmd in chromium magick curl; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "Error: $cmd not found"
        exit 1
    fi
done

# Check if server is running (-k for self-signed certs)
if ! curl -sk "$BASE_URL" > /dev/null 2>&1; then
    echo "Error: Server not responding at $BASE_URL"
    echo "Start with: STEGASOO_AUTH_ENABLED=false python frontends/web/app.py"
    exit 1
fi

# Capture a single screenshot
capture() {
    local name="$1"
    local route="$2"
    local url="$BASE_URL$route"

    printf "  %-20s <- %s\n" "$name" "$route"
    chromium --headless --screenshot="$OUTPUT_DIR/$name.png" \
        --window-size="$WINDOW_SIZE" --hide-scrollbars \
        --disable-gpu --no-sandbox --ignore-certificate-errors \
        "$url" 2>/dev/null
}

echo "Capturing main pages..."
echo ""

# Core pages (always capture)
capture "WebUI"          "/"
capture "WebUI_Encode"   "/encode"
capture "WebUI_Decode"   "/decode"
capture "WebUI_Generate" "/generate"
capture "WebUI_Tools"    "/tools"
capture "WebUI_About"    "/about"

echo ""
echo "Capturing auth pages..."
echo ""

# Auth pages (may redirect if auth disabled, that's OK)
capture "WebUI_Login"    "/login"
capture "WebUI_Setup"    "/setup"
capture "WebUI_Account"  "/account"
capture "WebUI_Recover"  "/recover"

echo ""
echo "Converting to webp..."
echo ""

for png in "$OUTPUT_DIR"/WebUI*.png; do
    [ -f "$png" ] || continue
    name=$(basename "$png" .png)
    printf "  %-20s -> %s.webp\n" "$name.png" "$name"
    magick "$png" -quality 85 "$OUTPUT_DIR/$name.webp"
    rm -f "$png"
done

echo ""
echo "Done! Screenshots:"
echo ""
ls -lh "$OUTPUT_DIR"/WebUI*.webp 2>/dev/null | awk '{print "  " $NF " (" $5 ")"}'
echo ""
