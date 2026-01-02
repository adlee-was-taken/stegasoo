# Stegasoo v4.0.0 Release Checklist

## Overview

This checklist covers functionality testing for the v4.0.0 release.

### Changes in v4.0.0

| Change | v3.2.0 | v4.0.0 |
|--------|--------|--------|
| Python version | 3.10-3.12 | 3.10-3.12 (3.13 NOT supported) |
| JPEG handling | Could crash on quality=100 | Normalized before jpegio |
| Header size | 65 bytes | 65 bytes (unchanged) |
| API | passphrase, no date_str | Same (no breaking changes) |
| Format version | 4 | 4 (compatible with v3.2.0) |

### Key Points
- **No breaking API changes from v3.2.0**
- **v4.0 CAN decode v3.2.0 images** (same format version)
- **v4.0 CANNOT decode v3.1.x or earlier images**
- **Python 3.13 is NOT supported** (jpegio C extension ABI incompatibility)

---

## 1. Pre-Release Checks

### 1.1 Python Version

```bash
python --version  # Must be 3.10, 3.11, or 3.12
```

- [ ] Python version is 3.10, 3.11, or 3.12
- [ ] NOT Python 3.13 (jpegio will crash)

### 1.2 Dependencies

```bash
pip list | grep -E "jpegio|scipy|pillow|argon2"
```

- [ ] jpegio installed (for DCT JPEG support)
- [ ] scipy installed (for DCT mode)
- [ ] pillow installed
- [ ] argon2-cffi installed

---

## 2. Core Library Tests

### 2.1 Run Unit Tests

```bash
cd /path/to/stegasoo
pytest tests/ -v
```

- [ ] All tests pass
- [ ] No deprecation warnings for removed parameters

### 2.2 JPEG Normalization Test (NEW in v4.0)

```bash
python -c "
from PIL import Image
import io
from stegasoo import encode, decode

# Create quality=100 JPEG (triggers normalization)
img = Image.new('RGB', (400, 400), 'red')
buf = io.BytesIO()
img.save(buf, format='JPEG', quality=100)
jpeg_data = buf.getvalue()

# This should NOT crash (v3.2.0 would crash here)
result = encode(
    message='Test quality 100',
    reference_photo=jpeg_data,
    carrier_image=jpeg_data,
    passphrase='test phrase four words',
    pin='123456',
    embed_mode='dct'
)
print('✓ Quality=100 JPEG encode OK')

decoded = decode(
    stego_image=result.stego_image,
    reference_photo=jpeg_data,
    passphrase='test phrase four words',
    pin='123456'
)
assert decoded.message == 'Test quality 100'
print('✓ Quality=100 JPEG decode OK')
"
```

- [ ] Quality=100 JPEG encoding works (no crash)
- [ ] Quality=100 JPEG decoding works

### 2.3 Large Image Test (NEW in v4.0)

```bash
python -c "
from PIL import Image
import io
from stegasoo import encode, decode

# Create large image (similar to 14MB real photo)
img = Image.new('RGB', (4000, 3000), 'blue')
buf = io.BytesIO()
img.save(buf, format='PNG')
large_image = buf.getvalue()
print(f'Test image size: {len(large_image) / 1024 / 1024:.1f} MB')

result = encode(
    message='Large image test',
    reference_photo=large_image,
    carrier_image=large_image,
    passphrase='large image test phrase',
    pin='123456'
)
print('✓ Large image encode OK')

decoded = decode(
    stego_image=result.stego_image,
    reference_photo=large_image,
    passphrase='large image test phrase',
    pin='123456'
)
assert decoded.message == 'Large image test'
print('✓ Large image decode OK')
"
```

- [ ] Large image (12MP+) encoding works
- [ ] Large image decoding works

---

## 3. Docker Build Tests

### 3.1 Base Image Build

```bash
# Build base image (one-time, 5-10 min)
sudo docker build -f Dockerfile.base -t stegasoo-base:latest .
```

- [ ] Base image builds successfully
- [ ] jpegio + scipy + numpy verification passes

### 3.2 Application Build

```bash
# Fast build using base image
sudo docker-compose build
```

- [ ] Web container builds
- [ ] API container builds

### 3.3 Container Startup

```bash
sudo docker-compose up -d
sudo docker-compose logs
```

- [ ] Web container starts without errors
- [ ] API container starts without errors
- [ ] No import errors in logs

---

## 4. Web UI Tests (`http://localhost:5000`)

