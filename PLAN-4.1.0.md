# Stegasoo 4.1.0 Plan

## Overview

Version 4.1.0 is a feature release focusing on small-group deployment improvements and new utilities.

## Goals

1. ~~**Multi-User Support** - Admin can create up to 16 users for shared deployments~~ ✅ DONE
2. **Channel Key QR** - Easy visual sharing of channel keys via QR codes
3. **CLI Channel Commands** - Manage channel keys from command line
4. **Advanced Tools** - Image/stego utilities (TBD)

---

## Feature 1: Multi-User Support ✅ COMPLETED

> Implemented in commit 7b33501. All requirements met.

### Requirements

- 16 users + 1 admin maximum (17 total)
- First user created at setup is always admin
- Admin can add/delete users, reset passwords
- Regular users can only change their own password
- No self-registration (admin-invite only)

### Database Changes

**Update User model in `frontends/web/models.py`:**

```python
class User(db.Model):
    id = Column(Integer, primary_key=True)
    username = Column(String(80), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default='user')  # 'admin' or 'user'
    created_at = Column(DateTime, default=datetime.utcnow)
```

**Migration:** Add `role` and `created_at` columns. Existing users get `role='admin'`.

### New Routes

| Route | Method | Access | Description |
|-------|--------|--------|-------------|
| `/admin/users` | GET | admin | List all users |
| `/admin/users/new` | GET, POST | admin | Create user form |
| `/admin/users/<id>/delete` | POST | admin | Delete user |
| `/admin/users/<id>/reset-password` | POST | admin | Generate temp password |

### New Decorator

```python
# auth.py
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for('login'))
        if current_user.role != 'admin':
            flash('Admin access required', 'error')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated
```

### UI Changes

**Navigation (for admin users):**
- Add "Users" link in navbar (visible only to admin)

**Account page (`/account`):**
- Admin sees link to user management
- All users see their own password change form

**New template: `templates/admin/users.html`:**
- Table: Username | Role | Created | Actions
- Actions: Reset Password, Delete (disabled for self)
- "Add User" button (disabled if at 16 user limit)
- Show count: "3 of 16 users"

**New template: `templates/admin/user_new.html`:**
- Username field (email-style allowed)
- Password field (auto-populated with random 8-char, admin can override)
- Submit → confirmation page shows password once with copy button

### Validation

- Username: 3-80 chars, alphanumeric + underscore/hyphen + @/. for email-style
- Password: 8+ chars (same as current)
- Can't delete yourself
- Can't demote the last admin
- Deleting user immediately invalidates their sessions

---

## Feature 2: Channel Key QR

### Web UI

**About page additions:**

If `STEGASOO_CHANNEL_KEY` environment variable is set:

```
┌─────────────────────────────────────────┐
│  Channel Key                            │
│                                         │
│  ██████████████    Your server uses a   │
│  ██          ██    private channel key. │
│  ██  ██████  ██    Share this QR with   │
│  ██  ██████  ██    others to join.      │
│  ██          ██                         │
│  ██████████████    [Copy Key] [Download]│
│                                         │
│  Key: abc123...xyz                      │
└─────────────────────────────────────────┘
```

- QR generated server-side using `qrcode` library
- "Copy Key" copies text to clipboard
- "Download QR" saves as PNG

**Implementation:**

```python
# about route addition
@app.route('/about')
def about():
    channel_key = os.environ.get('STEGASOO_CHANNEL_KEY', '')
    channel_qr_b64 = None
    if channel_key:
        # Generate QR as base64 PNG
        qr = qrcode.make(channel_key)
        buffer = BytesIO()
        qr.save(buffer, format='PNG')
        channel_qr_b64 = base64.b64encode(buffer.getvalue()).decode()
    return render_template('about.html',
                          channel_key=channel_key,
                          channel_qr=channel_qr_b64)
```

### CLI Commands

**New command group: `stegasoo channel`**

