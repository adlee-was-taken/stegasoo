#!/bin/bash
#
# Apply ARM64 patch to jpegio
# This script tries multiple strategies to remove the x86-specific -m64 flag
#
# Usage: ./apply-patch.sh /path/to/jpegio
#

set -e

JPEGIO_DIR="${1:-.}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PATCH_FILE="$SCRIPT_DIR/arm64.patch"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

cd "$JPEGIO_DIR"

echo "Applying ARM64 patch to jpegio..."

# Strategy 1: Try the standard patch file
if [ -f "$PATCH_FILE" ]; then
    echo "  Trying patch file..."
    if patch -p1 --dry-run < "$PATCH_FILE" >/dev/null 2>&1; then
        patch -p1 < "$PATCH_FILE"
        echo -e "  ${GREEN}✓ Patch applied successfully${NC}"
        exit 0
    else
        echo -e "  ${YELLOW}Patch file didn't apply cleanly, trying fallback...${NC}"
    fi
fi

# Strategy 2: Sed replacement (handles any number of occurrences)
if grep -q "cargs.append('-m64')" setup.py 2>/dev/null; then
    echo "  Using sed fallback..."
    sed -i "s/cargs.append('-m64')/pass  # ARM64: removed x86-specific -m64 flag/g" setup.py

    # Verify the fix
    if grep -q "cargs.append('-m64')" setup.py; then
        echo -e "  ${RED}✗ Sed replacement failed${NC}"
        exit 1
    fi

    echo -e "  ${GREEN}✓ Sed fallback successful${NC}"
    exit 0
fi

# Strategy 3: Check if already patched
if grep -q "ARM64: removed" setup.py 2>/dev/null; then
    echo -e "  ${GREEN}✓ Already patched${NC}"
    exit 0
fi

# Strategy 4: Python-based patching (most flexible)
echo "  Using Python fallback..."
python3 << 'PYTHON_PATCH'
import re
import sys

with open('setup.py', 'r') as f:
    content = f.read()

original = content

# Pattern 1: Direct replacement
content = re.sub(
    r"cargs\.append\(['\"]+-m64['\"]+\)",
    "pass  # ARM64: removed x86-specific -m64 flag",
    content
)

# Pattern 2: Handle variations with different quotes or spacing
content = re.sub(
    r"cargs\.append\s*\(\s*['\"]+-m64['\"]+\s*\)",
    "pass  # ARM64: removed x86-specific -m64 flag",
    content
)

if content == original:
    # Check if already patched or pattern not found
    if "ARM64: removed" in content:
        print("Already patched")
        sys.exit(0)
    else:
        print("Warning: -m64 pattern not found in setup.py")
        print("This may indicate jpegio's structure has changed significantly")
        sys.exit(0)  # Don't fail - maybe they removed it upstream

with open('setup.py', 'w') as f:
    f.write(content)

print("Python patch applied")
PYTHON_PATCH

if [ $? -eq 0 ]; then
    echo -e "  ${GREEN}✓ Python fallback successful${NC}"
    exit 0
fi

echo -e "${RED}✗ All patching strategies failed${NC}"
echo "Please check jpegio's setup.py manually"
exit 1
