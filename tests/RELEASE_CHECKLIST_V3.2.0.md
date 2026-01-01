# Stegasoo v3.2.0 Release Checklist

## Overview

This checklist covers comprehensive functionality testing for the v3.2.0 release, which introduces breaking changes from v3.1.x.

### Breaking Changes in v3.2.0

| Change | v3.1.x | v3.2.0 |
|--------|--------|--------|
| Passphrase model | 7 daily phrases (`day_phrase`) | Single `passphrase` |
| Date parameter | Required `date_str` | Removed |
| Default words | 3 | 4 |
| Format version | 3 | 4 |
| Backward compatible | N/A | ❌ Cannot decode v3.1.x images |

---

## 1. Core Library Tests

### 1.1 Key Generation (`src/stegasoo/keygen.py`)

- [ ] **generate_pin()** - Default 6 digits, no leading zero
- [ ] **generate_pin(length=9)** - Custom length works
- [ ] **generate_phrase(words=4)** - Default 4 words
- [ ] **generate_phrase(words=6)** - Custom word count
- [ ] **generate_credentials(use_pin=True)** - Returns single passphrase
- [ ] **generate_credentials(use_rsa=True)** - RSA key generation
- [ ] **generate_credentials(use_pin=False, use_rsa=False)** - Raises error
- [ ] **Credentials.passphrase** - Single string, not dict
- [ ] **Credentials.passphrase_entropy** - Correct entropy (4 words = 44 bits)
- [ ] **Credentials.total_entropy** - Sum is correct

### 1.2 Encoding (`src/stegasoo/steganography.py`)

- [ ] **encode() with passphrase** - New parameter name works
- [ ] **encode() without date_str** - No date parameter needed
- [ ] **HEADER_OVERHEAD = 65** - Correct constant
- [ ] **LSB mode** - Default, full color PNG output
- [ ] **DCT mode** - Frequency domain embedding
- [ ] **DCT + JPEG output** - Works correctly
- [ ] **DCT + color mode** - Preserves colors
- [ ] **Capacity calculation** - Uses 65-byte overhead

### 1.3 Decoding (`src/stegasoo/steganography.py`)

- [ ] **decode() with passphrase** - New parameter name works
- [ ] **decode() without date_str** - No date parameter needed
- [ ] **Auto mode detection** - LSB vs DCT automatic
- [ ] **Wrong passphrase** - Raises DecryptionError
- [ ] **Wrong PIN** - Raises DecryptionError
- [ ] **Wrong reference photo** - Raises DecryptionError

### 1.4 DCT Steganography (`src/stegasoo/dct_steganography.py`)

- [ ] **Y channel extraction** - Uses correct formula (not just R channel)
- [ ] **Color mode encoding** - YCbCr conversion works
- [ ] **Grayscale mode** - Converts to grayscale
- [ ] **JPEG output** - Quality 95, proper format
- [ ] **PNG output** - Lossless DCT output

### 1.5 Batch Processing (`src/stegasoo/batch.py`)

- [ ] **BatchCredentials.passphrase** - Single field, not dict
- [ ] **BatchCredentials.from_dict()** - Accepts both old and new format
- [ ] **batch_encode()** - Uses passphrase parameter
- [ ] **batch_decode()** - Uses passphrase parameter

### 1.6 Validation

- [ ] **validate_passphrase()** - New function works
- [ ] **validate_passphrase() warning** - Warns if < 4 words
- [ ] **validate_pin()** - 6-9 digits, no leading zero
- [ ] **validate_message()** - Non-empty, within size limits

---

## 2. CLI Frontend Tests (`frontends/cli/main.py`)

### 2.1 Generate Command

```bash
# Test default generation (4 words, PIN)
stegasoo generate --pin

# Test custom word count
stegasoo generate --pin --words 6

# Test RSA generation
stegasoo generate --rsa

# Test JSON output
stegasoo generate --pin --json
```

