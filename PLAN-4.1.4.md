# Stegasoo 4.1.4 Plan

## Build / Deploy
- [x] Pre-built Python 3.12 venv tarball for Pi (skip 20+ min compile) - see details below
- [x] Fixed partition sizing in flash script (16GB rootfs for faster imaging)
- [x] Rename `flash-pi.sh` → `flash-stock-img.sh` for clarity
- [x] pip-audit integration in release validation

### Pi venv Tarball Approach
1. Flash fresh Pi image, let it fully build (20+ min compile)
2. Once running and working, SSH in and create optimized tarball:
   ```bash
   cd /opt/stegasoo
   # Strip caches and tests (295MB → 208MB)
   find venv/ -type d -name '__pycache__' -exec rm -rf {} + 2>/dev/null
   find venv/ -type d -name 'tests' -exec rm -rf {} + 2>/dev/null
   find venv/ -type d -name 'test' -exec rm -rf {} + 2>/dev/null
   # Compress with zstd (208MB → 39MB)
   tar -cf - venv/ | zstd -19 -T0 > /tmp/stegasoo-venv-pi-arm64.tar.zst
   ```
3. Pull tarball to host: `scp admin@pi:/tmp/stegasoo-venv-pi-arm64.tar.zst rpi/`
4. setup.sh auto-detects and extracts tarball if present in rpi/
5. Re-flash and test fresh build with pre-built venv (should be <2 min vs 20+)

## Features
- [x] QR channel key sharing (see detailed plan below)
- [ ] Role-based permissions: admin / mod / user
- [x] `stegasoo info` fastfetch-style command (version, service status, channel, CPU, temp, etc.)
- [ ] Better capacity estimates / pre-flight check before encode fails

---

## QR Channel Key Sharing - Implementation Plan

### Current State
- ✅ **CLI**: `stegasoo channel qr` generates ASCII/PNG QR for server channel key
- ✅ **Web UI (about.html)**: Client-side QR generator exists - input key, generate/show QR, download PNG
- ✅ **Account page**: Shows saved channel keys with fingerprint, rename, delete
- ❌ No role restrictions on QR sharing
- ❌ No QR button for saved keys on account page
- ❌ No QR scanning to import keys

### Design Decisions

**UI Placement** (avoiding encode/decode page crowding):
- Keep QR generator in **about.html** (already exists, logical place for tools)
- Add QR button to **account.html** saved keys (small icon, doesn't crowd)
- Both should be admin-only

**Role Restriction** (per user request):
- QR sharing = admin only (hide generator + saved key QR buttons from non-admins)
- Prerequisite: Need role-based permissions feature first
- Interim option: Just hide from non-admin users using existing `is_admin` flag

### Implementation Steps

#### Phase 1: Admin-only restriction (quick win)
1. **about.html**: Wrap QR generator section in `{% if is_admin %}` block
2. **Account route**: Pass `is_admin` to template (if not already)
3. **account.html**: Add small QR icon button to saved keys row (admin only)
   - Opens modal with QR canvas (reuse qrcode.js pattern from about.html)
   - Download PNG button in modal

#### Phase 2: QR Import (optional enhancement)
1. Add "Import via QR" button to account.html key-add section
2. Use device camera or file upload to scan QR
3. Decode and populate channel_key input field
4. Requires `pyzbar` on server OR client-side JS library like `jsQR`

### Files to Modify

```
frontends/web/app.py
  - about() route: Add missing vars: is_admin, channel_configured,
    channel_fingerprint, channel_source (BUG: currently not passed!)
  - account() route: ✅ Already passes is_admin

frontends/web/templates/about.html
  - Wrap channel key QR section in {% if is_admin %}

frontends/web/templates/account.html
  - Add QR button to saved keys (admin only)
  - Add QR modal (copy pattern from about.html)
  - Include qrcode.min.js CDN script
```

### Bug Found During Research
The about.html template uses `channel_configured`, `channel_fingerprint`,
`channel_source` but the route doesn't pass them - always shows "public mode".
Fix this while implementing QR admin restriction.

### Exact Code Changes

**app.py - Fix about() route (around line 1564):**
```python
@app.route("/about")
def about():
    from stegasoo.channel import get_channel_status
    channel_status = get_channel_status()

    # Check if user is admin (for QR sharing)
    current_user = get_current_user()
    is_admin = current_user.is_admin if current_user else False

    return render_template(
        "about.html",
        has_argon2=has_argon2(),
        has_qrcode_read=HAS_QRCODE_READ,
        # Channel info (bugfix)
        channel_configured=channel_status["configured"],
        channel_fingerprint=channel_status.get("fingerprint"),
        channel_source=channel_status.get("source"),
        # Admin check for QR sharing
        is_admin=is_admin,
    )
```

### Template Changes Preview

**account.html - Add to saved key row:**
```html
{% if is_admin %}
<button type="button" class="btn btn-outline-info btn-sm"
        onclick="showKeyQr('{{ key.channel_key }}')" title="Show QR">
    <i class="bi bi-qr-code"></i>
</button>
{% endif %}
```

**about.html - Wrap existing section:**
```html
{% if is_admin %}
<!-- Channel Key QR Generator -->
<div class="card bg-dark border-secondary">
    ...existing QR generator...
</div>
{% endif %}
```

### Testing Checklist (Phase 1 Implemented)
- [ ] Non-admin users cannot see QR generator in about.html
- [ ] Non-admin users cannot see QR buttons on account page
- [ ] Admin users can generate QR for any saved key
- [ ] QR downloads work correctly
- [ ] QR scans correctly with phone camera

### Implementation Status
**Phase 1: COMPLETE** - Admin-only QR sharing implemented:
- `app.py`: Fixed about() route to pass channel status + is_admin
- `about.html`: QR generator wrapped in `{% if is_admin %}` with Admin badge
- `account.html`: QR button added to saved keys (admin only), modal + JS for generation/download

---

## Security
- [ ] Optional encryption for temp file storage (paranoid mode, config toggle)

## Docs
- [x] Update UNDER_THE_HOOD.md (v4.1 changes, channel keys)
- [ ] General docs refresh

## Ideas (maybe later)
- [ ] Stego detection tool
- [ ] Browser extension
- [ ] Pi snapshot/backup feature