### 4.1 Home Page

- [ ] v4.0 badge visible
- [ ] "Learn More" button is white/visible
- [ ] No references to "day phrase" or dates

### 4.2 Generate Page (`/generate`)

- [ ] Default is 4 words
- [ ] Single passphrase generated (not 7 daily)
- [ ] PIN toggle shows/hides digits
- [ ] Memory aid generator works

### 4.3 Encode Page (`/encode`)

- [ ] Passphrase field has blue glow on focus
- [ ] PIN field has orange glow on focus
- [ ] PIN box is 180px wide (fits LastPass icon)
- [ ] Passphrase font shrinks for long input (stepped)
- [ ] RSA .pem/QR toggle works
- [ ] QR image preview shows when selected
- [ ] DCT mode options appear when selected
- [ ] Encoding works (LSB mode)
- [ ] Encoding works (DCT mode)

### 4.4 Decode Page (`/decode`)

- [ ] Same styling as encode (glowing inputs)
- [ ] RSA .pem/QR toggle works (matches encode layout)
- [ ] QR image preview shows when selected
- [ ] Copy button is below message (not overlapping)
- [ ] Decoding works (LSB mode)
- [ ] Decoding works (DCT mode)
- [ ] Auto mode detection works

### 4.5 About Page (`/about`)

- [ ] Version history table present
- [ ] v4.0.0 entry in table
- [ ] Python 3.10-3.12 requirement noted
- [ ] No marketing language ("military-grade" removed)

---

## 5. API Tests (`http://localhost:8000`)

### 5.1 Status Endpoint

```bash
curl http://localhost:8000/
```

- [ ] Returns version "4.0.0"
- [ ] No import errors

### 5.2 Generate Endpoint

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"use_pin": true}'
```

- [ ] Returns single `passphrase` string
- [ ] Returns 4 words by default

### 5.3 OpenAPI Docs

- [ ] `/docs` loads (Swagger UI)
- [ ] `/redoc` loads (ReDoc)
- [ ] All endpoints documented

---

## 6. CLI Tests

### 6.1 Version

```bash
stegasoo --version
```

- [ ] Shows 4.0.0

### 6.2 Generate

```bash
stegasoo generate --pin --words 4
```

- [ ] Single passphrase output
- [ ] 4 words generated

### 6.3 Encode/Decode Roundtrip

```bash
# Generate test image
python -c "from PIL import Image; Image.new('RGB', (200,200), 'red').save('/tmp/test.png')"

# Encode
stegasoo encode \
  -r /tmp/test.png \
  -c /tmp/test.png \
  -p "cli test phrase here" \
  --pin 123456 \
  -m "CLI roundtrip test" \
  -o /tmp/stego.png

# Decode
stegasoo decode \
  -r /tmp/test.png \
  -s /tmp/stego.png \
  -p "cli test phrase here" \
  --pin 123456
```

- [ ] Encode succeeds
- [ ] Decode returns correct message

---

## 7. Cross-Version Compatibility

### 7.1 v3.2.0 Compatibility

- [ ] v4.0 can decode v3.2.0 images (same format version 4)

### 7.2 v3.1.x Incompatibility

- [ ] v4.0 fails gracefully on v3.1.x images
- [ ] Error message is clear

---

## 8. Documentation Review

### 8.1 Updated Files

- [ ] README.md - v4.0 references
- [ ] INSTALL.md - Python 3.13 warning prominent
- [ ] SECURITY.md - v4.0 changes documented
- [ ] UNDER_THE_HOOD.md - JPEG normalization section

### 8.2 Template Updates

- [ ] All 7 templates updated
- [ ] No v3.x badges remaining
- [ ] Version history in About page

---

## 9. Quick Smoke Test Script

```bash
#!/bin/bash
# v4.0.0 Smoke Test

set -e

echo "=== Stegasoo v4.0.0 Smoke Test ==="

# Check version
echo "1. Checking version..."
python -c "import stegasoo; assert stegasoo.__version__.startswith('4.'), f'Wrong version: {stegasoo.__version__}'; print(f'✓ Version: {stegasoo.__version__}')"

# Check Python version
echo "2. Checking Python version..."
python -c "
import sys
v = sys.version_info
assert v.major == 3 and 10 <= v.minor <= 12, f'Python {v.major}.{v.minor} not supported'
print(f'✓ Python {v.major}.{v.minor}.{v.micro}')
"

