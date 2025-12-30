# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x.x   | :white_check_mark: |
| 1.x.x   | :x:                |

## Reporting a Vulnerability

**Please do not report security vulnerabilities through public GitHub issues.**

Instead, please email: **security@example.com** (replace with your email)

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Any suggested fixes

You should receive a response within 48 hours. We'll work with you to understand and address the issue.

---

# Threat Model

## What Stegasoo Protects

Stegasoo is designed to hide the **existence** of a secret message within an ordinary-looking image, protected by multi-factor authentication.

### Protection Goals

| Goal | How It's Achieved |
|------|-------------------|
| **Confidentiality** | AES-256-GCM encryption with Argon2id key derivation |
| **Steganography** | LSB embedding with pseudo-random pixel selection |
| **Authentication** | Multi-factor: reference photo + passphrase + PIN (or RSA key) |
| **Integrity** | GCM authentication tag detects tampering |

### Security Factors

Stegasoo combines multiple authentication factors:

```
┌─────────────────────────────────────────────────────────────┐
│                     Key Derivation                          │
│                                                             │
│  Reference Photo ─────┐                                     │
│  (something you have) │                                     │
│                       ├──► Argon2id ──► AES-256 Key         │
│  Day Passphrase ──────┤    (256MB RAM)                      │
│  (something you know) │                                     │
│                       │                                     │
│  PIN or RSA Key ──────┘                                     │
│  (second factor)                                            │
└─────────────────────────────────────────────────────────────┘
```

## What Stegasoo Does NOT Protect Against

### 1. Statistical Steganalysis

**Risk:** Advanced analysis can detect that an image contains hidden data.

**Reality:** LSB steganography is detectable by:
- Chi-square analysis
- RS analysis
- Machine learning classifiers

**Mitigation:** Stegasoo uses pseudo-random pixel selection (not sequential), which helps but doesn't eliminate detectability.

**Recommendation:** Don't rely on Stegasoo if your adversary has:
- Access to the original carrier image
- Sophisticated forensic tools
- Motivation to analyze your specific images

### 2. Compromised Endpoints

**Risk:** If your device is compromised, the attacker can capture credentials.

**Not protected:**
- Keyloggers capturing your PIN/passphrase
- Screen capture of decoded messages
- Memory scraping during encode/decode
- Malware on sender or receiver device

**Recommendation:** Use on trusted devices only.

### 3. Reference Photo Exposure

**Risk:** The reference photo is a critical secret.

**If leaked:** Attacker only needs to guess/brute-force the passphrase + PIN.

**Recommendation:**
- Never share the reference photo
- Use a unique photo (not posted online)
- Store securely (encrypted drive, password manager)

### 4. Weak Credentials

**Risk:** Short PINs or common passphrases can be brute-forced.

| PIN Length | Combinations | Time to Brute Force* |
|------------|--------------|----------------------|
| 4 digits   | 10,000       | Seconds              |
| 6 digits   | 1,000,000    | Minutes              |
| 8 digits   | 100,000,000  | Hours                |
| 9 digits   | 1,000,000,000| Days                 |

*With Argon2 (256MB RAM, 4 iterations), each attempt takes ~1 second, making brute force slow but not impossible for short PINs.

**Recommendation:**
- Use 8+ digit PINs
- Use 4+ word passphrases
- Consider RSA keys for high-security use cases

### 5. Image Modification

**Risk:** Lossy compression destroys hidden data.

**Data is destroyed by:**
- JPEG compression
- Resizing
- Filters/effects
- Screenshots
- Social media upload (Instagram, Twitter, etc.)

**Recommendation:** 
- Always use lossless formats (PNG, BMP)
- Transfer files directly (email, Signal, USB)
- Never upload stego images to social media

### 6. Metadata Leakage

**Risk:** The stego image itself may reveal information.

**Potential leaks:**
- File creation timestamp
- Camera EXIF data (if carrier has it)
- File size changes

**Mitigation:** Stegasoo strips EXIF on output, but timestamps remain.

### 7. Traffic Analysis

**Risk:** The act of sending an image may be suspicious.

**Not protected:**
- Network observers seeing you send image files
- Email metadata showing sender/receiver
- Frequency analysis of communications

**Recommendation:** Use alongside normal image-sharing behavior.

## Cryptographic Details

### Encryption

| Component | Algorithm | Parameters |
|-----------|-----------|------------|
| Key Derivation | Argon2id | 256MB RAM, 4 iterations, 4 parallelism |
| Fallback KDF | PBKDF2-SHA256 | 600,000 iterations |
| Encryption | AES-256-GCM | 12-byte IV, 16-byte tag |
| Photo Hash | SHA-256 | Full image bytes |

### Pixel Selection

Pixels are selected pseudo-randomly using a key derived from:
```
pixel_key = SHA256(photo_hash || passphrase || date || pin/rsa_signature)
```

This prevents:
- Sequential embedding patterns
- Statistical detection of modified regions

### Format

```
┌──────────────────────────────────────────────────────────────┐
│ Magic (4B) │ Version (1B) │ Date (10B) │ Salt (32B) │ IV (12B) │
├──────────────────────────────────────────────────────────────┤
│ Encrypted Payload (AES-256-GCM)                              │
│ ├── Type (1B): 0x01=text, 0x02=file                          │
│ ├── Length (4B)                                              │
│ ├── Data (variable)                                          │
│ └── [Filename if file] (variable)                            │
├──────────────────────────────────────────────────────────────┤
│ GCM Auth Tag (16B)                                           │
└──────────────────────────────────────────────────────────────┘
```

## Best Practices

### For Maximum Security

1. **Use RSA keys** instead of PINs for authentication
2. **Use unique reference photos** not available online
3. **Use long passphrases** (4+ random words)
4. **Transfer via secure channels** (Signal, encrypted email)
5. **Delete stego images** after message is read
6. **Keep software updated** for security fixes

### For Casual Privacy

1. **6-digit PIN** is sufficient for non-adversarial use
2. **3-word passphrase** provides reasonable security
3. **PNG format** always for output
4. **Direct file transfer** (email attachment, AirDrop)

## Known Limitations

| Limitation | Impact | Status |
|------------|--------|--------|
| LSB is detectable | Statistical analysis can detect hidden data | By design (tradeoff for capacity) |
| No forward secrecy | Compromised key decrypts all messages | Use different keys per message for high security |
| Date in header | Reveals when message was encoded | By design (enables day-specific passphrases) |
| No deniability | Single password = single message | Future: plausible deniability layers |

## Security Audit Status

This software has **not** been professionally audited. Use at your own risk for sensitive applications.

If you're a security researcher interested in auditing Stegasoo, please reach out.

---

## Version History (Security Relevant)

| Version | Security Changes |
|---------|------------------|
| 2.2.0   | Added compression (no security impact) |
| 2.1.0   | Upgraded to Argon2id, increased iterations |
| 2.0.0   | Added RSA key support |
| 1.0.0   | Initial release |
