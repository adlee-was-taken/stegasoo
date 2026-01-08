#!/bin/bash
#
# Stegasoo Smoke Test
# Tests all core functionality against a running instance (Pi, Docker, or dev)
#
# Usage: ./smoke-test.sh [host] [port] [user] [pass]
#
# Examples:
#   ./smoke-test.sh                          # Pi default (stegasoo.local:443)
#   ./smoke-test.sh localhost 5000           # Docker default
#   ./smoke-test.sh 192.168.1.100 5000       # Custom host
#

set -e

# Configuration
HOST="${1:-stegasoo.local}"
PORT="${2:-443}"
USER="${3:-admin}"
PASS="${4:-stegasoo}"

# Build URL (don't include :443 since it's default for https)
if [ "$PORT" = "443" ]; then
    BASE_URL="https://$HOST"
else
    BASE_URL="https://$HOST:$PORT"
fi
COOKIE_JAR="/tmp/stegasoo_smoke_cookies.txt"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEST_DATA="$SCRIPT_DIR/../test_data"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

PASSED=0
FAILED=0

# -----------------------------------------------------------------------------
# Helper functions
# -----------------------------------------------------------------------------

log_test() {
    echo -e "${CYAN}[TEST]${NC} $1"
}

log_pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    PASSED=$((PASSED + 1))
}

log_fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAILED=$((FAILED + 1))
}

curl_get() {
    curl -sk "$BASE_URL$1" -b "$COOKIE_JAR" -c "$COOKIE_JAR" "${@:2}"
}

curl_post() {
    curl -sk -X POST "$BASE_URL$1" -b "$COOKIE_JAR" -c "$COOKIE_JAR" "${@:2}"
}

wait_for_job() {
    local endpoint="$1"
    local job_id="$2"
    local max_polls="${3:-30}"

    for i in $(seq 1 $max_polls); do
        sleep 1
        result=$(curl_get "$endpoint/$job_id")
        if echo "$result" | grep -q '"status":\s*"complete"'; then
            echo "$result"
            return 0
        fi
        if echo "$result" | grep -q '"status":\s*"error"'; then
            echo "$result"
            return 1
        fi
    done
    echo '{"status":"timeout"}'
    return 1
}

# -----------------------------------------------------------------------------
# Tests
# -----------------------------------------------------------------------------

test_connectivity() {
    log_test "Connectivity to $BASE_URL"
    if curl -sk --connect-timeout 5 "$BASE_URL" -o /dev/null; then
        log_pass "Server reachable"
    else
        log_fail "Cannot reach server"
        exit 1
    fi
}

test_setup_or_login() {
    log_test "Setup/Login"

    # Check if setup needed
    response=$(curl_get "/" -L -o /dev/null -w "%{url_effective}")

    if echo "$response" | grep -q "/setup"; then
        log_test "Completing first-time setup..."
        curl_post "/setup" \
            -d "username=$USER" \
            -d "password=$PASS" \
            -d "password_confirm=$PASS" \
            -L -o /dev/null
    fi

    # Login
    curl_get "/login" -o /dev/null  # Get session
    curl_post "/login" \
        -d "username=$USER" \
        -d "password=$PASS" \
        -L -o /dev/null

    # Verify logged in
    code=$(curl_get "/encode" -o /dev/null -w "%{http_code}")
    if [ "$code" = "200" ]; then
        log_pass "Authenticated successfully"
    else
        log_fail "Authentication failed (got $code)"
    fi
}

test_pages() {
    log_test "Page accessibility"

    local pages="encode decode generate tools about"
    local all_pass=true

    for page in $pages; do
        code=$(curl_get "/$page" -o /dev/null -w "%{http_code}")
        if [ "$code" = "200" ]; then
            echo -e "  ${GREEN}✓${NC} /$page"
        else
            echo -e "  ${RED}✗${NC} /$page ($code)"
            all_pass=false
        fi
    done

    if $all_pass; then
        log_pass "All pages accessible"
    else
        log_fail "Some pages inaccessible"
    fi
}

