#!/bin/bash
# =============================================================================
# Stegasoo Release Validation Script
# =============================================================================
# Automated pre-release validation to catch issues before tagging a release.
#
# Usage:
#   ./scripts/validate-release.sh              # Local validation only
#   ./scripts/validate-release.sh --pi         # Include Pi smoke test
#   PI_IP=192.168.0.4 ./scripts/validate-release.sh --pi
#
# Exit codes:
#   0 = All tests passed
#   1 = One or more tests failed
# =============================================================================

# Don't use set -e as we need to handle test failures gracefully

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Default Pi IP (can be overridden via environment)
PI_IP="${PI_IP:-192.168.0.4}"
PI_USER="${PI_USER:-alee}"
INCLUDE_PI=false
INCLUDE_DOCKER=true

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --pi)
            INCLUDE_PI=true
            shift
            ;;
        --no-docker)
            INCLUDE_DOCKER=false
            shift
            ;;
        --help|-h)
            echo "Usage: $0 [--pi] [--no-docker]"
            echo ""
            echo "Options:"
            echo "  --pi         Include Pi smoke test (requires SSH access)"
            echo "  --no-docker  Skip Docker build/test"
            echo ""
            echo "Environment:"
            echo "  PI_IP        Pi IP address (default: 192.168.0.4)"
            echo "  PI_USER      Pi SSH user (default: alee)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Track results
TESTS_RUN=0
TESTS_PASSED=0
TESTS_FAILED=0
FAILED_TESTS=()

# Helper functions
pass() {
    echo -e "${GREEN}[PASS]${NC} $1"
    ((TESTS_PASSED++))
    ((TESTS_RUN++))
}

fail() {
    echo -e "${RED}[FAIL]${NC} $1"
    FAILED_TESTS+=("$1")
    ((TESTS_FAILED++))
    ((TESTS_RUN++))
}

skip() {
    echo -e "${YELLOW}[SKIP]${NC} $1"
}

section() {
    echo ""
    echo -e "${CYAN}━━━ $1 ━━━${NC}"
}

# =============================================================================
# Header
# =============================================================================
echo -e "${CYAN}╔═══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         Stegasoo Release Validation                           ║${NC}"
echo -e "${CYAN}╚═══════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Get version from pyproject.toml
VERSION=$(grep '^version = ' pyproject.toml | head -1 | cut -d'"' -f2)
echo -e "Version: ${YELLOW}${VERSION}${NC}"
echo -e "Branch:  ${YELLOW}$(git branch --show-current)${NC}"
echo ""

# =============================================================================
# 1. Code Quality Checks
# =============================================================================
section "Code Quality"

# Ruff linting
if command -v ./venv/bin/ruff &> /dev/null; then
    echo -n "Running ruff check... "
    if ./venv/bin/ruff check src/ frontends/ --quiet 2>/dev/null; then
        pass "Ruff linting"
    else
        fail "Ruff linting (run: ./venv/bin/ruff check src/ frontends/)"
    fi
else
    skip "Ruff not installed"
fi

# =============================================================================
# 2. Unit Tests (if they exist)
# =============================================================================
section "Unit Tests"

if ls tests/test_*.py 1> /dev/null 2>&1; then
    echo -n "Running pytest... "
    if ./venv/bin/pytest tests/ -q --tb=no 2>/dev/null; then
        pass "Pytest unit tests"
    else
        fail "Pytest unit tests"
    fi
else
    skip "No unit tests found (tests/test_*.py)"
fi

# =============================================================================
# 3. Import Tests
# =============================================================================
section "Import Tests"

# Test core library import
echo -n "Testing stegasoo import... "
if ./venv/bin/python -c "from stegasoo import encode, decode; print('OK')" 2>/dev/null | grep -q OK; then
    pass "Core library import"
else
    fail "Core library import"
fi

# Test DCT support
echo -n "Testing DCT support... "
if ./venv/bin/python -c "from stegasoo import has_dct_support; assert has_dct_support(), 'No DCT'; print('OK')" 2>/dev/null | grep -q OK; then
    pass "DCT support available"
else
    fail "DCT support (scipy/jpegio missing?)"
fi

# Test CLI import
echo -n "Testing CLI import... "
if ./venv/bin/python -c "from stegasoo.cli import main; print('OK')" 2>/dev/null | grep -q OK; then
    pass "CLI module import"
else
    fail "CLI module import"
fi

# =============================================================================
# 4. Encode/Decode Sanity Test
# =============================================================================
section "Encode/Decode Test"