- [ ] Output shows single `PASSPHRASE:` not daily phrases
- [ ] Default is 4 words
- [ ] JSON has `passphrase` field, not `phrases` dict
- [ ] Entropy shows `passphrase_entropy`

### 2.2 Encode Command

```bash
# Test basic encode
stegasoo encode -r ref.jpg -c carrier.png \
  -p "word1 word2 word3 word4" --pin 123456 \
  -m "Secret message"

# Test DCT mode
stegasoo encode -r ref.jpg -c carrier.png \
  -p "word1 word2 word3 word4" --pin 123456 \
  -m "Secret" --mode dct

# Test DCT + JPEG
stegasoo encode -r ref.jpg -c carrier.png \
  -p "word1 word2 word3 word4" --pin 123456 \
  -m "Secret" --mode dct --dct-format jpeg
```

- [ ] `-p` / `--passphrase` parameter works
- [ ] No `--date` parameter exists
- [ ] LSB mode produces PNG
- [ ] DCT mode works
- [ ] DCT + JPEG output works
- [ ] Output filename has no date suffix

### 2.3 Decode Command

```bash
# Test basic decode
stegasoo decode -r ref.jpg -s stego.png \
  -p "word1 word2 word3 word4" --pin 123456

# Test auto mode detection
stegasoo decode -r ref.jpg -s stego.png \
  -p "word1 word2 word3 word4" --pin 123456 --mode auto
```

- [ ] `-p` / `--passphrase` parameter works
- [ ] No `--date` parameter exists
- [ ] Auto-detects LSB vs DCT
- [ ] Outputs decoded message

### 2.4 Other Commands

```bash
# Verify command
stegasoo verify -s stego.png

# Compare command
stegasoo compare original.png stego.png

# Modes command
stegasoo modes

# Capacity command
stegasoo capacity carrier.png
```

- [ ] All commands work without errors
- [ ] No references to "day phrase" or dates

---

## 3. API Frontend Tests (`frontends/api/main.py`)

### 3.1 Status Endpoint

```bash
curl http://localhost:8000/
```

- [ ] Returns `version: "3.2.0"`
- [ ] Includes `breaking_changes` object
- [ ] No `day_names` field

### 3.2 Generate Endpoint

```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"use_pin": true, "words_per_passphrase": 4}'
```

- [ ] Parameter is `words_per_passphrase` (not `words_per_phrase`)
- [ ] Response has `passphrase` string field
- [ ] Response has `phrases: null`
- [ ] Entropy field is `passphrase` not `phrase`

### 3.3 Encode Endpoint

```bash
curl -X POST http://localhost:8000/encode \
  -H "Content-Type: application/json" \
  -d '{
    "message": "Secret",
    "passphrase": "word1 word2 word3 word4",
    "pin": "123456",
    "reference_photo_base64": "...",
    "carrier_image_base64": "..."
  }'
```

- [ ] Parameter is `passphrase` (not `day_phrase`)
- [ ] No `date_str` parameter accepted
- [ ] Response has `date_used: null`
- [ ] Response has `day_of_week: null`

### 3.4 Decode Endpoint

```bash
curl -X POST http://localhost:8000/decode \
  -H "Content-Type: application/json" \
  -d '{
    "passphrase": "word1 word2 word3 word4",
    "pin": "123456",
    "stego_image_base64": "...",
    "reference_photo_base64": "..."
  }'
```

- [ ] Parameter is `passphrase` (not `day_phrase`)
- [ ] No `date_str` parameter needed
- [ ] Auto-detects embedding mode

### 3.5 Multipart Endpoints

```bash
# Encode multipart
curl -X POST http://localhost:8000/encode/multipart \
  -F "passphrase=word1 word2 word3 word4" \
  -F "pin=123456" \
  -F "message=Secret" \
  -F "reference_photo=@ref.jpg" \
  -F "carrier=@carrier.png"

# Decode multipart
curl -X POST http://localhost:8000/decode/multipart \
  -F "passphrase=word1 word2 word3 word4" \
  -F "pin=123456" \
  -F "reference_photo=@ref.jpg" \
  -F "stego_image=@stego.png"
```

