# Stegasoo REST API Documentation (v4.0.1)

Complete REST API reference for Stegasoo steganography operations.

## Table of Contents

- [Overview](#overview)
- [What's New in v4.0.0](#whats-new-in-v400)
- [Installation](#installation)
- [Base URL](#base-url)
- [Endpoints](#endpoints)
  - [GET /](#get--status)
  - [GET /modes](#get-modes)
  - [GET /channel/status](#get-channelstatus)
  - [POST /channel/generate](#post-channelgenerate)
  - [POST /channel/set](#post-channelset)
  - [DELETE /channel](#delete-channel)
  - [POST /generate](#post-generate)
  - [POST /encode](#post-encode-json)
  - [POST /encode/file](#post-encodefile)
  - [POST /encode/multipart](#post-encodemultipart)
  - [POST /decode](#post-decode-json)
  - [POST /decode/multipart](#post-decodemultipart)
  - [POST /compare](#post-compare)
  - [POST /will-fit](#post-will-fit)
  - [POST /image/info](#post-imageinfo)
- [Channel Keys](#channel-keys)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Code Examples](#code-examples)

---

## Overview

The Stegasoo REST API provides programmatic access to all steganography operations:

- **Generate** credentials (passphrase, PINs, RSA keys)
- **Encode** messages or files into images (LSB or DCT mode)
- **Decode** messages or files from images (auto-detects mode)
- **Channel keys** for deployment/group isolation (v4.0.0)
- **Analyze** image capacity and compare modes

The API supports both JSON (base64-encoded images) and multipart form data (direct file uploads).

---

## What's New in v4.0.0

Version 4.0.0 adds **channel key** support for deployment/group isolation:

| Feature | Description |
|---------|-------------|
| Channel keys | 256-bit keys that isolate message groups |
| New endpoints | `/channel/status`, `/channel/generate`, `/channel/set`, `DELETE /channel` |
| Encode/decode param | `channel_key` parameter on all encode/decode endpoints |
| Response headers | `X-Stegasoo-Channel-Mode` and `X-Stegasoo-Channel-Fingerprint` |

**Key benefits:**
- ✅ Isolate messages between teams, deployments, or groups
- ✅ Same credentials can't decode messages from different channels
- ✅ Backward compatible (public mode = no channel key)

**Breaking change:** v4.0.0 messages (with channel key) cannot be decoded by v3.x installations.

---

## Installation

### From PyPI

```bash
pip install stegasoo[api]
```

### Running the Server

**Development:**
```bash
cd frontends/api
python main.py
```

**Production:**
```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Docker with channel key:**
```bash
STEGASOO_CHANNEL_KEY=XXXX-XXXX-... docker-compose up api
```

---

## Base URL

| Environment | URL |
|-------------|-----|
| Local Development | `http://localhost:8000` |
| Docker | `http://localhost:8000` |
| Production | Configure as needed |

---

## Endpoints

### GET / (Status)

Check API status and configuration.

#### Response

```json
{
  "version": "4.0.1",
  "has_argon2": true,
  "has_qrcode_read": true,
  "has_dct": true,
  "max_payload_kb": 500,
  "available_modes": ["lsb", "dct"],
  "dct_features": {
    "output_formats": ["png", "jpeg"],
    "color_modes": ["grayscale", "color"]
  },
  "channel": {
    "mode": "private",
    "configured": true,
    "fingerprint": "ABCD-••••-••••-••••-••••-••••-••••-3456",
    "source": "~/.stegasoo/channel.key"
  },
  "breaking_changes": {
    "v4_channel_key": "Messages encoded with channel key require same key to decode",
    "format_version": 5,
    "backward_compatible": false
  }
}
```

---

### GET /modes

Get available embedding modes and channel status.

#### Response

```json
{
  "lsb": {
    "available": true,
    "name": "Spatial LSB",
    "description": "Embed in pixel LSBs, outputs PNG/BMP",
    "output_format": "PNG (color)",
    "capacity_ratio": "100%"
  },
  "dct": {
    "available": true,
    "name": "DCT Domain",
    "output_formats": ["png", "jpeg"],
    "color_modes": ["grayscale", "color"],
    "capacity_ratio": "~20% of LSB",
    "requires": "scipy"
  },
  "channel": {
    "mode": "private",
    "configured": true,
    "fingerprint": "ABCD-••••-••••-••••-••••-••••-••••-3456"
  }
}
```

---

### GET /channel/status

Get current channel key status. **New in v4.0.0.**

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `reveal` | boolean | `false` | Include full key in response |

#### Response

```json
{
  "mode": "private",
  "configured": true,
  "fingerprint": "ABCD-••••-••••-••••-••••-••••-••••-3456",
  "source": "~/.stegasoo/channel.key",
  "key": null
}
```

With `reveal=true`:

```json
{
  "mode": "private",
  "configured": true,
  "fingerprint": "ABCD-••••-••••-••••-••••-••••-••••-3456",
  "source": "~/.stegasoo/channel.key",
  "key": "ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456"
}
```

#### cURL Example

```bash
# Show status
curl http://localhost:8000/channel/status

# Reveal full key
curl "http://localhost:8000/channel/status?reveal=true"
```

---

### POST /channel/generate

Generate a new channel key. **New in v4.0.0.**

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `save` | boolean | `false` | Save to user config |
| `save_project` | boolean | `false` | Save to project config |

#### Response

```json
{
  "key": "ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456",
  "fingerprint": "ABCD-••••-••••-••••-••••-••••-••••-3456",
  "saved": true,
  "save_location": "~/.stegasoo/channel.key"
}
```

#### cURL Examples

```bash
# Just generate (don't save)
curl -X POST http://localhost:8000/channel/generate

# Generate and save to user config
curl -X POST "http://localhost:8000/channel/generate?save=true"

# Generate and save to project config
curl -X POST "http://localhost:8000/channel/generate?save_project=true"
```

---

### POST /channel/set

Set/save a channel key to config. **New in v4.0.0.**

#### Request Body

```json
{
  "key": "ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456",
  "location": "user"
}
```

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `key` | string | required | Channel key |
| `location` | string | `"user"` | `"user"` or `"project"` |

#### Response

```json
{
  "success": true,
  "location": "~/.stegasoo/channel.key",
  "fingerprint": "ABCD-••••-••••-••••-••••-••••-••••-3456"
}
```

---

### DELETE /channel

Clear channel key from config. **New in v4.0.0.**

#### Query Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `location` | string | `"user"` | `"user"`, `"project"`, or `"all"` |

#### Response

```json
{
  "success": true,
  "mode": "public",
  "still_configured": false,
  "remaining_source": null
}
```

#### cURL Example

```bash
# Clear user config
curl -X DELETE http://localhost:8000/channel

# Clear project config
curl -X DELETE "http://localhost:8000/channel?location=project"

# Clear all
curl -X DELETE "http://localhost:8000/channel?location=all"
```

---

### POST /generate

Generate credentials for encoding/decoding.

#### Request Body

```json
{
  "use_pin": true,
  "use_rsa": false,
  "pin_length": 6,
  "rsa_bits": 2048,
  "words_per_passphrase": 4
}
```

#### Response

```json
{
  "passphrase": "abandon ability able about",
  "pin": "847293",
  "rsa_key_pem": null,
  "entropy": {
    "passphrase": 44,
    "pin": 19,
    "rsa": 0,
    "total": 63
  }
}
```

---

### POST /encode (JSON)

Encode a text message into an image.

#### Request Body

```json
{
  "message": "Secret message here",
  "reference_photo_base64": "iVBORw0KGgo...",
  "carrier_image_base64": "iVBORw0KGgo...",
  "passphrase": "apple forest thunder mountain",
  "pin": "123456",
  "rsa_key_base64": null,
  "rsa_password": null,
  "channel_key": null,
  "embed_mode": "lsb",
  "dct_output_format": "png",
  "dct_color_mode": "grayscale"
}
```

#### Channel Key Parameter (v4.0.0)

| Value | Effect |
|-------|--------|
| `null` | Auto mode - use server-configured key |
| `""` (empty string) | Public mode - no channel isolation |
| `"XXXX-XXXX-..."` | Explicit key - use this specific key |

#### Response

```json
{
  "stego_image_base64": "iVBORw0KGgo...",
  "filename": "a1b2c3d4.png",
  "capacity_used_percent": 12.4,
  "embed_mode": "lsb",
  "output_format": "png",
  "color_mode": "color",
  "channel_mode": "private",
  "channel_fingerprint": "ABCD-••••-••••-••••-••••-••••-••••-3456"
}
```

---

### POST /encode/file

Encode a file into an image (JSON with base64).

Same parameters as `/encode`, plus:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_data_base64` | string | ✓ | Base64-encoded file data |
| `filename` | string | ✓ | Original filename |
| `mime_type` | string | | MIME type |

---

### POST /encode/multipart

Encode using multipart form data (file uploads).

#### Form Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `passphrase` | string | ✓ | Passphrase |
| `reference_photo` | file | ✓ | Reference photo |
| `carrier` | file | ✓ | Carrier image |
| `message` | string | * | Text message |
| `payload_file` | file | * | Binary file to embed |
| `pin` | string | | Static PIN |
| `rsa_key` | file | | RSA key (.pem) |
| `rsa_key_qr` | file | | RSA key (QR code image) |
| `rsa_password` | string | | RSA key password |
| `channel_key` | string | | `"auto"` (default), `"none"=public`, or explicit key |
| `embed_mode` | string | | `"lsb"` or `"dct"` |
| `dct_output_format` | string | | `"png"` or `"jpeg"` |
| `dct_color_mode` | string | | `"grayscale"` or `"color"` |

\* Provide either `message` or `payload_file`

#### Channel Key in Multipart

For form data, the channel_key field uses strings:

| Value | Effect |
|-------|--------|
| `"auto"` | Use server config (default) |
| `"none"` | Public mode |
| `"XXXX-XXXX-..."` | Explicit key |

#### Response

Returns the stego image directly with headers:

```http
HTTP/1.1 200 OK
Content-Type: image/png
Content-Disposition: attachment; filename=a1b2c3d4.png
X-Stegasoo-Capacity-Percent: 12.4
X-Stegasoo-Embed-Mode: lsb
X-Stegasoo-Channel-Mode: private
X-Stegasoo-Channel-Fingerprint: ABCD-••••-...-3456
X-Stegasoo-Version: 4.0.1

<binary image data>
```

#### cURL Examples

```bash
# Encode with auto channel key (default)
curl -X POST http://localhost:8000/encode/multipart \
  -F "passphrase=apple forest thunder mountain" \
  -F "pin=123456" \
  -F "message=Secret message" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png

# Encode with explicit channel key
curl -X POST http://localhost:8000/encode/multipart \
  -F "passphrase=words here" \
  -F "pin=123456" \
  -F "message=Team message" \
  -F "channel_key=ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png

# Encode in public mode (no channel isolation)
curl -X POST http://localhost:8000/encode/multipart \
  -F "passphrase=words here" \
  -F "pin=123456" \
  -F "message=Public message" \
  -F "channel_key=none" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png
```

---

### POST /decode (JSON)

Decode a message or file from a stego image.

#### Request Body

```json
{
  "stego_image_base64": "iVBORw0KGgo...",
  "reference_photo_base64": "iVBORw0KGgo...",
  "passphrase": "apple forest thunder mountain",
  "pin": "123456",
  "rsa_key_base64": null,
  "rsa_password": null,
  "channel_key": null,
  "embed_mode": "auto"
}
```

#### Response (Text)

```json
{
  "payload_type": "text",
  "message": "Secret message here",
  "file_data_base64": null,
  "filename": null,
  "mime_type": null
}
```

#### Response (File)

```json
{
  "payload_type": "file",
  "message": null,
  "file_data_base64": "UEsDBBQAAAA...",
  "filename": "document.pdf",
  "mime_type": "application/pdf"
}
```

---

### POST /decode/multipart

Decode using multipart form data.

#### Form Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `passphrase` | string | ✓ | Passphrase |
| `reference_photo` | file | ✓ | Reference photo |
| `stego_image` | file | ✓ | Stego image to decode |
| `pin` | string | | Static PIN |
| `rsa_key` | file | | RSA key (.pem) |
| `rsa_key_qr` | file | | RSA key (QR code image) |
| `rsa_password` | string | | RSA key password |
| `channel_key` | string | | `"auto"` (default), `"none"=public`, or explicit key |
| `embed_mode` | string | | `"auto"`, `"lsb"`, or `"dct"` |

---

## Channel Keys

### Overview

Channel keys provide **deployment/group isolation**. Messages encoded with a channel key can only be decoded with the same key.

### Key Format

```
ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456
└──┘ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘ └──┘
  8 groups of 4 alphanumeric characters (256 bits)
```

### Storage Locations

Keys are checked in order:

| Priority | Location | Best For |
|----------|----------|----------|
| 1 | `STEGASOO_CHANNEL_KEY` env var | Docker, CI/CD |
| 2 | `./config/channel.key` | Project-specific |
| 3 | `~/.stegasoo/channel.key` | User default |

### API Parameter Values

#### JSON Endpoints (`/encode`, `/decode`)

| Value | Effect |
|-------|--------|
| `null` | Auto - use server config |
| `""` | Public mode |
| `"XXXX-..."` | Explicit key |

#### Multipart Endpoints (`/encode/multipart`, `/decode/multipart`)

| Value | Effect |
|-------|--------|
| `"auto"` | Use server config (default) |
| `"none"` | Public mode |
| `"XXXX-..."` | Explicit key |

### Workflow Example

```bash
# 1. Generate a channel key for the team
KEY=$(curl -s -X POST http://localhost:8000/channel/generate | jq -r '.key')
echo "Team key: $KEY"

# 2. Distribute to team members (securely!)

# 3. Each deployment sets the key
export STEGASOO_CHANNEL_KEY=$KEY

# 4. Encode - automatically uses server key
curl -X POST http://localhost:8000/encode/multipart \
  -F "passphrase=team passphrase" \
  -F "pin=123456" \
  -F "message=Team secret" \
  -F "reference_photo=@ref.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png

# 5. Decode - automatically uses server key
curl -X POST http://localhost:8000/decode/multipart \
  -F "passphrase=team passphrase" \
  -F "pin=123456" \
  -F "reference_photo=@ref.jpg" \
  -F "stego_image=@stego.png"
```

---

## Data Models

### ChannelStatusResponse

```json
{
  "mode": "private",
  "configured": true,
  "fingerprint": "ABCD-••••-...-3456",
  "source": "~/.stegasoo/channel.key",
  "key": "ABCD-1234-..." 
}
```

### EncodeResponse (v4.0.0)

```json
{
  "stego_image_base64": "string",
  "filename": "string",
  "capacity_used_percent": 12.4,
  "embed_mode": "lsb",
  "output_format": "png",
  "color_mode": "color",
  "channel_mode": "private",
  "channel_fingerprint": "ABCD-••••-...-3456"
}
```

### DecodeResponse

```json
{
  "payload_type": "text",
  "message": "string",
  "file_data_base64": null,
  "filename": null,
  "mime_type": null
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Use Case |
|------|---------|----------|
| 200 | OK | Successful operation |
| 400 | Bad Request | Invalid input, capacity error, invalid channel key |
| 401 | Unauthorized | Decryption failed, channel key mismatch |
| 500 | Internal Error | Unexpected server error |
| 501 | Not Implemented | Feature unavailable |

### Channel Key Errors

| Status | Error | Cause |
|--------|-------|-------|
| 400 | "Invalid channel key format" | Key doesn't match `XXXX-XXXX-...` pattern |
| 401 | "Message encoded with channel key but none configured" | Need to provide channel key |
| 401 | "Message encoded without channel key" | Use `channel_key=""` or `"none"` |

---

## Code Examples

### Python

```python
import requests

BASE_URL = "http://localhost:8000"

# Check channel status
status = requests.get(f"{BASE_URL}/channel/status").json()
print(f"Channel mode: {status['mode']}")
print(f"Fingerprint: {status.get('fingerprint', 'N/A')}")

# Generate channel key
response = requests.post(f"{BASE_URL}/channel/generate?save=true")
key_info = response.json()
print(f"Generated: {key_info['fingerprint']}")

# Encode with channel key (auto from server)
with open("ref.jpg", "rb") as ref, open("carrier.png", "rb") as carrier:
    response = requests.post(f"{BASE_URL}/encode/multipart", files={
        "reference_photo": ref,
        "carrier": carrier,
    }, data={
        "message": "Team secret",
        "passphrase": "apple forest thunder",
        "pin": "123456",
        # channel_key defaults to "auto" (use server config)
    })
    
    with open("stego.png", "wb") as f:
        f.write(response.content)
    
    print(f"Channel mode: {response.headers.get('X-Stegasoo-Channel-Mode')}")

# Encode with explicit channel key
with open("ref.jpg", "rb") as ref, open("carrier.png", "rb") as carrier:
    response = requests.post(f"{BASE_URL}/encode/multipart", files={
        "reference_photo": ref,
        "carrier": carrier,
    }, data={
        "message": "Using explicit key",
        "passphrase": "words here",
        "pin": "123456",
        "channel_key": "ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456",
    })

# Decode
with open("ref.jpg", "rb") as ref, open("stego.png", "rb") as stego:
    response = requests.post(f"{BASE_URL}/decode/multipart", files={
        "reference_photo": ref,
        "stego_image": stego,
    }, data={
        "passphrase": "apple forest thunder",
        "pin": "123456",
        # channel_key defaults to "auto"
    })
    
    result = response.json()
    print(f"Decoded: {result.get('message')}")
```

### JavaScript

```javascript
const axios = require('axios');
const FormData = require('form-data');
const fs = require('fs');

const BASE_URL = 'http://localhost:8000';

async function main() {
    // Check channel status
    const status = await axios.get(`${BASE_URL}/channel/status`);
    console.log('Channel:', status.data.mode);
    
    // Encode with auto channel key
    const form = new FormData();
    form.append('passphrase', 'apple forest thunder');
    form.append('pin', '123456');
    form.append('message', 'Secret');
    form.append('reference_photo', fs.createReadStream('ref.jpg'));
    form.append('carrier', fs.createReadStream('carrier.png'));
    // channel_key defaults to "auto" (use server config)
    
    const response = await axios.post(`${BASE_URL}/encode/multipart`, form, {
        headers: form.getHeaders(),
        responseType: 'arraybuffer'
    });
    
    fs.writeFileSync('stego.png', response.data);
    console.log('Channel mode:', response.headers['x-stegasoo-channel-mode']);
}

main();
```

### cURL / Bash

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"

# Check channel status
echo "Channel status:"
curl -s "$BASE_URL/channel/status" | jq .

# Generate and save channel key
echo "Generating channel key..."
curl -s -X POST "$BASE_URL/channel/generate?save=true" | jq .

# Encode (channel_key defaults to "auto")
echo "Encoding..."
curl -s -X POST "$BASE_URL/encode/multipart" \
  -F "passphrase=apple forest thunder" \
  -F "pin=123456" \
  -F "message=Secret message" \
  -F "reference_photo=@ref.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png

echo "Encoded to stego.png"

# Decode
echo "Decoding..."
curl -s -X POST "$BASE_URL/decode/multipart" \
  -F "passphrase=apple forest thunder" \
  -F "pin=123456" \
  -F "reference_photo=@ref.jpg" \
  -F "stego_image=@stego.png" | jq .
```

---

## Docker Configuration

### docker-compose.yml

```yaml
x-common-env: &common-env
  STEGASOO_CHANNEL_KEY: ${STEGASOO_CHANNEL_KEY:-}

services:
  api:
    build:
      context: .
      target: api
    ports:
      - "8000:8000"
    environment:
      <<: *common-env
```

### .env (gitignored)

```bash
STEGASOO_CHANNEL_KEY=ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456
```

### Generate key for .env

```bash
curl -s -X POST http://localhost:8000/channel/generate | \
  jq -r '"STEGASOO_CHANNEL_KEY=\(.key)"' >> .env
```

---

## See Also

- [CLI Documentation](CLI.md) - Command-line interface
- [Web UI Documentation](WEB_UI.md) - Browser interface
- [README](../README.md) - Project overview
