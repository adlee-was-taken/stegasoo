# Web Frontend Update Summary for v3.2.0

## Overview

The Flask web frontend has been updated to align with Stegasoo v3.2.0's breaking changes:
1. **Removed date dependency** - No date selection or tracking in UI
2. **Renamed day_phrase → passphrase** - Updated all forms and templates
3. **Increased default words** - From 3 to 4 for better security

## Key Changes

### 1. Form Parameter Changes

#### Generate Page

**Before (v3.1.0):**
```python
words_per_phrase = int(request.form.get('words_per_phrase', 3))
# Generated daily phrases for all days of the week
```

**After (v3.2.0):**
```python
words_per_passphrase = int(request.form.get('words_per_passphrase', 4))
# Generates single passphrase
```

**Template variables changed:**
- `phrases` → `passphrase` (single string instead of dict)
- `words_per_phrase` → `words_per_passphrase`
- `phrase_entropy` → `passphrase_entropy`
- Removed `days` variable (no longer needed)

#### Encode Page

**Before (v3.1.0):**
```python
day_phrase = request.form.get('day_phrase', '')
client_date = request.form.get('client_date', '').strip()
day_of_week = get_today_day()  # Used in template

encode_result = encode(
    ...,
    day_phrase=day_phrase,
    date_str=date_str,
    ...
)
```

**After (v3.2.0):**
```python
passphrase = request.form.get('passphrase', '')
# No client_date or day_of_week needed

encode_result = encode(
    ...,
    passphrase=passphrase,  # Renamed
    # date_str removed
    ...
)
```

#### Decode Page

**Before (v3.1.0):**
```python
day_phrase = request.form.get('day_phrase', '')
stego_date = request.form.get('stego_date', '').strip()

decode_result = decode(
    ...,
    day_phrase=day_phrase,
    date_str=stego_date if stego_date else None,
    ...
)
```

**After (v3.2.0):**
```python
passphrase = request.form.get('passphrase', '')
# No stego_date needed

decode_result = decode(
    ...,
    passphrase=passphrase,  # Renamed
    # date_str removed
    ...
)
```

### 2. Template Context Updates

**inject_globals() changes:**

**Added:**
```python
'min_passphrase_words': MIN_PASSPHRASE_WORDS,
'recommended_passphrase_words': RECOMMENDED_PASSPHRASE_WORDS,
'default_passphrase_words': DEFAULT_PASSPHRASE_WORDS,
```

**Used for:**
- Showing passphrase length requirements
- Default values in generate form
- Validation messages

### 3. Validation Updates

**Added passphrase validation:**
```python
from stegasoo import validate_passphrase

# In encode_page()
result = validate_passphrase(passphrase)
if not result.is_valid:
    flash(result.error_message, 'error')
    return ...

# Show warning if passphrase is short
if result.warning:
    flash(result.warning, 'warning')
```

### 4. Error Message Updates

**Before:**
```python
flash('Day phrase is required', 'error')
flash('Decryption failed. Check your phrase, PIN...', 'error')
```

**After:**
```python
flash('Passphrase is required', 'error')
flash('Decryption failed. Check your passphrase, PIN...', 'error')
```

## Template Changes Needed

These Flask routes will need corresponding template updates:

### generate.html

**Changes needed:**
```html
<!-- Before -->
<label for="words_per_phrase">Words per phrase</label>
<input type="number" name="words_per_phrase" value="3">

{% if generated %}
  <h3>Daily Phrases</h3>
  {% for day in days %}
    <tr>
      <td>{{ day }}</td>
      <td>{{ phrases[day] }}</td>
    </tr>
  {% endfor %}
{% endif %}

<!-- After -->
<label for="words_per_passphrase">Words per passphrase</label>
<input type="number" name="words_per_passphrase" value="{{ default_passphrase_words }}">

{% if generated %}
  <h3>Passphrase</h3>
  <div class="passphrase-display">
    <code>{{ passphrase }}</code>
    <p class="help-text">Use this passphrase to encode and decode messages (no date needed!)</p>
  </div>
{% endif %}
```

**Entropy display:**
```html
<!-- Before -->
<li>Phrase entropy: {{ phrase_entropy }} bits</li>

<!-- After -->
<li>Passphrase entropy: {{ passphrase_entropy }} bits ({{ words_per_passphrase }} words)</li>
```

### encode.html

**Changes needed:**
```html
<!-- Before -->
<label for="day_phrase">Day Phrase</label>
<input type="text" name="day_phrase" required>

<label for="client_date">Encoding Date (Optional)</label>
<input type="date" name="client_date">
<p class="help-text">Defaults to today: {{ day_of_week }}</p>

<!-- After -->
<label for="passphrase">Passphrase</label>
<input type="text" name="passphrase" required 
       placeholder="Enter at least {{ recommended_passphrase_words }} words">
<p class="help-text">
  v3.2.0: No date needed! Use your passphrase anytime.
</p>
```

### decode.html

**Changes needed:**
```html
<!-- Before -->
<label for="day_phrase">Day Phrase</label>
<input type="text" name="day_phrase" required>

<label for="stego_date">Encoding Date</label>
<input type="date" name="stego_date" id="stego_date">
<p class="help-text">Will be auto-detected from filename if possible</p>

<script>
// Auto-detect date from filename
stegoInput.addEventListener('change', function() {
  const filename = this.files[0]?.name || '';
  const dateMatch = filename.match(/_(\d{4})(\d{2})(\d{2})/);
  if (dateMatch) {
    document.getElementById('stego_date').value = 
      `${dateMatch[1]}-${dateMatch[2]}-${dateMatch[3]}`;
  }
});
</script>

<!-- After -->
<label for="passphrase">Passphrase</label>
<input type="text" name="passphrase" required 
       placeholder="Enter your passphrase">
<p class="help-text">
  v3.2.0: No date needed to decode!
</p>

<!-- Remove date detection script -->
```

