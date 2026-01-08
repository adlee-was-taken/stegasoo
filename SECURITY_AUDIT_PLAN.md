# Stegasoo Security Audit Plan

> **Target Audience**: Developers, security reviewers, and deployment administrators
> **Scope**: Web UI, REST API, CLI, and cryptographic core
> **Deployment Model**: Air-gapped / private LAN (primary), Internet-facing (secondary)

---

## Overview

Stegasoo is a steganography tool designed for **air-gapped deployments** on private networks. While the primary threat model assumes a trusted local network, this audit plan covers security best practices for both isolated and potentially exposed deployments.

### Known Limitations (By Design)

- **Self-signed certificates**: HTTPS uses self-signed certs; users must add exceptions or deploy their own CA
- **No rate limiting**: Assumes trusted users on private network
- **Single-node**: No distributed session store; sessions are per-instance
- **Air-gap focus**: External security (firewalls, network isolation) is user's responsibility

---

## 1. Authentication & Authorization

### 1.1 Password Security
- [ ] Passwords hashed with Argon2id (preferred) or PBKDF2 fallback
- [ ] Minimum password length enforced (8+ characters)
- [ ] Password not logged or exposed in error messages
- [ ] Password change requires current password verification
- [ ] Admin re-authentication required for sensitive operations (channel key export)

### 1.2 Session Management
- [ ] Session tokens are cryptographically random
- [ ] Session cookies have `HttpOnly` flag
- [ ] Session cookies have `Secure` flag (when HTTPS enabled)
- [ ] Session cookies have `SameSite` attribute
- [ ] Sessions invalidated on logout
- [ ] Sessions invalidated on password change
- [ ] Session timeout configured appropriately

### 1.3 Authorization
- [ ] Admin-only routes protected by `@admin_required` decorator
- [ ] User-only routes protected by `@login_required` decorator
- [ ] Users cannot access other users' saved channel keys
- [ ] Users cannot modify other users' accounts
- [ ] Role escalation not possible through API manipulation

---

## 2. Cryptographic Implementation

### 2.1 Key Derivation
- [ ] KDF uses Argon2id with appropriate parameters (memory, iterations, parallelism)
- [ ] PBKDF2 fallback uses sufficient iterations (600,000+)
- [ ] Salt is cryptographically random and unique per operation
- [ ] PIN/passphrase combined securely before KDF

### 2.2 Encryption
- [ ] AES-256-GCM used for payload encryption
- [ ] Nonce/IV is unique per encryption operation
- [ ] Authentication tag verified before decryption
- [ ] No padding oracle vulnerabilities

### 2.3 Channel Keys
- [ ] Channel keys are 128-bit (32 hex chars)
- [ ] Channel key derivation uses HKDF or similar
- [ ] Channel isolation prevents cross-channel decryption
- [ ] Fingerprint reveals no information about full key

### 2.4 Random Number Generation
- [ ] All random values use `secrets` module or OS CSPRNG
- [ ] No use of `random` module for security-sensitive operations

---

## 3. Input Validation & Injection Prevention

### 3.1 Web UI
- [ ] All user input sanitized before rendering (XSS prevention)
- [ ] Jinja2 auto-escaping enabled
- [ ] No `| safe` filter on user-controlled content
- [ ] Content-Security-Policy header configured
- [ ] X-Content-Type-Options: nosniff

### 3.2 File Uploads
- [ ] File size limits enforced server-side
- [ ] File type validation (magic bytes, not just extension)
- [ ] Uploaded files not executed
- [ ] Filenames sanitized (path traversal prevention)
- [ ] Temporary files cleaned up after processing

### 3.3 API Inputs
- [ ] JSON schema validation on API endpoints
- [ ] Integer overflow checks on size parameters
- [ ] No SQL injection (parameterized queries only)
- [ ] No command injection (no shell=True with user input)

---

## 4. Steganography-Specific Security

### 4.1 Carrier Image Handling
- [ ] Malformed images don't crash the server (PIL/jpegio hardening)
- [ ] DCT mode subprocess isolation for crash protection
- [ ] Memory limits on image processing
- [ ] No arbitrary code execution from image metadata

### 4.2 Payload Security
- [ ] Payload size limits enforced
- [ ] Encrypted payload indistinguishable from random noise
- [ ] No metadata leakage in output images
- [ ] Reference photo required (prevents dictionary attacks)

### 4.3 Capacity Reporting
- [ ] Capacity calculation doesn't leak information about encoding method
- [ ] Failed decodes don't reveal why (wrong key vs no data vs corrupted)

---

## 5. Network & Transport Security

