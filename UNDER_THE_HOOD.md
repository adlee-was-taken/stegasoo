# Stegasoo Technical Deep Dive: Encoding & Decoding

A detailed breakdown of how Stegasoo's LSB and DCT steganography modes work under the hood.

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
│                           STEGASOO ARCHITECTURE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   INPUTS                    PROCESSING                      OUTPUT          │
│   ───────                   ──────────                      ──────          │
│                                                                             │
│   Reference Photo ─┐                                                        │
│   Day Phrase ──────┼──► Argon2id KDF ──► AES-256 Key                       │
│   PIN/RSA Key ─────┘                           │                            │
│                                                ▼                            │
│   Message/File ────────────────────────► AES-256-GCM ──► Ciphertext        │
│                                          Encryption            │            │
│                                                                ▼            │
│   Carrier Image ───────────────────────────────────────► Embedding ──► Stego│
│                                                          (LSB/DCT)    Image │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

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
def validate_encode_inputs(reference_photo, carrier, message, day_phrase, pin, rsa_key):
    # Check image dimensions (max 24 megapixels)
    # Validate PIN format (6-9 digits)
    # Validate day phrase (3-12 words from BIP-39)
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
def derive_key(reference_hash: bytes, day_phrase: str, pin: str, 
               rsa_signature: bytes = None) -> bytes:
    """
    Combine all authentication factors into one AES key.
    """
    # Concatenate all factors
    key_material = reference_hash + day_phrase.encode() + pin.encode()
    
    if rsa_signature:
        key_material += rsa_signature
    
    # Argon2id parameters (memory-hard to resist GPU attacks)
    # - Memory: 256 MB
    # - Iterations: 3
    # - Parallelism: 4
    # - Output: 32 bytes (256 bits)
    
    key = argon2.hash_password_raw(
        password=key_material,
        salt=random_salt,  # 16 bytes, stored with ciphertext
        time_cost=3,
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
    """
    # Header format:
    # [8 bytes]  - Magic number: "STGSOO" + version + mode
    # [4 bytes]  - Payload length
    # [N bytes]  - Encrypted payload
    
    if mode == 'lsb':
        magic = b'STGSOO\x03\x01'  # v3, mode 1 (LSB)
    else:
        magic = b'STGSOO\x03\x02'  # v3, mode 2 (DCT)
    
    length = struct.pack('>I', len(encrypted_data))
    
    return magic + length + encrypted_data
```

### Step 7: Embedding (Mode-Specific)

This is where LSB and DCT diverge. See detailed sections below.

---

## The Decoding Pipeline

Decoding is essentially the reverse:

```
Stego Image ──► Extract Header ──► Detect Mode ──► Extract Data ──► Decrypt ──► Decompress ──► Output
                     │                  │
                     ▼                  ▼
              Validate Magic      LSB or DCT
              Get Payload Size    extraction
```

### Step 1: Mode Detection

```python
# __init__.py
def decode(stego_image: bytes, reference_photo: bytes, 
           day_phrase: str, pin: str, rsa_key: bytes = None) -> bytes:
    """
    Auto-detect embedding mode and decode.
    """
    # Try to read magic header from LSB positions first
    header = extract_header_lsb(stego_image, seed=derive_seed(...))
    
    if header.startswith(b'STGSOO'):
        version = header[6]
        mode = header[7]
        
        if mode == 0x01:
            return decode_lsb(...)
        elif mode == 0x02:
            return decode_dct(...)
    
    raise InvalidStegoError("No valid Stegasoo header found")
```

### Step 2: Key Re-derivation

The receiver must provide the **exact same inputs** to derive the same key:
- Same reference photo (processed to same hash)
- Same day phrase
- Same PIN
- Same RSA key (if used)

Any mismatch → wrong key → decryption fails (GCM tag mismatch)

### Step 3: Extraction & Decryption

```python
# crypto.py
def decrypt(encrypted_blob: bytes, key: bytes) -> bytes:
    """
    Decrypt AES-256-GCM encrypted data.
    """
    salt = encrypted_blob[0:16]
    nonce = encrypted_blob[16:28]
    tag = encrypted_blob[28:44]
    ciphertext = encrypted_blob[44:]
    
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    
    try:
        plaintext = cipher.decrypt_and_verify(ciphertext, tag)
        return plaintext
    except ValueError:
        raise DecryptionError("Authentication failed - wrong key or corrupted data")
```

---

## LSB Mode Deep Dive

### What is LSB Steganography?

LSB (Least Significant Bit) hides data in the lowest bit of each color channel. Changing the LSB changes the pixel value by at most 1 (e.g., 142 → 141 or 143), which is imperceptible.

```
Original pixel (RGB): [142, 87, 203]
Binary:               [10001110, 01010111, 11001011]
                              ^        ^        ^
                           LSB      LSB      LSB

To embed bits [1, 0, 1]:
Modified:             [10001111, 01010110, 11001011]
New pixel (RGB):      [143, 86, 203]

Difference: Imperceptible to human eye
```

### LSB Embedding Process

```python
# steganography.py
def embed_lsb(carrier_image: bytes, payload: bytes, seed: bytes) -> bytes:
    """
    Embed payload using LSB steganography with pseudo-random pixel selection.
    """
    img = Image.open(io.BytesIO(carrier_image))
    pixels = np.array(img)
    
    # 1. Calculate capacity
    height, width, channels = pixels.shape
    total_bits = height * width * channels  # 3 bits per pixel (RGB)
    capacity_bytes = total_bits // 8
    
    if len(payload) > capacity_bytes:
        raise CapacityError(f"Payload {len(payload)} > capacity {capacity_bytes}")
    
    # 2. Generate pseudo-random pixel order (defeats steganalysis)
    rng = np.random.default_rng(seed=int.from_bytes(seed[:8], 'big'))
    
    # Create list of all (y, x, channel) positions
    positions = [(y, x, c) 
                 for y in range(height) 
                 for x in range(width) 
                 for c in range(channels)]
    
    # Shuffle deterministically based on seed
    rng.shuffle(positions)
    
    # 3. Convert payload to bits
    payload_bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
    
    # 4. Embed each bit
    for i, bit in enumerate(payload_bits):
        y, x, c = positions[i]
        
        # Clear LSB, then set to our bit
        pixels[y, x, c] = (pixels[y, x, c] & 0xFE) | bit
    
    # 5. Save as PNG (lossless - preserves LSBs)
    output = io.BytesIO()
    Image.fromarray(pixels).save(output, format='PNG')
    return output.getvalue()
```

### Why Pseudo-Random Positions?

Sequential embedding (left-to-right, top-to-bottom) creates statistical patterns detectable by steganalysis tools. Random scattering:

```
Sequential (detectable):          Random (undetectable):
┌─────────────────────┐          ┌─────────────────────┐
│█████████████........│          │.█..█.█...█..█.█..█.│
│.....................│          │█...█..█.█..█...█.█.│
│.....................│          │..█.█..█...█.█.█...█│
│.....................│          │.█..█.█..█...█..█..█│
└─────────────────────┘          └─────────────────────┘
  ↑ Pattern visible               ↑ Uniform distribution
```

### LSB Extraction Process

```python
# steganography.py  
def extract_lsb(stego_image: bytes, seed: bytes, length: int) -> bytes:
    """
    Extract payload from LSB positions.
    """
    img = Image.open(io.BytesIO(stego_image))
    pixels = np.array(img)
    
    # Regenerate same position sequence
    rng = np.random.default_rng(seed=int.from_bytes(seed[:8], 'big'))
    positions = [...]  # Same as embedding
    rng.shuffle(positions)
    
    # Extract bits
    bits = []
    for i in range(length * 8):
        y, x, c = positions[i]
        bits.append(pixels[y, x, c] & 1)  # Get LSB
    
    # Convert bits to bytes
    return np.packbits(bits).tobytes()
```

### LSB Capacity Formula

```
Capacity (bytes) = (Width × Height × 3 channels) / 8 bits

Example: 1920×1080 image
= 1920 × 1080 × 3 / 8
= 777,600 bytes (~759 KB)
```

### LSB Limitations

| Limitation | Description |
|------------|-------------|
| **JPEG destroys data** | JPEG recompression changes pixel values, destroying LSBs |
| **Screenshots may corrupt** | Screen capture may alter pixels |
| **Social media unusable** | All platforms recompress images |
| **Steganalysis vulnerable** | Chi-square analysis can detect LSB patterns |

---

## DCT Mode Deep Dive

### What is DCT Steganography?

DCT (Discrete Cosine Transform) hides data in the frequency coefficients of the image rather than raw pixels. JPEG images are already stored as DCT coefficients, making this approach survive JPEG recompression.

### Understanding DCT Basics

```
Spatial Domain (pixels)          Frequency Domain (DCT)
┌────────────────────┐           ┌────────────────────┐
│ 52  55  61  66 ... │           │ 415  -30  -6   3   │  DC + low freq
│ 62  59  55  90 ... │   DCT     │ -22  -17   5  -3   │  
│ 63  59  66  88 ... │  ────►    │  -9    9   4   2   │  
│ 67  61  68  96 ... │           │  -4    2   1  -1   │  high freq
│ ...                │           │  ...               │
└────────────────────┘           └────────────────────┘
    8×8 pixel block                 8×8 coefficient block
```

**Key insight**: Modifying mid-frequency coefficients is:
1. Less visible than modifying pixels
2. Survives JPEG recompression (coefficients are preserved)
3. Harder to detect statistically

### DCT Embedding Process (scipy-based, PNG output)

```python
# dct_steganography.py
def embed_in_dct(payload: bytes, carrier: bytes, seed: bytes,
                 output_format: str = 'png', color_mode: str = 'color') -> bytes:
    """
    Embed payload in DCT coefficients.
    """
    img = Image.open(io.BytesIO(carrier))
    
    if color_mode == 'grayscale':
        img = img.convert('L')
        channels = [np.array(img)]
    else:
        # Convert to YCbCr (JPEG color space)
        # Embed only in Y (luminance) channel
        ycbcr = img.convert('YCbCr')
        y, cb, cr = ycbcr.split()
        channels = [np.array(y)]
        color_channels = (cb, cr)  # Preserve for reconstruction
    
    y_channel = channels[0].astype(float)
    height, width = y_channel.shape
    
    # 1. Pad to multiple of 8
    pad_h = (8 - height % 8) % 8
    pad_w = (8 - width % 8) % 8
    y_padded = np.pad(y_channel, ((0, pad_h), (0, pad_w)), mode='edge')
    
    # 2. Process 8x8 blocks
    blocks_h = y_padded.shape[0] // 8
    blocks_w = y_padded.shape[1] // 8
    total_blocks = blocks_h * blocks_w
    
    # 3. Generate random block order
    rng = np.random.default_rng(seed=int.from_bytes(seed[:8], 'big'))
    block_indices = list(range(total_blocks))
    rng.shuffle(block_indices)
    
    # 4. Embed using QIM (Quantization Index Modulation)
    payload_bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
    bit_index = 0
    
    # Positions within 8x8 block for embedding (mid-frequency)
    # Avoid DC (0,0) and very high frequencies
    embed_positions = [(1,2), (2,1), (2,2), (1,3), (3,1), (2,3), (3,2), (3,3),
                       (0,4), (4,0), (1,4), (4,1), (2,4), (4,2), (3,4), (4,3)]
    
    DELTA = 16  # Quantization step
    
    for block_idx in block_indices:
        if bit_index >= len(payload_bits):
            break
            
        by = (block_idx // blocks_w) * 8
        bx = (block_idx % blocks_w) * 8
        
        # Extract 8x8 block
        block = y_padded[by:by+8, bx:bx+8]
        
        # Apply DCT
        dct_block = scipy.fftpack.dct(
            scipy.fftpack.dct(block.T, norm='ortho').T, 
            norm='ortho'
        )
        
        # Embed bits in each position
        for pos in embed_positions:
            if bit_index >= len(payload_bits):
                break
            
            coef = dct_block[pos]
            bit = payload_bits[bit_index]
            
            # QIM embedding:
            # Quantize coefficient, then adjust to encode bit
            quantized = round(coef / DELTA)
            if quantized % 2 != bit:
                quantized += 1 if bit else -1
            dct_block[pos] = quantized * DELTA
            
            bit_index += 1
        
        # Apply inverse DCT
        block = scipy.fftpack.idct(
            scipy.fftpack.idct(dct_block.T, norm='ortho').T,
            norm='ortho'
        )
        
        y_padded[by:by+8, bx:bx+8] = block
    
    # 5. Reconstruct image
    y_modified = y_padded[:height, :width]  # Remove padding
    y_modified = np.clip(y_modified, 0, 255).astype(np.uint8)
    
    if color_mode == 'color':
        # Merge modified Y with original Cb, Cr
        result = Image.merge('YCbCr', (
            Image.fromarray(y_modified),
            color_channels[0],
            color_channels[1]
        )).convert('RGB')
    else:
        result = Image.fromarray(y_modified)
    
    # 6. Save
    output = io.BytesIO()
    if output_format == 'jpeg':
        result.save(output, format='JPEG', quality=95)
    else:
        result.save(output, format='PNG')
    
    return output.getvalue()
```

### DCT Embedding Process (jpegio-based, native JPEG)

```python
# dct_steganography.py
def embed_in_jpeg_native(payload: bytes, jpeg_carrier: bytes, seed: bytes) -> bytes:
    """
    Embed directly in JPEG DCT coefficients using jpegio.
    This preserves coefficients WITHOUT re-encoding.
    """
    import jpegio
    
    # 1. Read JPEG structure (coefficients, quantization tables, etc.)
    jpeg = jpegio.read(io.BytesIO(jpeg_carrier))
    
    # Y channel coefficients (component 0)
    y_coefs = jpeg.coef_arrays[0]  # Shape: (height/8, width/8, 8, 8)
    
    # 2. Find embeddable coefficients
    # Rules:
    # - Skip DC coefficient (index 0,0 in each block)
    # - Skip zero coefficients (would become non-zero, visible)
    # - Skip ±1 coefficients (LSB change might zero them)
    
    embeddable = []
    for by in range(y_coefs.shape[0]):
        for bx in range(y_coefs.shape[1]):
            for i in range(8):
                for j in range(8):
                    if i == 0 and j == 0:  # Skip DC
                        continue
                    coef = y_coefs[by, bx, i, j]
                    if abs(coef) >= 2:  # Safe to modify
                        embeddable.append((by, bx, i, j))
    
    # 3. Shuffle positions
    rng = np.random.default_rng(seed=int.from_bytes(seed[:8], 'big'))
    rng.shuffle(embeddable)
    
    # 4. Embed bits in LSB of coefficients
    payload_bits = np.unpackbits(np.frombuffer(payload, dtype=np.uint8))
    
    for i, bit in enumerate(payload_bits):
        if i >= len(embeddable):
            raise CapacityError("Payload too large for carrier")
        
        by, bx, ci, cj = embeddable[i]
        coef = y_coefs[by, bx, ci, cj]
        
        # Modify LSB
        if coef > 0:
            y_coefs[by, bx, ci, cj] = (abs(coef) & ~1) | bit
        else:
            y_coefs[by, bx, ci, cj] = -((abs(coef) & ~1) | bit)
    
    # 5. Write JPEG (preserves structure, no re-encoding)
    jpeg.coef_arrays[0] = y_coefs
    
    output = io.BytesIO()
    jpegio.write(jpeg, output)
    return output.getvalue()
```

### Why jpegio Matters

```
WITHOUT jpegio (broken):
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│ JPEG Input  │───►│ PIL Decode   │───►│ Modify      │───►│ PIL Encode   │
│             │    │ (decompress) │    │ Pixels      │    │ (recompress) │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
                                                                  │
                                                                  ▼
                                                          RE-QUANTIZATION
                                                          DESTROYS DATA!

WITH jpegio (correct):
┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│ JPEG Input  │───►│ jpegio.read  │───►│ Modify      │───►│ jpegio.write │
│             │    │ (raw coefs)  │    │ Coefs       │    │ (raw coefs)  │
└─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
                                                                  │
                                                                  ▼
                                                          COEFFICIENTS
                                                          PRESERVED!
```

### DCT Capacity Formula

```
Capacity depends on image content (more texture = more non-zero coefficients)

Rough estimate:
Capacity (bytes) ≈ (Width × Height × bits_per_block) / (64 × 8)

Where bits_per_block ≈ 8-16 depending on image complexity

Example: 1920×1080 image
≈ 1920 × 1080 × 12 / 512
≈ 48,600 bytes (~47 KB)

Actual capacity varies from ~30 KB to ~75 KB for 1080p
```

### DCT Advantages

| Advantage | Description |
|-----------|-------------|
| **Survives JPEG recompression** | Coefficients mostly preserved |
| **Social media compatible** | Works after Instagram/WhatsApp compression |
| **Better steganalysis resistance** | Harder to detect statistically |
| **Natural-looking output** | JPEG artifacts expected |

### DCT Limitations

| Limitation | Description |
|------------|-------------|
| **Lower capacity** | ~10% of LSB capacity |
| **Slower processing** | DCT transforms are compute-intensive |
| **Requires scipy/jpegio** | Additional dependencies |
| **Quality-dependent** | Heavy recompression still degrades data |

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

---

## Security Considerations

### What Makes Stegasoo Secure?

```
MULTI-FACTOR AUTHENTICATION
────────────────────────────
Factor 1: Reference Photo    ─┐
  • 80-256 bits entropy       │
  • "Something you have"      │
                              ├──► Combined entropy: 133-400+ bits
Factor 2: Day Phrase         │    (Beyond brute force)
  • 33-132 bits entropy       │
  • "Something you know"      │
  • Rotates daily             │
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

### Complete Encode Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              ENCODE FLOW                                      │
└──────────────────────────────────────────────────────────────────────────────┘

User Inputs                    Processing                           Output
───────────                    ──────────                           ──────

Reference Photo ──────┐
                      ├──► get_image_hash() ──► ref_hash (32 bytes)
                      │         │
Day Phrase ───────────┤         ▼
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

### Complete Decode Flow

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                              DECODE FLOW                                      │
└──────────────────────────────────────────────────────────────────────────────┘

User Inputs                    Processing                           Output
───────────                    ──────────                           ──────

Reference Photo ──────┐
                      ├──► get_image_hash() ──► ref_hash (32 bytes)
                      │         │
Day Phrase ───────────┤         ▼
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
