# Stegasoo CLI Documentation

Complete command-line interface reference for Stegasoo steganography operations.

## Table of Contents

- [Installation](#installation)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [generate](#generate-command)
  - [encode](#encode-command)
  - [decode](#decode-command)
  - [info](#info-command)
- [Embedding Modes](#embedding-modes)
- [Security Factors](#security-factors)
- [Workflow Examples](#workflow-examples)
- [Piping & Scripting](#piping--scripting)
- [Error Handling](#error-handling)
- [Exit Codes](#exit-codes)

---

## Installation

### From PyPI

```bash
# CLI only
pip install stegasoo[cli]

# CLI with DCT support
pip install stegasoo[cli,dct]

# With all extras
pip install stegasoo[all]
```

### From Source

```bash
git clone https://github.com/example/stegasoo.git
cd stegasoo
pip install -e ".[cli,dct]"
```

### Verify Installation

```bash
stegasoo --version
stegasoo --help

# Check DCT support
python -c "from stegasoo.dct_steganography import has_jpegio_support; print('jpegio:', has_jpegio_support())"
```

---

## Quick Start

```bash
# 1. Generate credentials (do this once, memorize results)
stegasoo generate --pin --words 3

# 2. Encode a message (LSB mode - default)
stegasoo encode \
  --ref secret_photo.jpg \
  --carrier meme.png \
  --phrase "apple forest thunder" \
  --pin 123456 \
  --message "Meet at midnight"

# 3. Encode for social media (DCT mode)
stegasoo encode \
  --ref secret_photo.jpg \
  --carrier meme.png \
  --phrase "apple forest thunder" \
  --pin 123456 \
  --message "Meet at midnight" \
  --mode dct \
  --format jpeg

# 4. Decode a message (auto-detects mode)
stegasoo decode \
  --ref secret_photo.jpg \
  --stego stego_abc123_20251227.png \
  --phrase "apple forest thunder" \
  --pin 123456
```

---

## Commands

### Generate Command

Generate credentials for encoding/decoding operations. Creates daily passphrases and optionally a PIN and/or RSA key.

#### Synopsis

```bash
stegasoo generate [OPTIONS]
```

#### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--pin/--no-pin` | | flag | `--pin` | Generate a PIN |
| `--rsa/--no-rsa` | | flag | `--no-rsa` | Generate an RSA key |
| `--pin-length` | | 6-9 | 6 | PIN length in digits |
| `--rsa-bits` | | choice | 2048 | RSA key size (2048, 3072, 4096) |
| `--words` | | 3-12 | 3 | Words per daily phrase |
| `--output` | `-o` | path | | Save RSA key to file |
| `--password` | `-p` | string | | Password for RSA key file |
| `--json` | | flag | | Output as JSON |

#### Examples

**Basic generation with PIN (default):**
```bash
stegasoo generate
```

Output:
```
═══════════════════════════════════════════════════════════════
  STEGASOO CREDENTIALS
═══════════════════════════════════════════════════════════════

⚠️  MEMORIZE THESE AND CLOSE THIS WINDOW
    Do not screenshot or save to file!

─── STATIC PIN ───
    847293

─── DAILY PHRASES ───
    Monday    │ abandon ability able
    Tuesday   │ actor actress actual
    Wednesday │ advice aerobic affair
    Thursday  │ afraid again age
    Friday    │ agree ahead aim
    Saturday  │ airport aisle alarm
    Sunday    │ album alcohol alert

─── SECURITY ───
    Phrase entropy:  33 bits
    PIN entropy:     19 bits
    Combined:        52 bits
    + photo entropy: 80-256 bits
```

**Generate with RSA key:**
```bash
stegasoo generate --rsa --rsa-bits 4096
```

**Save RSA key to encrypted file:**
```bash
stegasoo generate --rsa -o mykey.pem -p "mysecretpassword"
```

**Maximum security (longer phrases + both factors):**
```bash
stegasoo generate --pin --rsa --words 6 --pin-length 9
```

**JSON output for scripting:**
```bash
stegasoo generate --json | jq '.phrases.Monday'
```

**RSA only (no PIN):**
```bash
stegasoo generate --no-pin --rsa -o key.pem -p "password123"
```

---

### Encode Command

Encode a secret message into an image using steganography.

#### Synopsis

```bash
stegasoo encode [OPTIONS]
```

#### Options

| Option | Short | Type | Required | Default | Description |
|--------|-------|------|----------|---------|-------------|
| `--ref` | `-r` | path | ✓ | | Reference photo (shared secret) |
| `--carrier` | `-c` | path | ✓ | | Carrier image to hide message in |
| `--phrase` | `-p` | string | ✓ | | Today's passphrase |
| `--message` | `-m` | string | | | Message to encode |
| `--message-file` | `-f` | path | | | Read message from file |
| `--pin` | | string | * | | Static PIN (6-9 digits) |
| `--key` | `-k` | path | * | | RSA key file |
| `--key-password` | | string | | | Password for RSA key |
| `--output` | `-o` | path | | | Output filename |
| `--date` | | YYYY-MM-DD | | | Date override |
| `--mode` | | choice | | `lsb` | Embedding mode: `lsb` or `dct` |
| `--format` | | choice | | `png` | Output format: `png` or `jpeg` (DCT only) |
| `--color` | | choice | | `color` | Color mode: `color` or `grayscale` (DCT only) |
| `--quiet` | `-q` | flag | | | Suppress output |

\* At least one of `--pin` or `--key` is required.

#### Message Input Methods

1. **Command line argument:**
   ```bash
   stegasoo encode -r ref.jpg -c carrier.png -p "phrase" --pin 123456 -m "Secret message"
   ```

2. **From file:**
   ```bash
   stegasoo encode -r ref.jpg -c carrier.png -p "phrase" --pin 123456 -f message.txt
   ```

3. **From stdin (pipe):**
   ```bash
   echo "Secret message" | stegasoo encode -r ref.jpg -c carrier.png -p "phrase" --pin 123456
   ```

#### Examples

**Basic encoding with PIN (LSB mode - default):**
```bash
stegasoo encode \
  --ref photos/vacation.jpg \
  --carrier memes/funny_cat.png \
  --phrase "correct horse battery" \
  --pin 847293 \
  --message "The package arrives Tuesday"
```

Output:
```
✓ Encoded successfully!
  Output: a1b2c3d4_20251227.png
  Size: 245,832 bytes
  Mode: LSB
  Capacity used: 12.4%
  Date: 2025-12-27
```

**DCT mode for social media (JPEG output):**
```bash
stegasoo encode \
  --ref photos/vacation.jpg \
  --carrier memes/funny_cat.png \
  --phrase "correct horse battery" \
  --pin 847293 \
  --message "The package arrives Tuesday" \
  --mode dct \
  --format jpeg
```

Output:
```
✓ Encoded successfully!
  Output: a1b2c3d4_20251227.jpg
  Size: 89,432 bytes
  Mode: DCT (color, jpeg)
  Capacity used: 45.2%
  Date: 2025-12-27
  
  ⚠️  DCT mode is experimental
```

**DCT mode with PNG output (maximum DCT capacity):**
```bash
stegasoo encode \
  -r ref.jpg \
  -c carrier.png \
  -p "phrase words here" \
  --pin 123456 \
  -m "Longer message that needs more space" \
  --mode dct \
  --format png \
  --color color
```

**DCT grayscale mode:**
```bash
stegasoo encode \
  -r ref.jpg \
  -c bw_photo.png \
  -p "phrase" \
  --pin 123456 \
  -m "Message" \
  --mode dct \
  --color grayscale
```

**With RSA key:**
```bash
stegasoo encode \
  -r reference.jpg \
  -c carrier.png \
  -p "apple forest thunder" \
  -k mykey.pem \
  --key-password "secretpassword" \
  -m "Encrypted with RSA"
```

**Both PIN and RSA (maximum security):**
```bash
stegasoo encode \
  -r ref.jpg \
  -c carrier.png \
  -p "word1 word2 word3" \
  --pin 123456 \
  -k mykey.pem \
  --key-password "pass" \
  -m "Double-locked message"
```

**Custom output filename:**
```bash
stegasoo encode \
  -r ref.jpg \
  -c carrier.png \
  -p "phrase words here" \
  --pin 123456 \
  -m "Message" \
  -o holiday_photo.png
```

**Encoding with specific date (for testing):**
```bash
stegasoo encode \
  -r ref.jpg \
  -c carrier.png \
  -p "monday phrase here" \
  --pin 123456 \
  -m "Message" \
  --date 2025-12-29
```

**Long message from file:**
```bash
stegasoo encode \
  -r ref.jpg \
  -c large_image.png \
  -p "phrase" \
  --pin 123456 \
  -f secret_document.txt \
  -o output.png
```

**Quiet mode for scripting:**
```bash
stegasoo encode -r ref.jpg -c carrier.png -p "phrase" --pin 123456 -m "msg" -q -o out.png
# No output, just creates the file
```

---

### Decode Command

Decode a secret message from a stego image. **Automatically detects LSB vs DCT mode.**

#### Synopsis

```bash
stegasoo decode [OPTIONS]
```

#### Options

| Option | Short | Type | Required | Description |
|--------|-------|------|----------|-------------|
| `--ref` | `-r` | path | ✓ | Reference photo (same as encoding) |
| `--stego` | `-s` | path | ✓ | Stego image to decode |
| `--phrase` | `-p` | string | ✓ | Passphrase for the encoding day |
| `--pin` | | string | * | Static PIN |
| `--key` | `-k` | path | * | RSA key file |
| `--key-password` | | string | | Password for RSA key |
| `--output` | `-o` | path | | Save message to file |
| `--quiet` | `-q` | flag | | Output only the message |

\* Must provide the same security factors used during encoding.

#### Examples

**Basic decoding with PIN:**
```bash
stegasoo decode \
  --ref photos/vacation.jpg \
  --stego received_image.png \
  --phrase "correct horse battery" \
  --pin 847293
```

Output:
```
✓ Decoded successfully!
  Mode detected: LSB

The package arrives Tuesday
```

**Decoding DCT image (auto-detected):**
```bash
stegasoo decode \
  --ref photos/vacation.jpg \
  --stego received_image.jpg \
  --phrase "correct horse battery" \
  --pin 847293
```

Output:
```
✓ Decoded successfully!
  Mode detected: DCT

The package arrives Tuesday
```

**With RSA key:**
```bash
stegasoo decode \
  -r reference.jpg \
  -s stego_image.png \
  -p "apple forest thunder" \
  -k mykey.pem \
  --key-password "secretpassword"
```

**Save decoded message to file:**
```bash
stegasoo decode \
  -r ref.jpg \
  -s stego.png \
  -p "phrase" \
  --pin 123456 \
  -o decoded_message.txt
```

Output:
```
✓ Decoded successfully!
  Saved to: decoded_message.txt
```

**Quiet mode (message only):**
```bash
stegasoo decode -r ref.jpg -s stego.png -p "phrase" --pin 123456 -q
```

Output:
```
The package arrives Tuesday
```

**Pipe to another command:**
```bash
stegasoo decode -r ref.jpg -s stego.png -p "phrase" --pin 123456 -q | gpg --decrypt
```

---

### Info Command

Display information about an image's capacity for both LSB and DCT modes.

#### Synopsis

```bash
stegasoo info IMAGE
```

#### Arguments

| Argument | Type | Description |
|----------|------|-------------|
| `IMAGE` | path | Path to image file |

#### Examples

**Check carrier image capacity:**
```bash
stegasoo info vacation_photo.png
```

Output:
```
Image: vacation_photo.png
  Dimensions:  1920 × 1080
  Pixels:      2,073,600
  Mode:        RGB
  Format:      PNG

Capacity:
  LSB Mode:    ~776,970 bytes (758 KB)
  DCT Mode:    ~64,800 bytes (63 KB)  [approximate]
  
  Note: DCT capacity varies based on image content
```

**Check stego image (shows encoding date and mode):**
```bash
stegasoo info stego_a1b2c3d4_20251227.png
```

Output:
```
Image: stego_a1b2c3d4_20251227.png
  Dimensions:  1920 × 1080
  Pixels:      2,073,600
  Mode:        RGB
  Format:      PNG

Stego Info:
  Embed date:  2025-12-27 (Saturday)
  Embed mode:  DCT (detected)

Capacity:
  LSB Mode:    ~776,970 bytes (758 KB)
  DCT Mode:    ~64,800 bytes (63 KB)  [approximate]
```

---

## Embedding Modes

Stegasoo v3.0+ supports two steganography algorithms.

### LSB Mode (Default)

**Least Significant Bit** embedding modifies pixel values directly.

```bash
stegasoo encode ... --mode lsb
# or just omit --mode (LSB is default)
```

| Aspect | Details |
|--------|---------|
| **Capacity** | ~3 bits/pixel (~770 KB for 1920×1080) |
| **Output** | PNG only (lossless required) |
| **Resilience** | ❌ Destroyed by JPEG compression |
| **Best For** | Maximum capacity, controlled channels |

### DCT Mode (Experimental)

**Discrete Cosine Transform** embedding hides data in frequency coefficients.

```bash
stegasoo encode ... --mode dct --format jpeg --color color
```

| Aspect | Details |
|--------|---------|
| **Capacity** | ~0.25 bits/pixel (~65 KB for 1920×1080) |
| **Output** | PNG or JPEG |
| **Resilience** | ✅ Survives JPEG compression |
| **Best For** | Social media, messaging apps |

> ⚠️ **Experimental**: DCT mode may have edge cases. Test with your workflow.

### DCT Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--format` | `png`, `jpeg` | `png` | Output image format |
| `--color` | `color`, `grayscale` | `color` | Color processing |

### Choosing the Right Mode

```
Will the image be recompressed?
(social media, messaging apps, etc.)
           │
    ┌──────┴──────┐
    ▼             ▼
   YES           NO
    │             │
    ▼             ▼
Use DCT       Use LSB
--mode dct    (default)
--format jpeg
```

### Capacity Comparison

| Mode | 1920×1080 Capacity |
|------|-------------------|
| LSB (PNG) | ~770 KB |
| DCT (PNG) | ~65 KB |
| DCT (JPEG) | ~30-50 KB |

---

## Security Factors

Stegasoo uses multiple authentication factors:

| Factor | Description | Entropy |
|--------|-------------|---------|
| Reference Photo | A photo both parties have | ~80-256 bits |
| Day Phrase | Changes daily (e.g., 3 BIP-39 words) | ~33 bits (3 words) |
| Static PIN | Same every day (6-9 digits) | ~20 bits (6 digits) |
| RSA Key | Shared key file | ~128 bits effective |

### Minimum Requirements

- At least one of PIN or RSA key must be provided
- Reference photo is always required
- Day phrase is always required

### Security Configurations

| Configuration | Entropy (excl. photo) | Use Case |
|--------------|----------------------|----------|
| 3-word phrase + 6-digit PIN | ~53 bits | Casual use |
| 6-word phrase + 9-digit PIN | ~96 bits | Standard security |
| 3-word phrase + RSA 2048 | ~161 bits | File-based auth |
| 6-word phrase + PIN + RSA | ~224 bits | Maximum security |

---

## Workflow Examples

### Daily Secure Communication

**Setup (once):**
```bash
# Both parties generate same credentials
stegasoo generate --pin --words 3

# Or share RSA key securely
stegasoo generate --rsa -o shared_key.pem -p "agreedpassword"
# Securely transfer shared_key.pem to recipient
```

**Sender (daily - private channel):**
```bash
# For email, file transfer, etc. (no recompression)
stegasoo encode \
  -r our_shared_photo.jpg \
  -c random_meme.png \
  -p "$TODAY_PHRASE" \
  --pin 847293 \
  -m "Meeting moved to 3pm"
```

**Sender (daily - social media):**
```bash
# For Instagram, Twitter, WhatsApp, etc.
stegasoo encode \
  -r our_shared_photo.jpg \
  -c random_meme.png \
  -p "$TODAY_PHRASE" \
  --pin 847293 \
  -m "Meeting moved to 3pm" \
  --mode dct \
  --format jpeg
```

**Recipient (daily):**
```bash
# Works for both LSB and DCT (auto-detected)
stegasoo decode \
  -r our_shared_photo.jpg \
  -s received_image.png \
  -p "monday phrase words" \
  --pin 847293
```

### Batch Processing

**Encode multiple messages (LSB):**
```bash
#!/bin/bash
PHRASE="apple forest thunder"
PIN="123456"
REF="reference.jpg"

for file in messages/*.txt; do
  name=$(basename "$file" .txt)
  stegasoo encode \
    -r "$REF" \
    -c "carriers/${name}.png" \
    -p "$PHRASE" \
    --pin "$PIN" \
    -f "$file" \
    -o "output/${name}_stego.png" \
    -q
  echo "Encoded: $name"
done
```

**Encode for social media (DCT):**
```bash
#!/bin/bash
for file in messages/*.txt; do
  name=$(basename "$file" .txt)
  stegasoo encode \
    -r "$REF" \
    -c "carriers/${name}.png" \
    -p "$PHRASE" \
    --pin "$PIN" \
    -f "$file" \
    --mode dct \
    --format jpeg \
    -o "output/${name}_social.jpg" \
    -q
  echo "Encoded for social: $name"
done
```

### Archive with Date Preservation

```bash
# Encode with specific date for archival
stegasoo encode \
  -r ref.jpg \
  -c carrier.png \
  -p "archive phrase words" \
  --pin 123456 \
  -m "Historical record" \
  --date 2025-01-15 \
  -o archive_2025-01-15.png
```

### Testing Mode Compatibility

```bash
# Encode with DCT
stegasoo encode \
  -r ref.jpg \
  -c carrier.png \
  -p "test phrase" \
  --pin 123456 \
  -m "Test message" \
  --mode dct \
  --format jpeg \
  -o test_dct.jpg

# Simulate social media recompression
convert test_dct.jpg -quality 85 test_recompressed.jpg

# Decode (should still work!)
stegasoo decode \
  -r ref.jpg \
  -s test_recompressed.jpg \
  -p "test phrase" \
  --pin 123456
```

---

## Piping & Scripting

### Stdin/Stdout Support

**Encode from pipe:**
```bash
cat secret.txt | stegasoo encode -r ref.jpg -c carrier.png -p "phrase" --pin 123456 -o out.png
```

**Decode to pipe:**
```bash
stegasoo decode -r ref.jpg -s stego.png -p "phrase" --pin 123456 -q | less
```

**Chain with encryption:**
```bash
# Encode GPG-encrypted content
gpg -e -r recipient@email.com secret.txt
cat secret.txt.gpg | base64 | stegasoo encode -r ref.jpg -c carrier.png -p "phrase" --pin 123456

# Decode and decrypt
stegasoo decode -r ref.jpg -s stego.png -p "phrase" --pin 123456 -q | base64 -d | gpg -d
```

### JSON Output for Scripts

```bash
# Get credentials as JSON
creds=$(stegasoo generate --json)

# Extract specific fields
pin=$(echo "$creds" | jq -r '.pin')
monday=$(echo "$creds" | jq -r '.phrases.Monday')
entropy=$(echo "$creds" | jq -r '.entropy.total')

echo "PIN: $pin"
echo "Monday phrase: $monday"
echo "Total entropy: $entropy bits"
```

### Error Handling in Scripts

```bash
#!/bin/bash
set -e

if ! stegasoo decode -r ref.jpg -s stego.png -p "phrase" --pin 123456 -q 2>/dev/null; then
  echo "Decryption failed - check credentials"
  exit 1
fi
```

### Mode Detection in Scripts

```bash
#!/bin/bash
# Get mode from verbose output
MODE=$(stegasoo decode -r ref.jpg -s stego.png -p "phrase" --pin 123456 2>&1 | grep "Mode detected" | awk '{print $3}')
echo "Image was encoded with: $MODE mode"
```

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Must provide --pin or --key" | No security factor given | Add `--pin` or `--key` option |
| "PIN must be 6-9 digits" | Invalid PIN format | Use numeric PIN, 6-9 chars |
| "PIN cannot start with zero" | Leading zero in PIN | Use PIN starting with 1-9 |
| "Carrier image too small" | Message exceeds capacity | Use larger carrier or LSB mode |
| "Message too long for DCT capacity" | DCT has less space | Shorten message or use LSB |
| "Decryption failed" | Wrong credentials | Verify phrase, PIN, ref photo |
| "Invalid or missing Stegasoo header" | Wrong mode or corruption | Check mode, try other credentials |
| "RSA key is password-protected" | Missing key password | Add `--key-password` option |
| "jpegio not available" | Missing library | Install: `pip install jpegio` |
| "Invalid --format for LSB mode" | JPEG with LSB | Use `--mode dct` for JPEG output |

### Troubleshooting Decryption Failures

1. **Check the encoding date:** The filename often contains the date (e.g., `_20251227`)
2. **Use correct phrase:** The phrase must match the day the message was encoded, not today
3. **Verify reference photo:** Must be the exact same file, not a resized copy
4. **Check stego image:** 
   - LSB: Ensure it wasn't resized, recompressed, or converted
   - DCT: More resilient, but heavy recompression may still destroy data
5. **Check embedding mode:** The decoder auto-detects, but if issues persist, verify the original was encoded with the expected mode

### DCT-Specific Issues

| Issue | Cause | Solution |
|-------|-------|----------|
| "Invalid or missing Stegasoo header" after social media | Heavy recompression | Try higher quality original or shorter message |
| JPEG output not working | jpegio not installed | `pip install jpegio` |
| Lower capacity than expected | Normal for DCT | DCT has ~10% of LSB capacity |

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error |
| 2 | Invalid arguments/options |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `PYTHONPATH` | Include `src/` for development |

---

## Dependencies

### Core Dependencies

- `pillow` - Image processing
- `cryptography` - Encryption
- `argon2-cffi` - Key derivation
- `click` - CLI framework

### DCT Mode Dependencies

- `scipy` - DCT transformations
- `jpegio` - Native JPEG coefficient access (recommended)

Install DCT dependencies:
```bash
pip install scipy jpegio
```

Check availability:
```bash
python -c "import scipy; print('scipy:', scipy.__version__)"
python -c "import jpegio; print('jpegio: available')"
```

---

## See Also

- [API Documentation](API.md) - REST API reference
- [Web UI Documentation](WEB_UI.md) - Browser interface guide
- [README](README.md) - Project overview and security model
