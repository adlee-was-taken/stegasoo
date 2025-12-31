# Stegasoo Web UI Documentation

Complete guide for the Stegasoo web-based steganography interface.

## Table of Contents

- [Overview](#overview)
- [Installation & Setup](#installation--setup)
- [Pages & Features](#pages--features)
  - [Home Page](#home-page)
  - [Generate Credentials](#generate-credentials)
  - [Encode Message](#encode-message)
  - [Decode Message](#decode-message)
  - [About Page](#about-page)
- [Embedding Modes](#embedding-modes)
  - [LSB Mode (Default)](#lsb-mode-default)
  - [DCT Mode (Experimental)](#dct-mode-experimental)
- [User Interface Guide](#user-interface-guide)
- [Workflow Examples](#workflow-examples)
- [Security Features](#security-features)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Mobile Support](#mobile-support)

---

## Overview

The Stegasoo Web UI provides a user-friendly browser-based interface for:

- **Generating** secure credentials (phrases, PINs, RSA keys)
- **Encoding** secret messages into images
- **Decoding** hidden messages from images
- **Learning** about the security model

Built with Flask, Bootstrap 5, and a modern dark theme.

### Features

- ✅ Drag-and-drop file uploads
- ✅ Image previews
- ✅ Client-side date detection
- ✅ Native sharing (Web Share API)
- ✅ Responsive design (mobile-friendly)
- ✅ Password-protected RSA key downloads
- ✅ Real-time entropy calculations
- ✅ Automatic file cleanup
- ✅ **DCT steganography mode** (v3.0+) - JPEG-resilient embedding
- ✅ **Color mode selection** (v3.0.1+) - Preserve carrier colors

---

## Installation & Setup

### From PyPI

```bash
pip install stegasoo[web]
```

This automatically installs DCT dependencies (scipy, jpegio) for full functionality.

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
3. **Memorize** your phrases and PIN
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
2. **Day Phrase** - Changes daily
3. **Static PIN** - Same every day

---

### Generate Credentials

**URL:** `/generate`

Create a new set of credentials for steganography operations.

#### Configuration Options

| Option | Range | Default | Description |
|--------|-------|---------|-------------|
| Words per phrase | 3-12 | 3 | BIP-39 words per daily phrase |
| Use PIN | on/off | on | Generate a numeric PIN |
| PIN length | 6-9 | 6 | Digits in the PIN |
| Use RSA Key | on/off | off | Generate an RSA key pair |
| RSA key size | 2048/3072/4096 | 2048 | Key size in bits |

#### Entropy Calculator

The UI displays real-time entropy calculations:

```
Estimated entropy: ~53 bits
[==========>                    ] Good for most use cases
• Reference photo adds ~80-256 bits more
```

#### Generated Output

After clicking "Generate Credentials":

**Static PIN** (if enabled):
```
┌─────────────────────┐
│      8 4 7 2 9 3    │
└─────────────────────┘
Use this 6-digit PIN every day
```

**Daily Phrases:**
```
Day         │ Phrase
─────────────────────────────────────────
Monday      │ abandon ability able
Tuesday     │ actor actress actual
Wednesday   │ advice aerobic affair
Thursday    │ afraid again age
Friday      │ agree ahead aim
Saturday    │ airport aisle alarm
Sunday      │ album alcohol alert
```

**RSA Key** (if enabled):
- Copy to clipboard button
- Download as password-protected .pem file

**Security Summary:**
```
Phrase entropy: 33 bits/phrase
PIN entropy:    19 bits/PIN
RSA entropy:    128 bits/RSA
─────────────────────────────
Total:          180 bits
+ reference photo (~80-256 bits) = 260+ bits combined
```

#### RSA Key Download

1. Click "Download as .pem"
2. Enter a password (minimum 8 characters)
3. Click "Download Protected Key"
4. Save the file securely
5. Share with your communication partner through a secure channel

---

### Encode Message

**URL:** `/encode`

Hide a secret message inside an image.

#### Input Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Reference Photo | Image file | ✓ | Your shared secret photo |
| Carrier Image | Image file | ✓ | Image to hide message in |
| Secret Message | Text | ✓ | Message to hide (max 50KB) |
| Day Phrase | Text | ✓ | Today's passphrase |
| PIN | Number | * | Your static PIN |
| RSA Key | .pem file | * | Your shared RSA key |
| RSA Key Password | Password | | Password for encrypted key |

\* At least one security factor (PIN or RSA Key) required.

#### Advanced Options (v3.0+)

Expand "Advanced Options" to access embedding mode settings:

| Option | Values | Default | Description |
|--------|--------|---------|-------------|
| Embedding Mode | LSB / DCT | LSB | Steganography algorithm |
| Output Format | PNG / JPEG | PNG | Output image format (DCT only) |
| Color Mode | Color / Grayscale | Color | Carrier color handling (DCT only) |

See [Embedding Modes](#embedding-modes) for detailed explanations.

#### Drag-and-Drop Upload

Both image upload zones support:
- Click to browse
- Drag and drop files
- Instant image preview
- File name display

#### Character Counter

```
Message: [                                              ]
         1,234 / 50,000 characters                  2%
```

Shows warning at 80% capacity.

#### Day Detection

The page automatically detects your local day of week and updates the label:
```
Saturday's Phrase: [                    ]
```

#### Encoding Process

1. Fill in all required fields
2. (Optional) Expand "Advanced Options" for DCT mode
3. Click "Encode Message"
4. Wait for processing (shows spinner)
5. Redirected to result page

#### Result Page

**URL:** `/encode/result/<file_id>`

After successful encoding:

```
┌────────────────────────────────────────┐
│  ✓ Message Encoded Successfully!       │
│                                        │
│     📄 a1b2c3d4_20251227.png          │
│     Your secret message is hidden      │
│     in this image                      │
│                                        │
│     Mode: DCT (Color, JPEG)            │  ← v3.0+ shows mode info
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

Extract a hidden message from a stego image.

#### Input Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| Reference Photo | Image file | ✓ | Same photo used for encoding |
| Stego Image | Image file | ✓ | Image containing hidden message |
| Day Phrase | Text | ✓ | Phrase for the **encoding** day |
| PIN | Number | * | Same PIN used for encoding |
| RSA Key | .pem file | * | Same RSA key used for encoding |
| RSA Key Password | Password | | Password for encrypted key |

\* Must match security factors used during encoding.

#### Automatic Mode Detection (v3.0+)

The decoder automatically detects whether a stego image uses LSB or DCT mode. You don't need to specify the mode manually—it just works!

#### Date Detection from Filename

When you upload a stego image with a date in the filename (e.g., `stego_20251227.png`), the UI:
1. Extracts the date
2. Determines the day of week
3. Updates the phrase label: "Saturday's Phrase"

This helps you use the correct daily phrase.

#### Decoding Process

1. Fill in all required fields
2. Click "Decode Message"
3. Wait for processing
4. View decoded message on same page

#### Successful Decode

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

#### Troubleshooting Tips

If decryption fails:
1. **Check the date** - Use phrase for encoding day, not today
2. **Same reference photo** - Must be identical file
3. **Correct PIN/RSA** - Match what was used for encoding
4. **Image integrity** - Ensure no resizing/recompression

---

### About Page

**URL:** `/about`

Information about the Stegasoo project, security model, and credits.

---

## Embedding Modes

Stegasoo v3.0+ offers two steganography algorithms, each with different trade-offs.

### LSB Mode (Default)

**Least Significant Bit** embedding modifies the least significant bits of pixel values.

| Aspect | Details |
|--------|---------|
| **Capacity** | ~3 bits/pixel (~770 KB for 1920×1080) |
| **Output Format** | PNG only (lossless required) |
| **Resilience** | ❌ Destroyed by JPEG compression |
| **Best For** | Maximum capacity, controlled sharing |

**When to use LSB:**
- Sharing via lossless channels (email attachment, file transfer)
- Maximum message capacity needed
- Recipient won't modify the image

### DCT Mode (Experimental)

**Discrete Cosine Transform** embedding hides data in frequency domain coefficients.

| Aspect | Details |
|--------|---------|
| **Capacity** | ~0.25 bits/pixel (~65 KB for 1920×1080 PNG, ~30-50 KB JPEG) |
| **Output Formats** | PNG or JPEG |
| **Resilience** | ✅ Survives JPEG compression |
| **Best For** | Social media, messaging apps, web sharing |

> ⚠️ **Experimental Feature**: DCT mode is marked experimental and may have edge cases. Test with your specific workflow before relying on it for critical messages.

**When to use DCT:**
- Posting to social media (which recompresses images)
- Sharing via messaging apps (WhatsApp, Telegram, etc.)
- When channel may apply JPEG compression
- Smaller messages that fit in reduced capacity

#### DCT Output Formats

| Format | Pros | Cons |
|--------|------|------|
| **PNG** | Lossless, predictable | Larger file, obvious if channel expects JPEG |
| **JPEG** | Native format, natural | Slightly lower capacity |

#### DCT Color Modes

| Mode | Description | Use Case |
|------|-------------|----------|
| **Color** | Embeds in luminance (Y), preserves chrominance | Most images, photos |
| **Grayscale** | Converts to grayscale before embedding | Black & white images |

### Capacity Comparison

For a 1920×1080 image:

| Mode | Approximate Capacity |
|------|---------------------|
| LSB (PNG) | ~770 KB |
| DCT (PNG, Color) | ~65 KB |
| DCT (JPEG) | ~30-50 KB |

### Choosing the Right Mode

```
┌─────────────────────────────────────────────────────────────┐
│                    Mode Selection Guide                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Will the image be recompressed (social media, chat apps)?  │
│                          │                                  │
│              ┌───────────┴───────────┐                      │
│              ▼                       ▼                      │
│             YES                     NO                      │
│              │                       │                      │
│              ▼                       ▼                      │
│         Use DCT Mode            Use LSB Mode                │
│              │                       │                      │
│              ▼                       ▼                      │
│    Output: JPEG (natural)     Output: PNG (automatic)       │
│    Color: Color (usually)     Capacity: ~770 KB             │
│    Capacity: ~30-50 KB                                      │
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
| Experimental | Orange badge | DCT mode indicator |

### Form Validation

- Real-time validation feedback
- Clear error messages in alerts
- Required field indicators
- Input constraints (max length, format)

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
- Warning (yellow) - Caution needed

---

## Workflow Examples

### First-Time Setup (Both Parties)

**Party A:**
1. Go to `/generate`
2. Configure: PIN ✓, 3 words, 6 digits
3. Click "Generate Credentials"
4. **Write down** phrases and PIN on paper
5. **Memorize** over the next few days
6. Destroy the paper

**Share with Party B (in person or secure channel):**
- The 7 daily phrases
- The PIN
- The reference photo file (if not already shared)

### Sending a Secret Message (LSB - Default)

1. Go to `/encode`
2. Upload your shared reference photo
3. Upload any carrier image (meme, vacation photo, etc.)
4. Type your secret message
5. Enter today's phrase (check your memory!)
6. Enter your PIN
7. Click "Encode Message"
8. Download or share the resulting image
9. Send via any channel (email, file transfer)

### Sending via Social Media (DCT Mode)

1. Go to `/encode`
2. Upload your shared reference photo
3. Upload carrier image
4. Type your secret message
5. Enter today's phrase and PIN
6. **Expand "Advanced Options"**
7. **Select "DCT" embedding mode**
8. **Select "JPEG" output format**
9. Click "Encode Message"
10. Download and post to social media

The recipient can decode even after the platform recompresses the image!

### Receiving a Secret Message

1. Receive the stego image through any channel
2. Go to `/decode`
3. Upload the same reference photo
4. Upload the received stego image
5. Note the date in the filename (e.g., `_20251227`)
6. Enter the phrase for **that day** (not today!)
7. Enter the PIN
8. Click "Decode Message"
9. Read the secret message

> 💡 Decoding automatically detects LSB vs DCT mode—no configuration needed!

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
| Local date detection | JavaScript `Date()` object |
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
| DCT | Lower capacity, but survives recompression |

Both modes use the same strong encryption (AES-256-GCM with Argon2id key derivation).

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `FLASK_ENV` | production | Flask environment |
| `PYTHONPATH` | - | Include `src/` for development |

### Application Limits

| Limit | Value | Config Location |
|-------|-------|-----------------|
| Max file upload | 5 MB | `app.config['MAX_CONTENT_LENGTH']` |
| File expiry | 5 minutes | `TEMP_FILE_EXPIRY` |
| Max image pixels | 4 MP | `stegasoo.constants` |
| Max message size | 50 KB | `stegasoo.constants` |
| PIN length | 6-9 digits | `stegasoo.constants` |

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
    deploy:
      resources:
        limits:
          memory: 768M   # Increased for scipy/DCT
        reservations:
          memory: 384M
```

---

## Troubleshooting

### Common Issues

#### "Decryption failed"

**Causes:**
- Wrong day phrase
- Wrong PIN
- Different reference photo
- Stego image was modified

**Solutions:**
1. Check the date in the stego filename
2. Use the phrase for that specific day
3. Verify you're using the original reference photo
4. Ensure the stego image wasn't resized/recompressed (LSB mode)

#### "Invalid or missing Stegasoo header" (DCT Mode)

**Causes:**
- Image was heavily recompressed
- Wrong credentials
- Corrupted during transfer

**Solutions:**
1. If sharing via lossy channel, ensure DCT mode was used for encoding
2. Verify credentials match
3. Try obtaining original file

#### "Carrier image too small"

**Cause:** Message too large for carrier capacity

**Solutions:**
1. Use a larger carrier image (more pixels)
2. Shorten the message
3. Use LSB mode for more capacity (if channel supports it)
4. Check capacity with `/info` command (CLI)

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

#### DCT mode shows "jpegio not available"

**Cause:** jpegio library not installed (required for JPEG output)

**Solution:** 
```bash
pip install jpegio
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
- [README](README.md) - Project overview