echo -n "Running encode/decode sanity check... "
SANITY_RESULT=$(./venv/bin/python << 'EOF' 2>&1
import sys
sys.path.insert(0, 'src')
from stegasoo import encode, decode

with open('test_data/carrier.jpg', 'rb') as f:
    carrier = f.read()
with open('test_data/ref.jpg', 'rb') as f:
    ref = f.read()

# LSB test
result = encode(message="sanity test", reference_photo=ref, carrier_image=carrier,
                passphrase="test", pin="123456", embed_mode="lsb")
decoded = decode(stego_image=result.stego_image, reference_photo=ref,
                 passphrase="test", pin="123456", embed_mode="lsb")
assert decoded.message == "sanity test", f"LSB mismatch: {decoded.message}"

# DCT test
result = encode(message="dct sanity", reference_photo=ref, carrier_image=carrier,
                passphrase="dct", pin="654321", embed_mode="dct")
decoded = decode(stego_image=result.stego_image, reference_photo=ref,
                 passphrase="dct", pin="654321", embed_mode="dct")
assert decoded.message == "dct sanity", f"DCT mismatch: {decoded.message}"

print("OK")
EOF
)

if echo "$SANITY_RESULT" | grep -q "OK"; then
    pass "Encode/decode sanity (LSB + DCT)"
else
    fail "Encode/decode sanity: $SANITY_RESULT"
fi

# =============================================================================
# 5. Docker Build & Test (optional)
# =============================================================================
if $INCLUDE_DOCKER; then
    section "Docker"

    if command -v docker &> /dev/null || command -v sudo &> /dev/null; then
        DOCKER_CMD="docker"
        if ! docker info &>/dev/null 2>&1; then
            DOCKER_CMD="sudo docker"
        fi

        echo -n "Building Docker image... "
        if $DOCKER_CMD build -t stegasoo:validate -q . >/dev/null 2>&1; then
            pass "Docker build"

            # Test container starts
            echo -n "Testing container startup... "
            CONTAINER_ID=$($DOCKER_CMD run -d -p 15000:5000 stegasoo:validate 2>/dev/null)
            sleep 3

            if curl -s -o /dev/null -w "%{http_code}" http://localhost:15000/ 2>/dev/null | grep -qE "200|302"; then
                pass "Container responds to HTTP"
            else
                fail "Container HTTP response"
            fi

            # Cleanup
            $DOCKER_CMD stop "$CONTAINER_ID" >/dev/null 2>&1 || true
            $DOCKER_CMD rm "$CONTAINER_ID" >/dev/null 2>&1 || true
        else
            fail "Docker build"
        fi

        # Cleanup test image
        $DOCKER_CMD rmi stegasoo:validate >/dev/null 2>&1 || true
    else
        skip "Docker not available"
    fi
else
    skip "Docker tests (use --docker to enable)"
fi

# =============================================================================
# 6. Pi Smoke Test (optional)
# =============================================================================
if $INCLUDE_PI; then
    section "Pi Smoke Test"

    echo -n "Testing SSH connectivity to $PI_USER@$PI_IP... "
    if ssh -o ConnectTimeout=5 -o BatchMode=yes "$PI_USER@$PI_IP" "echo OK" 2>/dev/null | grep -q OK; then
        pass "SSH connectivity"

        echo -n "Checking stegasoo service status... "
        if ssh "$PI_USER@$PI_IP" "systemctl is-active stegasoo" 2>/dev/null | grep -q active; then
            pass "Stegasoo service running"

            echo -n "Running smoke test on Pi... "
            SMOKE_RESULT=$(ssh "$PI_USER@$PI_IP" "cd /home/$PI_USER/stegasoo && bash tests/smoke-test.sh --quick 2>&1" || echo "FAILED")
            if echo "$SMOKE_RESULT" | grep -qE "All tests passed|PASS"; then
                pass "Pi smoke test"
            else
                fail "Pi smoke test"
            fi
        else
            fail "Stegasoo service not running"
        fi
    else
        fail "SSH connectivity to Pi"
    fi
else
    skip "Pi smoke test (use --pi to enable)"
fi

# =============================================================================
# Summary
# =============================================================================
echo ""
echo -e "${CYAN}━━━ Summary ━━━${NC}"
echo ""
echo -e "Tests run:    ${TESTS_RUN}"
echo -e "Passed:       ${GREEN}${TESTS_PASSED}${NC}"
echo -e "Failed:       ${RED}${TESTS_FAILED}${NC}"

if [ ${#FAILED_TESTS[@]} -gt 0 ]; then
    echo ""
    echo -e "${RED}Failed tests:${NC}"
    for test in "${FAILED_TESTS[@]}"; do
        echo -e "  - $test"
    done
fi

echo ""
if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ All validation checks passed!${NC}"
    echo -e "  Ready to tag release ${VERSION}"
    exit 0
else
    echo -e "${RED}✗ Validation failed - fix issues before release${NC}"
    exit 1
fi