test_encode_decode_dct() {
    log_test "DCT Encode/Decode round trip"

    local message="DCT smoke test $(date +%s)"

    # Encode
    response=$(curl_post "/encode" \
        -F "reference_photo=@$TEST_DATA/ref.jpg" \
        -F "carrier=@$TEST_DATA/carrier.jpg" \
        -F "message=$message" \
        -F "passphrase=tower booty sunny windy" \
        -F "pin=727643678" \
        -F "embed_mode=dct" \
        -F "channel_key=auto" \
        -F "async=true")

    job_id=$(echo "$response" | grep -oP '"job_id":\s*"[^"]+"' | cut -d'"' -f4)

    if [ -z "$job_id" ]; then
        log_fail "DCT encode - no job ID returned"
        return
    fi

    # Wait for encode
    result=$(wait_for_job "/encode/status" "$job_id" 15)
    if ! echo "$result" | grep -q '"status":\s*"complete"'; then
        log_fail "DCT encode timeout or error"
        return
    fi

    file_id=$(echo "$result" | grep -oP '"file_id":\s*"[^"]+"' | cut -d'"' -f4)
    curl_get "/encode/download/$file_id" -o /tmp/stego_dct_test.jpg

    echo -e "  ${GREEN}✓${NC} Encoded $(ls -lh /tmp/stego_dct_test.jpg | awk '{print $5}')"

    # Decode
    response=$(curl_post "/decode" \
        -F "reference_photo=@$TEST_DATA/ref.jpg" \
        -F "stego_image=@/tmp/stego_dct_test.jpg" \
        -F "passphrase=tower booty sunny windy" \
        -F "pin=727643678" \
        -F "embed_mode=auto" \
        -F "channel_key=auto" \
        -F "async=true")

    job_id=$(echo "$response" | grep -oP '"job_id":\s*"[^"]+"' | cut -d'"' -f4)

    # Wait for decode (DCT is slower on Pi)
    result=$(wait_for_job "/decode/status" "$job_id" 60)

    if echo "$result" | grep -q "$message"; then
        log_pass "DCT round trip - message verified"
    else
        log_fail "DCT decode - message mismatch"
        echo "  Expected: $message"
        echo "  Got: $result"
    fi
}

test_encode_decode_lsb() {
    log_test "LSB Encode/Decode round trip"

    local message="LSB smoke test $(date +%s)"

    # Encode
    response=$(curl_post "/encode" \
        -F "reference_photo=@$TEST_DATA/ref.jpg" \
        -F "carrier=@$TEST_DATA/carrier.jpg" \
        -F "message=$message" \
        -F "passphrase=tower booty sunny windy" \
        -F "pin=727643678" \
        -F "embed_mode=lsb" \
        -F "channel_key=auto" \
        -F "async=true")

    job_id=$(echo "$response" | grep -oP '"job_id":\s*"[^"]+"' | cut -d'"' -f4)

    if [ -z "$job_id" ]; then
        log_fail "LSB encode - no job ID returned"
        return
    fi

    result=$(wait_for_job "/encode/status" "$job_id" 10)
    if ! echo "$result" | grep -q '"status":\s*"complete"'; then
        log_fail "LSB encode timeout or error"
        return
    fi

    file_id=$(echo "$result" | grep -oP '"file_id":\s*"[^"]+"' | cut -d'"' -f4)
    curl_get "/encode/download/$file_id" -o /tmp/stego_lsb_test.png

    echo -e "  ${GREEN}✓${NC} Encoded $(ls -lh /tmp/stego_lsb_test.png | awk '{print $5}')"

    # Decode
    response=$(curl_post "/decode" \
        -F "reference_photo=@$TEST_DATA/ref.jpg" \
        -F "stego_image=@/tmp/stego_lsb_test.png" \
        -F "passphrase=tower booty sunny windy" \
        -F "pin=727643678" \
        -F "embed_mode=lsb" \
        -F "channel_key=auto" \
        -F "async=true")

    job_id=$(echo "$response" | grep -oP '"job_id":\s*"[^"]+"' | cut -d'"' -f4)
    result=$(wait_for_job "/decode/status" "$job_id" 15)

    if echo "$result" | grep -q "$message"; then
        log_pass "LSB round trip - message verified"
    else
        log_fail "LSB decode - message mismatch"
    fi
}

test_tools() {
    log_test "Tools endpoints"

    # Capacity check
    response=$(curl_post "/api/tools/capacity" \
        -F "image=@$TEST_DATA/carrier.jpg" \
        -w "%{http_code}" -o /tmp/capacity_result.json)

    if [ "$response" = "200" ]; then
        echo -e "  ${GREEN}✓${NC} Capacity check"
    else
        echo -e "  ${RED}✗${NC} Capacity check ($response)"
    fi

    # EXIF read
    response=$(curl_post "/api/tools/exif" \
        -F "image=@$TEST_DATA/carrier.jpg" \
        -w "%{http_code}" -o /tmp/exif_result.json)

    if [ "$response" = "200" ]; then
        echo -e "  ${GREEN}✓${NC} EXIF read"
        log_pass "Tools API works"
    else
        echo -e "  ${RED}✗${NC} EXIF read ($response)"
        log_fail "Tools API failed"
    fi
}

# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║              Stegasoo Smoke Test                              ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Target: ${YELLOW}$BASE_URL${NC}"
echo -e "User:   ${YELLOW}$USER${NC}"
echo ""

# Clean up
rm -f "$COOKIE_JAR" /tmp/stego_*_test.* /tmp/exif_stripped.jpg

# Run tests
test_connectivity
test_setup_or_login
test_pages
test_encode_decode_lsb
test_encode_decode_dct
test_tools

# Summary
echo ""
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"
echo -e "Results: ${GREEN}$PASSED passed${NC}, ${RED}$FAILED failed${NC}"
echo -e "${CYAN}════════════════════════════════════════════════════════════════${NC}"

# Clean up
rm -f "$COOKIE_JAR"

if [ $FAILED -gt 0 ]; then
    exit 1
fi
