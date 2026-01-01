# Stegasoo CLI Documentation (v3.2.0)

Complete command-line interface reference for Stegasoo steganography operations.

## Table of Contents

- [Installation](#installation)
- [What's New in v3.2.0](#whats-new-in-v320)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [generate](#generate-command)
  - [encode](#encode-command)
  - [decode](#decode-command)
  - [verify](#verify-command)
  - [info](#info-command)
  - [compare](#compare-command)
  - [modes](#modes-command)
  - [strip-metadata](#strip-metadata-command)
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
python -c "from stegasoo import has_dct_support; print('DCT:', 'available' if has_dct_support() else 'requires scipy')"
```

---

## What's New in v3.2.0

Version 3.2.0 brings major simplifications to the authentication system:

| Change | Before (v3.1) | After (v3.2.0) |
|--------|---------------|----------------|
| Passphrase | Daily rotation (7 phrases) | Single passphrase |
| Date parameter | Required for encode/decode | Removed entirely |
| Default words | 3 words per phrase | 4 words |
| Terminology | `day_phrase`, `phrase` | `passphrase` |

**Key benefits:**
- ✅ No need to remember which day a message was encoded
- ✅ True asynchronous communication
- ✅ Simpler credential management
- ✅ Stronger default security (4 words = ~44 bits entropy)

**Migration:** Old stego images encoded with v3.1.x cannot be decoded with v3.2.0 due to the removed date-based key derivation. Keep v3.1.x installed if you need to access old images.

---

## Quick Start

```bash
# 1. Generate credentials (do this once, memorize results)
stegasoo generate

# 2. Encode a message (LSB mode - default)
stegasoo encode \
  --ref secret_photo.jpg \
  --carrier meme.png \
  --passphrase "apple forest thunder mountain" \
  --pin 123456 \
  --message "Meet at midnight"

# 3. Encode for social media (DCT mode)
stegasoo encode \
  --ref secret_photo.jpg \
  --carrier meme.png \
  --passphrase "apple forest thunder mountain" \
  --pin 123456 \
  --message "Meet at midnight" \
  --mode dct \
  --dct-format jpeg

# 4. Decode a message (auto-detects mode)
stegasoo decode \
  --ref secret_photo.jpg \
  --stego stego_abc123.png \
  --passphrase "apple forest thunder mountain" \
  --pin 123456
```

---

## Commands

### Generate Command

Generate credentials for encoding/decoding operations. Creates a passphrase and optionally a PIN and/or RSA key.

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
| `--words` | | 3-12 | 4 | Words in passphrase (v3.2.0: default increased to 4) |
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
============================================================
  STEGASOO CREDENTIALS (v3.2.0)
============================================================

⚠️  MEMORIZE THESE AND CLOSE THIS WINDOW
    Do not screenshot or save to file!

─── STATIC PIN ───
    847293

─── PASSPHRASE ───
    abandon ability able about

─── SECURITY ───
    Passphrase entropy: 44 bits (4 words)
    PIN entropy:        19 bits
    Combined:           63 bits
    + photo entropy:    80-256 bits

✓ v3.2.0: Use this passphrase anytime - no date needed!
```

**Generate with more words for higher security:**
```bash
stegasoo generate --words 6
```

**Generate with RSA key:**
```bash
stegasoo generate --rsa --rsa-bits 4096
```

**Save RSA key to encrypted file:**
```bash
stegasoo generate --rsa -o mykey.pem -p "mysecretpassword"
```

**Maximum security (longer passphrase + both factors):**
```bash
stegasoo generate --pin --rsa --words 6 --pin-length 9
```

**JSON output for scripting:**
```bash
stegasoo generate --json
```

Output:
```json
{
  "passphrase": "abandon ability able about",
  "pin": "847293",
  "rsa_key": null,
  "entropy": {
    "passphrase": 44,
    "pin": 19,
    "rsa": 0,
    "total": 63
  }
}
```

**Extract passphrase from JSON:**
```bash
stegasoo generate --json | jq -r '.passphrase'
```

**RSA only (no PIN):**
```bash
stegasoo generate --no-pin --rsa -o key.pem -p "password123"
```

---

### Encode Command

Encode a secret message or file into an image using steganography.

#### Synopsis

```bash
stegasoo encode [OPTIONS]
```

#### Options

| Option | Short | Type | Required | Default | Description |
|--------|-------|------|----------|---------|-------------|
| `--ref` | `-r` | path | ✓ | | Reference photo (shared secret) |
| `--carrier` | `-c` | path | ✓ | | Carrier image to hide message in |
| `--passphrase` | `-p` | string | ✓ | | Passphrase (v3.2.0: single, no date needed) |
| `--message` | `-m` | string | | | Message to encode |
| `--message-file` | `-f` | path | | | Read message from file |
| `--embed-file` | `-e` | path | | | Embed a binary file |
| `--pin` | | string | * | | Static PIN (6-9 digits) |
| `--key` | `-k` | path | * | | RSA key file |
| `--key-qr` | | path | * | | RSA key from QR code image |
| `--key-password` | | string | | | Password for RSA key |
| `--output` | `-o` | path | | | Output filename |
| `--mode` | | choice | | `lsb` | Embedding mode: `lsb` or `dct` |
| `--dct-format` | | choice | | `png` | DCT output: `png` or `jpeg` |
| `--dct-color` | | choice | | `grayscale` | DCT color: `grayscale` or `color` |
| `--quiet` | `-q` | flag | | | Suppress output |

\* At least one of `--pin`, `--key`, or `--key-qr` is required.

#### Message Input Methods

1. **Command line argument:**
   ```bash
   stegasoo encode -r ref.jpg -c carrier.png -p "four word passphrase" --pin 123456 -m "Secret message"
   ```

2. **From file:**
   ```bash
   stegasoo encode -r ref.jpg -c carrier.png -p "four word passphrase" --pin 123456 -f message.txt
   ```

3. **From stdin (pipe):**
   ```bash
   echo "Secret message" | stegasoo encode -r ref.jpg -c carrier.png -p "four word passphrase" --pin 123456
   ```

4. **Embed binary file:**
   ```bash
   stegasoo encode -r ref.jpg -c carrier.png -p "four word passphrase" --pin 123456 -e secret.pdf
   ```

#### Examples

**Basic encoding with PIN (LSB mode - default):**
```bash
stegasoo encode \
  --ref photos/vacation.jpg \
  --carrier memes/funny_cat.png \
  --passphrase "correct horse battery staple" \
  --pin 847293 \
  --message "The package arrives Tuesday"
```

Output:
```
Mode: LSB (12.4% capacity)
✓ Encoded successfully!
  Output: a1b2c3d4.png
  Size: 245,832 bytes
  Capacity used: 12.4%
```

**DCT mode for social media (JPEG output):**
```bash
stegasoo encode \
  --ref photos/vacation.jpg \
  --carrier memes/funny_cat.png \
  --passphrase "correct horse battery staple" \
  --pin 847293 \
  --message "The package arrives Tuesday" \
  --mode dct \
  --dct-format jpeg
```

Output:
```
Mode: DCT (grayscale, JPEG) (45.2% capacity)
✓ Encoded successfully!
  Output: a1b2c3d4.jpg
  Size: 89,432 bytes
  Capacity used: 45.2%
  DCT output: JPEG (grayscale)
```

**DCT mode with color preservation:**
```bash
stegasoo encode \
  -r ref.jpg \
  -c carrier.png \
  -p "phrase words here now" \
  --pin 123456 \
  -m "Message" \
  --mode dct \
  --dct-color color \
  --dct-format png
```

**With RSA key:**
```bash
stegasoo encode \
  -r reference.jpg \
  -c carrier.png \
  -p "apple forest thunder mountain" \
  -k mykey.pem \
  --key-password "secretpassword" \
  -m "Encrypted with RSA"
```

**Both PIN and RSA (maximum security):**
```bash
stegasoo encode \
  -r ref.jpg \
  -c carrier.png \
  -p "word1 word2 word3 word4" \
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
  -p "phrase words here now" \
  --pin 123456 \
  -m "Message" \
  -o holiday_photo.png
```

**Embed a binary file:**
```bash
stegasoo encode \
  -r ref.jpg \
  -c large_image.png \
  -p "secure phrase words here" \
  --pin 123456 \
  -e secret_document.pdf \
  -o output.png
```

**Quiet mode for scripting:**
```bash
stegasoo encode -r ref.jpg -c carrier.png -p "phrase" --pin 123456 -m "msg" -q -o out.png
# No output, just creates the file
```

---

### Decode Command

Decode a secret message or file from a stego image. **Automatically detects LSB vs DCT mode.**

#### Synopsis

```bash
stegasoo decode [OPTIONS]
```

#### Options

| Option | Short | Type | Required | Description |
|--------|-------|------|----------|-------------|
| `--ref` | `-r` | path | ✓ | Reference photo (same as encoding) |
| `--stego` | `-s` | path | ✓ | Stego image to decode |
| `--passphrase` | `-p` | string | ✓ | Passphrase used for encoding |
| `--pin` | | string | * | Static PIN |
| `--key` | `-k` | path | * | RSA key file |
| `--key-qr` | | path | * | RSA key from QR code image |
| `--key-password` | | string | | Password for RSA key |
| `--output` | `-o` | path | | Save message to file |
| `--mode` | | choice | | Extraction mode: `auto`, `lsb`, or `dct` |
| `--quiet` | `-q` | flag | | Output only the message |
| `--force` | | flag | | Overwrite existing output file |

\* Must provide the same security factors used during encoding.

#### Examples

**Basic decoding with PIN:**
```bash
stegasoo decode \
  --ref photos/vacation.jpg \
  --stego received_image.png \
  --passphrase "correct horse battery staple" \
  --pin 847293
```

Output:
```
✓ Decoded successfully!

The package arrives Tuesday
```

**Decoding DCT image (auto-detected):**
```bash
stegasoo decode \
  --ref photos/vacation.jpg \
  --stego received_image.jpg \
  --passphrase "correct horse battery staple" \
  --pin 847293
```

**With RSA key:**
```bash
stegasoo decode \
  -r reference.jpg \
  -s stego_image.png \
  -p "apple forest thunder mountain" \
  -k mykey.pem \
  --key-password "secretpassword"
```

**Save decoded message to file:**
```bash
stegasoo decode \
  -r ref.jpg \
  -s stego.png \
  -p "passphrase words here now" \
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

**Force specific extraction mode:**
```bash
stegasoo decode -r ref.jpg -s stego.png -p "phrase" --pin 123456 --mode dct
```

---

### Verify Command

Verify that a stego image can be decoded without extracting the actual message content.

#### Synopsis

```bash
stegasoo verify [OPTIONS]
```

#### Options

| Option | Short | Type | Required | Description |
|--------|-------|------|----------|-------------|
| `--ref` | `-r` | path | ✓ | Reference photo |
| `--stego` | `-s` | path | ✓ | Stego image to verify |
| `--passphrase` | `-p` | string | ✓ | Passphrase |
| `--pin` | | string | * | Static PIN |
| `--key` | `-k` | path | * | RSA key file |
| `--key-qr` | | path | * | RSA key from QR code |
| `--key-password` | | string | | Password for RSA key |
| `--mode` | | choice | | Extraction mode: `auto`, `lsb`, or `dct` |
| `--json` | | flag | | Output as JSON |

#### Examples

**Basic verification:**
```bash
stegasoo verify -r photo.jpg -s stego.png -p "my passphrase here" --pin 123456
```

Output:
```
✓ Valid stego image
  Payload:  text (142 bytes)
  Size:     142 bytes
```

**JSON output:**
```bash
stegasoo verify -r photo.jpg -s stego.png -p "words here" --pin 123456 --json
```

Output:
```json
{
  "valid": true,
  "stego_file": "stego.png",
  "payload_type": "text",
  "payload_size": 142
}
```

**Failed verification:**
```bash
stegasoo verify -r photo.jpg -s stego.png -p "wrong passphrase" --pin 123456
```

Output:
```
✗ Verification failed
  Error: Decryption failed: Invalid authentication tag
```

---

### Info Command

Display information about an image's capacity for both LSB and DCT modes.

#### Synopsis

```bash
stegasoo info IMAGE [OPTIONS]
```

#### Options

| Option | Type | Description |
|--------|------|-------------|
| `--json` | flag | Output as JSON |

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
    LSB mode:  ~776,970 bytes (758.8 KB)
    DCT mode:  ~64,800 bytes (63.3 KB) ✓
    DCT ratio: 8.3% of LSB
    DCT options: grayscale/color, png/jpeg
```

**JSON output:**
```bash
stegasoo info photo.png --json
```

Output:
```json
{
  "file": "photo.png",
  "width": 1920,
  "height": 1080,
  "pixels": 2073600,
  "mode": "RGB",
  "format": "PNG",
  "capacity": {
    "lsb": {
      "bytes": 776970,
      "kb": 758.8
    },
    "dct": {
      "bytes": 64800,
      "kb": 63.3,
      "available": true,
      "ratio_vs_lsb": 8.3,
      "output_formats": ["png", "jpeg"],
      "color_modes": ["grayscale", "color"]
    }
  }
}
```

---

### Compare Command

Compare LSB and DCT embedding modes for an image with recommendations.

#### Synopsis

```bash
stegasoo compare IMAGE [OPTIONS]
```

#### Options

| Option | Short | Type | Description |
|--------|-------|------|-------------|
| `--payload-size` | `-s` | int | Check if specific payload size fits |
| `--json` | | flag | Output as JSON |

#### Examples

**Basic comparison:**
```bash
stegasoo compare carrier.png
```

Output:
```
=== Mode Comparison: carrier.png ===
  Dimensions: 1920 × 1080

  ┌─── LSB Mode ───
  │ Capacity:  776,970 bytes (758.8 KB)
  │ Output:    PNG
  │ Status:    ✓ Available
  │
  ├─── DCT Mode ───
  │ Capacity:  64,800 bytes (63.3 KB)
  │ Ratio:     8.3% of LSB capacity
  │ Status:    ✓ Available
  │ Formats:   PNG (lossless), JPEG (smaller)
  │ Colors:    Grayscale (default), Color
  │
  └─── Recommendation ───
    LSB for larger payloads, DCT for better stealth
    DCT supports color output with --dct-color color
```

**Check if payload fits:**
```bash
stegasoo compare carrier.png --payload-size 50000
```

Output:
```
=== Mode Comparison: carrier.png ===
  Dimensions: 1920 × 1080

  ┌─── LSB Mode ───
  │ Capacity:  776,970 bytes (758.8 KB)
  │ Output:    PNG
  │ Status:    ✓ Available
  │
  ├─── DCT Mode ───
  │ Capacity:  64,800 bytes (63.3 KB)
  │ Ratio:     8.3% of LSB capacity
  │ Status:    ✓ Available
  │ Formats:   PNG (lossless), JPEG (smaller)
  │ Colors:    Grayscale (default), Color
  │
  ├─── Payload Check ───
  │ Size:      50,000 bytes
  │ LSB mode:  ✓ Fits
  │ DCT mode:  ✓ Fits
  │
  └─── Recommendation ───
    DCT mode for better stealth (payload fits both modes)
    Use --dct-color color to preserve original colors
```

---

### Modes Command

Show available embedding modes and their status.

#### Synopsis

```bash
stegasoo modes
```

#### Example Output

```
=== Stegasoo Embedding Modes (v3.2.0) ===

  LSB Mode (Spatial LSB)
    Status:      ✓ Always available
    Output:      PNG/BMP (full color)
    Capacity:    ~375 KB per megapixel
    Use case:    Larger payloads, color preservation
    CLI flag:    --mode lsb (default)

  DCT Mode (Frequency Domain)
    Status:      ✓ Available
    Capacity:    ~75 KB per megapixel (~20% of LSB)
    Use case:    Better stealth, frequency domain hiding
    CLI flag:    --mode dct

  DCT Options
    Output format:
      --dct-format png     Lossless, larger file (default)
      --dct-format jpeg    Lossy, smaller, more natural

    Color mode:
      --dct-color grayscale   Traditional DCT (default)
      --dct-color color       Preserves original colors

  v3.2.0 Changes:
    ✓ No date parameters needed
    ✓ Single passphrase (no daily rotation)
    ✓ Default passphrase increased to 4 words
    ✓ True asynchronous communications

  Examples:
    # Traditional DCT (grayscale PNG)
    stegasoo encode ... --mode dct

    # Color-preserving DCT with JPEG output
    stegasoo encode ... --mode dct --dct-color color --dct-format jpeg

    # Compare modes for an image
    stegasoo compare carrier.png
```

---

### Strip-Metadata Command

Remove all metadata (EXIF, GPS, etc.) from an image.

#### Synopsis

```bash
stegasoo strip-metadata IMAGE [OPTIONS]
```

#### Options

| Option | Short | Type | Default | Description |
|--------|-------|------|---------|-------------|
| `--output` | `-o` | path | | Output file (default: overwrites as PNG) |
| `--format` | `-f` | choice | PNG | Output format: `PNG` or `BMP` |
| `--quiet` | `-q` | flag | | Suppress output |

#### Examples

```bash
# Strip metadata, save as PNG
stegasoo strip-metadata photo.jpg -o clean.png

# Overwrite in place (converts to PNG)
stegasoo strip-metadata photo.jpg
```

Output:
```
✓ Metadata stripped
  Input:  photo.jpg (2,456,789 bytes)
  Output: clean.png (1,234,567 bytes)
```

---

## Embedding Modes

Stegasoo supports two steganography algorithms.

### LSB Mode (Default)

**Least Significant Bit** embedding modifies pixel values directly.

```bash
stegasoo encode ... --mode lsb
# or just omit --mode (LSB is default)
```

| Aspect | Details |
|--------|---------|
| **Capacity** | ~3 bits/pixel (~375 KB for 1920×1080) |
| **Output** | PNG only (lossless required) |
| **Resilience** | ❌ Destroyed by JPEG compression |
| **Best For** | Maximum capacity, controlled channels |

### DCT Mode

**Discrete Cosine Transform** embedding hides data in frequency coefficients.

```bash
stegasoo encode ... --mode dct --dct-format jpeg --dct-color color
```

| Aspect | Details |
|--------|---------|
| **Capacity** | ~0.25 bits/pixel (~65 KB for 1920×1080) |
| **Output** | PNG or JPEG |
| **Resilience** | ✅ Better resistance to analysis |
| **Best For** | Social media, stealth requirements |

### DCT Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `--dct-format` | `png`, `jpeg` | `png` | Output image format |
| `--dct-color` | `grayscale`, `color` | `grayscale` | Color processing |

### Choosing the Right Mode

```
Need maximum capacity?
           │
    ┌──────┴──────┐
    ▼             ▼
   YES           NO
    │             │
    ▼             ▼
Use LSB       Need stealth?
(default)          │
           ┌──────┴──────┐
           ▼             ▼
          YES           NO
           │             │
           ▼             ▼
        Use DCT       Use LSB
        --mode dct    (default)
```

### Capacity Comparison

| Mode | 1920×1080 Capacity |
|------|-------------------|
| LSB (PNG) | ~375 KB |
| DCT (PNG) | ~65 KB |
| DCT (JPEG) | ~50 KB |

---

## Security Factors

Stegasoo uses multiple authentication factors:

| Factor | Description | Entropy |
|--------|-------------|---------|
| Reference Photo | A photo both parties have | ~80-256 bits |
| Passphrase | BIP-39 word phrase | ~44 bits (4 words) |
| Static PIN | Numeric PIN (6-9 digits) | ~20 bits (6 digits) |
| RSA Key | Shared key file | ~128 bits effective |

### Minimum Requirements

- At least one of PIN or RSA key must be provided
- Reference photo is always required
- Passphrase is always required

### Security Configurations

| Configuration | Entropy (excl. photo) | Use Case |
|--------------|----------------------|----------|
| 4-word passphrase + 6-digit PIN | ~63 bits | Standard use |
| 6-word passphrase + 6-digit PIN | ~85 bits | Enhanced security |
| 4-word passphrase + RSA 2048 | ~172 bits | File-based auth |
| 6-word passphrase + PIN + RSA | ~213 bits | Maximum security |

---

## Workflow Examples

### Basic Secure Communication

**Setup (once):**
```bash
# Both parties generate credentials
stegasoo generate

# Or share RSA key securely
stegasoo generate --rsa -o shared_key.pem -p "agreedpassword"
# Securely transfer shared_key.pem to recipient
```

**Sender:**
```bash
# For email, file transfer, etc. (no recompression)
stegasoo encode \
  -r our_shared_photo.jpg \
  -c random_meme.png \
  -p "our shared passphrase here" \
  --pin 847293 \
  -m "Meeting moved to 3pm"
```

**Sender (social media):**
```bash
# For platforms that may recompress
stegasoo encode \
  -r our_shared_photo.jpg \
  -c random_meme.png \
  -p "our shared passphrase here" \
  --pin 847293 \
  -m "Meeting moved to 3pm" \
  --mode dct \
  --dct-format jpeg
```

**Recipient:**
```bash
# Works for both LSB and DCT (auto-detected)
stegasoo decode \
  -r our_shared_photo.jpg \
  -s received_image.png \
  -p "our shared passphrase here" \
  --pin 847293
```

### Batch Processing

**Encode multiple messages:**
```bash
#!/bin/bash
PASSPHRASE="apple forest thunder mountain"
PIN="123456"
REF="reference.jpg"

for file in messages/*.txt; do
  name=$(basename "$file" .txt)
  stegasoo encode \
    -r "$REF" \
    -c "carriers/${name}.png" \
    -p "$PASSPHRASE" \
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
    -p "$PASSPHRASE" \
    --pin "$PIN" \
    -f "$file" \
    --mode dct \
    --dct-format jpeg \
    -o "output/${name}_social.jpg" \
    -q
  echo "Encoded for social: $name"
done
```

---

## Piping & Scripting

### Stdin/Stdout Support

**Encode from pipe:**
```bash
cat secret.txt | stegasoo encode -r ref.jpg -c carrier.png -p "phrase words" --pin 123456 -o out.png
```

**Decode to pipe:**
```bash
stegasoo decode -r ref.jpg -s stego.png -p "phrase words" --pin 123456 -q | less
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
passphrase=$(echo "$creds" | jq -r '.passphrase')
pin=$(echo "$creds" | jq -r '.pin')
entropy=$(echo "$creds" | jq -r '.entropy.total')

echo "Passphrase: $passphrase"
echo "PIN: $pin"
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

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Must provide --pin or --key" | No security factor given | Add `--pin` or `--key` option |
| "PIN must be 6-9 digits" | Invalid PIN format | Use numeric PIN, 6-9 chars |
| "Payload too large for LSB mode" | Message exceeds capacity | Use larger carrier or shorter message |
| "Payload too large for DCT mode" | DCT has less space | Use LSB mode or shorter message |
| "Decryption failed" | Wrong credentials | Verify passphrase, PIN, ref photo |
| "DCT mode requires scipy" | Missing library | Install: `pip install scipy` |

### Troubleshooting Decryption Failures

1. **Check passphrase:** Must be exact match (case-sensitive)
2. **Verify reference photo:** Must be the exact same file, not a resized copy
3. **Check stego image:** 
   - LSB: Ensure it wasn't resized, recompressed, or converted
   - DCT: More resilient but not immune to heavy processing
4. **Verify PIN/key:** Must match exactly what was used for encoding

### v3.2.0 Migration Note

If you're trying to decode images created with v3.1.x:
- v3.2.0 **cannot** decode v3.1.x images (date-based key derivation removed)
- Keep v3.1.x installed to access old images
- Re-encode old messages with v3.2.0 for forward compatibility

---

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | General error / decryption failed |
| 2 | Invalid arguments/options |

---

## Environment Variables

| Variable | Description |
|----------|-------------|
| `PYTHONPATH` | Include `src/` for development |
| `STEGASOO_DEBUG` | Enable debug output (set to `1`) |

---

## Dependencies

### Core Dependencies

- `pillow` - Image processing
- `cryptography` - Encryption
- `argon2-cffi` - Key derivation
- `click` - CLI framework

### DCT Mode Dependencies

- `scipy` - DCT transformations

Install DCT dependencies:
```bash
pip install scipy
```

Check availability:
```bash
stegasoo modes
# or
python -c "from stegasoo import has_dct_support; print('DCT:', has_dct_support())"
```

---

## See Also

- [API Documentation](API.md) - Python API reference
- [Web UI Documentation](WEB_UI.md) - Browser interface guide
- [README](../README.md) - Project overview and security model
