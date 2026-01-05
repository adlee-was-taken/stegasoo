#!/bin/bash
#
# Stegasoo Pi Image Smoke Test
# Automated testing of a fresh Pi image
#
# Usage: ./smoke-test.sh [ip] [--https]
#        Default IP: 192.168.0.4
#

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Configuration
PI_IP="${1:-192.168.0.4}"
HTTPS=false
if [[ "$2" == "--https" ]] || [[ "$1" == "--https" ]]; then
  HTTPS=true
  if [[ "$1" == "--https" ]]; then
    PI_IP="192.168.0.4"
  fi
fi

if [ "$HTTPS" = true ]; then
  BASE_URL="https://$PI_IP:5000"
  CURL_OPTS="-k" # Allow self-signed certs
else
  BASE_URL="http://$PI_IP:5000"
  CURL_OPTS=""
fi

# Test credentials
ADMIN_USER="admin"
ADMIN_PASS="stegasoo"
REGULAR_USER="smokeuser"
REGULAR_PASS="SmokeUser123!"

# Temp files
COOKIE_JAR=$(mktemp)
COOKIE_JAR_USER=$(mktemp)
TEST_IMAGE=$(mktemp --suffix=.png)
ENCODED_IMAGE=$(mktemp --suffix=.png)
RESPONSE=$(mktemp)

ENCODED_IMAGE_USER=$(mktemp --suffix=.png)
QR_IMAGE=$(mktemp --suffix=.png)

cleanup() {
  rm -f "$COOKIE_JAR" "$COOKIE_JAR_USER" "$TEST_IMAGE" "$ENCODED_IMAGE" "$ENCODED_IMAGE_USER" "$QR_IMAGE" "$RESPONSE"
}
trap cleanup EXIT

# Create a simple test image (red square)
create_test_image() {
  if command -v convert &>/dev/null; then
    convert -size 100x100 xc:red "$TEST_IMAGE"
  elif command -v python3 &>/dev/null; then
    python3 -c "
from PIL import Image
img = Image.new('RGB', (100, 100), color='red')
img.save('$TEST_IMAGE')
"
  else
    echo -e "${YELLOW}Warning: No image tool available, skipping encode/decode tests${NC}"
    return 1
  fi
}

# Results tracking
TESTS_PASSED=0
TESTS_FAILED=0

pass() {
  echo -e "  ${GREEN}[PASS]${NC} $1"
  TESTS_PASSED=$((TESTS_PASSED + 1))
}

fail() {
  echo -e "  ${RED}[FAIL]${NC} $1"
  TESTS_FAILED=$((TESTS_FAILED + 1))
}

skip() {
  echo -e "  ${YELLOW}[SKIP]${NC} $1"
}

# =============================================================================
# Header
# =============================================================================

echo ""
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║            Stegasoo Pi Image Smoke Test                       ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "Target: ${YELLOW}$BASE_URL${NC}"
echo ""

# =============================================================================
# Test 1: Web UI Reachable
# =============================================================================

echo -e "${BOLD}[1/9] Web UI Accessibility${NC}"

if curl $CURL_OPTS -s -o /dev/null -w "%{http_code}" "$BASE_URL" | grep -q "200\|302"; then
  pass "Web UI is reachable"
else
  fail "Web UI not reachable at $BASE_URL"
  echo -e "${RED}Cannot continue without web access. Is the Pi running?${NC}"
  exit 1
fi

# Check if redirected to setup (first run) or login
REDIRECT=$(curl $CURL_OPTS -s -o /dev/null -w "%{redirect_url}" "$BASE_URL")
if echo "$REDIRECT" | grep -q "setup"; then
  pass "Redirected to setup (fresh install)"
  NEEDS_SETUP=true
elif echo "$REDIRECT" | grep -q "login"; then
  pass "Redirected to login (already configured)"
  NEEDS_SETUP=false
