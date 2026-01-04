# Stegasoo Web UI Documentation (v4.0.2)

Complete guide for the Stegasoo web-based steganography interface.

## Table of Contents

- [Overview](#overview)
- [What's New in v4.0.2](#whats-new-in-v402)
- [Authentication & HTTPS](#authentication--https)
- [Installation & Setup](#installation--setup)
- [Pages & Features](#pages--features)
  - [Home Page](#home-page)
  - [Generate Credentials](#generate-credentials)
  - [Encode Message](#encode-message)
  - [Decode Message](#decode-message)
  - [About Page](#about-page)
- [Embedding Modes](#embedding-modes)
  - [DCT Mode (Default)](#dct-mode-default)
  - [LSB Mode](#lsb-mode)
- [User Interface Guide](#user-interface-guide)
- [Workflow Examples](#workflow-examples)
- [Security Features](#security-features)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Mobile Support](#mobile-support)

---

## Overview

The Stegasoo Web UI provides a user-friendly browser-based interface for:

- **Generating** secure credentials (passphrase, PINs, RSA keys)
- **Encoding** secret messages or files into images
- **Decoding** hidden messages or files from images
- **Learning** about the security model

Built with Flask, Bootstrap 5, and a modern dark theme.

### Features

- ✅ Drag-and-drop file uploads
- ✅ Image previews with scan animations
- ✅ Native sharing (Web Share API)
- ✅ Responsive design (mobile-friendly)
- ✅ Password-protected RSA key downloads
- ✅ Real-time entropy calculations
- ✅ Automatic file cleanup
- ✅ **DCT steganography mode** - Now the default for social media resilience
- ✅ **Color mode selection** - Preserve carrier colors
- ✅ **File embedding** - Hide files, not just text
- ✅ **QR code RSA keys** - Scan to import keys
- ✅ **v3.3.0: Streamlined UI** - Compact mode selection, improved form flow

---

## What's New in v4.0.2

Version 4.0.2 adds authentication and HTTPS support for secure home network deployment:

| Feature | Description |
|---------|-------------|
| **Authentication** | Single-admin login with SQLite3 user storage |
| **First-run setup** | Wizard to create admin account on first access |
| **Account management** | Change password page |
| **Optional HTTPS** | Auto-generated self-signed certificates |
| **UI improvements** | Larger QR previews, consistent panel styling |

**Key benefits:**
- ✅ Secure your Web UI with username/password
- ✅ No manual database setup - automatic on first run
- ✅ HTTPS with auto-generated certs for home networks
- ✅ Configurable via environment variables
- ✅ Improved readability of QR preview panels

---

## Authentication & HTTPS

### Overview

v4.0.2 adds optional authentication and HTTPS for secure home network deployment.

### First-Run Setup

On first access, you'll be prompted to create an admin account:

1. Navigate to `http://localhost:5000`
2. You'll be redirected to `/setup`
3. Enter a username (e.g., "admin")
4. Enter a password (minimum 8 characters)
5. Confirm the password
6. Click "Create Admin Account"

The admin account is stored in `frontends/web/instance/stegasoo.db` (SQLite).

### Login

After setup, protected pages require login:

- **Protected routes:** `/encode`, `/decode`, `/generate`, `/account`, `/api/*`
- **Public routes:** `/`, `/about`, `/login`, `/setup`

### Account Management

Access `/account` to:
- View current username
- Change your password
- Logout

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STEGASOO_AUTH_ENABLED` | `true` | Enable/disable authentication |
| `STEGASOO_HTTPS_ENABLED` | `false` | Enable HTTPS with self-signed certs |
| `STEGASOO_HOSTNAME` | `localhost` | Hostname for certificate generation |

### Enabling HTTPS

```bash
# Enable HTTPS
export STEGASOO_HTTPS_ENABLED=true
export STEGASOO_HOSTNAME=stegasoo.local  # Optional: your hostname

cd frontends/web
python app.py
```

On first run with HTTPS enabled:
- Generates RSA 2048-bit private key
- Creates self-signed X.509 certificate (365 days validity)
- Stores in `frontends/web/certs/`
- Server starts on https://localhost:5000

**Note:** Browsers will show a security warning for self-signed certificates. This is expected for home network use.

**Tip:** To avoid browser warnings, use [mkcert](https://github.com/FiloSottile/mkcert) to generate locally-trusted certificates:

```bash
# Install mkcert and create local CA (one-time)
mkcert -install

# Generate trusted certs for your Pi
mkcert -key-file key.pem -cert-file cert.pem stegasoo.local localhost 127.0.0.1 YOUR_PI_IP

# Copy to certs directory
mv key.pem cert.pem frontends/web/certs/
```

### Disabling Authentication

For development or trusted networks:

```bash
export STEGASOO_AUTH_ENABLED=false
cd frontends/web
python app.py
```

### Docker Configuration

```yaml
# docker-compose.yml
services:
  web:
    environment:
      STEGASOO_AUTH_ENABLED: "true"
      STEGASOO_HTTPS_ENABLED: "true"
      STEGASOO_HOSTNAME: "stegasoo.local"
    volumes:
      - ./instance:/app/frontends/web/instance  # Persist user database
      - ./certs:/app/frontends/web/certs        # Persist SSL certs
```

### Security Notes

- Passwords are hashed with Argon2id (time_cost=3, memory_cost=64MB)
- Single admin user only (no registration)
- Session-based authentication using Flask sessions
- Database stored in `instance/stegasoo.db` (add to `.gitignore`)

---

## Installation & Setup

### From PyPI

```bash
pip install stegasoo[web]
```

This automatically installs DCT dependencies (scipy) for full functionality.

### From Source

```bash
git clone https://github.com/example/stegasoo.git
cd stegasoo
pip install -e ".[web]"
```

### Running the Server

**Development:**
```bash
cd frontends/web
python app.py
```
Server starts at http://localhost:5000

**Production with Gunicorn:**
```bash
cd frontends/web
gunicorn --bind 0.0.0.0:5000 --workers 2 --threads 4 --timeout 60 app:app
```

**Docker:**
```bash
docker-compose up web
```

### First-Time Setup

1. Navigate to http://localhost:5000
2. Click "Generate" to create your credentials
3. **Memorize** your passphrase and PIN
4. Share credentials securely with your communication partner

---

## Pages & Features

### Home Page

**URL:** `/`

The landing page introduces Stegasoo and provides quick access to all features.

#### Main Actions

| Card | Description | Link |
|------|-------------|------|
| **Encode Message** | Hide a secret in an image | `/encode` |
| **Decode Message** | Extract a hidden message | `/decode` |
| **Generate Keys** | Create new credentials | `/generate` |

#### "How It Works" Section

Explains the three key components:
1. **Reference Photo** - Shared secret image
2. **Passphrase** - Your secret phrase (v3.2.0: same every time!)
3. **Static PIN** - Same every day

---

### Generate Credentials

**URL:** `/generate`

Create a new set of credentials for steganography operations.

#### Configuration Options

| Option | Range | Default | Description |
|--------|-------|---------|-------------|
| Words per passphrase | 3-12 | 4 | BIP-39 words in passphrase |
| Use PIN | on/off | on | Generate a numeric PIN |
| PIN length | 6-9 | 6 | Digits in the PIN |
| Use RSA Key | on/off | off | Generate an RSA key pair |
| RSA key size | 2048/3072/4096 | 2048 | Key size in bits |

#### Entropy Calculator

The UI displays real-time entropy calculations:

```
Estimated entropy: ~63 bits
[=============>                 ] Good for most use cases
• Reference photo adds ~80-256 bits more
```

#### Generated Output (v3.2.0)

After clicking "Generate Credentials":

**Static PIN** (if enabled):
```
┌─────────────────────┐
│      8 4 7 2 9 3    │
└─────────────────────┘
Use this 6-digit PIN every time
```

**Passphrase** (v3.2.0: single passphrase, no daily rotation):
```
┌─────────────────────────────────────────┐
│  abandon ability able about             │
│                                         │
│  Use this passphrase to encode and      │
│  decode messages - no date needed!      │
└─────────────────────────────────────────┘
```

**RSA Key** (if enabled):
- Copy to clipboard button
- Download as password-protected .pem file
- Download as QR code image

**Security Summary:**
```
Passphrase entropy: 44 bits (4 words)
PIN entropy:        19 bits
RSA entropy:        128 bits
─────────────────────────────
Total:              191 bits
+ reference photo (~80-256 bits) = 271+ bits combined
```

#### RSA Key Download

1. Click "Download as .pem"
2. Enter a password (minimum 8 characters)
3. Click "Download Protected Key"
4. Save the file securely
5. Share with your communication partner through a secure channel

#### RSA Key QR Code

For easier sharing, you can also:
1. Click "Download QR Code"
2. Save the QR code image
3. Your partner can scan it to import the key

---

### Encode Message

**URL:** `/encode`

Hide a secret message or file inside an image.

#### Form Flow (v3.3.0)

The encode form follows a logical flow:

1. **Load Images** - Reference photo and carrier image
2. **View Capacity** - Shows available capacity for DCT and LSB modes
3. **Select Mode** - DCT (default) or LSB with inline tooltips
4. **Enter Payload** - Text message or file
5. **Add Security** - Passphrase, PIN, and/or RSA key

#### Input Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Reference Photo | Image file | ✓ | Your shared secret photo |
| Carrier Image | Image file | ✓ | Image to hide message in |
| Embedding Mode | Toggle | ✓ | DCT (default) or LSB |
| Payload Type | Toggle | ✓ | Text message or file |
| Secret Message | Text | * | Message to hide (max 50KB) |
| File to Embed | File | * | File to hide (max 2MB) |
| Passphrase | Text | ✓ | Your passphrase |
| PIN | Number | ** | Your static PIN |
| RSA Key | .pem file | ** | Your shared RSA key |
| RSA Key QR | Image file | ** | QR code containing RSA key |
| RSA Key Password | Password | | Password for encrypted key |

\* One of message or file required.
\*\* At least one security factor (PIN or RSA Key) required.

#### Embedding Mode Selection (v3.3.0)

The mode selector is now a compact inline toggle:

```
┌────────────────────────────────────────────────────────────┐
│  ◉ 🔊 DCT · Social Media ⓘ  │  ○ ⊞ LSB · Email & Files ⓘ │
└────────────────────────────────────────────────────────────┘
```

- **DCT** - Default, best for social media sharing
- **LSB** - Higher capacity, for lossless channels
- **ⓘ** - Hover for details (capacity, output format, etc.)

#### DCT Options

When DCT mode is selected, additional options appear:

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| Output Format | PNG / JPEG | JPEG | Output image format |
| Color Mode | Color / Grayscale | Color | Carrier color handling |

#### Drag-and-Drop Upload

Both image upload zones support:
- Click to browse
- Drag and drop files
- Instant image preview with scan animation
- Status indicators ("Hash Acquired", "Carrier Loaded")

#### Capacity Info Panel

After loading a carrier image, a capacity panel appears:

```
┌─────────────────────────────────────────────────────────┐
│ 📏 Carrier: 1920 × 1080 (2.1 MP)   DCT: 150 KB  LSB: 750 KB │
└─────────────────────────────────────────────────────────┘
```

#### Character Counter

```
Message: [                                              ]
         1,234 / 50,000 characters                  2%
```

Shows warning at 80% capacity.

#### Encoding Process

1. Upload reference photo and carrier image
2. View capacity info panel
3. Select embedding mode (DCT default)
4. Choose payload type and enter content
5. Enter passphrase and security factors
6. Click "Encode Message"
7. Wait for processing (shows spinner)
8. Redirected to result page

#### Result Page

**URL:** `/encode/result/<file_id>`

After successful encoding:

```
┌────────────────────────────────────────┐
│  ✓ Message Encoded Successfully!       │
│                                        │
│     📄 a1b2c3d4.png                    │
│     Your secret is hidden              │
│     in this image                      │
│                                        │
│     Mode: DCT (Color, JPEG)            │
│     Capacity used: 45.2%               │
│                                        │
│     [    Download Image    ]           │
│     [      Share Image     ]           │
│                                        │
│  ⚠️ File expires in 5 minutes.         │
│     Download or share now.             │
│                                        │
│     [ Encode Another Message ]         │
└────────────────────────────────────────┘
```

**Share Options:**

1. **Native Share** (mobile/supported browsers):
   - Uses Web Share API
   - Opens system share sheet
   - Can share directly to apps

2. **Fallback Share** (desktop):
   - Email link
   - Telegram link
   - WhatsApp link
   - Copy link to clipboard

---

### Decode Message

**URL:** `/decode`

Extract a hidden message or file from a stego image.

#### Input Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Reference Photo | Image file | ✓ | Same photo used for encoding |
| Stego Image | Image file | ✓ | Image containing hidden message |
| Passphrase | Text | ✓ | Same passphrase used for encoding |
| PIN | Number | * | Same PIN used for encoding |
| RSA Key | .pem file | * | Same RSA key used for encoding |
| RSA Key QR | Image file | * | QR code containing RSA key |
| RSA Key Password | Password | | Password for encrypted key |

\* Must match security factors used during encoding.

#### Automatic Mode Detection

The decoder automatically detects whether a stego image uses LSB or DCT mode. You don't need to specify the mode manually—it just works!

#### Decoding Process (v3.2.0 Simplified)

1. Upload the same reference photo
2. Upload the received stego image
3. Enter your passphrase (no date needed!)
4. Enter your PIN and/or RSA key
5. Click "Decode Message"
6. View decoded message or download decoded file

#### Successful Decode (Text)

```
┌────────────────────────────────────────┐
│  ✓ Message Decrypted Successfully!     │
│                                        │
│  Decoded Message:                      │
│  ┌──────────────────────────────────┐  │
│  │ Meet at midnight. The package    │  │
│  │ will be under the bridge.        │  │
│  └──────────────────────────────────┘  │
│                                        │
│     [ Decode Another Message ]         │
└────────────────────────────────────────┘
```

#### Successful Decode (File)

```
┌────────────────────────────────────────┐
│  ✓ File Extracted Successfully!        │
│                                        │
│     📄 secret_document.pdf             │
│     Size: 245 KB                       │
│     Type: application/pdf              │
│                                        │
│     [    Download File    ]            │
│                                        │
│  ⚠️ File expires in 5 minutes.         │
│                                        │
│     [ Decode Another Message ]         │
└────────────────────────────────────────┘
```

#### Troubleshooting Tips

If decryption fails:
1. **Check passphrase** - Must be exact match (case-sensitive)
2. **Same reference photo** - Must be identical file
3. **Correct PIN/RSA** - Match what was used for encoding
4. **Image integrity** - Ensure no resizing/recompression (LSB mode)

---

### About Page

**URL:** `/about`

Information about the Stegasoo project, security model, and credits.

Includes:
- Version information (v3.3.0)
- Recent UI improvements
- Security model overview
- Dependency status (Argon2, QR code support)

---

## Embedding Modes

Stegasoo offers two steganography algorithms, each with different trade-offs.

### DCT Mode (Default)

**Discrete Cosine Transform** embedding hides data in frequency domain coefficients. This is now the default mode when scipy is available.

| Aspect | Details |
|--------|---------|
| **Capacity** | ~0.5 bits/pixel (~75 KB/MP) |
| **Output Formats** | PNG or JPEG |
| **Resilience** | ✅ Survives JPEG recompression |
| **Best For** | Social media, messaging apps |

**When to use DCT:**
- Sharing via social media (Instagram, WhatsApp, Telegram)
- When image may be recompressed
- When stealth is important
- Smaller messages that fit in reduced capacity

#### DCT Output Formats

| Format | Pros | Cons |
|--------|------|------|
| **JPEG** | Native format, natural, smaller, resilient | Slightly lower capacity |
| **PNG** | Lossless, predictable | Larger file |

#### DCT Color Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Color** | Embeds in luminance (Y), preserves chrominance | Most images, photos |
| **Grayscale** | Converts to grayscale before embedding | Black & white images |

### LSB Mode

**Least Significant Bit** embedding modifies the least significant bits of pixel values.

| Aspect | Details |
|--------|---------|
| **Capacity** | ~3 bits/pixel (~375 KB/MP) |
| **Output Format** | PNG only (lossless required) |
| **Resilience** | ❌ Destroyed by JPEG compression |
| **Best For** | Maximum capacity, controlled sharing |

**When to use LSB:**
- Sharing via lossless channels (email attachment, file transfer, cloud storage)
- Maximum message capacity needed
- Recipient won't modify/recompress the image

### Capacity Comparison

For a 1920×1080 image (~2 MP):

| Mode | Approximate Capacity |
|------|---------------------|
| LSB (PNG) | ~750 KB |
| DCT (PNG, Color) | ~150 KB |
| DCT (JPEG) | ~150 KB |

### Choosing the Right Mode

```
┌─────────────────────────────────────────────────────────────┐
│                    Mode Selection Guide                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Sharing via social media / messaging app?                  │
│              │                                              │
│      ┌───────┴───────┐                                      │
│      ▼               ▼                                      │
│     YES             NO                                      │
│      │               │                                      │
│      ▼               ▼                                      │
│  Use DCT        Need maximum capacity?                      │
│  (default)           │                                      │
│              ┌───────┴───────┐                              │
│              ▼               ▼                              │
│             YES             NO                              │
│              │               │                              │
│              ▼               ▼                              │
│          Use LSB        Use DCT                             │
│                        (default)                            │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## User Interface Guide

### Layout Structure

```
┌──────────────────────────────────────────────────────────────┐
│  🦕 Stegasoo                    [Encode] [Decode] [Generate] │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌────────────────────────────────────────────────────┐     │
│   │                    Page Content                     │     │
│   │                                                    │     │
│   │   ┌──────────────┐    ┌──────────────┐            │     │
│   │   │  Upload Zone  │    │  Upload Zone  │            │     │
│   │   │  (Reference)  │    │  (Carrier)    │            │     │
│   │   └──────────────┘    └──────────────┘            │     │
│   │                                                    │     │
│   │   Passphrase: [________________________]           │     │
│   │   PIN:        [____________]                       │     │
│   │                                                    │     │
│   │   [Advanced Options ▼]                             │     │
│   │   ┌────────────────────────────────────────────┐  │     │
│   │   │ Embedding Mode: [LSB ▼]                    │  │     │
│   │   │ Output Format:  [PNG ▼]  (DCT only)        │  │     │
│   │   │ Color Mode:     [Color ▼] (DCT only)       │  │     │
│   │   └────────────────────────────────────────────┘  │     │
│   │                                                    │     │
│   │   [        Encode Message        ]                │     │
│   │                                                    │     │
│   └────────────────────────────────────────────────────┘     │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│                         Footer                               │
└──────────────────────────────────────────────────────────────┘
```

### Color Scheme

| Element | Color | Purpose |
|---------|-------|---------|
| Background | Dark gradient | Reduce eye strain |
| Cards | Semi-transparent | Visual hierarchy |
| Headers | Purple gradient | Brand identity |
| Success | Green | Positive actions |
| Warning | Yellow | Caution messages |
| Error | Red | Error states |

### Form Validation

- Real-time validation feedback
- Clear error messages in alerts
- Required field indicators
- Input constraints (max length, format)
- Passphrase word count validation (v3.2.0)

### Loading States

During long operations:
- Button shows spinner
- Button text changes (e.g., "Encoding...")
- Button is disabled to prevent double-submit

### Flash Messages

```
┌──────────────────────────────────────────────┐
│ ✓ Credentials Generated!              [×]   │
└──────────────────────────────────────────────┘
```

Types:
- Success (green) - Operation completed
- Error (red) - Operation failed
- Warning (yellow) - Caution needed (e.g., short passphrase)

---

## Workflow Examples

### First-Time Setup (Both Parties)

**Party A:**
1. Go to `/generate`
2. Configure: PIN ✓, 4 words, 6 digits
3. Click "Generate Credentials"
4. **Write down** passphrase and PIN on paper
5. **Memorize** over the next few days
6. Destroy the paper

**Share with Party B (in person or secure channel):**
- The passphrase (just one phrase now!)
- The PIN
- The reference photo file (if not already shared)

### Sending a Secret Message (LSB - Default)

1. Go to `/encode`
2. Upload your shared reference photo
3. Upload any carrier image (meme, vacation photo, etc.)
4. Type your secret message
5. Enter your passphrase
6. Enter your PIN
7. Click "Encode Message"
8. Download or share the resulting image
9. Send via any channel (email, file transfer)

### Sending with DCT Mode

1. Go to `/encode`
2. Upload your shared reference photo
3. Upload carrier image
4. Type your secret message
5. Enter your passphrase and PIN
6. **Expand "Advanced Options"**
7. **Select "DCT" embedding mode**
8. **Select "JPEG" output format** (optional)
9. Click "Encode Message"
10. Download and share

### Receiving a Secret Message (v3.2.0 Simplified)

1. Receive the stego image through any channel
2. Go to `/decode`
3. Upload the same reference photo
4. Upload the received stego image
5. Enter your passphrase (no date needed!)
6. Enter your PIN
7. Click "Decode Message"
8. Read the secret message or download the file

### Embedding a File

1. Go to `/encode`
2. Upload reference photo and carrier image
3. Select "File" as payload type
4. Upload the file to embed (max 2MB)
5. Enter passphrase and PIN
6. Click "Encode Message"
7. Download the stego image

### Extracting a File

1. Go to `/decode`
2. Upload reference photo and stego image
3. Enter passphrase and PIN
4. Click "Decode Message"
5. Click "Download File" to save the extracted file

### Changing Credentials

To rotate to new credentials:
1. Both parties generate new credentials together
2. Agree on a cutover date
3. Messages encoded before cutover use old credentials
4. Messages encoded after cutover use new credentials

---

## Security Features

### Client-Side Security

| Feature | Implementation |
|---------|----------------|
| No credential storage | Nothing saved in browser |
| Automatic cleanup | Files deleted after 5 minutes |
| HTTPS support | Configure at server level |

### Server-Side Security

| Feature | Implementation |
|---------|----------------|
| Memory-hard KDF | Argon2id (256MB RAM) |
| Authenticated encryption | AES-256-GCM |
| Random salt | Per-message salt |
| Temporary storage | In-memory, auto-expiring |
| Input validation | All inputs validated |
| File size limits | 5MB max upload |

### File Security

| Aspect | Protection |
|--------|------------|
| Upload location | `/tmp/stego_uploads` (Docker) |
| Storage duration | 5 minutes maximum |
| Access control | Random 16-byte file ID |
| Cleanup | Automatic + manual |

### Embedding Mode Security

| Mode | Security Consideration |
|------|----------------------|
| LSB | Full capacity, but fragile to modification |
| DCT | Lower capacity, frequency domain hiding |

Both modes use the same strong encryption (AES-256-GCM with Argon2id key derivation).

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | production | Flask environment |
| `PYTHONPATH` | - | Include `src/` for development |
| `STEGASOO_AUTH_ENABLED` | `true` | Enable/disable authentication (v4.0.2) |
| `STEGASOO_HTTPS_ENABLED` | `false` | Enable HTTPS with self-signed certs (v4.0.2) |
| `STEGASOO_HOSTNAME` | `localhost` | Hostname for certificate CN (v4.0.2) |
| `STEGASOO_CHANNEL_KEY` | - | Channel key for deployment isolation |

### Application Limits

| Limit | Value | Config Location |
|-------|-------|-----------------|
| Max file upload | 5 MB | `app.config['MAX_CONTENT_LENGTH']` |
| File expiry | 5 minutes | `TEMP_FILE_EXPIRY` |
| Max image pixels | 4 MP | `stegasoo.constants` |
| Max message size | 50 KB | `stegasoo.constants` |
| Max file payload | 2 MB | `stegasoo.constants` |
| PIN length | 6-9 digits | `stegasoo.constants` |
| Passphrase words | 3-12 | `stegasoo.constants` |

### Production Deployment

**With Gunicorn:**
```bash
gunicorn \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --threads 4 \
  --timeout 60 \
  app:app
```

**Worker Calculation:**
- Each encode/decode uses ~256MB RAM (Argon2) + ~100MB for scipy (DCT mode)
- Formula: `workers = (available_RAM - 512MB) / 350MB`

**With Nginx (reverse proxy):**
```nginx
server {
    listen 80;
    server_name stegasoo.example.com;

    client_max_body_size 10M;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_read_timeout 120s;
    }
}
```

**With Docker Compose:**
```yaml
services:
  web:
    build:
      context: .
      target: web
    ports:
      - "5000:5000"
    environment:
      STEGASOO_AUTH_ENABLED: "true"
      STEGASOO_HTTPS_ENABLED: "false"
      STEGASOO_CHANNEL_KEY: ${STEGASOO_CHANNEL_KEY:-}
    volumes:
      - stegasoo-web-data:/app/frontends/web/instance
      - stegasoo-web-certs:/app/frontends/web/certs
    deploy:
      resources:
        limits:
          memory: 768M
        reservations:
          memory: 384M

volumes:
  stegasoo-web-data:
  stegasoo-web-certs:
```

---

## Troubleshooting

### Common Issues

#### "Decryption failed"

**Causes:**
- Wrong passphrase
- Wrong PIN
- Different reference photo
- Stego image was modified

**Solutions:**
1. Verify exact passphrase (case-sensitive)
2. Verify you're using the original reference photo
3. Ensure the stego image wasn't resized/recompressed (LSB mode)

#### "Invalid or missing Stegasoo header"

**Causes:**
- Image was heavily recompressed
- Wrong credentials
- Corrupted during transfer

**Solutions:**
1. Verify credentials match
2. Try obtaining original file
3. If using DCT mode, some modification is expected to work

#### "Carrier image too small"

**Cause:** Message too large for carrier capacity

**Solutions:**
1. Use a larger carrier image (more pixels)
2. Shorten the message
3. Use LSB mode for more capacity

#### "Passphrase should have at least 4 words"

**Cause:** Passphrase too short (v3.2.0 warning)

**Solutions:**
1. Use a longer passphrase for better security
2. Can still proceed with shorter passphrase (warning only)

#### "You must provide at least a PIN or RSA Key"

**Cause:** No security factor selected

**Solution:** Enter a PIN and/or upload an RSA key

#### Upload fails silently

**Causes:**
- File too large (>5MB)
- Invalid file type
- Browser issue

**Solutions:**
1. Reduce file size
2. Use PNG, JPG, or BMP formats
3. Try a different browser

#### RSA key password error

**Causes:**
- Wrong password
- Unencrypted key with password provided
- Corrupted key file

**Solutions:**
1. Verify the correct password
2. If key is unencrypted, leave password blank
3. Re-download or regenerate the key

#### DCT mode shows "requires scipy"

**Cause:** scipy library not installed

**Solution:** 
```bash
pip install scipy
# Or rebuild Docker image
docker-compose build --no-cache
```

### Browser Compatibility

| Browser | Status | Notes |
|---------|--------|-------|
| Chrome 80+ | ✓ Full | Web Share API supported |
| Firefox 80+ | ✓ Full | Limited Web Share |
| Safari 14+ | ✓ Full | Web Share on iOS |
| Edge 80+ | ✓ Full | Web Share API supported |
| IE 11 | ✗ None | Not supported |

### Performance Issues

**Slow encoding/decoding:**
- Normal: Argon2 is intentionally slow (security feature)
- DCT mode adds ~1-2 seconds for transform operations
- Expected time: 3-7 seconds per operation

**High memory usage:**
- Normal: Argon2 requires 256MB RAM
- DCT mode adds scipy memory overhead (~100MB)
- Configure worker count based on available RAM

---

## Mobile Support

### Responsive Design

The UI adapts to mobile screens:
- Single-column layout on small screens
- Touch-friendly buttons (48px minimum)
- Readable text without zooming
- Scrollable tables
- Collapsible "Advanced Options" for cleaner mobile view

### Mobile-Specific Features

**Native Sharing:**
On supported mobile browsers, the "Share Image" button opens the native share sheet, allowing you to share directly to:
- Messaging apps (iMessage, WhatsApp, Telegram)
- Social media (Instagram, Twitter)
- Email
- Other installed apps

**Camera Upload:**
File input accepts camera capture:
- Take a new photo as reference
- Capture carrier image directly

### PWA Support (Future)

The web app can be added to home screen on mobile devices for quick access.

---

## Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| `Tab` | Navigate between fields |
| `Enter` | Submit form (when focused) |
| `Esc` | Close modal/alert |

---

## Accessibility

| Feature | Implementation |
|---------|----------------|
| Screen readers | ARIA labels on interactive elements |
| Keyboard navigation | Full tab support |
| Color contrast | WCAG AA compliant |
| Focus indicators | Visible focus rings |
| Form labels | All inputs labeled |

---

## See Also

- [CLI Documentation](CLI.md) - Command-line interface
- [API Documentation](API.md) - REST API reference
- [Web Frontend Update Summary](web/WEB_FRONTEND_UPDATE_SUMMARY_V3.2.0.md) - Migration details
- [README](../README.md) - Project overview
