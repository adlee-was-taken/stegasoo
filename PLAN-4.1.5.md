# Stegasoo 4.1.5 Plan

## Decode Progress Bar (Real Progress)

Mirror the encode async pattern for decode operations.

### Backend Changes

**1. Add async mode to `/decode` route (`app.py`)**
- Check for `async=true` form param
- Generate job_id, store job, submit to executor
- Return `{"job_id": ..., "status": "pending"}` immediately

**2. Add decode status/progress endpoints (`app.py`)**
```python
@app.route("/decode/status/<job_id>")
def decode_status(job_id):
    # Return {"status": "pending|running|complete|error", "result": {...}}

@app.route("/decode/progress/<job_id>")
def decode_progress(job_id):
    # Read from /tmp/stegasoo_progress_{job_id}.json
    # Return {"percent": 0-100, "phase": "..."}
```

**3. Add `_run_decode_job()` background worker (`app.py`)**
- Similar to `_run_encode_job()`
- Pass `progress_file` param to decode function
- Store result/error in job dict

**4. Update decode functions to write progress (`lsb_steganography.py`, `dct_steganography.py`)**

Phases for decode:
- `"starting"` (0%)
- `"reading"` (10%) - reading stego image
- `"extracting"` (30%) - extracting hidden data
- `"decrypting"` (60%) - Argon2 + AES decryption
- `"verifying"` (80%) - HMAC verification
- `"finalizing"` (95%) - preparing output
- `"complete"` (100%)

### Frontend Changes

**5. Update decode form submission (`decode.html`)**
- Add async form handler like encode
- Call `Stegasoo.submitDecodeAsync(form, btn)`

**6. Add decode async methods (`stegasoo.js`)**
```javascript
submitDecodeAsync(form, btn)     // POST with async=true, show modal
pollDecodeProgress(jobId)        // Poll /decode/status, /decode/progress
```

Reuse existing:
- `showProgressModal('Decoding')`
- `updateProgress(percent, phase)`

**7. Handle decode result redirect**
- On complete: redirect to `/decode/result/{file_id}` or display inline

### Files to Modify

```
frontends/web/app.py
  - Add async handling to /decode route (~line 1300+)
  - Add /decode/status/<job_id> endpoint
  - Add /decode/progress/<job_id> endpoint
  - Add _run_decode_job() function

frontends/web/static/js/stegasoo.js
  - Add submitDecodeAsync()
  - Add pollDecodeProgress()

frontends/web/templates/decode.html
  - Update form submit to use async mode

src/stegasoo/lsb_steganography.py
  - Add progress_file param to decode()
  - Write progress at each phase

src/stegasoo/dct_steganography.py
  - Add progress_file param to decode()
  - Write progress at each phase
```

### Testing Checklist

- [ ] Decode shows progress modal on submit
- [ ] Progress bar animates through phases
- [ ] Successful decode redirects to result
- [ ] Failed decode shows error in modal
- [ ] Works for both LSB and DCT modes
- [ ] Works for message and file payloads
- [ ] Progress file cleaned up after completion

---

---

## Browser Webcam QR Scanning

Add webcam-based QR code scanning for all key input fields.

### Use Cases
- Import channel key via QR scan on account page
- Scan QR codes instead of typing long keys

### Implementation

**1. Add JS QR scanning library**
- Use `jsQR` or `html5-qrcode` (client-side, no server needed)
- Include via CDN in base template

**2. Add camera button to channel key inputs**
- Account page: "Add Key" field
- Encode/decode pages: channel key selector (if manual input)

**3. Camera modal component**
- Request camera permission
- Live video preview
- Auto-detect QR and populate input field
- Close modal on successful scan

### Files to Modify
```
frontends/web/templates/base.html      - Add QR library CDN
frontends/web/templates/account.html   - Camera button + modal
frontends/web/static/js/stegasoo.js    - QR scan methods
```

### Testing Checklist
- [ ] Camera permission prompt works
- [ ] QR detected and input populated
- [ ] Works on mobile browsers
- [ ] Graceful fallback if no camera

---

## Other 4.1.5 Ideas (if time)

- [ ] Role-based permissions: admin / mod / user
- [ ] Better capacity estimates / pre-flight check
- [ ] Stego detection tool

## Bugs / Nice to Have

- [ ] **flash-stock-img.sh 16GB resize not working** - partition still full SD size after flash, makes dd pull slow. Investigate resize2fs/parted logic and test fix.