- [ ] Form field is `passphrase` (not `day_phrase`)
- [ ] No `date_str` field
- [ ] Headers include `X-Stegasoo-Version: 3.2.0`
- [ ] No date headers in response

---

## 4. Web Frontend Tests (`frontends/web/app.py`)

### 4.1 Generate Page (`/generate`)

- [ ] Form field is `words_per_passphrase`
- [ ] Default slider value is 4
- [ ] Output shows single passphrase, not 7 daily phrases
- [ ] Memory aid works with single passphrase
- [ ] Entropy display shows `passphrase_entropy`
- [ ] v3.2.0 badge visible

### 4.2 Encode Page (`/encode`)

- [ ] Form field is `passphrase`
- [ ] No date selection field
- [ ] v3.2.0 badge on passphrase label
- [ ] Passphrase validation warning works (< 4 words)
- [ ] DCT mode options work
- [ ] Success result shows no date info

### 4.3 Decode Page (`/decode`)

- [ ] Form field is `passphrase`
- [ ] No date input field
- [ ] No date detection from filename JavaScript
- [ ] Troubleshooting mentions v3.2.0 compatibility
- [ ] Auto mode detection works

### 4.4 Other Pages

- [ ] **Home** (`/`) - Shows v3.2.0 badge, passphrase terminology
- [ ] **About** (`/about`) - Updated terminology, v3.2.0 features
- [ ] **Footer** - Says "Passphrase" not "Day-Phrase"

---

## 5. Integration Tests

### 5.1 Full Roundtrip Tests

```bash
# Generate → Encode → Decode (LSB)
stegasoo generate --pin > creds.json
stegasoo encode -r ref.jpg -c carrier.png -p "..." --pin 123456 -m "Test" -o stego.png
stegasoo decode -r ref.jpg -s stego.png -p "..." --pin 123456

# Generate → Encode → Decode (DCT)
stegasoo encode -r ref.jpg -c carrier.png -p "..." --pin 123456 -m "Test" --mode dct -o stego_dct.png
stegasoo decode -r ref.jpg -s stego_dct.png -p "..." --pin 123456
```

- [ ] LSB roundtrip works
- [ ] DCT roundtrip works
- [ ] DCT + JPEG roundtrip works
- [ ] File embedding roundtrip works

### 5.2 Cross-Frontend Tests

- [ ] Encode via CLI, decode via API
- [ ] Encode via API, decode via Web
- [ ] Encode via Web, decode via CLI

### 5.3 Error Handling

- [ ] Wrong passphrase shows clear error
- [ ] Wrong PIN shows clear error
- [ ] Wrong reference photo shows clear error
- [ ] Capacity exceeded shows clear error
- [ ] Invalid image shows clear error

---

## 6. Documentation Tests

### 6.1 CLI Documentation (`frontends/CLI.md`)

- [ ] "What's New in v3.2.0" section exists
- [ ] All examples use 4-word passphrases
- [ ] No `--date` parameter in examples
- [ ] Command reference is complete
- [ ] Migration notes for v3.1.x users

### 6.2 API Documentation (`frontends/API.md`)

- [ ] "What's New in v3.2.0" section exists
- [ ] All request examples use `passphrase`
- [ ] No `date_str` in request models
- [ ] Response models show `date_used: null`
- [ ] Code examples updated

### 6.3 Web UI Documentation (`frontends/WEB_UI.md`)

- [ ] "What's New in v3.2.0" section exists
- [ ] Workflow examples use passphrase
- [ ] No date selection in screenshots/descriptions
- [ ] Troubleshooting updated

---

## 7. Backward Compatibility Tests

### 7.1 v3.1.x Image Decoding

- [ ] Attempting to decode v3.1.x image with v3.2.0 fails gracefully
- [ ] Error message mentions version incompatibility
- [ ] Suggests using v3.1.x for old images

### 7.2 Migration Path

