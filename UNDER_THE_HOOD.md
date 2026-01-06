# Stegasoo Technical Deep Dive: Encoding & Decoding

A detailed breakdown of how Stegasoo's LSB and DCT steganography modes work under the hood.

**Version 4.0** - Updated for simplified authentication (no date dependency)

---

## Table of Contents

1. [High-Level Overview](#high-level-overview)
2. [The Encoding Pipeline](#the-encoding-pipeline)
3. [The Decoding Pipeline](#the-decoding-pipeline)
4. [LSB Mode Deep Dive](#lsb-mode-deep-dive)
5. [DCT Mode Deep Dive](#dct-mode-deep-dive)
6. [Comparison Table](#comparison-table)
7. [Security Considerations](#security-considerations)

---

## High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           STEGASOO ARCHITECTURE (v4.0)                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   INPUTS                    PROCESSING                      OUTPUT          │
│   ───────                   ──────────                      ──────          │
│                                                                             │
│   Reference Photo ─┐                                                        │
│   Passphrase ──────┼──► Argon2id KDF ──► AES-256 Key                        │
│   PIN/RSA Key ─────┘                           │                            │
│                                                ▼                            │
│   Message/File ────────────────────────► AES-256-GCM ──► Ciphertext         │
│                                          Encryption            │            │
│                                                                ▼            │
│   Carrier Image ───────────────────────────────────────► Embedding ──► Stego│
│                                                          (LSB/DCT)    Image │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### v4.0 Changes

| Change | v3.x | v4.0 |
|--------|------|------|
| Authentication | day_phrase + date | passphrase (no date) |
| Default words | 3 | 4 |
| Header size | 75 bytes | 65 bytes (no date field) |
| Python support | 3.10+ | 3.10-3.12 only |

### Module Responsibilities

| Module | File | Purpose |
|--------|------|---------|
| **Crypto** | `crypto.py` | Key derivation (Argon2id), AES-256-GCM encryption/decryption |
| **Steganography** | `steganography.py` | LSB pixel manipulation, capacity calculation |
| **DCT Steganography** | `dct_steganography.py` | Frequency-domain embedding, jpegio integration |
| **Compression** | `compression.py` | Optional LZ4 compression of payload |
| **Validation** | `validation.py` | Input validation, size limits |
| **Utils** | `utils.py` | Image hashing, format detection |

---

## The Encoding Pipeline

### Step 1: Input Collection & Validation

```python
# validation.py
def validate_encode_inputs(reference_photo, carrier, message, passphrase, pin, rsa_key):
    # Check image dimensions (max 24 megapixels)
    # Validate PIN format (6-9 digits)
    # Validate passphrase (3-12 words from BIP-39)
    # Check payload size vs carrier capacity
    # Ensure reference != carrier (security)
```

### Step 2: Reference Photo Processing

```python
# utils.py
def get_image_hash(image_bytes: bytes) -> bytes:
    """
    Generate deterministic hash from reference photo.
    This is the 'something you have' factor.
    """
    # Resize to 256x256 (normalize different resolutions)
    # Convert to grayscale (normalize color variations)
    # Apply slight blur (reduce JPEG artifact sensitivity)
    # SHA-256 hash of processed pixels
    return hashlib.sha256(processed_pixels).digest()  # 32 bytes
```

**Why process the image?** Minor variations (JPEG recompression, slight crops) in the reference photo between sender and receiver would produce different hashes, breaking decryption. The preprocessing makes the hash more resilient.

### Step 3: Key Derivation (Argon2id)

```python
# crypto.py
def derive_key(reference_hash: bytes, passphrase: str, pin: str, 
               rsa_signature: bytes = None) -> bytes:
    """
    Combine all authentication factors into one AES key.
    v4.0: No date parameter - simplified authentication.
    """
    # Concatenate all factors
    key_material = reference_hash + passphrase.encode() + pin.encode()
    
    if rsa_signature:
        key_material += rsa_signature
    
    # Argon2id parameters (memory-hard to resist GPU attacks)
    # - Memory: 256 MB
    # - Iterations: 4
    # - Parallelism: 4
    # - Output: 32 bytes (256 bits)
    
    key = argon2.hash_password_raw(
        password=key_material,
        salt=random_salt,  # 16 bytes, stored with ciphertext
        time_cost=4,
        memory_cost=262144,  # 256 MB
        parallelism=4,
        hash_len=32,
        type=argon2.Type.ID
    )
    return key  # 32-byte AES-256 key
```

**Why Argon2id?**
- **Memory-hard**: Requires 256MB RAM per attempt, defeating GPU/ASIC attacks
- **Time-hard**: ~2-3 seconds per derivation
- **Side-channel resistant**: ID variant protects against timing attacks

### Step 4: Payload Preparation

```python
# compression.py (optional)
def prepare_payload(data: bytes, filename: str = None) -> bytes:
    """
    Prepare the payload with metadata header.
    """
    # Header format (variable length):
    # [1 byte]  - Flags (compression, file mode, etc.)
    # [4 bytes] - Original data length (big-endian)
    # [2 bytes] - Filename length (if file mode)
    # [N bytes] - Filename (if file mode)
    # [N bytes] - Data (possibly compressed)
    
    header = struct.pack('>BI', flags, len(data))
    
    if filename:
        header += struct.pack('>H', len(filename)) + filename.encode()
    
    # Optional LZ4 compression
    if should_compress(data):
        data = lz4.frame.compress(data)
        flags |= FLAG_COMPRESSED
    
    return header + data
```

### Step 5: AES-256-GCM Encryption

```python
# crypto.py
def encrypt(plaintext: bytes, key: bytes) -> bytes:
    """
    Encrypt payload with AES-256-GCM.
    Returns: salt + nonce + ciphertext + tag
    """
    salt = os.urandom(16)       # Random salt for key derivation
    nonce = os.urandom(12)      # Random nonce for GCM
    
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    ciphertext, tag = cipher.encrypt_and_digest(plaintext)
    
    # Final encrypted blob:
    # [16 bytes] Salt
    # [12 bytes] Nonce  
    # [16 bytes] Auth Tag
    # [N bytes]  Ciphertext
    
    return salt + nonce + tag + ciphertext
```

**Why GCM?**
- **Authenticated encryption**: Detects tampering
- **No padding oracle**: Stream cipher mode
- **Built-in integrity**: 128-bit authentication tag

### Step 6: Stego Header Construction

```python
# steganography.py / dct_steganography.py
def build_stego_header(encrypted_data: bytes, mode: str) -> bytes:
    """
    Build the header that precedes embedded data.
    v4.0: Simplified header (no date field)
    """
    # Header format:
    # [4 bytes]  - Magic number: "STGO" (v4)
    # [1 byte]   - Version (0x04)
    # [1 byte]   - Mode (0x01=LSB, 0x02=DCT)
    # [4 bytes]  - Payload length
    # [N bytes]  - Encrypted payload
    
    if mode == 'lsb':
        magic = b'STGO\x04\x01'  # v4, mode 1 (LSB)
    else:
        magic = b'STGO\x04\x02'  # v4, mode 2 (DCT)
    
    length = struct.pack('>I', len(encrypted_data))
    
    return magic + length + encrypted_data
```

### Step 7: Embedding (Mode-Specific)

This is where LSB and DCT diverge. See detailed sections below.

---

## The Decoding Pipeline

### Step 1: Mode Detection

```python
def detect_mode(stego_image: bytes) -> str:
    """
    Detect which embedding mode was used.
    Checks format and magic bytes.
    """
    img = Image.open(io.BytesIO(stego_image))
    
    # JPEG images with JPGS magic = DCT mode with jpegio
    if img.format == 'JPEG':
        # Check for jpegio magic
        return 'dct'
    
    # PNG/BMP: Read first few bytes from LSB
    # Check for STGO or DCTS magic
    magic = extract_header_lsb(stego_image, 6)
    
    if magic.startswith(b'STGO'):
        mode_byte = magic[5]
        return 'lsb' if mode_byte == 0x01 else 'dct'
    elif magic.startswith(b'DCTS'):
        return 'dct'
    
    return 'lsb'  # Default fallback
```

### Step 2: Key Re-derivation

```python
# Same process as encoding
def derive_key_for_decode(reference_hash, passphrase, pin, rsa_signature=None):
    # Must use SAME parameters as encoding
    # No date parameter in v4.0
    return derive_key(reference_hash, passphrase, pin, rsa_signature)
```

### Step 3: Data Extraction

```python
def extract_data(stego_image: bytes, mode: str) -> bytes:
    """
    Extract raw bytes from stego image.
    Mode-specific extraction.
    """
    if mode == 'dct':
        return extract_from_dct(stego_image, pixel_key)
    else:
        return extract_from_lsb(stego_image, pixel_key)
```

### Step 4: Decryption & Payload Recovery

```python
def decrypt_and_recover(encrypted_data: bytes, key: bytes) -> Union[str, bytes]:
    """
    Decrypt and extract original message/file.
    """
    # Parse header
    salt = encrypted_data[:16]
    nonce = encrypted_data[16:28]
    tag = encrypted_data[28:44]
    ciphertext = encrypted_data[44:]
    
    # Decrypt
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext = cipher.decrypt_and_verify(ciphertext, tag)
    
    # Decompress if needed
    if plaintext[0] & FLAG_COMPRESSED:
        plaintext = lz4.frame.decompress(plaintext[5:])
    
    # Extract payload
    return parse_payload(plaintext)
```

---

## LSB Mode Deep Dive

### How LSB Embedding Works

LSB (Least Significant Bit) embedding modifies the lowest bit of each color channel in selected pixels.

```
Original Pixel (RGB):
  R: 11010110  G: 01101001  B: 10110100
              ↓         ↓         ↓
              └─────────┴─────────┘
                 3 bits available

After embedding "101":
  R: 1101011[1]  G: 0110100[0]  B: 1011010[1]
              ↑         ↑         ↑
           modified  modified  modified
```

### Pixel Selection Algorithm

```python
def select_pixels(carrier_shape, num_bits, seed: bytes) -> List[Tuple[int, int, int]]:
    """
    Generate pseudo-random pixel coordinates.
    Distributes modifications across entire image.
    """
    height, width, channels = carrier_shape
    total_positions = height * width * 3  # RGB channels
    
    # Use seed to generate reproducible random order
    rng = np.random.RandomState(int.from_bytes(seed[:4], 'big'))
    all_positions = np.arange(total_positions)
    rng.shuffle(all_positions)
    
    # Convert flat indices to (y, x, channel)
    selected = []
    for idx in all_positions[:num_bits]:
        y = idx // (width * 3)
        x = (idx % (width * 3)) // 3
        c = idx % 3
        selected.append((y, x, c))
    
    return selected
```

### Embedding Process

```python
def embed_lsb(carrier: np.ndarray, data: bytes, seed: bytes) -> np.ndarray:
    """
    Embed data using LSB substitution.
    """
    bits = bytes_to_bits(data)
    positions = select_pixels(carrier.shape, len(bits), seed)
    
    stego = carrier.copy()
    for i, (y, x, c) in enumerate(positions):
        # Clear LSB and set to our bit
        stego[y, x, c] = (stego[y, x, c] & 0xFE) | bits[i]
    
    return stego
```

### Capacity Calculation

```python
def calculate_lsb_capacity(width: int, height: int) -> int:
    """
    Calculate maximum payload size for LSB mode.
    """
    total_bits = width * height * 3  # 3 bits per pixel (RGB)
    header_bits = 10 * 8  # 10-byte stego header
    available_bits = total_bits - header_bits
    
    return available_bits // 8  # Convert to bytes
```

**Example capacities:**
- 1920×1080: ~770 KB
- 4000×3000: ~4.5 MB
- 800×600: ~180 KB

---

## DCT Mode Deep Dive

### How DCT Embedding Works

DCT (Discrete Cosine Transform) mode embeds data in the frequency-domain coefficients, making it resilient to JPEG compression.

```
Image Block (8×8 pixels)
         ↓
    DCT Transform
         ↓
DCT Coefficients (8×8)
┌────────────────────┐
│ DC  AC₁ AC₂ AC₃ ...│  ← Lower frequencies (top-left)
│ AC₄ AC₅ AC₆ ...    │
│ ...        ...     │  ← Mid frequencies (embed here)
│ ...            ... │
│           AC₆₃ ────│  ← Higher frequencies (bottom-right)
└────────────────────┘
         ↓
   Modify select ACs
         ↓
    IDCT Transform
         ↓
Modified Image Block
```

### Coefficient Selection

```python
# dct_steganography.py
EMBED_POSITIONS = [
    (0, 1), (1, 0), (2, 0), (1, 1), (0, 2), (0, 3), (1, 2), (2, 1), (3, 0),
    (4, 0), (3, 1), (2, 2), (1, 3), (0, 4), (0, 5), (1, 4), (2, 3), (3, 2),
    (4, 1), (5, 0), (5, 1), (4, 2), (3, 3), (2, 4), (1, 5), (0, 6), (0, 7),
    (1, 6), (2, 5), (3, 4), (4, 3), (5, 2), (6, 1), (7, 0),
]

# Use positions 4-20 (mid-frequency, good balance)
DEFAULT_EMBED_POSITIONS = EMBED_POSITIONS[4:20]  # 16 positions per block
```

**Why mid-frequency?**
- DC coefficient (0,0): Too visible, contains brightness
- Low AC: Visible changes, but survives compression
- Mid AC: Best balance of invisibility + resilience
- High AC: Invisible but destroyed by compression

### Block Processing

```python
def embed_in_block(block: np.ndarray, bits: List[int]) -> np.ndarray:
    """
    Embed bits in a single 8×8 block.
    """
    # Forward DCT
    dct_block = dct_2d(block)
    
    # Embed using quantization
    for i, pos in enumerate(DEFAULT_EMBED_POSITIONS):
        if i >= len(bits):
            break
        
        coef = dct_block[pos[0], pos[1]]
        # Quantize and modify LSB
        quantized = round(coef / QUANT_STEP)
        if (quantized % 2) != bits[i]:
            quantized += 1 if coef > 0 else -1
        dct_block[pos[0], pos[1]] = quantized * QUANT_STEP
    
    # Inverse DCT
    return idct_2d(dct_block)
```

### jpegio Integration (Native JPEG Output)

```python
def embed_jpegio(data: bytes, carrier_jpeg: bytes, seed: bytes) -> bytes:
    """
    Embed directly in JPEG DCT coefficients using jpegio.
    Preserves JPEG structure perfectly.
    
    Note: Requires Python 3.12 or earlier (jpegio incompatible with 3.13)
    """
    import jpegio as jio
    
    # Normalize problematic JPEGs (quality=100 causes crashes)
    carrier_jpeg = normalize_jpeg_for_jpegio(carrier_jpeg)
    
    # Read existing JPEG coefficients
    jpeg = jio.read(temp_file_from_bytes(carrier_jpeg))
    coef_array = jpeg.coef_arrays[0]  # Y channel
    
    # Find usable coefficients (magnitude >= 2, non-DC)
    positions = get_usable_positions(coef_array)
    order = generate_order(len(positions), seed)
    
    # Embed by modifying coefficient LSBs
    bits = bytes_to_bits(data)
    for i, pos_idx in enumerate(order[:len(bits)]):
        row, col = positions[pos_idx]
        coef = coef_array[row, col]
        
        if (coef & 1) != bits[i]:
            # Flip LSB while preserving sign
            if coef > 0:
                coef_array[row, col] = coef - 1 if (coef & 1) else coef + 1
            else:
                coef_array[row, col] = coef + 1 if (coef & 1) else coef - 1
    
    # Write modified JPEG
    jio.write(jpeg, output_path)
    return read_bytes(output_path)
```

### JPEG Normalization (v4.0)

```python
def normalize_jpeg_for_jpegio(image_data: bytes) -> bytes:
    """
    Normalize problematic JPEGs before jpegio processing.
    
    JPEGs with quality=100 have quantization tables with all values=1,
    which causes jpegio to crash. Re-save at quality 95.
    """
    img = Image.open(io.BytesIO(image_data))
    
    if img.format != 'JPEG':
        return image_data
    
    # Check if any quantization table has all values <= 1
    needs_normalization = False
    if hasattr(img, 'quantization'):
        for table in img.quantization.values():
            if max(table) <= 1:
                needs_normalization = True
                break
    
    if not needs_normalization:
        return image_data
    
    # Re-save at safe quality
    buffer = io.BytesIO()
    img.save(buffer, format='JPEG', quality=95, subsampling=0)
    return buffer.getvalue()
```

### DCT Capacity Calculation

```python
def calculate_dct_capacity(width: int, height: int) -> int:
    """
    Calculate maximum payload for DCT mode.
    """
    blocks_x = width // 8
    blocks_y = height // 8
    total_blocks = blocks_x * blocks_y
    
    bits_per_block = len(DEFAULT_EMBED_POSITIONS)  # 16
    total_bits = total_blocks * bits_per_block
    
    header_bits = 10 * 8  # Stego header
    available_bits = total_bits - header_bits
    
    return available_bits // 8
```

**Example capacities:**
- 1920×1080: ~64 KB
- 4000×3000: ~375 KB
- 800×600: ~14 KB

### Why DCT Survives JPEG Compression

```
Original JPEG:    Stego JPEG:      Re-compressed:
                                   
DCT coefficients  Modified DCT     Coefficients 
preserved in      coefficients     re-quantized
file format       still valid      
      │                 │                │
      ▼                 ▼                ▼
   [DCT] ──────►  [Modified] ──────►  [Still
   [coefs]        [DCT coefs]         Modified!]
                                   
LSB changes survive because they're embedded in 
the frequency domain, not spatial pixel values.
```

### DCT Advantages

| Advantage | Description |
|-----------|-------------|
| **JPEG resilient** | Survives social media upload |
| **Better steganalysis resistance** | Harder to detect statistically |
| **Natural-looking output** | JPEG artifacts expected |

### DCT Limitations

| Limitation | Description |
|------------|-------------|
| **Lower capacity** | ~10% of LSB capacity |
| **Slower processing** | DCT transforms are compute-intensive |
| **Requires scipy/jpegio** | Additional dependencies |
| **Quality-dependent** | Heavy recompression still degrades data |
| **Python version** | jpegio requires Python 3.12 or earlier |

---

## Comparison Table

| Aspect | LSB Mode | DCT Mode |
|--------|----------|----------|
| **Capacity (1080p)** | ~770 KB | ~50 KB |
| **Output Format** | PNG only | PNG or JPEG |
| **Survives JPEG** | ❌ No | ✅ Yes |
| **Social Media** | ❌ Broken | ✅ Works |
| **Processing Speed** | Fast (~0.5s) | Slower (~2s) |
| **Dependencies** | Pillow, NumPy | + scipy, jpegio |
| **Color Support** | Full color | Color or Grayscale |
| **Detection Resistance** | Moderate | Better |
| **Best For** | Email, cloud storage | Social media, messaging |
| **Max Tested Image** | 14MB+ | 14MB+ |

---

## Security Considerations

### What Makes Stegasoo Secure?

```
MULTI-FACTOR AUTHENTICATION (v4.0)
──────────────────────────────────
Factor 1: Reference Photo    ─┐
  • 80-256 bits entropy       │
  • "Something you have"      │
                              ├──► Combined entropy: 133-400+ bits
Factor 2: Passphrase         │    (Beyond brute force)
  • 43-132 bits entropy       │
  • "Something you know"      │
  • 4 words default (v4.0)    │
                              │
Factor 3: PIN                 │
  • 20-30 bits entropy        │
  • "Something you know"      │
                              │
Factor 4: RSA Key (optional) ─┘
  • 112-128 bits entropy
  • "Something you have"

MEMORY-HARD KDF (Argon2id)
──────────────────────────
• 256 MB RAM per attempt
• ~3 seconds per attempt
• Defeats GPU/ASIC attacks
• 10 attempts = 30 seconds, not 0.00001 seconds

AUTHENTICATED ENCRYPTION (AES-256-GCM)
──────────────────────────────────────
• 256-bit key (unbreakable)
• Built-in integrity check
• Detects tampering
• No padding oracle attacks
```

### Attack Surface Analysis

| Attack | LSB Protection | DCT Protection |
|--------|----------------|----------------|
| Visual inspection | ✅ Imperceptible | ✅ Imperceptible |
| File size analysis | ⚠️ PNG larger | ✅ JPEG natural |
| Histogram analysis | ⚠️ Slight anomalies | ✅ Normal JPEG |
| Chi-square attack | ⚠️ Detectable at scale | ✅ Resistant |
| RS steganalysis | ⚠️ Detectable | ✅ Resistant |
| JPEG recompression | ❌ Destroyed | ✅ Survives |

### Threat Model

**Stegasoo protects against:**
- ✅ Passive eavesdropping
- ✅ Casual inspection of images
- ✅ Basic forensic analysis
- ✅ Brute force key guessing
- ✅ JPEG recompression (DCT mode)

**Stegasoo does NOT protect against:**
- ⚠️ Targeted forensic analysis with original carrier
- ⚠️ Nation-state level steganalysis
- ⚠️ Rubber hose cryptanalysis (coercion)
- ⚠️ Compromise of reference photo or credentials

---

## Data Flow Diagrams

### Complete Encode Flow (v4.0)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              ENCODE FLOW (v4.0)                               │
└──────────────────────────────────────────────────────────────────────────────┘

User Inputs                    Processing                           Output
───────────                    ──────────                           ──────

Reference Photo ──────┐
                      ├──► get_image_hash() ──► ref_hash (32 bytes)
                      │         │
Passphrase ───────────┤         ▼
                      ├──► derive_key() ──────► aes_key (32 bytes)
PIN ──────────────────┤    (Argon2id)               │
                      │                             │
RSA Key (optional) ───┘                             │
                                                    ▼
Message/File ──────────► prepare_payload() ──► encrypt() ──► ciphertext
                         (compress, header)    (AES-GCM)         │
                                                                 │
                                                                 ▼
                                                    build_stego_header()
                                                    (magic + length)
                                                                 │
Carrier Image ─────────────────────────────────────────►  embed()
                                                          │     │
                                              ┌───────────┴─────┴────────────┐
                                              │                              │
                                       LSB Mode                       DCT Mode
                                              │                              │
                                              ▼                              ▼
                                     embed_lsb()                    embed_in_dct()
                                     (pixel LSBs)                   (DCT coefficients)
                                              │                              │
                                              ▼                              ▼
                                         PNG Output                  PNG or JPEG
                                              │                              │
                                              └──────────┬───────────────────┘
                                                         │
                                                         ▼
                                                   Stego Image
                                                   (downloadable)
```

### Complete Decode Flow (v4.0)

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              DECODE FLOW (v4.0)                               │
└──────────────────────────────────────────────────────────────────────────────┘

User Inputs                    Processing                           Output
───────────                    ──────────                           ──────

Reference Photo ──────┐
                      ├──► get_image_hash() ──► ref_hash (32 bytes)
                      │         │
Passphrase ───────────┤         ▼
                      ├──► derive_key() ──────► aes_key (32 bytes)
PIN ──────────────────┤    (Argon2id)               │
                      │    (MUST MATCH!)            │
RSA Key (optional) ───┘                             │
                                                    │
                                                    ▼
Stego Image ──────────► detect_mode() ──────► extract()
                        (read magic)          │     │
                              │     ┌─────────┴─────┴──────────┐
                              │     │                          │
                              │  LSB Mode                DCT Mode
                              │     │                          │
                              │     ▼                          ▼
                              │  extract_lsb()          extract_from_dct()
                              │     │                          │
                              │     └────────┬─────────────────┘
                              │              │
                              │              ▼
                              │     parse_stego_header()
                              │     (magic, length)
                              │              │
                              │              ▼
                              └────────► decrypt()
                                         (AES-GCM)
                                              │
                                              ▼
                                     decompress()
                                     (if compressed)
                                              │
                                              ▼
                                     extract_payload()
                                     (handle file/text)
                                              │
                                              ▼
                                     Original Message
                                     or File
```

---

## Summary

**LSB Mode** is simpler, faster, and higher capacity - perfect for controlled channels where images won't be modified.

**DCT Mode** is more complex but survives real-world image processing - essential for social media and messaging apps.

Both modes share the same cryptographic foundation (Argon2id + AES-256-GCM) and multi-factor authentication, ensuring security regardless of embedding method.

The choice comes down to your use case:
- **Private channel?** → LSB (maximum capacity)
- **Public platform?** → DCT (maximum compatibility)

### v4.0 Simplifications

- **No more date tracking** - encode/decode anytime without remembering dates
- **Single passphrase** - no daily rotation to manage
- **Default 4 words** - better security out of the box
- **JPEG normalization** - handles quality=100 images automatically
- **Large image support** - tested with 14MB+ images
