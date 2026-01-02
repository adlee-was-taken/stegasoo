# Stegasoo CLI Documentation (v4.0.1)

Complete command-line interface reference for Stegasoo steganography operations.

## Table of Contents

- [Installation](#installation)
- [What's New in v4.0.0](#whats-new-in-v400)
- [Quick Start](#quick-start)
- [Commands](#commands)
  - [generate](#generate-command)
  - [encode](#encode-command)
  - [decode](#decode-command)
  - [verify](#verify-command)
  - [channel](#channel-command)
  - [info](#info-command)
  - [compare](#compare-command)
  - [modes](#modes-command)
  - [strip-metadata](#strip-metadata-command)
- [Channel Keys](#channel-keys)
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

# Check channel key status
stegasoo channel show
```

---

## What's New in v4.0.0

Version 4.0.0 adds **channel key** support for deployment/group isolation:

| Feature | Description |
|---------|-------------|
| Channel keys | 256-bit keys that isolate message groups |
| Deployment isolation | Different deployments can't read each other's messages |
| CLI management | New `stegasoo channel` command group |
| Flexible override | Use server config, explicit key, or public mode |

**Key benefits:**
- ✅ Isolate messages between teams, deployments, or groups
- ✅ Same credentials can't decode messages from different channels
- ✅ Backward compatible (public mode = no channel key)
- ✅ Easy key distribution via environment variables or config files

**Breaking change:** v4.0.0 messages (with channel key) cannot be decoded by v3.x installations.

---

## Quick Start

```bash
# 1. Generate credentials (do this once, memorize results)
stegasoo generate

# 2. (Optional) Set up channel key for deployment isolation
stegasoo channel generate --save

# 3. Encode a message (uses configured channel key automatically)
stegasoo encode \
  --ref secret_photo.jpg \
  --carrier meme.png \
  --passphrase "apple forest thunder mountain" \
  --pin 123456 \
  --message "Meet at midnight"

# 4. Decode a message (uses same channel key)
stegasoo decode \
  --ref secret_photo.jpg \
  --stego stego_abc123.png \
  --passphrase "apple forest thunder mountain" \
  --pin 123456

# 5. Decode without channel key (public mode)
stegasoo decode \
  --ref secret_photo.jpg \
  --stego public_stego.png \
  --passphrase "words here now" \
  --pin 123456 \
  --no-channel
```

---

## Commands

### Generate Command

Generate credentials for encoding/decoding operations.

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
| `--words` | | 3-12 | 4 | Words in passphrase |
| `--output` | `-o` | path | | Save RSA key to file |
| `--password` | `-p` | string | | Password for RSA key file |
| `--json` | | flag | | Output as JSON |

#### Examples

```bash
# Basic generation with PIN (default)
stegasoo generate

# Generate with more words for higher security
stegasoo generate --words 6

# Generate with RSA key
stegasoo generate --rsa --rsa-bits 4096

# Save RSA key to encrypted file
stegasoo generate --rsa -o mykey.pem -p "mysecretpassword"
```

---

### Encode Command

Encode a secret message or file into an image.

#### Synopsis

```bash
stegasoo encode [OPTIONS]
```

#### Options

| Option | Short | Type | Required | Default | Description |
|--------|-------|------|----------|---------|-------------|
| `--ref` | `-r` | path | ✓ | | Reference photo |
| `--carrier` | `-c` | path | ✓ | | Carrier image |
| `--passphrase` | `-p` | string | ✓ | | Passphrase |
| `--message` | `-m` | string | | | Message to encode |
| `--message-file` | `-f` | path | | | Read message from file |
| `--embed-file` | `-e` | path | | | Embed a binary file |
| `--pin` | | string | * | | Static PIN (6-9 digits) |
| `--key` | `-k` | path | * | | RSA key file |
| `--key-qr` | | path | * | | RSA key from QR code |
| `--key-password` | | string | | | RSA key password |
| `--channel` | | string | | auto | Channel key (v4.0.0) |
| `--channel-file` | | path | | | Read channel key from file |
| `--no-channel` | | flag | | | Force public mode |
| `--output` | `-o` | path | | | Output filename |
| `--mode` | | choice | | `lsb` | Embedding mode |
| `--dct-format` | | choice | | `png` | DCT output format |
| `--dct-color` | | choice | | `grayscale` | DCT color mode |
| `--quiet` | `-q` | flag | | | Suppress output |

\* At least one of `--pin`, `--key`, or `--key-qr` is required.

#### Channel Key Options

| Option | Effect |
|--------|--------|
| *(none)* | Use server-configured key (auto mode) |
| `--channel KEY` | Use explicit channel key |
| `--channel auto` | Same as no option |
| `--channel-file F` | Read channel key from file |
| `--no-channel` | Force public mode (no isolation) |

#### Examples

```bash
# Basic encoding (uses server channel key if configured)
stegasoo encode \
  -r photo.jpg -c meme.png \
  -p "correct horse battery staple" \
  --pin 847293 \
  -m "The package arrives Tuesday"

# With explicit channel key
stegasoo encode \
  -r photo.jpg -c meme.png \
  -p "correct horse battery staple" \
  --pin 847293 \
  -m "Secret message" \
  --channel ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456

# Public mode (no channel isolation)
stegasoo encode \
  -r photo.jpg -c meme.png \
  -p "correct horse battery staple" \
  --pin 847293 \
  -m "Public message" \
  --no-channel

# DCT mode for social media
stegasoo encode \
  -r photo.jpg -c meme.png \
  -p "words here" --pin 847293 \
  -m "Secret" \
  --mode dct --dct-format jpeg
```

---

### Decode Command

Decode a secret message or file from a stego image.

#### Synopsis

```bash
stegasoo decode [OPTIONS]
```

#### Options

| Option | Short | Type | Required | Default | Description |
|--------|-------|------|----------|---------|-------------|
| `--ref` | `-r` | path | ✓ | | Reference photo |
| `--stego` | `-s` | path | ✓ | | Stego image |
| `--passphrase` | `-p` | string | ✓ | | Passphrase |
| `--pin` | | string | * | | Static PIN |
| `--key` | `-k` | path | * | | RSA key file |
| `--key-qr` | | path | * | | RSA key from QR code |
| `--key-password` | | string | | | RSA key password |
| `--channel` | | string | | auto | Channel key (v4.0.0) |
| `--channel-file` | | path | | | Read channel key from file |
| `--no-channel` | | flag | | | Force public mode |
| `--output` | `-o` | path | | | Save output to file |
| `--mode` | | choice | | `auto` | Extraction mode |
| `--quiet` | `-q` | flag | | | Minimal output |
| `--force` | | flag | | | Overwrite existing file |

#### Examples

```bash
# Basic decoding (uses server channel key)
stegasoo decode \
  -r photo.jpg -s stego.png \
  -p "correct horse battery staple" \
  --pin 847293

# With explicit channel key
stegasoo decode \
  -r photo.jpg -s stego.png \
  -p "words here" --pin 847293 \
  --channel ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456

# Decode public image (no channel key was used)
stegasoo decode \
  -r photo.jpg -s stego.png \
  -p "words here" --pin 847293 \
  --no-channel

# Save to file
stegasoo decode \
  -r photo.jpg -s stego.png \
  -p "words" --pin 123456 \
  -o decoded.txt
```

---

### Verify Command

Verify credentials without extracting the message.

#### Synopsis

```bash
stegasoo verify [OPTIONS]
```

#### Options

Same as `decode`, minus `--output` and `--force`. Adds `--json` for JSON output.

#### Examples

```bash
# Quick verification
stegasoo verify -r photo.jpg -s stego.png -p "phrase" --pin 123456

# With explicit channel key
stegasoo verify -r photo.jpg -s stego.png -p "phrase" --pin 123456 \
  --channel ABCD-1234-...

# JSON output
stegasoo verify -r photo.jpg -s stego.png -p "phrase" --pin 123456 --json
```

---

### Channel Command

Manage channel keys for deployment/group isolation.

#### Subcommands

| Subcommand | Description |
|------------|-------------|
| `generate` | Create a new channel key |
| `show` | Display current channel key status |
| `set` | Save a channel key to config |
| `clear` | Remove channel key from config |

#### channel generate

```bash
stegasoo channel generate [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--save` | `-s` | Save to user config (~/.stegasoo/channel.key) |
| `--save-project` | | Save to project config (./config/channel.key) |
| `--env` | `-e` | Output as environment variable export |
| `--quiet` | `-q` | Output only the key |

**Examples:**

```bash
# Just display a new key
stegasoo channel generate

# Save to user config
stegasoo channel generate --save

# Add to .env file
stegasoo channel generate --env >> .env

# For scripts
KEY=$(stegasoo channel generate -q)
```

#### channel show

```bash
stegasoo channel show [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--reveal` | `-r` | Show full key (not just fingerprint) |
| `--json` | | Output as JSON |

**Examples:**

```bash
# Show status (fingerprint only)
stegasoo channel show

# Reveal full key
stegasoo channel show --reveal

# JSON for scripts
stegasoo channel show --json
```

**Output:**

```
─── CHANNEL KEY STATUS ───

    Mode: PRIVATE
    Fingerprint: ABCD-••••-••••-••••-••••-••••-••••-3456
    Source: ~/.stegasoo/channel.key

    Messages require this channel key to decode.
```

#### channel set

```bash
stegasoo channel set [KEY] [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--file` | `-f` | Read key from file |
| `--project` | `-p` | Save to project config instead of user |

**Examples:**

```bash
# Set from command line
stegasoo channel set ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456

# Set from file
stegasoo channel set --file channel.key

# Set in project config
stegasoo channel set XXXX-... --project
```

#### channel clear

```bash
stegasoo channel clear [OPTIONS]
```

| Option | Short | Description |
|--------|-------|-------------|
| `--project` | `-p` | Clear project config |
| `--all` | | Clear both user and project configs |
| `--force` | `-f` | Skip confirmation |

**Examples:**

```bash
# Clear user config (with confirmation)
stegasoo channel clear

# Clear project config
stegasoo channel clear --project

# Clear all configs without confirmation
stegasoo channel clear --all --force
```

---

### Info Command

Show information about an image file.

```bash
stegasoo info IMAGE [OPTIONS]
```

---

### Compare Command

Compare embedding mode capacities for an image.

```bash
stegasoo compare IMAGE [OPTIONS]
```

---

### Modes Command

Show available embedding modes and their status.

```bash
stegasoo modes
```

Now also displays channel key status.

---

### Strip-Metadata Command

Remove all metadata from an image.

```bash
stegasoo strip-metadata IMAGE [OPTIONS]
```

---

## Channel Keys

Channel keys provide **deployment/group isolation** - messages encoded with a channel key can only be decoded by systems with the same key.

### Key Format

```
ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456
└──┘ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘
  8 groups of 4 alphanumeric characters (256 bits)
```

### Storage Locations

Channel keys are checked in this order:

| Priority | Location | Best For |
|----------|----------|----------|
| 1 | `STEGASOO_CHANNEL_KEY` env var | Docker, CI/CD |
| 2 | `./config/channel.key` | Project-specific |
| 3 | `~/.stegasoo/channel.key` | User default |

### Modes

| Mode | Description | CLI Option |
|------|-------------|------------|
| **Auto** | Use server-configured key | *(default)* |
| **Explicit** | Use specific key | `--channel KEY` |
| **Public** | No channel isolation | `--no-channel` |

### Fingerprints

For security, full keys aren't displayed by default. Instead, a fingerprint is shown:

```
Full key:    ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456
Fingerprint: ABCD-••••-••••-••••-••••-••••-••••-3456
```

### Use Cases

**Team isolation:**
```bash
# Team A
export STEGASOO_CHANNEL_KEY=AAAA-1111-...

# Team B  
export STEGASOO_CHANNEL_KEY=BBBB-2222-...

# Messages from Team A can only be decoded by Team A
```

**Development vs Production:**
```bash
# Development
./config/channel.key contains DEV-KEY-...

# Production
STEGASOO_CHANNEL_KEY=PROD-KEY-... in Docker

# Dev messages can't be decoded in production
```

**Public messages:**
```bash
# Anyone with credentials can decode
stegasoo encode ... --no-channel
stegasoo decode ... --no-channel
```

---

## Embedding Modes

### LSB Mode (Default)

```bash
stegasoo encode ... --mode lsb
```

| Aspect | Details |
|--------|---------|
| **Capacity** | ~375 KB for 1920×1080 |
| **Output** | PNG only |
| **Best For** | Maximum capacity |

### DCT Mode

```bash
stegasoo encode ... --mode dct --dct-format jpeg --dct-color color
```

| Aspect | Details |
|--------|---------|
| **Capacity** | ~65 KB for 1920×1080 |
| **Output** | PNG or JPEG |
| **Best For** | Social media, stealth |

---

## Security Factors

| Factor | Description | Entropy |
|--------|-------------|---------|
| Reference Photo | Shared image | ~80-256 bits |
| Passphrase | BIP-39 words | ~44 bits (4 words) |
| Static PIN | Numeric (6-9) | ~20 bits (6 digits) |
| RSA Key | Shared key file | ~128 bits |
| Channel Key (v4.0.0) | Deployment isolation | ~256 bits |

---

## Workflow Examples

### Team Setup with Channel Key

**Initial setup (team lead):**
```bash
# Generate team channel key
stegasoo channel generate -q > team_channel.key

# Distribute to team members securely
# (encrypted email, secure file share, etc.)
```

**Team member setup:**
```bash
# Save received key
stegasoo channel set --file team_channel.key

# Verify
stegasoo channel show
```

**Daily use:**
```bash
# Channel key is used automatically
stegasoo encode -r ref.jpg -c meme.png -p "phrase" --pin 123456 -m "Team message"
stegasoo decode -r ref.jpg -s stego.png -p "phrase" --pin 123456
```

### Docker Deployment

**docker-compose.yml:**
```yaml
x-common-env: &common-env
  STEGASOO_CHANNEL_KEY: ${STEGASOO_CHANNEL_KEY:-}

services:
  web:
    environment:
      <<: *common-env
  api:
    environment:
      <<: *common-env
```

**.env (gitignored):**
```bash
STEGASOO_CHANNEL_KEY=ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456
```

### CI/CD Pipeline

```bash
# Generate key for CI
CHANNEL_KEY=$(stegasoo channel generate -q)

# Use in pipeline
STEGASOO_CHANNEL_KEY=$CHANNEL_KEY stegasoo encode ...
```

---

## Piping & Scripting

### Extract channel key for scripts

```bash
# Get just the key
KEY=$(stegasoo channel show --json | jq -r '.key // empty')

# Get fingerprint
FINGERPRINT=$(stegasoo channel show --json | jq -r '.fingerprint // "none"')

# Check if configured
if stegasoo channel show --json | jq -e '.configured' > /dev/null; then
  echo "Channel key is configured"
fi
```

### Generate and use immediately

```bash
# Generate, save, and use
stegasoo channel generate --save
stegasoo encode -r ref.jpg -c carrier.png -p "phrase" --pin 123456 -m "message"
```

---

## Error Handling

### Channel Key Errors

| Error | Cause | Solution |
|-------|-------|----------|
| "Invalid channel key format" | Key doesn't match pattern | Use `stegasoo channel generate` |
| "Message encoded with channel key but none configured" | Missing channel key | Set key or use `--channel` |
| "Message encoded without channel key" | Used `--no-channel` to encode | Decode with `--no-channel` |
| "Channel key mismatch" | Wrong key | Verify correct key |

### Troubleshooting

```bash
# Check current channel status
stegasoo channel show

# Try decoding with explicit key
stegasoo decode ... --channel XXXX-XXXX-...

# Try decoding without channel key
stegasoo decode ... --no-channel
```

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
| `STEGASOO_CHANNEL_KEY` | Channel key for deployment isolation (v4.0.0) |
| `PYTHONPATH` | Include `src/` for development |
| `STEGASOO_DEBUG` | Enable debug output (set to `1`) |

---

## See Also

- [API Documentation](API.md) - Python API reference
- [Web UI Documentation](WEB_UI.md) - Browser interface guide
- [README](../README.md) - Project overview and security model