# Check DCT support
echo "3. Checking DCT support..."
python -c "
from stegasoo import has_dct_support
from stegasoo.dct_steganography import has_jpegio_support
print(f'  DCT (scipy): {has_dct_support()}')
print(f'  JPEG native (jpegio): {has_jpegio_support()}')
assert has_dct_support(), 'DCT not available'
print('✓ DCT support OK')
"

# Test encode/decode roundtrip
echo "4. Testing encode/decode roundtrip..."
python -c "
from stegasoo import encode, decode
from PIL import Image
import io

img = Image.new('RGB', (200, 200), color='blue')
buf = io.BytesIO()
img.save(buf, format='PNG')
test_image = buf.getvalue()

result = encode(
    message='Hello v4.0.0!',
    reference_photo=test_image,
    carrier_image=test_image,
    passphrase='test phrase four words',
    pin='123456'
)

decoded = decode(
    stego_image=result.stego_image,
    reference_photo=test_image,
    passphrase='test phrase four words',
    pin='123456'
)

assert decoded.message == 'Hello v4.0.0!', f'Got: {decoded.message}'
print('✓ LSB roundtrip OK')
"

# Test DCT mode
echo "5. Testing DCT mode..."
python -c "
from stegasoo import encode, decode
from PIL import Image
import io

img = Image.new('RGB', (400, 400), color='green')
buf = io.BytesIO()
img.save(buf, format='PNG')
test_image = buf.getvalue()

result = encode(
    message='DCT v4.0 test',
    reference_photo=test_image,
    carrier_image=test_image,
    passphrase='dct test phrase here',
    pin='123456',
    embed_mode='dct'
)

decoded = decode(
    stego_image=result.stego_image,
    reference_photo=test_image,
    passphrase='dct test phrase here',
    pin='123456'
)

assert decoded.message == 'DCT v4.0 test'
print('✓ DCT roundtrip OK')
"

# Test JPEG quality=100 (v4.0 fix)
echo "6. Testing JPEG quality=100 handling..."
python -c "
from stegasoo import encode, decode
from PIL import Image
import io

img = Image.new('RGB', (400, 400), color='red')
buf = io.BytesIO()
img.save(buf, format='JPEG', quality=100)
jpeg_q100 = buf.getvalue()

result = encode(
    message='Quality 100 test',
    reference_photo=jpeg_q100,
    carrier_image=jpeg_q100,
    passphrase='jpeg quality test here',
    pin='123456',
    embed_mode='dct'
)

decoded = decode(
    stego_image=result.stego_image,
    reference_photo=jpeg_q100,
    passphrase='jpeg quality test here',
    pin='123456'
)

assert decoded.message == 'Quality 100 test'
print('✓ JPEG quality=100 OK (v4.0 fix working)')
"

echo ""
echo "=== All smoke tests passed! ==="
echo "Ready for release."
```

---

## 10. Release Steps

### 10.1 Final Checks

- [ ] All tests pass
- [ ] All Docker containers work
- [ ] Documentation updated
- [ ] Version bumped in `constants.py` and `pyproject.toml`

### 10.2 Git

```bash
git add -A
git status  # Review changes
git commit -m "v4.0.0: JPEG normalization, Python 3.12, UI polish"
git tag v4.0.0
git push origin main --tags
```

- [ ] Changes committed
- [ ] Tag created
- [ ] Pushed to remote

### 10.3 Release Notes

```markdown
## v4.0.0

### What's New
- **JPEG Normalization**: Quality=100 JPEGs now work with DCT mode
- **Python 3.12**: Recommended version (3.13 NOT supported due to jpegio)
- **UI Polish**: Glowing input fields, better layout, version history

### Fixes
- Fixed jpegio crash on quality=100 JPEG images
- Fixed QR code input on decode page
- Fixed passphrase font sizing (stepped instead of smooth)

### Breaking Changes
- Python 3.13 is NOT supported

### Compatibility
- v4.0 can decode v3.2.0 images (same format)
- v4.0 CANNOT decode v3.1.x or earlier
```

---

## Sign-Off

| Area | Tested By | Date | Status |
|------|-----------|------|--------|
| Python/Dependencies | | | ☐ |
| Unit Tests | | | ☐ |
| Docker Build | | | ☐ |
| Web UI | | | ☐ |
| API | | | ☐ |
| CLI | | | ☐ |
| Documentation | | | ☐ |

**Release Approved:** ☐

**Released By:** _________________

**Release Date:** _________________