### index.html

**Changes needed:**
```html
<!-- Before -->
<p>Generate daily passphrases and security credentials</p>
<p>Hide messages using day-specific phrases</p>

<!-- After -->
<p>Generate passphrases and security credentials</p>
<p>v3.2.0: Simplified - no more daily rotation!</p>
```

### about.html

**Add v3.2.0 section:**
```html
<h2>Version 3.2.0 Changes</h2>
<ul>
  <li><strong>No date dependency</strong> - Encode and decode anytime without tracking dates</li>
  <li><strong>Single passphrase</strong> - No more daily rotation, just remember one strong passphrase</li>
  <li><strong>Better security</strong> - Default passphrase length increased to 4 words</li>
  <li><strong>Asynchronous ready</strong> - Perfect for dead drops and delayed delivery</li>
</ul>
```

## JavaScript Changes Needed

### Remove date-related code:

```javascript
// REMOVE THIS (date detection from filename)
function detectDateFromFilename(filename) {
  const match = filename.match(/_(\d{4})(\d{2})(\d{2})/);
  if (match) {
    return `${match[1]}-${match[2]}-${match[3]}`;
  }
  return null;
}

// REMOVE THIS (day-of-week display)
function updateDayOfWeek() {
  const dateInput = document.getElementById('client_date');
  const dayDisplay = document.getElementById('day_display');
  // ...
}
```

### Update validation:

```javascript
// Before
const dayPhrase = document.getElementById('day_phrase').value;
if (!dayPhrase || dayPhrase.trim().length === 0) {
  alert('Day phrase is required');
  return false;
}

// After
const passphrase = document.getElementById('passphrase').value;
if (!passphrase || passphrase.trim().length === 0) {
  alert('Passphrase is required');
  return false;
}

// Add word count validation
const words = passphrase.trim().split(/\s+/);
if (words.length < {{ min_passphrase_words }}) {
  alert(`Passphrase should have at least {{ recommended_passphrase_words }} words`);
  return false;
}
```

## CSS Updates

Add styling for passphrase warnings:

```css
.passphrase-display {
  background: #f5f5f5;
  padding: 15px;
  border-radius: 5px;
  margin: 10px 0;
}

.passphrase-display code {
  font-size: 1.2em;
  color: #2c3e50;
  word-break: break-word;
}

.help-text.v3-2-0 {
  color: #3498db;
  font-weight: bold;
}

.flash.warning {
  background-color: #fff3cd;
  border-left: 4px solid #ffc107;
  color: #856404;
}
```

## Migration Notes for Users

Add to templates:

```html
<div class="alert alert-info">
  <h4>⚠️ v3.2.0 Breaking Changes</h4>
  <p>If you have messages encoded with v3.1.0:</p>
  <ul>
    <li>They cannot be decoded with v3.2.0</li>
    <li>You need the original v3.1.0 installation to decode them</li>
    <li>After decoding, you can re-encode with v3.2.0</li>
  </ul>
</div>
```

## Form Field Summary

### Changed Field Names

| Old Name (v3.1.0) | New Name (v3.2.0) | Type |
|-------------------|-------------------|------|
| `day_phrase` | `passphrase` | text input |
| `words_per_phrase` | `words_per_passphrase` | number input |
| `client_date` | (removed) | date input |
| `stego_date` | (removed) | date input |

### New Validation Attributes

```html
<input type="text" name="passphrase" 
       required
       minlength="{{ min_passphrase_words * 4 }}"
       placeholder="Enter at least {{ recommended_passphrase_words }} words"
       pattern="^\s*\S+(\s+\S+){3,}.*$"
       title="Please enter at least 4 words">
```

## Testing Checklist

- [ ] Generate page creates single passphrase
- [ ] Generate page shows correct entropy (4 words = 44 bits)
- [ ] Generate page doesn't show day names
- [ ] Encode page accepts passphrase (not day_phrase)
- [ ] Encode page doesn't have date selection
- [ ] Encode page shows v3.2.0 help text
- [ ] Decode page accepts passphrase
- [ ] Decode page doesn't have date input
- [ ] Decode page doesn't auto-detect date from filename
- [ ] Error messages say "passphrase" not "day phrase"
- [ ] Validation shows warnings for short passphrases
- [ ] QR code functionality still works
- [ ] DCT mode options still work
- [ ] All flash messages updated

## Implementation Status

✅ Flask routes updated
✅ Form parameter names changed
✅ Function calls updated
✅ Validation added for passphrases
✅ Error messages updated
✅ Template context updated
⏳ Templates need updating (generate.html, encode.html, decode.html, index.html, about.html)
⏳ JavaScript needs updating
⏳ CSS styling for v3.2.0 features

## Quick Reference

**To test the Flask app:**
```bash
cd frontends/web
python app.py
# Visit http://localhost:5000
```

**Key user-facing changes:**
1. Generate: Shows one passphrase, not 7 daily phrases
2. Encode: No date selection, just passphrase
3. Decode: No date needed, just passphrase

**Benefits to highlight:**
- ✅ Simpler UI (fewer fields)
- ✅ No date tracking needed
- ✅ Encode today, decode anytime
- ✅ Perfect for asynchronous communications