```bash
# Generate a new channel key
stegasoo channel generate
# Output:
# Channel Key: stg_abc123...xyz789
#
# ██████████████████
# ██              ██
# ██  ██████████  ██
# ...
#
# Set in environment: export STEGASOO_CHANNEL_KEY="stg_abc123..."

# Show current key (from env or argument)
stegasoo channel show
# Output:
# Channel Key: stg_abc123...xyz789

# Display QR in terminal (ASCII)
stegasoo channel qr
# Output: ASCII QR code

# Save QR as PNG
stegasoo channel qr -o channel-key.png
# Output: Saved to channel-key.png

# Explicit format selection
stegasoo channel qr --format ascii      # Terminal (default)
stegasoo channel qr --format png -o -   # PNG to stdout
```

**Implementation notes:**

- Use `qrcode[pil]` for PNG output
- Use `qrcode` with `print_ascii()` for terminal
- Read key from `--key` argument or `STEGASOO_CHANNEL_KEY` env var
- `generate` uses existing `generate_channel_key()` from `stegasoo.channel`

---

## File Changes Summary

### New Files

| File | Description |
|------|-------------|
| `frontends/web/templates/admin/users.html` | User management page |
| `frontends/web/templates/admin/user_new.html` | Add user form |

### Modified Files

| File | Changes |
|------|---------|
| `frontends/web/models.py` | Add `role`, `created_at` to User |
| `frontends/web/auth.py` | Add `@admin_required`, user management routes |
| `frontends/web/templates/base.html` | Add Users link for admins |
| `frontends/web/templates/account.html` | Add admin link |
| `frontends/web/templates/about.html` | Add channel key QR section |
| `src/stegasoo/cli.py` | Add `channel` command group |

---

## Testing Plan

### Multi-User

1. Fresh install → first user is admin
2. Admin can create users up to limit (16)
3. Admin can't create 17th user (shows error)
4. Regular user can log in, encode/decode
5. Regular user can't access `/admin/users`
6. Admin can reset user password
7. Admin can delete user
8. Admin can't delete self
9. Existing 4.0.2 databases upgrade correctly (single user becomes admin)

### Channel Key QR

1. About page shows nothing if no channel key
2. About page shows QR + key if channel key set
3. Copy button works
4. Download gives valid PNG
5. QR scans correctly to key value

### CLI

1. `channel generate` creates valid key + shows QR
2. `channel show` displays current key
3. `channel qr` outputs ASCII to terminal
4. `channel qr -o file.png` saves PNG
5. Commands work with `--key` override
6. Commands read from env var

---

## Feature 3: Advanced Tools

### Included Tools

| Tool | Web | CLI | Description |
|------|-----|-----|-------------|
| **Capacity Calculator** | ✓ | ✓ | Upload image → show DCT/LSB capacity |
| **Metadata Stripper** | ✓ | ✓ | Remove EXIF/metadata from image |
| **Stego Detector** | ✓ | ✓ | Analyze image for signs of hidden data |
| **Image Compare** | ✓ | - | Side-by-side before/after diff |
| **Header Peek** | ✓ | ✓ | Check for Stegasoo header without decrypting |
| **Batch Mode** | - | ✓ | Encode/decode multiple files |

### Web UI: `/tools` Page

New page with card-based layout:

```
┌─────────────────────────────────────────────────────────────┐
│  🛠️ Advanced Tools                                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │ 📏 Capacity     │  │ 🧹 Metadata     │                   │
│  │   Calculator    │  │   Stripper      │                   │
│  │                 │  │                 │                   │
│  │ Check how much  │  │ Remove EXIF     │                   │
│  │ data fits       │  │ before encoding │                   │
│  └─────────────────┘  └─────────────────┘                   │
│                                                             │
│  ┌─────────────────┐  ┌─────────────────┐                   │
│  │ 🔍 Stego        │  │ 🔎 Header       │                   │
│  │   Detector      │  │   Peek          │                   │
│  │                 │  │                 │                   │
│  │ Analyze image   │  │ Check for       │                   │
│  │ for hidden data │  │ Stegasoo data   │                   │
│  └─────────────────┘  └─────────────────┘                   │
│                                                             │
│  ┌─────────────────┐                                        │
│  │ ⚖️ Image        │                                        │
│  │   Compare       │                                        │
│  │                 │                                        │
│  │ Before/after    │                                        │
│  │ diff view       │                                        │
│  └─────────────────┘                                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Each card opens a modal or expands inline for the tool interface.

### CLI Structure

```bash
# Capacity calculator
stegasoo capacity image.jpg
stegasoo capacity image.jpg --format json

