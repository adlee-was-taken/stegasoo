# Stegasoo REST API Documentation

Complete REST API reference for Stegasoo steganography operations.

## Table of Contents

- [Overview](#overview)
- [Installation](#installation)
- [Authentication](#authentication)
- [Base URL](#base-url)
- [Endpoints](#endpoints)
  - [GET /](#get--status)
  - [POST /generate](#post-generate)
  - [POST /encode](#post-encode-json)
  - [POST /encode/multipart](#post-encodemultipart)
  - [POST /decode](#post-decode-json)
  - [POST /decode/multipart](#post-decodemultipart)
  - [POST /image/info](#post-imageinfo)
- [Embedding Modes](#embedding-modes)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Code Examples](#code-examples)
- [Rate Limiting](#rate-limiting)
- [Security Considerations](#security-considerations)

---

## Overview

The Stegasoo REST API provides programmatic access to all steganography operations:

- **Generate** credentials (phrases, PINs, RSA keys)
- **Encode** messages into images (LSB or DCT mode)
- **Decode** messages from images (auto-detects mode)
- **Analyze** image capacity

The API supports both JSON (base64-encoded images) and multipart form data (direct file uploads).

### What's New in v3.0.2

- **DCT Steganography Mode** - JPEG-resilient embedding
- **Output Format Selection** - PNG or JPEG output
- **Color Mode Selection** - Color or grayscale processing
- **jpegio Integration** - Proper JPEG coefficient manipulation

---

## Installation

### From PyPI

```bash
pip install stegasoo[api]
```

This automatically installs DCT dependencies (scipy, jpegio) for full functionality.

### From Source

```bash
git clone https://github.com/example/stegasoo.git
cd stegasoo
pip install -e ".[api]"
```

### Running the Server

**Development:**
```bash
cd frontends/api
python main.py
```

**Production:**
```bash
cd frontends/api
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
```

**Docker:**
```bash
docker-compose up api
```

---

## Authentication

The API currently operates without authentication. For production deployments, implement authentication at the reverse proxy level (nginx, Caddy) or add API key middleware.

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

#### Request

```http
GET / HTTP/1.1
Host: localhost:8000
```

#### Response

```json
{
  "version": "3.0.2",
  "has_argon2": true,
  "has_dct": true,
  "has_jpegio": true,
  "day_names": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Stegasoo library version |
| `has_argon2` | boolean | Whether Argon2id is available |
| `has_dct` | boolean | Whether DCT mode is available (scipy) |
| `has_jpegio` | boolean | Whether native JPEG DCT is available |
| `day_names` | array | Day names for phrase mapping |

#### cURL Example

```bash
curl http://localhost:8000/
```

---

### POST /generate

Generate credentials for encoding/decoding.

#### Request

```http
POST /generate HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "use_pin": true,
  "use_rsa": false,
  "pin_length": 6,
  "rsa_bits": 2048,
  "words_per_phrase": 3
}
```

#### Request Body

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_pin` | boolean | `true` | Generate a PIN |
| `use_rsa` | boolean | `false` | Generate an RSA key |
| `pin_length` | integer | `6` | PIN length (6-9) |
| `rsa_bits` | integer | `2048` | RSA key size (2048, 3072, 4096) |
| `words_per_phrase` | integer | `3` | Words per phrase (3-12) |

#### Response

```json
{
  "phrases": {
    "Monday": "abandon ability able",
    "Tuesday": "actor actress actual",
    "Wednesday": "advice aerobic affair",
    "Thursday": "afraid again age",
    "Friday": "agree ahead aim",
    "Saturday": "airport aisle alarm",
    "Sunday": "album alcohol alert"
  },
  "pin": "847293",
  "rsa_key_pem": null,
  "entropy": {
    "phrase": 33,
    "pin": 19,
    "rsa": 0,
    "total": 52
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `phrases` | object | Day-to-phrase mapping |
| `pin` | string\|null | Generated PIN (if requested) |
| `rsa_key_pem` | string\|null | PEM-encoded RSA key (if requested) |
| `entropy.phrase` | integer | Entropy from phrases (bits) |
| `entropy.pin` | integer | Entropy from PIN (bits) |
| `entropy.rsa` | integer | Entropy from RSA key (bits) |
| `entropy.total` | integer | Combined entropy (bits) |

#### cURL Examples

**PIN only:**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"use_pin": true, "use_rsa": false}'
```

**RSA only:**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"use_pin": false, "use_rsa": true, "rsa_bits": 4096}'
```

**Both with custom settings:**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "use_pin": true,
    "use_rsa": true,
    "pin_length": 9,
    "rsa_bits": 4096,
    "words_per_phrase": 6
  }'
```

---

### POST /encode (JSON)

Encode a message using base64-encoded images.

#### Request

```http
POST /encode HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "message": "Secret message here",
  "reference_photo_base64": "iVBORw0KGgo...",
  "carrier_image_base64": "iVBORw0KGgo...",
  "day_phrase": "apple forest thunder",
  "pin": "123456",
  "rsa_key_base64": null,
  "rsa_password": null,
  "date_str": null,
  "embedding_mode": "lsb",
  "output_format": "png",
  "color_mode": "color"
}
```

#### Request Body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | ✓ | | Message to encode |
| `reference_photo_base64` | string | ✓ | | Base64-encoded reference photo |
| `carrier_image_base64` | string | ✓ | | Base64-encoded carrier image |
| `day_phrase` | string | ✓ | | Today's passphrase |
| `pin` | string | * | | Static PIN (6-9 digits) |
| `rsa_key_base64` | string | * | | Base64-encoded RSA key PEM |
| `rsa_password` | string | | | Password for RSA key |
| `date_str` | string | | | Date override (YYYY-MM-DD) |
| `embedding_mode` | string | | `"lsb"` | `"lsb"` or `"dct"` |
| `output_format` | string | | `"png"` | `"png"` or `"jpeg"` (DCT only) |
| `color_mode` | string | | `"color"` | `"color"` or `"grayscale"` (DCT only) |

\* At least one of `pin` or `rsa_key_base64` required.

#### Response

```json
{
  "stego_image_base64": "iVBORw0KGgo...",
  "filename": "a1b2c3d4_20251227.png",
  "capacity_used_percent": 12.4,
  "date_used": "2025-12-27",
  "day_of_week": "Saturday",
  "embedding_mode": "lsb",
  "output_format": "png",
  "color_mode": null
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `stego_image_base64` | string | Base64-encoded stego image |
| `filename` | string | Suggested filename |
| `capacity_used_percent` | float | Percentage of capacity used |
| `date_used` | string | Date embedded in image (YYYY-MM-DD) |
| `day_of_week` | string | Day name for passphrase rotation |
| `embedding_mode` | string | Mode used: `"lsb"` or `"dct"` |
| `output_format` | string | Output format: `"png"` or `"jpeg"` |
| `color_mode` | string\|null | Color mode (DCT only): `"color"` or `"grayscale"` |

#### cURL Example (LSB Mode - Default)

```bash
# Prepare base64-encoded images
REF_B64=$(base64 -w0 reference.jpg)
CARRIER_B64=$(base64 -w0 carrier.png)

curl -X POST http://localhost:8000/encode \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"Secret message\",
    \"reference_photo_base64\": \"$REF_B64\",
    \"carrier_image_base64\": \"$CARRIER_B64\",
    \"day_phrase\": \"apple forest thunder\",
    \"pin\": \"123456\"
  }" | jq -r '.stego_image_base64' | base64 -d > stego.png
```

#### cURL Example (DCT Mode with JPEG Output)

```bash
curl -X POST http://localhost:8000/encode \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"Secret message\",
    \"reference_photo_base64\": \"$REF_B64\",
    \"carrier_image_base64\": \"$CARRIER_B64\",
    \"day_phrase\": \"apple forest thunder\",
    \"pin\": \"123456\",
    \"embedding_mode\": \"dct\",
    \"output_format\": \"jpeg\",
    \"color_mode\": \"color\"
  }" | jq -r '.stego_image_base64' | base64 -d > stego.jpg
```

---

### POST /encode/multipart

Encode a message using direct file uploads. Returns the stego image directly.

#### Request

```http
POST /encode/multipart HTTP/1.1
Host: localhost:8000
Content-Type: multipart/form-data; boundary=----FormBoundary

------FormBoundary
Content-Disposition: form-data; name="message"

Secret message here
------FormBoundary
Content-Disposition: form-data; name="day_phrase"

apple forest thunder
------FormBoundary
Content-Disposition: form-data; name="pin"

123456
------FormBoundary
Content-Disposition: form-data; name="embedding_mode"

dct
------FormBoundary
Content-Disposition: form-data; name="output_format"

jpeg
------FormBoundary
Content-Disposition: form-data; name="color_mode"

color
------FormBoundary
Content-Disposition: form-data; name="reference_photo"; filename="ref.jpg"
Content-Type: image/jpeg

<binary image data>
------FormBoundary
Content-Disposition: form-data; name="carrier"; filename="carrier.png"
Content-Type: image/png

<binary image data>
------FormBoundary--
```

#### Form Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | ✓ | | Message to encode |
| `reference_photo` | file | ✓ | | Reference photo file |
| `carrier` | file | ✓ | | Carrier image file |
| `day_phrase` | string | ✓ | | Today's passphrase |
| `pin` | string | * | | Static PIN |
| `rsa_key` | file | * | | RSA key file (.pem) |
| `rsa_password` | string | | | Password for RSA key |
| `date_str` | string | | | Date override (YYYY-MM-DD) |
| `embedding_mode` | string | | `"lsb"` | `"lsb"` or `"dct"` |
| `output_format` | string | | `"png"` | `"png"` or `"jpeg"` (DCT only) |
| `color_mode` | string | | `"color"` | `"color"` or `"grayscale"` (DCT only) |

\* At least one of `pin` or `rsa_key` required.

#### Response

Returns the image directly with headers:

```http
HTTP/1.1 200 OK
Content-Type: image/png
Content-Disposition: attachment; filename="a1b2c3d4_20251227.png"
X-Stegasoo-Date: 2025-12-27
X-Stegasoo-Day: Saturday
X-Stegasoo-Capacity-Used: 12.4
X-Stegasoo-Embedding-Mode: lsb
X-Stegasoo-Output-Format: png

<binary image data>
```

#### Response Headers

| Header | Description |
|--------|-------------|
| `Content-Type` | `image/png` or `image/jpeg` |
| `Content-Disposition` | Suggested filename |
| `X-Stegasoo-Date` | Encoding date |
| `X-Stegasoo-Day` | Day of week |
| `X-Stegasoo-Capacity-Used` | Capacity percentage |
| `X-Stegasoo-Embedding-Mode` | `lsb` or `dct` |
| `X-Stegasoo-Output-Format` | `png` or `jpeg` |
| `X-Stegasoo-Color-Mode` | `color` or `grayscale` (DCT only) |

#### cURL Example (DCT + JPEG)

```bash
curl -X POST http://localhost:8000/encode/multipart \
  -F "message=Secret message for social media" \
  -F "day_phrase=apple forest thunder" \
  -F "pin=123456" \
  -F "embedding_mode=dct" \
  -F "output_format=jpeg" \
  -F "color_mode=color" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.jpg
```

---

### POST /decode (JSON)

Decode a message using base64-encoded images. Auto-detects embedding mode.

#### Request

```http
POST /decode HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "stego_image_base64": "iVBORw0KGgo...",
  "reference_photo_base64": "iVBORw0KGgo...",
  "day_phrase": "apple forest thunder",
  "pin": "123456",
  "rsa_key_base64": null,
  "rsa_password": null
}
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `stego_image_base64` | string | ✓ | Base64-encoded stego image |
| `reference_photo_base64` | string | ✓ | Base64-encoded reference photo |
| `day_phrase` | string | ✓ | Passphrase for encoding day |
| `pin` | string | * | Static PIN |
| `rsa_key_base64` | string | * | Base64-encoded RSA key |
| `rsa_password` | string | | Password for RSA key |

\* Must match security factors used during encoding.

#### Response

```json
{
  "message": "Secret message here",
  "embedding_mode_detected": "dct"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Decoded message |
| `embedding_mode_detected` | string | Detected mode: `"lsb"` or `"dct"` |

#### cURL Example

```bash
STEGO_B64=$(base64 -w0 stego.png)
REF_B64=$(base64 -w0 reference.jpg)

curl -X POST http://localhost:8000/decode \
  -H "Content-Type: application/json" \
  -d "{
    \"stego_image_base64\": \"$STEGO_B64\",
    \"reference_photo_base64\": \"$REF_B64\",
    \"day_phrase\": \"apple forest thunder\",
    \"pin\": \"123456\"
  }"
```

---

### POST /decode/multipart

Decode using direct file uploads. Auto-detects embedding mode.

#### Form Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `stego_image` | file | ✓ | Stego image file |
| `reference_photo` | file | ✓ | Reference photo file |
| `day_phrase` | string | ✓ | Passphrase for encoding day |
| `pin` | string | * | Static PIN |
| `rsa_key` | file | * | RSA key file (.pem) |
| `rsa_password` | string | | Password for RSA key |

#### Response

```json
{
  "message": "Secret message here",
  "embedding_mode_detected": "lsb"
}
```

#### cURL Example

```bash
curl -X POST http://localhost:8000/decode/multipart \
  -F "day_phrase=apple forest thunder" \
  -F "pin=123456" \
  -F "reference_photo=@reference.jpg" \
  -F "stego_image=@stego.png"
```

---

### POST /image/info

Get image information and capacity for both LSB and DCT modes.

#### Request (JSON)

```http
POST /image/info HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "image_base64": "iVBORw0KGgo..."
}
```

#### Request (Multipart)

```bash
curl -X POST http://localhost:8000/image/info \
  -F "image=@carrier.png"
```

#### Response

```json
{
  "width": 1920,
  "height": 1080,
  "pixels": 2073600,
  "format": "PNG",
  "mode": "RGB",
  "capacity": {
    "lsb": {
      "bytes": 776970,
      "kb": 758
    },
    "dct": {
      "bytes": 64800,
      "kb": 63,
      "note": "Approximate - actual capacity depends on image content"
    }
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `width` | integer | Image width in pixels |
| `height` | integer | Image height in pixels |
| `pixels` | integer | Total pixel count |
| `format` | string | Image format (PNG, JPEG, etc.) |
| `mode` | string | Color mode (RGB, L, etc.) |
| `capacity.lsb.bytes` | integer | LSB capacity in bytes |
| `capacity.lsb.kb` | integer | LSB capacity in KB |
| `capacity.dct.bytes` | integer | Estimated DCT capacity in bytes |
| `capacity.dct.kb` | integer | Estimated DCT capacity in KB |
| `capacity.dct.note` | string | Capacity estimation note |

---

## Embedding Modes

### LSB Mode (Default)

**Least Significant Bit** embedding modifies pixel values directly.

| Aspect | Details |
|--------|---------|
| **Parameter** | `"embedding_mode": "lsb"` |
| **Capacity** | ~3 bits/pixel (~770 KB for 1920×1080) |
| **Output** | PNG only (lossless required) |
| **Resilience** | ❌ Destroyed by JPEG compression |
| **Best For** | Maximum capacity, controlled channels |

### DCT Mode (Experimental)

**Discrete Cosine Transform** embedding hides data in frequency coefficients.

| Aspect | Details |
|--------|---------|
| **Parameter** | `"embedding_mode": "dct"` |
| **Capacity** | ~0.25 bits/pixel (~65 KB for 1920×1080) |
| **Output** | PNG or JPEG |
| **Resilience** | ✅ Survives JPEG compression |
| **Best For** | Social media, messaging apps |

> ⚠️ **Experimental**: DCT mode may have edge cases. Test with your workflow.

### DCT Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `output_format` | `"png"`, `"jpeg"` | `"png"` | Output image format |
| `color_mode` | `"color"`, `"grayscale"` | `"color"` | Color processing mode |

### Capacity Comparison

| Mode | 1920×1080 Capacity |
|------|-------------------|
| LSB (PNG) | ~770 KB |
| DCT (PNG) | ~65 KB |
| DCT (JPEG) | ~30-50 KB |

---

## Data Models

### GenerateRequest

```json
{
  "use_pin": true,
  "use_rsa": false,
  "pin_length": 6,
  "rsa_bits": 2048,
  "words_per_phrase": 3
}
```

### GenerateResponse

```json
{
  "phrases": {"Monday": "...", "Tuesday": "...", ...},
  "pin": "123456",
  "rsa_key_pem": "-----BEGIN PRIVATE KEY-----...",
  "entropy": {"phrase": 33, "pin": 19, "rsa": 0, "total": 52}
}
```

### EncodeRequest

```json
{
  "message": "string",
  "reference_photo_base64": "string",
  "carrier_image_base64": "string",
  "day_phrase": "string",
  "pin": "string",
  "rsa_key_base64": "string",
  "rsa_password": "string",
  "date_str": "YYYY-MM-DD",
  "embedding_mode": "lsb",
  "output_format": "png",
  "color_mode": "color"
}
```

### EncodeResponse

```json
{
  "stego_image_base64": "string",
  "filename": "string",
  "capacity_used_percent": 12.4,
  "date_used": "YYYY-MM-DD",
  "day_of_week": "Saturday",
  "embedding_mode": "lsb",
  "output_format": "png",
  "color_mode": null
}
```

### DecodeRequest

```json
{
  "stego_image_base64": "string",
  "reference_photo_base64": "string",
  "day_phrase": "string",
  "pin": "string",
  "rsa_key_base64": "string",
  "rsa_password": "string"
}
```

### DecodeResponse

```json
{
  "message": "string",
  "embedding_mode_detected": "lsb"
}
```

### ImageInfoResponse

```json
{
  "width": 1920,
  "height": 1080,
  "pixels": 2073600,
  "format": "PNG",
  "mode": "RGB",
  "capacity": {
    "lsb": {"bytes": 776970, "kb": 758},
    "dct": {"bytes": 64800, "kb": 63, "note": "..."}
  }
}
```

### ErrorResponse

```json
{
  "error": "ErrorType",
  "detail": "Error description"
}
```

---

## Error Handling

### HTTP Status Codes

| Code | Meaning | Use Case |
|------|---------|----------|
| 200 | OK | Successful operation |
| 400 | Bad Request | Invalid input, capacity error |
| 401 | Unauthorized | Decryption failed (wrong credentials) |
| 500 | Internal Error | Unexpected server error |

### Error Response Format

```json
{
  "detail": "Error message describing the problem"
}
```

### Common Errors

| Status | Error | Solution |
|--------|-------|----------|
| 400 | "Must enable at least one of use_pin or use_rsa" | Set `use_pin` or `use_rsa` to true |
| 400 | "rsa_bits must be one of [2048, 3072, 4096]" | Use valid RSA key size |
| 400 | "Carrier image too small" | Use larger carrier image |
| 400 | "PIN must be 6-9 digits" | Fix PIN format |
| 400 | "Invalid embedding_mode" | Use `"lsb"` or `"dct"` |
| 400 | "output_format 'jpeg' requires embedding_mode 'dct'" | Use DCT mode for JPEG |
| 400 | "Message too long for DCT capacity" | Reduce message or use LSB |
| 401 | "Decryption failed. Check credentials." | Verify phrase, PIN, ref photo |
| 401 | "Invalid or missing Stegasoo header" | Wrong mode or corrupted image |

---

## Code Examples

### Python with requests

```python
import base64
import requests

BASE_URL = "http://localhost:8000"

# Generate credentials
response = requests.post(f"{BASE_URL}/generate", json={
    "use_pin": True,
    "use_rsa": False,
    "words_per_phrase": 3
})
creds = response.json()
print(f"PIN: {creds['pin']}")
print(f"Monday phrase: {creds['phrases']['Monday']}")

# Encode using multipart (LSB mode - default)
with open("reference.jpg", "rb") as ref, open("carrier.png", "rb") as carrier:
    response = requests.post(f"{BASE_URL}/encode/multipart", files={
        "reference_photo": ref,
        "carrier": carrier,
    }, data={
        "message": "Secret message",
        "day_phrase": "apple forest thunder",
        "pin": "123456"
    })
    
    with open("stego.png", "wb") as f:
        f.write(response.content)

# Encode using DCT mode for social media
with open("reference.jpg", "rb") as ref, open("carrier.png", "rb") as carrier:
    response = requests.post(f"{BASE_URL}/encode/multipart", files={
        "reference_photo": ref,
        "carrier": carrier,
    }, data={
        "message": "Secret message for Instagram",
        "day_phrase": "apple forest thunder",
        "pin": "123456",
        "embedding_mode": "dct",
        "output_format": "jpeg",
        "color_mode": "color"
    })
    
    with open("stego_social.jpg", "wb") as f:
        f.write(response.content)

# Decode using multipart (auto-detects mode)
with open("reference.jpg", "rb") as ref, open("stego.png", "rb") as stego:
    response = requests.post(f"{BASE_URL}/decode/multipart", files={
        "reference_photo": ref,
        "stego_image": stego,
    }, data={
        "day_phrase": "apple forest thunder",
        "pin": "123456"
    })
    
    result = response.json()
    print(f"Decoded: {result['message']}")
    print(f"Mode detected: {result['embedding_mode_detected']}")
```

### JavaScript/Node.js

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const BASE_URL = 'http://localhost:8000';

async function encodeDCT() {
    const form = new FormData();
    form.append('message', 'Secret message for social media');
    form.append('day_phrase', 'apple forest thunder');
    form.append('pin', '123456');
    form.append('embedding_mode', 'dct');
    form.append('output_format', 'jpeg');
    form.append('color_mode', 'color');
    form.append('reference_photo', fs.createReadStream('reference.jpg'));
    form.append('carrier', fs.createReadStream('carrier.png'));

    const response = await axios.post(`${BASE_URL}/encode/multipart`, form, {
        headers: form.getHeaders(),
        responseType: 'arraybuffer'
    });

    fs.writeFileSync('stego.jpg', response.data);
    console.log('Encoded with DCT mode');
    console.log('Embedding mode:', response.headers['x-stegasoo-embedding-mode']);
}

async function decode() {
    const form = new FormData();
    form.append('day_phrase', 'apple forest thunder');
    form.append('pin', '123456');
    form.append('reference_photo', fs.createReadStream('reference.jpg'));
    form.append('stego_image', fs.createReadStream('stego.jpg'));

    const response = await axios.post(`${BASE_URL}/decode/multipart`, form, {
        headers: form.getHeaders()
    });

    console.log('Decoded:', response.data.message);
    console.log('Mode detected:', response.data.embedding_mode_detected);
}

encodeDCT().then(decode);
```

### Go

```go
package main

import (
    "bytes"
    "encoding/json"
    "fmt"
    "io"
    "mime/multipart"
    "net/http"
    "os"
)

func main() {
    // Encode with DCT mode
    body := &bytes.Buffer{}
    writer := multipart.NewWriter(body)

    writer.WriteField("message", "Secret message")
    writer.WriteField("day_phrase", "apple forest thunder")
    writer.WriteField("pin", "123456")
    writer.WriteField("embedding_mode", "dct")
    writer.WriteField("output_format", "jpeg")
    writer.WriteField("color_mode", "color")

    ref, _ := os.Open("reference.jpg")
    refPart, _ := writer.CreateFormFile("reference_photo", "reference.jpg")
    io.Copy(refPart, ref)
    ref.Close()

    carrier, _ := os.Open("carrier.png")
    carrierPart, _ := writer.CreateFormFile("carrier", "carrier.png")
    io.Copy(carrierPart, carrier)
    carrier.Close()

    writer.Close()

    resp, _ := http.Post(
        "http://localhost:8000/encode/multipart",
        writer.FormDataContentType(),
        body,
    )

    // Check embedding mode from header
    fmt.Println("Embedding mode:", resp.Header.Get("X-Stegasoo-Embedding-Mode"))

    stego, _ := os.Create("stego.jpg")
    io.Copy(stego, resp.Body)
    stego.Close()
    resp.Body.Close()

    fmt.Println("Encoded successfully with DCT mode")
}
```

### Shell Script (Bash)

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"
REF_PHOTO="reference.jpg"
CARRIER="carrier.png"
PHRASE="apple forest thunder"
PIN="123456"
MESSAGE="Secret message"

# Encode with LSB (default)
echo "Encoding with LSB mode..."
curl -s -X POST "$BASE_URL/encode/multipart" \
  -F "message=$MESSAGE" \
  -F "day_phrase=$PHRASE" \
  -F "pin=$PIN" \
  -F "reference_photo=@$REF_PHOTO" \
  -F "carrier=@$CARRIER" \
  --output stego_lsb.png

echo "Encoded to stego_lsb.png"

# Encode with DCT for social media
echo "Encoding with DCT mode..."
curl -s -X POST "$BASE_URL/encode/multipart" \
  -F "message=$MESSAGE" \
  -F "day_phrase=$PHRASE" \
  -F "pin=$PIN" \
  -F "embedding_mode=dct" \
  -F "output_format=jpeg" \
  -F "color_mode=color" \
  -F "reference_photo=@$REF_PHOTO" \
  -F "carrier=@$CARRIER" \
  --output stego_dct.jpg

echo "Encoded to stego_dct.jpg"

# Decode (auto-detects mode)
echo "Decoding..."
RESULT=$(curl -s -X POST "$BASE_URL/decode/multipart" \
  -F "day_phrase=$PHRASE" \
  -F "pin=$PIN" \
  -F "reference_photo=@$REF_PHOTO" \
  -F "stego_image=@stego_dct.jpg")

echo "Decoded message: $(echo $RESULT | jq -r '.message')"
echo "Mode detected: $(echo $RESULT | jq -r '.embedding_mode_detected')"
```

---

## Rate Limiting

The API does not implement rate limiting by default. For production:

1. **Reverse Proxy**: Use nginx or Caddy rate limiting
2. **Application Level**: Add FastAPI middleware

Example nginx rate limiting:
```nginx
limit_req_zone $binary_remote_addr zone=stegasoo:10m rate=10r/s;

location /api/ {
    limit_req zone=stegasoo burst=20 nodelay;
    proxy_pass http://localhost:8000/;
}
```

---

## Security Considerations

### In Transit

- Use HTTPS in production
- Configure TLS at reverse proxy level

### Memory Usage

- Argon2id requires 256MB RAM per operation
- DCT mode adds ~100MB for scipy operations
- Concurrent requests can exhaust memory
- Limit workers based on available RAM

**Worker calculation:**
```
workers = (available_RAM - 512MB) / 350MB
```

### Input Validation

The API validates:
- PIN format (6-9 digits, no leading zero)
- Message size (max 50KB)
- Image size (max 5MB file, ~4MP dimensions)
- RSA key validity
- Embedding mode values
- Output format compatibility

### Credential Handling

- Credentials are never logged
- No persistent storage of secrets
- Memory cleared after operations

### Embedding Mode Security

| Mode | Consideration |
|------|--------------|
| LSB | Maximum capacity but fragile |
| DCT | Lower capacity but survives recompression |

Both modes use identical encryption (AES-256-GCM with Argon2id).

---

## Interactive Documentation

When the API is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## See Also

- [CLI Documentation](CLI.md) - Command-line interface
- [Web UI Documentation](WEB_UI.md) - Browser interface
- [README](README.md) - Project overview
