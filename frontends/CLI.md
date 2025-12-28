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

# With all extras
pip install stegasoo[all]
```

### From Source

```bash
git clone https://github.com/example/stegasoo.git
cd stegasoo
pip install -e ".[cli]"
```

### Verify Installation

```bash
stegasoo --version
stegasoo --help
```

---

## Quick Start

```bash
# 1. Generate credentials (do this once, memorize results)
stegasoo generate --pin --words 3

# 2. Encode a message
stegasoo encode \
  --ref secret_photo.jpg \
  --carrier meme.png \
  --phrase "apple forest thunder" \
  --pin 123456 \
  --message "Meet at midnight"

# 3. Decode a message
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
════════════════════════════════════════════════════════════
  STEGASOO CREDENTIALS
════════════════════════════════════════════════════════════

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

| Option | Short | Type | Required | Description |
|--------|-------|------|----------|-------------|
| `--ref` | `-r` | path | ✓ | Reference photo (shared secret) |
| `--carrier` | `-c` | path | ✓ | Carrier image to hide message in |
| `--phrase` | `-p` | string | ✓ | Today's passphrase |
| `--message` | `-m` | string | | Message to encode |
| `--message-file` | `-f` | path | | Read message from file |
| `--pin` | | string | * | Static PIN (6-9 digits) |
| `--key` | `-k` | path | * | RSA key file |
| `--key-password` | | string | | Password for RSA key |
| `--output` | `-o` | path | | Output filename |
| `--date` | | YYYY-MM-DD | | Date override |
| `--quiet` | `-q` | flag | | Suppress output |

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

**Basic encoding with PIN:**
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
  Capacity used: 12.4%
  Date: 2025-12-27
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

Decode a secret message from a stego image.

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

Display information about an image's capacity and embedded date.

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
  Capacity:    ~776,970 bytes (758 KB)
```

**Check stego image (shows encoding date):**
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
  Capacity:    ~776,970 bytes (758 KB)
  Embed date:  2025-12-27 (Saturday)
```

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

**Sender (daily):**
```bash
# Get today's phrase from your memorized list
TODAY_PHRASE="monday phrase words"

# Encode message
stegasoo encode \
  -r our_shared_photo.jpg \
  -c random_meme.png \
  -p "$TODAY_PHRASE" \
  --pin 847293 \
  -m "Meeting moved to 3pm"

# Share output image via normal channels (email, chat, etc.)
```

**Recipient (daily):**
```bash
# Use the phrase for the day the message was SENT
stegasoo decode \
  -r our_shared_photo.jpg \
  -s received_image.png \
  -p "monday phrase words" \
  --pin 847293
```

### Batch Processing

**Encode multiple messages:**
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

---

## Error Handling

### Common Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Must provide --pin or --key" | No security factor given | Add `--pin` or `--key` option |
| "PIN must be 6-9 digits" | Invalid PIN format | Use numeric PIN, 6-9 chars |
| "PIN cannot start with zero" | Leading zero in PIN | Use PIN starting with 1-9 |
| "Carrier image too small" | Message exceeds capacity | Use larger carrier image |
| "Decryption failed" | Wrong credentials | Verify phrase, PIN, ref photo |
| "RSA key is password-protected" | Missing key password | Add `--key-password` option |

### Troubleshooting Decryption Failures

1. **Check the encoding date:** The filename often contains the date (e.g., `_20251227`)
2. **Use correct phrase:** The phrase must match the day the message was encoded, not today
3. **Verify reference photo:** Must be the exact same file, not a resized copy
4. **Check stego image:** Ensure it wasn't resized, recompressed, or converted

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

## See Also

- [API Documentation](API.md) - REST API reference
- [Web UI Documentation](WEB_UI.md) - Browser interface guide
- [README](README.md) - Project overview and security model