# Metadata stripper
stegasoo strip image.jpg                    # Output to image_stripped.jpg
stegasoo strip image.jpg -o clean.jpg       # Custom output
stegasoo strip image.jpg --in-place         # Overwrite original

# Stego detector
stegasoo detect image.jpg
stegasoo detect image.jpg --verbose         # Detailed analysis

# Header peek
stegasoo peek image.jpg
# Output: "Stegasoo DCT header detected" or "No Stegasoo header found"

# Batch mode
stegasoo encode --batch manifest.json       # JSON with files + credentials
stegasoo decode --batch input_dir/ --out output_dir/
```

### Tool Details

#### Capacity Calculator
- Input: Image file
- Output: Dimensions, megapixels, DCT capacity, LSB capacity
- Web: Upload zone + results panel
- CLI: Table or JSON output

#### Metadata Stripper
- Input: Image file
- Output: Clean image (EXIF/metadata removed)
- Show what was removed (camera model, GPS, etc.)
- Preserve image quality

#### Stego Detector
- Input: Image file
- Analysis:
  - Chi-square analysis (LSB detection)
  - DCT coefficient histogram analysis
  - Visual inspection hints
- Output: Likelihood score + findings
- Note: Detection is probabilistic, not definitive

#### Image Compare
- Input: Two images (original + stego)
- Output:
  - Side-by-side view
  - Difference overlay (amplified)
  - Pixel-level stats (PSNR, SSIM)
- Web only (visual tool)

#### Header Peek
- Input: Image file
- Output: Header found (yes/no), mode (DCT/LSB), embedded size estimate
- Does NOT decrypt - just checks for valid header structure
- Useful for "is this a stego image?" without credentials

#### Batch Mode
- CLI only
- Manifest file (JSON) or directory-based
- Progress bar for multiple files
- Error handling per-file (continue on failure)

---

## Migration Notes

### Database Migration

For existing 4.0.2 installations:

```python
# migrations/add_user_role.py
def upgrade():
    # Add columns with defaults
    op.add_column('user', sa.Column('role', sa.String(20), default='user'))
    op.add_column('user', sa.Column('created_at', sa.DateTime))

    # Set existing users as admin (they were the first user)
    op.execute("UPDATE user SET role = 'admin' WHERE role IS NULL")
    op.execute("UPDATE user SET created_at = datetime('now') WHERE created_at IS NULL")
```

Or simpler: detect on startup, update schema automatically (current pattern).

---

## Out of Scope

- Per-user channel keys
- User groups/teams
- API authentication tokens
- User activity logging
- Password complexity rules beyond length

---

## Estimated Effort

| Component | Complexity |
|-----------|------------|
| Database schema change | Low |
| Admin routes + templates | Medium |
| Access control decorator | Low |
| About page QR | Low |
| CLI channel commands | Medium |
| Advanced Tools (TBD) | Medium-High |
| Testing | Medium |

---

## Decisions

1. **Temp password flow:** Password field auto-populates with random 8-char password. Admin can override if desired. Show password once on confirmation page.

2. **Session handling:** Yes - deleting a user immediately invalidates their active sessions (ban hammer).

3. **Username rules:** Sane requirements, email-style allowed. Validation: 3-80 chars, alphanumeric, underscore, hyphen, @ and . for email-style.

---

## Approval

- [x] Plan reviewed
- [x] Questions resolved
- [x] Ready to implement

## Progress

- [x] Multi-User Support (commit 7b33501)
- [ ] Channel Key QR
- [ ] CLI Channel Commands
- [ ] Advanced Tools