### 5.1 HTTPS Configuration
- [ ] TLS 1.2+ only (no SSLv3, TLS 1.0/1.1)
- [ ] Strong cipher suites configured
- [ ] Certificate generation uses 2048+ bit RSA or P-256 EC
- [ ] Private key file permissions restricted (600)

### 5.2 Headers
- [ ] X-Frame-Options: DENY (clickjacking prevention)
- [ ] X-Content-Type-Options: nosniff
- [ ] Referrer-Policy: same-origin
- [ ] Permissions-Policy configured

### 5.3 CORS (if applicable)
- [ ] CORS not enabled (or restricted to specific origins)
- [ ] Credentials not allowed cross-origin

---

## 6. Error Handling & Logging

### 6.1 Error Messages
- [ ] Stack traces not exposed to users in production
- [ ] Error messages don't reveal sensitive paths or config
- [ ] Failed login doesn't reveal if username exists

### 6.2 Logging
- [ ] Passwords never logged
- [ ] Channel keys never logged
- [ ] Passphrases never logged
- [ ] Log files have appropriate permissions
- [ ] Sensitive operations logged for audit trail (optional)

---

## 7. Dependency Security

### 7.1 Python Dependencies
- [ ] All dependencies pinned to specific versions
- [ ] No known vulnerabilities in dependencies (run `pip-audit` or `safety`)
- [ ] Dependencies from trusted sources only (PyPI)

### 7.2 Frontend Dependencies
- [ ] All JS/CSS served locally (air-gap ready)
- [ ] No CDN dependencies
- [ ] Bootstrap and libraries are official releases
- [ ] Subresource integrity considered for any external loads

---

## 8. Deployment Security

### 8.1 File Permissions
- [ ] Database file not world-readable (600 or 640)
- [ ] SSL certificates/keys not world-readable
- [ ] Config files with secrets protected
- [ ] Instance directory not in web root

### 8.2 Docker Deployment
- [ ] Container runs as non-root user
- [ ] No unnecessary capabilities
- [ ] Resource limits configured
- [ ] Health checks don't expose sensitive info

### 8.3 Raspberry Pi Deployment
- [ ] Default passwords changed
- [ ] SSH key-only authentication (recommended)
- [ ] Unnecessary services disabled
- [ ] Firewall configured (UFW/iptables)

---

## 9. Air-Gap Specific Considerations

### 9.1 Network Isolation
- [ ] Document expected network topology
- [ ] No phone-home or telemetry
- [ ] No external API calls
- [ ] Works fully offline after deployment

### 9.2 Key Distribution
- [ ] QR code export for channel keys (offline transfer)
- [ ] Print sheet for physical key backup
- [ ] No cloud sync or external key servers

### 9.3 Updates
- [ ] Document offline update procedure
- [ ] Signed releases (future consideration)
- [ ] Checksum verification for downloads

---

## 10. Penetration Testing Checklist

### 10.1 Authentication Attacks
- [ ] Brute force login (note: no rate limiting by design)
- [ ] Session fixation
- [ ] Session hijacking
- [ ] Password reset flow abuse

### 10.2 Injection Attacks
- [ ] SQL injection on all inputs
- [ ] XSS (stored, reflected, DOM-based)
- [ ] Command injection
- [ ] Path traversal
- [ ] SSTI (Server-Side Template Injection)

### 10.3 Business Logic
- [ ] Access control bypass
- [ ] IDOR (Insecure Direct Object Reference)
- [ ] Race conditions
- [ ] Integer overflow in capacity calculations

### 10.4 Cryptographic Attacks
- [ ] Known-plaintext attacks on stego output
- [ ] Timing attacks on password verification
- [ ] Padding oracle attacks
- [ ] Key reuse vulnerabilities

---

## Tools for Automated Testing

```bash
# Dependency vulnerability scan
pip-audit
safety check

# Static analysis
bandit -r stegasoo/ frontends/

# Web security scan (if exposed)
nikto -h https://localhost:5000
OWASP ZAP (manual)

# SSL/TLS configuration
testssl.sh https://localhost:5000

# Python code quality
ruff check .
mypy stegasoo/
```

---

## Audit Schedule

| Phase | Focus Area | Priority |
|-------|-----------|----------|
| Pre-release | Crypto implementation, auth flow | Critical |
| Post-release | Dependency scan, static analysis | High |
| Quarterly | Full penetration test | Medium |
| Ongoing | CVE monitoring for dependencies | High |

---

## Notes

- This plan assumes **trusted users on a private network** as the primary deployment model
- Internet-facing deployments should add rate limiting, fail2ban, and reverse proxy hardening
- For high-security deployments, consider external security audit by professionals

---

*Last updated: 2026-01-07*
