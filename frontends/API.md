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
- [Data Models](#data-models)
- [Error Handling](#error-handling)
- [Code Examples](#code-examples)
- [Rate Limiting](#rate-limiting)
- [Security Considerations](#security-considerations)

---

## Overview

The Stegasoo REST API provides programmatic access to all steganography operations:

- **Generate** credentials (phrases, PINs, RSA keys)
- **Encode** messages into images
- **Decode** messages from images
- **Analyze** image capacity

The API supports both JSON (base64-encoded images) and multipart form data (direct file uploads).

---

## Installation

### From PyPI

```bash
pip install stegasoo[api]
```

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
  "version": "2.0.1",
  "has_argon2": true,
  "day_names": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `version` | string | Stegasoo library version |
| `has_argon2` | boolean | Whether Argon2id is available |
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
  "date_str": null
}
```

#### Request Body

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | ✓ | Message to encode |
| `reference_photo_base64` | string | ✓ | Base64-encoded reference photo |
| `carrier_image_base64` | string | ✓ | Base64-encoded carrier image |
| `day_phrase` | string | ✓ | Today's passphrase |
| `pin` | string | * | Static PIN (6-9 digits) |
| `rsa_key_base64` | string | * | Base64-encoded RSA key PEM |
| `rsa_password` | string | | Password for RSA key |
| `date_str` | string | | Date override (YYYY-MM-DD) |

\* At least one of `pin` or `rsa_key_base64` required.

#### Response

```json
{
  "stego_image_base64": "iVBORw0KGgo...",
  "filename": "a1b2c3d4_20251227.png",
  "capacity_used_percent": 12.4,
  "date_used": "2025-12-27",
  "day_of_week": "Saturday"
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `stego_image_base64` | string | Base64-encoded stego PNG |
| `filename` | string | Suggested filename |
| `capacity_used_percent` | float | Percentage of capacity used |
| `date_used` | string | Date embedded in image (YYYY-MM-DD) |
| `day_of_week` | string | Day name for passphrase rotation |

#### cURL Example

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

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `message` | string | ✓ | Message to encode |
| `reference_photo` | file | ✓ | Reference photo file |
| `carrier` | file | ✓ | Carrier image file |
| `day_phrase` | string | ✓ | Today's passphrase |
| `pin` | string | * | Static PIN |
| `rsa_key` | file | * | RSA key file (.pem) |
| `rsa_password` | string | | Password for RSA key |
| `date_str` | string | | Date override (YYYY-MM-DD) |

\* At least one of `pin` or `rsa_key` required.

#### Response

Returns the PNG image directly with headers:
- `Content-Type: image/png`
- `Content-Disposition: attachment; filename=<generated_filename>.png`
- `X-Stegasoo-Date: 2025-12-27` (date used for encoding)
- `X-Stegasoo-Day: Saturday` (day of week for passphrase rotation)
- `X-Stegasoo-Capacity-Percent: 12.4` (capacity used)

#### cURL Examples

**With PIN:**
```bash
curl -X POST http://localhost:8000/encode/multipart \
  -F "message=Secret message" \
  -F "day_phrase=apple forest thunder" \
  -F "pin=123456" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png
```

**With RSA key:**
```bash
curl -X POST http://localhost:8000/encode/multipart \
  -F "message=Secret message" \
  -F "day_phrase=apple forest thunder" \
  -F "rsa_key=@mykey.pem" \
  -F "rsa_password=keypassword" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png
```

**With both PIN and RSA:**
```bash
curl -X POST http://localhost:8000/encode/multipart \
  -F "message=Maximum security message" \
  -F "day_phrase=apple forest thunder" \
  -F "pin=123456" \
  -F "rsa_key=@mykey.pem" \
  -F "rsa_password=keypassword" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png
```

**With custom date:**
```bash
curl -X POST http://localhost:8000/encode/multipart \
  -F "message=Backdated message" \
  -F "day_phrase=monday phrase here" \
  -F "pin=123456" \
  -F "date_str=2025-12-29" \
  -F "reference_photo=@reference.jpg" \
  -F "carrier=@carrier.png" \
  --output stego.png
```

---

### POST /decode (JSON)

Decode a message using base64-encoded images.

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

\* Must match the security factors used during encoding.

#### Response

```json
{
  "message": "Secret message here"
}
```

#### cURL Example

```bash
# Prepare base64-encoded images
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

Decode a message using direct file uploads.

#### Request

```http
POST /decode/multipart HTTP/1.1
Host: localhost:8000
Content-Type: multipart/form-data
```

#### Form Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `stego_image` | file | ✓ | Stego image file |
| `reference_photo` | file | ✓ | Reference photo file |
| `day_phrase` | string | ✓ | Passphrase for encoding day |
| `pin` | string | * | Static PIN |
| `rsa_key` | file | * | RSA key file |
| `rsa_password` | string | | Password for RSA key |

#### Response

```json
{
  "message": "Secret message here"
}
```

#### cURL Examples

**With PIN:**
```bash
curl -X POST http://localhost:8000/decode/multipart \
  -F "day_phrase=apple forest thunder" \
  -F "pin=123456" \
  -F "reference_photo=@reference.jpg" \
  -F "stego_image=@stego.png"
```

**With RSA key:**
```bash
curl -X POST http://localhost:8000/decode/multipart \
  -F "day_phrase=apple forest thunder" \
  -F "rsa_key=@mykey.pem" \
  -F "rsa_password=keypassword" \
  -F "reference_photo=@reference.jpg" \
  -F "stego_image=@stego.png"
```

---

### POST /image/info

Get information about an image's capacity.

#### Request

```http
POST /image/info HTTP/1.1
Host: localhost:8000
Content-Type: multipart/form-data
```

#### Form Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `image` | file | ✓ | Image file to analyze |

#### Response

```json
{
  "width": 1920,
  "height": 1080,
  "pixels": 2073600,
  "capacity_bytes": 776970,
  "capacity_kb": 758
}
```

#### Response Fields

| Field | Type | Description |
|-------|------|-------------|
| `width` | integer | Image width in pixels |
| `height` | integer | Image height in pixels |
| `pixels` | integer | Total pixel count |
| `capacity_bytes` | integer | Maximum message capacity (bytes) |
| `capacity_kb` | integer | Maximum message capacity (KB) |

#### cURL Example

```bash
curl -X POST http://localhost:8000/image/info \
  -F "image=@myimage.png"
```

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
  "date_str": "YYYY-MM-DD"
}
```

### EncodeResponse

```json
{
  "stego_image_base64": "string",
  "filename": "string",
  "capacity_used_percent": 12.4,
  "date_used": "YYYY-MM-DD",
  "day_of_week": "Saturday"
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
  "message": "string"
}
```

### ImageInfoResponse

```json
{
  "width": 1920,
  "height": 1080,
  "pixels": 2073600,
  "capacity_bytes": 776970,
  "capacity_kb": 758
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
| 401 | "Decryption failed. Check credentials." | Verify phrase, PIN, ref photo |
| 400 | "Message too long" | Reduce message size or use larger carrier |

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

# Encode using multipart
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

# Decode using multipart
with open("reference.jpg", "rb") as ref, open("stego.png", "rb") as stego:
    response = requests.post(f"{BASE_URL}/decode/multipart", files={
        "reference_photo": ref,
        "stego_image": stego,
    }, data={
        "day_phrase": "apple forest thunder",
        "pin": "123456"
    })
    
    print(f"Decoded: {response.json()['message']}")
```

### JavaScript/Node.js

```javascript
const FormData = require('form-data');
const fs = require('fs');
const axios = require('axios');

const BASE_URL = 'http://localhost:8000';

async function encode() {
    const form = new FormData();
    form.append('message', 'Secret message');
    form.append('day_phrase', 'apple forest thunder');
    form.append('pin', '123456');
    form.append('reference_photo', fs.createReadStream('reference.jpg'));
    form.append('carrier', fs.createReadStream('carrier.png'));

    const response = await axios.post(`${BASE_URL}/encode/multipart`, form, {
        headers: form.getHeaders(),
        responseType: 'arraybuffer'
    });

    fs.writeFileSync('stego.png', response.data);
    console.log('Encoded successfully');
}

async function decode() {
    const form = new FormData();
    form.append('day_phrase', 'apple forest thunder');
    form.append('pin', '123456');
    form.append('reference_photo', fs.createReadStream('reference.jpg'));
    form.append('stego_image', fs.createReadStream('stego.png'));

    const response = await axios.post(`${BASE_URL}/decode/multipart`, form, {
        headers: form.getHeaders()
    });

    console.log('Decoded:', response.data.message);
}

encode().then(decode);
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
    // Encode
    body := &bytes.Buffer{}
    writer := multipart.NewWriter(body)

    writer.WriteField("message", "Secret message")
    writer.WriteField("day_phrase", "apple forest thunder")
    writer.WriteField("pin", "123456")

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

    stego, _ := os.Create("stego.png")
    io.Copy(stego, resp.Body)
    stego.Close()
    resp.Body.Close()

    fmt.Println("Encoded successfully")
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

# Encode
echo "Encoding..."
curl -s -X POST "$BASE_URL/encode/multipart" \
  -F "message=$MESSAGE" \
  -F "day_phrase=$PHRASE" \
  -F "pin=$PIN" \
  -F "reference_photo=@$REF_PHOTO" \
  -F "carrier=@$CARRIER" \
  --output stego.png

echo "Encoded to stego.png"

# Decode
echo "Decoding..."
DECODED=$(curl -s -X POST "$BASE_URL/decode/multipart" \
  -F "day_phrase=$PHRASE" \
  -F "pin=$PIN" \
  -F "reference_photo=@$REF_PHOTO" \
  -F "stego_image=@stego.png" | jq -r '.message')

echo "Decoded message: $DECODED"
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
- Concurrent requests can exhaust memory
- Limit workers based on available RAM

### Input Validation

The API validates:
- PIN format (6-9 digits, no leading zero)
- Message size (max 50KB)
- Image size (max 5MB file, ~4MP dimensions)
- RSA key validity

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
- [README](README.md) - Project overview