- [ ] `BatchCredentials.from_dict()` accepts old `day_phrase` key
- [ ] `generate_credentials_legacy()` available if needed
- [ ] Documentation explains migration steps

---

## 8. Unit Test Updates

### 8.1 Test Files to Update

- [ ] `tests/test_stegasoo.py` - Use `passphrase` parameter
- [ ] `tests/test_batch.py` - Use `passphrase` in credentials
- [ ] `tests/test_compression.py` - No changes needed (compression unchanged)

### 8.2 New Tests Needed

- [ ] Test single passphrase generation
- [ ] Test `passphrase_words` parameter
- [ ] Test `validate_passphrase()` function
- [ ] Test DCT Y channel extraction
- [ ] Test 65-byte header overhead

---

## 9. Release Artifacts

### 9.1 Version Bumps

- [ ] `src/stegasoo/constants.py` - `__version__ = "3.2.0"`
- [ ] `pyproject.toml` or `setup.py` - version updated
- [ ] `CHANGELOG.md` - v3.2.0 section added

### 9.2 Documentation

- [ ] `README.md` - Updated for v3.2.0
- [ ] `frontends/CLI.md` - Complete
- [ ] `frontends/API.md` - Complete
- [ ] `frontends/WEB_UI.md` - Complete

### 9.3 Git

- [ ] All changes committed
- [ ] Tag created: `v3.2.0`
- [ ] Release notes written

---

## 10. Quick Smoke Test Script

```bash
#!/bin/bash
# v3.2.0 Smoke Test

set -e

echo "=== Stegasoo v3.2.0 Smoke Test ==="

# Check version
echo "1. Checking version..."
python -c "import stegasoo; print(f'Version: {stegasoo.__version__}')"

# Generate credentials
echo "2. Generating credentials..."
python -c "
from stegasoo import generate_credentials
creds = generate_credentials(use_pin=True, passphrase_words=4)
print(f'Passphrase: {creds.passphrase}')
print(f'PIN: {creds.pin}')
print(f'Entropy: {creds.total_entropy} bits')
assert ' ' in creds.passphrase, 'Passphrase should have spaces'
assert len(creds.passphrase.split()) == 4, 'Should have 4 words'
print('✓ Credentials OK')
"

# Test encode/decode roundtrip
echo "3. Testing encode/decode roundtrip..."
python -c "
from stegasoo import encode, decode
from PIL import Image
import io

# Create test image
img = Image.new('RGB', (200, 200), color='blue')
buf = io.BytesIO()
img.save(buf, format='PNG')
test_image = buf.getvalue()

# Encode
result = encode(
    message='Hello v3.2.0!',
    reference_photo=test_image,
    carrier_image=test_image,
    passphrase='test phrase four words',
    pin='123456'
)
print(f'Encoded: {result.filename}')

# Decode
decoded = decode(
    stego_image=result.stego_image,
    reference_photo=test_image,
    passphrase='test phrase four words',
    pin='123456'
)
assert decoded.message == 'Hello v3.2.0!', 'Message mismatch'
print(f'Decoded: {decoded.message}')
print('✓ Roundtrip OK')
"

# Test DCT mode
echo "4. Testing DCT mode..."
python -c "
from stegasoo import encode, decode, has_dct_support
if has_dct_support():
    from PIL import Image
    import io
    
    img = Image.new('RGB', (200, 200), color='green')
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    test_image = buf.getvalue()
    
    result = encode(
        message='DCT test',
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
    assert decoded.message == 'DCT test'
    print('✓ DCT Mode OK')
else:
    print('⚠ DCT mode not available (scipy not installed)')
"

echo ""
echo "=== All smoke tests passed! ==="
```

---

## Sign-Off

| Area | Tested By | Date | Status |
|------|-----------|------|--------|
| Core Library | | | ☐ |
| CLI Frontend | | | ☐ |
| API Frontend | | | ☐ |
| Web Frontend | | | ☐ |
| Documentation | | | ☐ |
| Integration | | | ☐ |

**Release Approved:** ☐

**Released By:** _________________

**Release Date:** _________________
