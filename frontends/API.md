# Stegasoo REST API Documentation (v3.2.0)

Complete REST API reference for Stegasoo steganography operations.

## Table of Contents

- [Overview](#overview)
- [What's New in v3.2.0](#whats-new-in-v320)
- [Installation](#installation)
- [Authentication](#authentication)
- [Base URL](#base-url)
- [Endpoints](#endpoints)
  - [GET /](#get--status)
  - [GET /modes](#get-modes)
  - [POST /generate](#post-generate)
  - [POST /encode](#post-encode-json)
  - [POST /encode/file](#post-encodefile)
  - [POST /encode/multipart](#post-encodemultipart)
  - [POST /decode](#post-decode-json)
  - [POST /decode/multipart](#post-decodemultipart)
  - [POST /compare](#post-compare)
  - [POST /will-fit](#post-will-fit)
  - [POST /image/info](#post-imageinfo)
  - [POST /extract-key-from-qr](#post-extract-key-from-qr)
- [Embedding Modes](#embedding-modes)
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Code Examples](#code-examples)
- [Rate Limiting](#rate-limiting)
- [Security Considerations](#security-considerations)

---

## Overview

The Stegasoo REST API provides programmatic access to all steganography operations:

- **Generate** credentials (passphrase, PINs, RSA keys)
- **Encode** messages or files into images (LSB or DCT mode)
- **Decode** messages or files from images (auto-detects mode)
- **Analyze** image capacity and compare modes

The API supports both JSON (base64-encoded images) and multipart form data (direct file uploads).

---

## What's New in v3.2.0

Version 3.2.0 introduces breaking changes to simplify the API:

| Change | Before (v3.1) | After (v3.2.0) |
|--------|---------------|----------------|
| Passphrase | Daily rotation (`phrases` dict) | Single `passphrase` string |
| Date parameter | `date_str` required/optional | Removed entirely |
| Field name | `day_phrase` | `passphrase` |
| Default words | 3 words | 4 words |

**Key benefits:**
- ✅ No need to track encoding dates
- ✅ Simpler request/response models
- ✅ True asynchronous communications
- ✅ Stronger default security (4 words = ~44 bits)

**Breaking Change:** v3.2.0 cannot decode images created with v3.1.x due to different key derivation.

---

## Installation

### From PyPI

```bash
pip install stegasoo[api]
```

This automatically installs DCT dependencies (scipy) for full functionality.

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
  "version": "3.2.0",
  "has_argon2": true,
  "has_qrcode_read": true,
  "has_dct": true,
  "max_payload_kb": 500,
  "available_modes": ["lsb", "dct"],
  "dct_features": {
    "output_formats": ["png", "jpeg"],
    "color_modes": ["grayscale", "color"],
    "default_output_format": "png",
    "default_color_mode": "grayscale"
  },
  "breaking_changes": {
    "date_removed": "No date_str parameter needed - encode/decode anytime",
    "passphrase_renamed": "day_phrase → passphrase (single passphrase, no daily rotation)",
    "format_version": 4,
    "backward_compatible": false
  }
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Stegasoo library version |
| `has_argon2` | boolean | Whether Argon2id is available |
| `has_qrcode_read` | boolean | Whether QR code reading is available |
| `has_dct` | boolean | Whether DCT mode is available (scipy) |
| `max_payload_kb` | integer | Maximum payload size in KB |
| `available_modes` | array | Available embedding modes |
| `dct_features` | object | DCT mode options (if available) |
| `breaking_changes` | object | v3.2.0 breaking changes info |

#### cURL Example

```bash
curl http://localhost:8000/
```

---

### GET /modes

Get available embedding modes and their status.

#### Request

```http
GET /modes HTTP/1.1
Host: localhost:8000
```

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
    "description": "Embed in DCT coefficients, frequency domain steganography",
    "output_formats": ["png", "jpeg"],
    "color_modes": ["grayscale", "color"],
    "capacity_ratio": "~20% of LSB",
    "requires": "scipy"
  }
}
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
  "words_per_passphrase": 4
}
```

#### Request Body

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `use_pin` | boolean | `true` | Generate a PIN |
| `use_rsa` | boolean | `false` | Generate an RSA key |
| `pin_length` | integer | `6` | PIN length (6-9) |
| `rsa_bits` | integer | `2048` | RSA key size (2048, 3072, 4096) |
| `words_per_passphrase` | integer | `4` | Words per passphrase (3-12) |

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
  },
  "phrases": null
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `passphrase` | string | Single passphrase (v3.2.0) |
| `pin` | string\|null | Generated PIN (if requested) |
| `rsa_key_pem` | string\|null | PEM-encoded RSA key (if requested) |
| `entropy.passphrase` | integer | Entropy from passphrase (bits) |
| `entropy.pin` | integer | Entropy from PIN (bits) |
| `entropy.rsa` | integer | Entropy from RSA key (bits) |
| `entropy.total` | integer | Combined entropy (bits) |
| `phrases` | null | Deprecated field (always null in v3.2.0) |

#### cURL Examples

**Default (PIN with 4-word passphrase):**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"use_pin": true}'
```

**RSA only with 6-word passphrase:**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{"use_pin": false, "use_rsa": true, "rsa_bits": 4096, "words_per_passphrase": 6}'
```

**Both PIN and RSA:**
```bash
curl -X POST http://localhost:8000/generate \
  -H "Content-Type: application/json" \
  -d '{
    "use_pin": true,
    "use_rsa": true,
    "pin_length": 9,
    "rsa_bits": 4096,
    "words_per_passphrase": 6
  }'
```

---

### POST /encode (JSON)

Encode a text message using base64-encoded images.

#### Request

```http
POST /encode HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "message": "Secret message here",
  "reference_photo_base64": "iVBORw0KGgo...",
  "carrier_image_base64": "iVBORw0KGgo...",
  "passphrase": "apple forest thunder mountain",
  "pin": "123456",
  "rsa_key_base64": null,
  "rsa_password": null,
  "embed_mode": "lsb",
  "dct_output_format": "png",
  "dct_color_mode": "grayscale"
}
```

#### Request Body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | ✓ | | Message to encode |
| `reference_photo_base64` | string | ✓ | | Base64-encoded reference photo |
| `carrier_image_base64` | string | ✓ | | Base64-encoded carrier image |
| `passphrase` | string | ✓ | | Passphrase (v3.2.0) |
| `pin` | string | * | | Static PIN (6-9 digits) |
| `rsa_key_base64` | string | * | | Base64-encoded RSA key PEM |
| `rsa_password` | string | | | Password for RSA key |
| `embed_mode` | string | | `"lsb"` | `"lsb"` or `"dct"` |
| `dct_output_format` | string | | `"png"` | `"png"` or `"jpeg"` (DCT only) |
| `dct_color_mode` | string | | `"grayscale"` | `"grayscale"` or `"color"` (DCT only) |

\* At least one of `pin` or `rsa_key_base64` required.

#### Response

```json
{
  "stego_image_base64": "iVBORw0KGgo...",
  "filename": "a1b2c3d4.png",
  "capacity_used_percent": 12.4,
  "embed_mode": "lsb",
  "output_format": "png",
  "color_mode": "color",
  "date_used": null,
  "day_of_week": null
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `stego_image_base64` | string | Base64-encoded stego image |
| `filename` | string | Suggested filename |
| `capacity_used_percent` | float | Percentage of capacity used |
| `embed_mode` | string | Mode used: `"lsb"` or `"dct"` |
| `output_format` | string | Output format: `"png"` or `"jpeg"` |
| `color_mode` | string | Color mode: `"color"` or `"grayscale"` |
| `date_used` | null | Deprecated (always null in v3.2.0) |
| `day_of_week` | null | Deprecated (always null in v3.2.0) |

#### cURL Example (LSB Mode)

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
    \"passphrase\": \"apple forest thunder mountain\",
    \"pin\": \"123456\"
  }" | jq -r '.stego_image_base64' | base64 -d > stego.png
```

#### cURL Example (DCT Mode with JPEG)

```bash
curl -X POST http://localhost:8000/encode \
  -H "Content-Type: application/json" \
  -d "{
    \"message\": \"Secret message\",
    \"reference_photo_base64\": \"$REF_B64\",
    \"carrier_image_base64\": \"$CARRIER_B64\",
    \"passphrase\": \"apple forest thunder mountain\",
    \"pin\": \"123456\",
    \"embed_mode\": \"dct\",
    \"dct_output_format\": \"jpeg\",
    \"dct_color_mode\": \"color\"
  }" | jq -r '.stego_image_base64' | base64 -d > stego.jpg
```

---

### POST /encode/file

Encode a binary file using base64-encoded data.

#### Request

```http
POST /encode/file HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "file_data_base64": "JVBERi0xLjQK...",
  "filename": "secret.pdf",
  "mime_type": "application/pdf",
  "reference_photo_base64": "iVBORw0KGgo...",
  "carrier_image_base64": "iVBORw0KGgo...",
  "passphrase": "apple forest thunder mountain",
  "pin": "123456",
  "embed_mode": "lsb"
}
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `file_data_base64` | string | ✓ | Base64-encoded file data |
| `filename` | string | ✓ | Original filename |
| `mime_type` | string | | MIME type of file |
| `reference_photo_base64` | string | ✓ | Base64-encoded reference photo |
| `carrier_image_base64` | string | ✓ | Base64-encoded carrier image |
| `passphrase` | string | ✓ | Passphrase |
| `pin` | string | * | Static PIN |
| `rsa_key_base64` | string | * | Base64-encoded RSA key |
| `embed_mode` | string | | `"lsb"` or `"dct"` |
| `dct_output_format` | string | | `"png"` or `"jpeg"` |
| `dct_color_mode` | string | | `"grayscale"` or `"color"` |

#### Response

Same as `/encode` endpoint.

---

### POST /encode/multipart

Encode using direct file uploads. Returns the stego image directly.

#### Form Fields

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `passphrase` | string | ✓ | | Passphrase (v3.2.0) |
| `reference_photo` | file | ✓ | | Reference photo file |
| `carrier` | file | ✓ | | Carrier image file |
| `message` | string | * | | Text message to encode |
| `payload_file` | file | * | | Binary file to embed |
| `pin` | string | ** | | Static PIN |
| `rsa_key` | file | ** | | RSA key file (.pem) |
| `rsa_key_qr` | file | ** | | RSA key from QR code image |
| `rsa_password` | string | | | Password for RSA key |
| `embed_mode` | string | | `"lsb"` | `"lsb"` or `"dct"` |
| `dct_output_format` | string | | `"png"` | `"png"` or `"jpeg"` |
| `dct_color_mode` | string | | `"grayscale"` | `"grayscale"` or `"color"` |

\* At least one of `message` or `payload_file` required.
\*\* At least one of `pin`, `rsa_key`, or `rsa_key_qr` required.

#### Response

Returns the image directly with headers:

```http
HTTP/1.1 200 OK
Content-Type: image/png
Content-Disposition: attachment; filename="a1b2c3d4.png"
X-Stegasoo-Capacity-Percent: 12.4
X-Stegasoo-Embed-Mode: lsb
X-Stegasoo-Output-Format: png
X-Stegasoo-Color-Mode: color
X-Stegasoo-Version: 3.2.0

<binary image data>
```

#### Response Headers

| Header | Description |
|--------|-------------|
| `Content-Type` | `image/png` or `image/jpeg` |
| `Content-Disposition` | Suggested filename |
| `X-Stegasoo-Capacity-Percent` | Capacity percentage used |
| `X-Stegasoo-Embed-Mode` | `lsb` or `dct` |
| `X-Stegasoo-Output-Format` | `png` or `jpeg` |
| `X-Stegasoo-Color-Mode` | `color` or `grayscale` |
| `X-Stegasoo-Version` | API version |

#### cURL Example (LSB)

```bash
curl -X POST http://localhost:8000/encode/multipart \
  -F "passphrase=apple forest thunder mountain" \
  -F "pin=123456" \
  -F "message=Secret message" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png
```

#### cURL Example (DCT + JPEG)

```bash
curl -X POST http://localhost:8000/encode/multipart \
  -F "passphrase=apple forest thunder mountain" \
  -F "pin=123456" \
  -F "message=Secret message for social media" \
  -F "embed_mode=dct" \
  -F "dct_output_format=jpeg" \
  -F "dct_color_mode=color" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.jpg
```

#### cURL Example (Embed File)

```bash
curl -X POST http://localhost:8000/encode/multipart \
  -F "passphrase=apple forest thunder mountain" \
  -F "pin=123456" \
  -F "payload_file=@secret.pdf" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png
```

---

### POST /decode (JSON)

Decode a message or file using base64-encoded images. Auto-detects embedding mode.

#### Request

```http
POST /decode HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "stego_image_base64": "iVBORw0KGgo...",
  "reference_photo_base64": "iVBORw0KGgo...",
  "passphrase": "apple forest thunder mountain",
  "pin": "123456",
  "rsa_key_base64": null,
  "rsa_password": null,
  "embed_mode": "auto"
}
```

#### Request Body

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `stego_image_base64` | string | ✓ | | Base64-encoded stego image |
| `reference_photo_base64` | string | ✓ | | Base64-encoded reference photo |
| `passphrase` | string | ✓ | | Passphrase |
| `pin` | string | * | | Static PIN |
| `rsa_key_base64` | string | * | | Base64-encoded RSA key |
| `rsa_password` | string | | | Password for RSA key |
| `embed_mode` | string | | `"auto"` | `"auto"`, `"lsb"`, or `"dct"` |

\* Must match security factors used during encoding.

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
  "file_data_base64": "JVBERi0xLjQK...",
  "filename": "secret.pdf",
  "mime_type": "application/pdf"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `payload_type` | string | `"text"` or `"file"` |
| `message` | string\|null | Decoded message (if text) |
| `file_data_base64` | string\|null | Base64-encoded file (if file) |
| `filename` | string\|null | Original filename (if file) |
| `mime_type` | string\|null | MIME type (if file) |

#### cURL Example

```bash
STEGO_B64=$(base64 -w0 stego.png)
REF_B64=$(base64 -w0 reference.jpg)

curl -X POST http://localhost:8000/decode \
  -H "Content-Type: application/json" \
  -d "{
    \"stego_image_base64\": \"$STEGO_B64\",
    \"reference_photo_base64\": \"$REF_B64\",
    \"passphrase\": \"apple forest thunder mountain\",
    \"pin\": \"123456\"
  }"
```

---

### POST /decode/multipart

Decode using direct file uploads. Auto-detects embedding mode.

#### Form Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `passphrase` | string | ✓ | Passphrase |
| `reference_photo` | file | ✓ | Reference photo file |
| `stego_image` | file | ✓ | Stego image file |
| `pin` | string | * | Static PIN |
| `rsa_key` | file | * | RSA key file (.pem) |
| `rsa_key_qr` | file | * | RSA key from QR code image |
| `rsa_password` | string | | Password for RSA key |
| `embed_mode` | string | | `"auto"`, `"lsb"`, or `"dct"` |

#### Response

Same JSON format as `/decode` endpoint.

#### cURL Example

```bash
curl -X POST http://localhost:8000/decode/multipart \
  -F "passphrase=apple forest thunder mountain" \
  -F "pin=123456" \
  -F "reference_photo=@reference.jpg" \
  -F "stego_image=@stego.png"
```

---

### POST /compare

Compare LSB and DCT embedding modes for a carrier image.

#### Request

```http
POST /compare HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "carrier_image_base64": "iVBORw0KGgo...",
  "payload_size": 50000
}
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `carrier_image_base64` | string | ✓ | Base64-encoded carrier image |
| `payload_size` | integer | | Optional payload size to check |

#### Response

```json
{
  "width": 1920,
  "height": 1080,
  "lsb": {
    "capacity_bytes": 776970,
    "capacity_kb": 758.8,
    "available": true,
    "output_format": "PNG"
  },
  "dct": {
    "capacity_bytes": 64800,
    "capacity_kb": 63.3,
    "available": true,
    "output_formats": ["png", "jpeg"],
    "color_modes": ["grayscale", "color"],
    "ratio_vs_lsb_percent": 8.3
  },
  "payload_check": {
    "size_bytes": 50000,
    "fits_lsb": true,
    "fits_dct": true
  },
  "recommendation": "dct (payload fits, better stealth)"
}
```

---

### POST /will-fit

Check if a payload of given size will fit in a carrier image.

#### Request

```http
POST /will-fit HTTP/1.1
Host: localhost:8000
Content-Type: application/json

{
  "carrier_image_base64": "iVBORw0KGgo...",
  "payload_size": 50000,
  "embed_mode": "lsb"
}
```

#### Response

```json
{
  "fits": true,
  "payload_size": 50000,
  "capacity": 776970,
  "usage_percent": 6.4,
  "headroom": 726970,
  "mode": "lsb"
}
```

---

### POST /image/info

Get image information and capacity.

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
  "capacity_bytes": 776970,
  "capacity_kb": 758,
  "modes": {
    "lsb": {
      "capacity_bytes": 776970,
      "capacity_kb": 758.8,
      "available": true,
      "output_format": "PNG"
    },
    "dct": {
      "capacity_bytes": 64800,
      "capacity_kb": 63.3,
      "available": true,
      "output_format": "PNG/JPEG (grayscale or color)"
    }
  }
}
```

---

### POST /extract-key-from-qr

Extract RSA key from a QR code image.

#### Request (Multipart)

```bash
curl -X POST http://localhost:8000/extract-key-from-qr \
  -F "qr_image=@keyqr.png"
```

#### Response

```json
{
  "success": true,
  "key_pem": "-----BEGIN PRIVATE KEY-----\n...",
  "error": null
}
```

---

## Embedding Modes

### LSB Mode (Default)

**Least Significant Bit** embedding modifies pixel values directly.

| Aspect | Details |
|--------|---------|
| **Parameter** | `"embed_mode": "lsb"` |
| **Capacity** | ~3 bits/pixel (~375 KB for 1920×1080) |
| **Output** | PNG only (lossless required) |
| **Resilience** | ❌ Destroyed by JPEG compression |
| **Best For** | Maximum capacity, controlled channels |

### DCT Mode

**Discrete Cosine Transform** embedding hides data in frequency coefficients.

| Aspect | Details |
|--------|---------|
| **Parameter** | `"embed_mode": "dct"` |
| **Capacity** | ~0.25 bits/pixel (~65 KB for 1920×1080) |
| **Output** | PNG or JPEG |
| **Resilience** | ✅ Better resistance to analysis |
| **Best For** | Stealth requirements |

### DCT Options

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| `dct_output_format` | `"png"`, `"jpeg"` | `"png"` | Output image format |
| `dct_color_mode` | `"grayscale"`, `"color"` | `"grayscale"` | Color processing mode |

### Capacity Comparison

| Mode | 1920×1080 Capacity |
|------|-------------------|
| LSB (PNG) | ~375 KB |
| DCT (PNG) | ~65 KB |
| DCT (JPEG) | ~50 KB |

---

## Data Models

### GenerateRequest

```json
{
  "use_pin": true,
  "use_rsa": false,
  "pin_length": 6,
  "rsa_bits": 2048,
  "words_per_passphrase": 4
}
```

### GenerateResponse

```json
{
  "passphrase": "word1 word2 word3 word4",
  "pin": "123456",
  "rsa_key_pem": null,
  "entropy": {"passphrase": 44, "pin": 19, "rsa": 0, "total": 63},
  "phrases": null
}
```

### EncodeRequest

```json
{
  "message": "string",
  "reference_photo_base64": "string",
  "carrier_image_base64": "string",
  "passphrase": "string",
  "pin": "string",
  "rsa_key_base64": "string",
  "rsa_password": "string",
  "embed_mode": "lsb",
  "dct_output_format": "png",
  "dct_color_mode": "grayscale"
}
```

### EncodeResponse

```json
{
  "stego_image_base64": "string",
  "filename": "string",
  "capacity_used_percent": 12.4,
  "embed_mode": "lsb",
  "output_format": "png",
  "color_mode": "color",
  "date_used": null,
  "day_of_week": null
}
```

### DecodeRequest

```json
{
  "stego_image_base64": "string",
  "reference_photo_base64": "string",
  "passphrase": "string",
  "pin": "string",
  "rsa_key_base64": "string",
  "rsa_password": "string",
  "embed_mode": "auto"
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

### ErrorResponse

```json
{
  "detail": "Error message describing the problem"
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
| 501 | Not Implemented | Feature unavailable (e.g., QR without pyzbar) |

### Common Errors

| Status | Error | Solution |
|--------|-------|----------|
| 400 | "Must enable at least one of use_pin or use_rsa" | Set `use_pin` or `use_rsa` to true |
| 400 | "Carrier image too small" | Use larger carrier image |
| 400 | "DCT mode requires scipy" | Install scipy |
| 400 | "embed_mode must be 'lsb' or 'dct'" | Fix embed_mode value |
| 401 | "Decryption failed. Check credentials." | Verify passphrase, PIN, ref photo |
| 501 | "QR code reading not available" | Install pyzbar and libzbar |

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
    "words_per_passphrase": 4
})
creds = response.json()
print(f"Passphrase: {creds['passphrase']}")
print(f"PIN: {creds['pin']}")

# Encode using multipart (LSB mode)
with open("reference.jpg", "rb") as ref, open("carrier.png", "rb") as carrier:
    response = requests.post(f"{BASE_URL}/encode/multipart", files={
        "reference_photo": ref,
        "carrier": carrier,
    }, data={
        "message": "Secret message",
        "passphrase": "apple forest thunder mountain",
        "pin": "123456"
    })
    
    with open("stego.png", "wb") as f:
        f.write(response.content)

# Encode with DCT for social media
with open("reference.jpg", "rb") as ref, open("carrier.png", "rb") as carrier:
    response = requests.post(f"{BASE_URL}/encode/multipart", files={
        "reference_photo": ref,
        "carrier": carrier,
    }, data={
        "message": "Secret message for Instagram",
        "passphrase": "apple forest thunder mountain",
        "pin": "123456",
        "embed_mode": "dct",
        "dct_output_format": "jpeg",
        "dct_color_mode": "color"
    })
    
    with open("stego_social.jpg", "wb") as f:
        f.write(response.content)

# Decode (auto-detects mode)
with open("reference.jpg", "rb") as ref, open("stego.png", "rb") as stego:
    response = requests.post(f"{BASE_URL}/decode/multipart", files={
        "reference_photo": ref,
        "stego_image": stego,
    }, data={
        "passphrase": "apple forest thunder mountain",
        "pin": "123456"
    })
    
    result = response.json()
    if result['payload_type'] == 'text':
        print(f"Decoded: {result['message']}")
    else:
        # Save decoded file
        file_data = base64.b64decode(result['file_data_base64'])
        with open(result['filename'], 'wb') as f:
            f.write(file_data)
```

### JavaScript/Node.js

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const BASE_URL = 'http://localhost:8000';

async function generate() {
    const response = await axios.post(`${BASE_URL}/generate`, {
        use_pin: true,
        words_per_passphrase: 4
    });
    
    console.log('Passphrase:', response.data.passphrase);
    console.log('PIN:', response.data.pin);
    return response.data;
}

async function encode(passphrase, pin) {
    const form = new FormData();
    form.append('passphrase', passphrase);
    form.append('pin', pin);
    form.append('message', 'Secret message');
    form.append('reference_photo', fs.createReadStream('reference.jpg'));
    form.append('carrier', fs.createReadStream('carrier.png'));

    const response = await axios.post(`${BASE_URL}/encode/multipart`, form, {
        headers: form.getHeaders(),
        responseType: 'arraybuffer'
    });

    fs.writeFileSync('stego.png', response.data);
    console.log('Encoded to stego.png');
}

async function decode(passphrase, pin) {
    const form = new FormData();
    form.append('passphrase', passphrase);
    form.append('pin', pin);
    form.append('reference_photo', fs.createReadStream('reference.jpg'));
    form.append('stego_image', fs.createReadStream('stego.png'));

    const response = await axios.post(`${BASE_URL}/decode/multipart`, form, {
        headers: form.getHeaders()
    });

    console.log('Decoded:', response.data.message);
}

// Usage
generate()
    .then(creds => encode(creds.passphrase, creds.pin))
    .then(() => decode('apple forest thunder mountain', '123456'));
```

### Shell Script (Bash)

```bash
#!/bin/bash

BASE_URL="http://localhost:8000"
PASSPHRASE="apple forest thunder mountain"
PIN="123456"

# Generate credentials
echo "Generating credentials..."
CREDS=$(curl -s -X POST "$BASE_URL/generate" \
  -H "Content-Type: application/json" \
  -d '{"use_pin": true, "words_per_passphrase": 4}')

echo "Passphrase: $(echo $CREDS | jq -r '.passphrase')"
echo "PIN: $(echo $CREDS | jq -r '.pin')"

# Encode
echo "Encoding..."
curl -s -X POST "$BASE_URL/encode/multipart" \
  -F "passphrase=$PASSPHRASE" \
  -F "pin=$PIN" \
  -F "message=Secret message" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png

echo "Encoded to stego.png"

# Decode
echo "Decoding..."
RESULT=$(curl -s -X POST "$BASE_URL/decode/multipart" \
  -F "passphrase=$PASSPHRASE" \
  -F "pin=$PIN" \
  -F "reference_photo=@reference.jpg" \
  -F "stego_image=@stego.png")

echo "Decoded: $(echo $RESULT | jq -r '.message')"
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
- Passphrase presence
- Image size limits
- RSA key validity
- Embedding mode values
- Output format compatibility

### Credential Handling

- Credentials are never logged
- No persistent storage of secrets
- Memory cleared after operations

---

## Interactive Documentation

When the API is running, visit:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

---

## See Also

- [CLI Documentation](CLI.md) - Command-line interface
- [Web UI Documentation](WEB_UI.md) - Browser interface
- [API Update Summary](api/API_UPDATE_SUMMARY_V3.2.0.md) - Migration guide
- [README](../README.md) - Project overview