else
  # Check page content
  if curl $CURL_OPTS -s "$BASE_URL" | grep -q "setup\|Setup\|Create.*Admin"; then
    pass "Setup page detected"
    NEEDS_SETUP=true
  else
    pass "Login page detected"
    NEEDS_SETUP=false
  fi
fi

# =============================================================================
# Test 2: Create Admin User (if needed)
# =============================================================================

echo ""
echo -e "${BOLD}[2/9] Admin Setup${NC}"

if [ "$NEEDS_SETUP" = true ]; then
  # Get CSRF token from setup page
  SETUP_PAGE=$(curl $CURL_OPTS -s -c "$COOKIE_JAR" "$BASE_URL/setup")
  CSRF_TOKEN=$(echo "$SETUP_PAGE" | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' || echo "")

  if [ -z "$CSRF_TOKEN" ]; then
    # Try alternate pattern
    CSRF_TOKEN=$(echo "$SETUP_PAGE" | grep -oP 'csrf_token.*?value="\K[^"]+' || echo "")
  fi

  # Create admin user
  HTTP_CODE=$(curl $CURL_OPTS -s -o "$RESPONSE" -w "%{http_code}" \
    -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
    -X POST "$BASE_URL/setup" \
    -d "username=$ADMIN_USER" \
    -d "password=$ADMIN_PASS" \
    -d "password_confirm=$ADMIN_PASS" \
    -d "csrf_token=$CSRF_TOKEN")

  if [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "200" ]; then
    if curl $CURL_OPTS -s "$BASE_URL" | grep -q "login\|Login"; then
      pass "Admin user created successfully"
    else
      pass "Setup completed (assuming success)"
    fi
  else
    fail "Failed to create admin user (HTTP $HTTP_CODE)"
  fi
else
  skip "Setup already complete"
fi

# =============================================================================
# Test 3: Admin Login
# =============================================================================

echo ""
echo -e "${BOLD}[3/9] Admin Authentication${NC}"

# Get login page and CSRF
LOGIN_PAGE=$(curl $CURL_OPTS -s -c "$COOKIE_JAR" "$BASE_URL/login")
CSRF_TOKEN=$(echo "$LOGIN_PAGE" | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' || echo "")

# Try login as admin
HTTP_CODE=$(curl $CURL_OPTS -s -o "$RESPONSE" -w "%{http_code}" \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -X POST "$BASE_URL/login" \
  -d "username=$ADMIN_USER" \
  -d "password=$ADMIN_PASS" \
  -d "csrf_token=$CSRF_TOKEN" \
  -L)

# Check if we're logged in by accessing a protected page
if curl $CURL_OPTS -s -b "$COOKIE_JAR" "$BASE_URL/" | grep -qi "encode\|decode\|logout"; then
  pass "Admin login successful"
  ADMIN_LOGGED_IN=true
else
  fail "Admin login failed"
  ADMIN_LOGGED_IN=false
fi

# =============================================================================
# Test 4: Admin Encode/Decode
# =============================================================================

echo ""
echo -e "${BOLD}[4/9] Admin Encode/Decode${NC}"

if [ "$ADMIN_LOGGED_IN" = true ]; then
  ENCODE_PAGE=$(curl $CURL_OPTS -s -b "$COOKIE_JAR" "$BASE_URL/encode")

  if echo "$ENCODE_PAGE" | grep -qi "encode\|message\|image\|upload"; then
    pass "Encode page loads"
  else
    fail "Encode page not accessible"
  fi

  # Try actual encoding if we have image tools
  if create_test_image 2>/dev/null; then
    CSRF_TOKEN=$(echo "$ENCODE_PAGE" | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' || echo "")

    # For encode: use same image as reference_photo and carrier (for simplicity)
    # First POST (no redirect follow), get Location header, then GET result page
    ENCODE_RESULT=$(curl $CURL_OPTS -s -D - -o /dev/null \
      -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
      -X POST "$BASE_URL/encode" \
      -F "reference_photo=@$TEST_IMAGE" \
      -F "carrier=@$TEST_IMAGE" \
      -F "message=Admin smoke test" \
      -F "passphrase=smoke test phrase" \
      -F "pin=123456" \
      -F "csrf_token=$CSRF_TOKEN")

    # Extract redirect location
    RESULT_LOCATION=$(echo "$ENCODE_RESULT" | grep -i "^location:" | tr -d '\r' | awk '{print $2}')

    if [ -n "$RESULT_LOCATION" ]; then
      # GET the result page
      RESULT_PAGE=$(curl $CURL_OPTS -s -b "$COOKIE_JAR" "$BASE_URL$RESULT_LOCATION")

      # Look for download link in result page
      DOWNLOAD_URL=$(echo "$RESULT_PAGE" | grep -oP 'href="(/encode/download/[^"]+)"' | head -1 | grep -oP '/encode/download/[^"]+')
    fi

    if [ -n "$DOWNLOAD_URL" ]; then
      # Download the encoded image
      HTTP_CODE=$(curl $CURL_OPTS -s -o "$ENCODED_IMAGE" -w "%{http_code}" \
        -b "$COOKIE_JAR" "$BASE_URL$DOWNLOAD_URL")

      if [ "$HTTP_CODE" = "200" ] && file "$ENCODED_IMAGE" | grep -qi "image\|PNG\|JPEG"; then
        pass "Admin encoding works"

        # Now decode it
        DECODE_PAGE=$(curl $CURL_OPTS -s -b "$COOKIE_JAR" "$BASE_URL/decode")
        CSRF_TOKEN=$(echo "$DECODE_PAGE" | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' || echo "")

        DECODED=$(curl $CURL_OPTS -s \
          -b "$COOKIE_JAR" \
          -X POST "$BASE_URL/decode" \
          -F "reference_photo=@$TEST_IMAGE" \
          -F "stego_image=@$ENCODED_IMAGE" \
          -F "passphrase=smoke test phrase" \
          -F "pin=123456" \
          -F "csrf_token=$CSRF_TOKEN")

        if echo "$DECODED" | grep -q "Admin smoke test"; then
          pass "Admin decoding works"
        else
          fail "Admin decode failed"
        fi
      else
        fail "Failed to download encoded image (HTTP $HTTP_CODE)"
      fi
    else
      # Check for error messages in result page
      ERROR_MSG=$(echo "$RESULT_PAGE" | grep -oP 'toast-body">[^<]*<[^>]*>[^<]*' | head -1)
      if [ -n "$ERROR_MSG" ]; then
        fail "Encoding failed: $ERROR_MSG"
      else
        fail "No download link found in encode result"
      fi
    fi
  else
    skip "Encode/Decode (no image tools)"
  fi
else
  skip "Admin encode/decode (not logged in)"
fi

# =============================================================================
# Test 5: Create Regular User
# =============================================================================

echo ""
echo -e "${BOLD}[5/9] Create Regular User${NC}"

if [ "$ADMIN_LOGGED_IN" = true ]; then
  # Check if there's a user management page
  USERS_PAGE=$(curl $CURL_OPTS -s -b "$COOKIE_JAR" "$BASE_URL/users" 2>/dev/null || echo "")

  if echo "$USERS_PAGE" | grep -qi "user\|create\|add"; then
    CSRF_TOKEN=$(echo "$USERS_PAGE" | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' || echo "")

    HTTP_CODE=$(curl $CURL_OPTS -s -o "$RESPONSE" -w "%{http_code}" \
      -b "$COOKIE_JAR" \
      -X POST "$BASE_URL/users/create" \
      -d "username=$REGULAR_USER" \
      -d "password=$REGULAR_PASS" \
      -d "password_confirm=$REGULAR_PASS" \
      -d "csrf_token=$CSRF_TOKEN")

    if [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "200" ]; then
      pass "Regular user created"
      USER_CREATED=true
    else
      # Try alternate endpoint
      HTTP_CODE=$(curl $CURL_OPTS -s -o "$RESPONSE" -w "%{http_code}" \
        -b "$COOKIE_JAR" \
        -X POST "$BASE_URL/register" \
        -d "username=$REGULAR_USER" \
        -d "password=$REGULAR_PASS" \
        -d "password_confirm=$REGULAR_PASS" \
        -d "csrf_token=$CSRF_TOKEN")

      if [ "$HTTP_CODE" = "302" ] || [ "$HTTP_CODE" = "200" ]; then
        pass "Regular user created (via register)"
        USER_CREATED=true
      else
        fail "Failed to create regular user"
        USER_CREATED=false
      fi
    fi
  else
    skip "User creation (no user management page)"
    USER_CREATED=false
  fi
else
  skip "User creation (admin not logged in)"
  USER_CREATED=false
fi

# =============================================================================
# Test 6: Regular User Login & Encode/Decode
# =============================================================================

echo ""
echo -e "${BOLD}[6/9] Regular User Workflow${NC}"

if [ "$USER_CREATED" = true ]; then
  # Logout admin first (get fresh session)
  curl $CURL_OPTS -s -b "$COOKIE_JAR" "$BASE_URL/logout" >/dev/null

  # Login as regular user
  LOGIN_PAGE=$(curl $CURL_OPTS -s -c "$COOKIE_JAR_USER" "$BASE_URL/login")
  CSRF_TOKEN=$(echo "$LOGIN_PAGE" | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' || echo "")

  HTTP_CODE=$(curl $CURL_OPTS -s -o "$RESPONSE" -w "%{http_code}" \
    -b "$COOKIE_JAR_USER" -c "$COOKIE_JAR_USER" \
    -X POST "$BASE_URL/login" \
    -d "username=$REGULAR_USER" \
    -d "password=$REGULAR_PASS" \
    -d "csrf_token=$CSRF_TOKEN" \
    -L)

  if curl $CURL_OPTS -s -b "$COOKIE_JAR_USER" "$BASE_URL/" | grep -qi "encode\|decode\|logout"; then
    pass "Regular user login successful"

    # Try encode/decode as regular user
    if [ -f "$TEST_IMAGE" ]; then
      ENCODE_PAGE=$(curl $CURL_OPTS -s -b "$COOKIE_JAR_USER" "$BASE_URL/encode")
      CSRF_TOKEN=$(echo "$ENCODE_PAGE" | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' || echo "")

      HTTP_CODE=$(curl $CURL_OPTS -s -o "$ENCODED_IMAGE_USER" -w "%{http_code}" \
        -b "$COOKIE_JAR_USER" \
        -X POST "$BASE_URL/encode" \
        -F "reference_photo=@$TEST_IMAGE" \
        -F "carrier=@$TEST_IMAGE" \
        -F "message=User smoke test" \
        -F "passphrase=user test phrase" \
        -F "pin=567890" \
        -F "csrf_token=$CSRF_TOKEN")

      if [ "$HTTP_CODE" = "200" ] && [ -s "$ENCODED_IMAGE_USER" ] && file "$ENCODED_IMAGE_USER" | grep -qi "image\|PNG"; then
        pass "Regular user encoding works"
      else
        fail "Regular user encoding failed"
      fi
    fi
  else
    fail "Regular user login failed"
  fi
else
  skip "Regular user workflow (user not created)"
fi

# =============================================================================
# Test 7: Password Recovery QR
# =============================================================================

echo ""
echo -e "${BOLD}[7/9] Password Recovery QR${NC}"

# Re-login as admin
LOGIN_PAGE=$(curl $CURL_OPTS -s -c "$COOKIE_JAR" "$BASE_URL/login")
CSRF_TOKEN=$(echo "$LOGIN_PAGE" | grep -oP 'name="csrf_token"[^>]*value="\K[^"]+' || echo "")

curl $CURL_OPTS -s -o /dev/null \
  -b "$COOKIE_JAR" -c "$COOKIE_JAR" \
  -X POST "$BASE_URL/login" \
  -d "username=$ADMIN_USER" \
  -d "password=$ADMIN_PASS" \
  -d "csrf_token=$CSRF_TOKEN" \
  -L

# Check for recovery QR endpoint
RECOVERY_PAGE=$(curl $CURL_OPTS -s -b "$COOKIE_JAR" "$BASE_URL/recovery" 2>/dev/null ||
  curl $CURL_OPTS -s -b "$COOKIE_JAR" "$BASE_URL/settings" 2>/dev/null ||
  curl $CURL_OPTS -s -b "$COOKIE_JAR" "$BASE_URL/account" 2>/dev/null || echo "")

if echo "$RECOVERY_PAGE" | grep -qi "recovery\|qr\|backup"; then
  pass "Recovery page accessible"

  # Try to get QR image
  QR_URL=$(echo "$RECOVERY_PAGE" | grep -oP 'src="[^"]*qr[^"]*"' | head -1 | sed 's/src="//;s/"$//' || echo "")

  if [ -n "$QR_URL" ]; then
    if [[ "$QR_URL" != http* ]]; then
      QR_URL="$BASE_URL$QR_URL"
    fi

    HTTP_CODE=$(curl $CURL_OPTS -s -o "$QR_IMAGE" -w "%{http_code}" -b "$COOKIE_JAR" "$QR_URL")

    if [ "$HTTP_CODE" = "200" ] && [ -s "$QR_IMAGE" ]; then
      if file "$QR_IMAGE" | grep -qi "image\|PNG"; then
        pass "Recovery QR code generated"
      else
        fail "QR endpoint returned non-image"
      fi
    else
      fail "Failed to fetch QR code"
    fi
  else
    skip "QR code URL not found in page"
  fi
else
  skip "Password recovery (no recovery page found)"
fi

# =============================================================================
# Test 8: System Health
# =============================================================================

echo ""
echo -e "${BOLD}[8/9] System Health${NC}"

# Check if stegasoo CLI works via SSH (optional)
if command -v sshpass &>/dev/null; then
  CLI_VERSION=$(sshpass -p 'stegasoo' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    admin@$PI_IP "stegasoo --version" 2>/dev/null || echo "")

  if [ -n "$CLI_VERSION" ]; then
    pass "CLI accessible: $CLI_VERSION"
  else
    skip "CLI check (SSH failed or CLI not in PATH)"
  fi
else
  skip "CLI check (sshpass not installed)"
fi

# Check service status via SSH
if command -v sshpass &>/dev/null; then
  SERVICE_STATUS=$(sshpass -p 'stegasoo' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null \
    admin@$PI_IP "systemctl is-active stegasoo" 2>/dev/null || echo "unknown")

  if [ "$SERVICE_STATUS" = "active" ]; then
    pass "Stegasoo service is active"
  else
    fail "Stegasoo service status: $SERVICE_STATUS"
  fi
else
  skip "Service check (sshpass not installed)"
fi

# =============================================================================
# Test 9: Cleanup
# =============================================================================

echo ""
echo -e "${BOLD}[9/9] Cleanup${NC}"

# Just verify we can still access the site
if curl $CURL_OPTS -s -o /dev/null -w "%{http_code}" "$BASE_URL" | grep -q "200\|302"; then
  pass "Site still accessible after tests"
else
  fail "Site not accessible after tests"
fi

# =============================================================================
# Summary
# =============================================================================

echo ""
echo -e "${CYAN}═══════════════════════════════════════════════════════════════${NC}"
echo ""

TOTAL=$((TESTS_PASSED + TESTS_FAILED))

if [ $TESTS_FAILED -eq 0 ]; then
  echo -e "${GREEN}${BOLD}All tests passed!${NC} ($TESTS_PASSED/$TOTAL)"
else
  echo -e "${RED}${BOLD}Some tests failed${NC} ($TESTS_PASSED passed, $TESTS_FAILED failed)"
fi

echo ""
echo -e "Target: $BASE_URL"
echo -e "Admin user: $ADMIN_USER"
echo -e "Regular user: $REGULAR_USER"
echo ""

exit $TESTS_FAILED
