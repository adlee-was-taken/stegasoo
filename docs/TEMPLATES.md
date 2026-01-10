# Stegasoo Web Templates Specification

Quick reference for all Jinja2 templates in `frontends/web/templates/`.

## Table of Contents

- [Layout](#layout)
- [Auth & Setup](#auth--setup)
- [Core Features](#core-features)
- [Tools & Account](#tools--account)
- [Admin](#admin)

---

## Layout

### `base.html`
**Purpose:** Master layout template - all pages extend this.

| Block | Description |
|-------|-------------|
| `{% block title %}` | Page title |
| `{% block content %}` | Main page content |
| `{% block scripts %}` | Page-specific JS |

**Key Elements:**
- `nav.navbar` - Bootstrap 5 navbar with logo, links, auth buttons
- `div.toast-container` - Flash message toasts (10s auto-dismiss)
- `main.container` - Content wrapper
- `footer` - Copyright + version

**Variables:** `is_authenticated`, `username`, `is_admin`

---

## Auth & Setup

### `login.html`
**Route:** `/login`

**Form:** `POST /login`
- `username` - text input
- `password` - password input
- "Forgot password?" link to `/recover`

**JS:** `static/js/auth.js` - password toggle

---

### `setup.html`
**Route:** `/setup` (first-run only)

**Form:** `POST /setup`
- `username` - admin username
- `password` - password (min 8 chars)
- `password_confirm` - confirmation

**JS:** Password confirmation validation

---

### `setup_recovery.html`
**Route:** `/setup/recovery`

**Form:** `POST /setup/recovery`
- `recovery_key` - hidden, pre-generated
- `action` - "save" or "skip"
- Checkbox confirmation required for save

**Features:**
- Recovery key display (readonly input)
- Copy to clipboard button
- QR code image (if available)
- Download options: text file, QR image
- Stego backup upload form

---

### `recover.html`
**Route:** `/recover`

**Form:** `POST /recover`
- `recovery_key` - textarea for key input
- `new_password` - new password
- `new_password_confirm` - confirmation

**Accordion:** "Extract from stego backup"
- `POST /recover/stego` with `stego_image` + `reference_image`
- Pre-fills recovery key on success

---

### `regenerate_recovery.html`
**Route:** `/account/recovery/regenerate` (admin only)

**Form:** `POST /account/recovery/regenerate`
- `recovery_key` - hidden field
- `action` - "save" or "cancel"
- Confirmation checkbox

**Features:**
- New key display
- QR code (obfuscated)
- Download: text, QR, stego backup
- Warning if replacing existing key

---

## Core Features

### `index.html`
**Route:** `/`

**Structure:**
- Hero section with tagline
- 3 action cards: Encode, Decode, Generate
- "How It Works" explainer section

---

### `generate.html`
**Route:** `/generate`

**Form:** `POST /generate`
- `words` - passphrase word count (3-12)
- `use_pin` - checkbox
- `pin_length` - PIN digits (6-9)
- `use_rsa` - checkbox
- `rsa_bits` - key size (2048/3072)

**Output panels:**
- Passphrase display
- PIN display (if enabled)
- RSA key + QR (if enabled)
- Entropy calculator

**JS:** `static/js/generate.js`

---

### `encode.html`
**Route:** `/encode`

**Form:** `POST /encode` (multipart)
- `reference_photo` - file upload (drag-drop zone)
- `carrier_image` - file upload (drag-drop zone)
- `mode` - radio: DCT (default) / LSB
- `dct_format` - PNG / JPEG
- `dct_color` - Color / Grayscale
- `payload_type` - radio: Text / File
- `message` - textarea (if text)
- `embed_file` - file input (if file)
- `passphrase` - text input
- `pin` - text input
- `rsa_key` / `rsa_key_qr` - file inputs
- `rsa_key_password` - password
- `channel_key` - select (saved keys) or manual input

**Panels:**
- Reference preview with "Hash Acquired" status
- Carrier preview with capacity info
- Character counter for message

**JS:** `static/js/encode.js`, `static/js/stegasoo.js`

---

### `encode_result.html`
**Route:** `/encode/result/<file_id>`

**Elements:**
- Success message
- Stego image preview
- Download button
- Share button (Web Share API)
- Mode/capacity info
- "Encode Another" link

**Variables:** `file_id`, `filename`, `mode`, `capacity_used`

---

### `decode.html`
**Route:** `/decode`

**Form:** `POST /decode` (multipart)
- `reference_photo` - file upload
- `stego_image` - file upload
- `passphrase` - text input
- `pin` - text input
- `rsa_key` / `rsa_key_qr` - file inputs
- `rsa_key_password` - password
- `channel_key` - select or manual

**Output:**
- Decoded message display
- File download (if file payload)

**JS:** `static/js/decode.js`, `static/js/stegasoo.js`

---

## Tools & Account

### `tools.html`
**Route:** `/tools`

**Tabbed interface:**

| Tab | Endpoint | Description |
|-----|----------|-------------|
| Capacity | `POST /api/tools/capacity` | Image capacity analysis |
| Peek | `POST /api/tools/peek` | Check for Stegasoo header |
| Strip | `POST /api/tools/strip` | Remove hidden data |
| EXIF | `POST /api/tools/exif/*` | Metadata viewer/editor |

**EXIF Editor features:**
- Upload image → view all EXIF fields
- Inline editing (click field to edit)
- "Clear All" button
- "Save" / "Download" buttons

**JS:** `static/js/tools.js`

---

### `account.html`
**Route:** `/account`

**Sections:**

1. **User Info** - Username, role badge, logout link

2. **Recovery Key** (admin only)
   - Status: Configured / Not Set
   - Generate/Regenerate button
   - Disable button

3. **Password Change**
   - `current_password`
   - `new_password`
   - `new_password_confirm`

4. **Saved Channel Keys**
   - List of saved keys with edit/delete
   - "Add Key" form (name + key)
   - Max 10 keys per user

**Variables:** `username`, `is_admin`, `has_recovery`, `channel_keys`

---

### `about.html`
**Route:** `/about`

**Sections:**
- Version info + feature badges
- Security model explanation
- Channel key QR (if configured)
- Dependency status table
- Credits + links

**Variables:** `version`, `has_dct`, `has_qr_write`, `has_qr_read`, `channel_key`, `channel_qr`

---

## Admin

### `admin/users.html`
**Route:** `/admin/users`

**Table columns:** Username | Role | Created | Actions

**Actions per user:**
- Reset Password button
- Delete button (disabled for self)

**Header:**
- User count: "X of 16 users"
- "Add User" button (modal trigger)

**Modal:** Add User form
- `username` input
- `role` select (admin/user)
- Auto-generated temp password display

---

### `admin/user_new.html`
**Route:** `/admin/users/new`

**Form:** `POST /admin/users/new`
- `username` - text input
- `role` - select (user/admin)

Redirects to `user_created.html` on success.

---

### `admin/user_created.html`
**Route:** `/admin/users/created`

**Display:**
- Success message
- Username
- Temporary password (copy button)
- "User must change password on first login" notice
- Back to users link

---

### `admin/password_reset.html`
**Route:** `/admin/users/<id>/password-reset`

**Display:**
- Success message
- New temporary password
- Copy button
- Back link

---

## Common Patterns

### Drag-Drop Upload Zones
```html
<div class="upload-zone" id="referenceZone">
    <input type="file" name="reference_photo" accept="image/*">
    <div class="preview"></div>
    <div class="status"></div>
</div>
```

### Password Toggle
```html
<div class="input-group">
    <input type="password" id="passwordInput">
    <button onclick="togglePassword('passwordInput', this)">
        <i class="bi bi-eye"></i>
    </button>
</div>
```

### Toast Flash Messages
Rendered in `base.html`, auto-dismiss after 10 seconds:
- `success` → green
- `warning` → yellow
- `error` → red

---

## External JS Files

| File | Used By |
|------|---------|
| `static/js/stegasoo.js` | encode, decode, about |
| `static/js/auth.js` | login, setup, recover, account |
| `static/js/generate.js` | generate |
| `static/js/encode.js` | encode |
| `static/js/decode.js` | decode |
| `static/js/tools.js` | tools |
