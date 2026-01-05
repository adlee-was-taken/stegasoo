# Stegasoo 4.1.2 Plan

## Release Theme
Polish and UX improvements after the 4.1.1 stability release.

---

## 1. Real Progress Bar for Encode/Decode

**Status:** Planned

**Problem:** Users see elapsed time but no indication of how far along the operation is. Long DCT encodes on Pi can take 2-3 minutes with no feedback.

**Solution:** Polling + progress file approach

### Backend Changes

1. **dct_steganography.py** - Write progress during block loop:
   ```python
   if progress_file and block_num % 50 == 0:
       with open(progress_file, 'w') as f:
           json.dump({"current": block_num, "total": total_blocks, "phase": "embedding"}, f)
   ```

2. **app.py** - New endpoints:
   - `POST /encode` returns `job_id`, starts subprocess
   - `GET /encode/progress/<job_id>` returns progress JSON
   - `GET /encode/result/<job_id>` returns final result when done

3. **Subprocess wrapper** - Pass progress file path to encode/decode functions

### Frontend Changes

1. **stegasoo.js** - After form submit:
   - Show progress bar (Bootstrap progress component)
   - Poll `/encode/progress/{job_id}` every 500ms
   - Update bar width and percentage text
   - Show phase (hashing, embedding, encoding, etc.)

2. **Templates** - Add progress bar markup to encode.html and decode.html

### Files to Modify
- `src/stegasoo/dct_steganography.py`
- `frontends/web/app.py`
- `frontends/web/static/js/stegasoo.js`
- `frontends/web/templates/encode.html`
- `frontends/web/templates/decode.html`

---

## 2. Granular Decode Error Messages

**Status:** Planned

**Problem:** Decode failures show generic "Decryption failed" - users don't know if it's wrong photo, wrong passphrase, wrong PIN, corrupted image, or format mismatch.

**Solution:** Bubble up specific error types from library to UI

### Library Level (`src/stegasoo/`)

1. **Custom exception classes:**
   ```python
   class StegasooError(Exception): pass
   class InvalidMagicBytesError(StegasooError): pass
   class DecryptionError(StegasooError): pass
   class ReedSolomonError(StegasooError): pass
   class PayloadTooLargeError(StegasooError): pass
   class InvalidHeaderError(StegasooError): pass
   class NoDataFoundError(StegasooError): pass
   ```

2. **Raise specific exceptions** in decode paths:
   - Magic bytes mismatch → "Not a Stegasoo image or wrong mode (LSB/DCT)"
   - RS decode failure → "Image corrupted beyond repair"
   - AES-GCM auth fail → "Wrong credentials (photo/passphrase/PIN)"
   - Header parse fail → "Invalid or corrupted header"
   - No stego data → "No hidden data found in image"

3. **Error codes** for programmatic handling:
   ```python
   class ErrorCode(Enum):
       INVALID_MAGIC = "invalid_magic"
       DECRYPTION_FAILED = "decryption_failed"
       RS_FAILED = "rs_failed"
       # etc.
   ```

### Web UI Level (`frontends/web/`)

1. **app.py** - Catch specific exceptions, return error type:
   ```python
   except InvalidMagicBytesError:
       flash("This doesn't appear to be a Stegasoo image, or mode mismatch", "danger")
   except DecryptionError:
       flash("Wrong credentials - check reference photo, passphrase, and PIN", "warning")
   ```

2. **decode.html** - Error-specific help text:
   - Wrong credentials → "Double-check your reference photo matches exactly"
   - Corrupted → "Image may have been re-saved or compressed"
   - Mode mismatch → "Try switching between Auto/DCT/LSB"

### Files to Modify
- `src/stegasoo/__init__.py` (export exceptions)
- `src/stegasoo/exceptions.py` (new file)
- `src/stegasoo/dct_steganography.py`
- `src/stegasoo/steganography.py` (LSB)
- `frontends/web/app.py`
- `frontends/web/templates/decode.html`

---

## 3. Mobile-Responsive Polish

**Status:** Planned

**Problem:** UI works on mobile but has rough edges - cramped buttons, hard-to-tap targets, awkward layouts on small screens.

**Solution:** Targeted CSS/layout fixes for mobile breakpoints

### Areas to Improve

1. **Encode/Decode Forms:**
   - Stack image drop zones vertically on mobile (currently side-by-side)
   - Larger touch targets for file inputs
   - Full-width buttons on small screens
   - Passphrase input readable at smaller sizes

2. **Navigation:**
   - Hamburger menu for mobile navbar (if not already)
   - Sticky header doesn't eat too much screen
   - Easy thumb reach for main actions

3. **Results/Output:**
   - Download buttons full-width on mobile
   - QR codes sized appropriately
   - Click-to-copy message box works well with touch

4. **Drop Zones:**
   - Larger tap targets
   - Visual feedback for touch (not just hover)
   - Camera integration hint on mobile ("Tap to take photo or choose file")

### Testing Targets
- iPhone SE (small)
- iPhone 14 (medium)
- iPad (tablet)
- Android Chrome

### Files to Modify
- `frontends/web/static/css/style.css` (or new mobile.css)
- `frontends/web/templates/encode.html`
- `frontends/web/templates/decode.html`
- `frontends/web/templates/base.html` (navbar)

---

## Testing Checklist

- [ ] Progress bar works on localhost
- [ ] Progress bar works on Pi (slower, more visible)
- [ ] Cancellation handling (what if user navigates away?)
- [ ] Error states display correctly
- [ ] Smoke test passes

---

## Notes

- Keep 4.1.2 focused - 3 features max
- Don't break DCT compatibility (4.1.1 RS format is stable)
- Test on Pi before release
