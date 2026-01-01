# API Update Summary for v3.2.0

## Overview

The FastAPI REST API has been updated to align with Stegasoo v3.2.0's breaking changes:
1. **Removed date dependency** - No `date_str` field in requests
2. **Renamed day_phrase → passphrase** - Updated all request/response models
3. **Updated generation** - Now generates single passphrase instead of daily phrases

## Breaking Changes

### Request Model Changes

#### 1. EncodeRequest & EncodeFileRequest

**Before (v3.1.0):**
```python
class EncodeRequest(BaseModel):
    message: str
    reference_photo_base64: str
    carrier_image_base64: str
    day_phrase: str  # ← Changed to passphrase
    pin: str = ""
    rsa_key_base64: Optional[str] = None
    rsa_password: Optional[str] = None
    date_str: Optional[str] = None  # ← REMOVED
    embed_mode: EmbedModeType = "lsb"
```

**After (v3.2.0):**
```python
class EncodeRequest(BaseModel):
    message: str
    reference_photo_base64: str
    carrier_image_base64: str
    passphrase: str = Field(description="Passphrase (v3.2.0: renamed from day_phrase)")
    pin: str = ""
    rsa_key_base64: Optional[str] = None
    rsa_password: Optional[str] = None
    # date_str removed in v3.2.0
    embed_mode: EmbedModeType = "lsb"
    dct_output_format: DctOutputFormatType = "png"
    dct_color_mode: DctColorModeType = "grayscale"
```

#### 2. DecodeRequest

**Before (v3.1.0):**
```python
class DecodeRequest(BaseModel):
    stego_image_base64: str
    reference_photo_base64: str
    day_phrase: str  # ← Changed to passphrase
    pin: str = ""
    rsa_key_base64: Optional[str] = None
    rsa_password: Optional[str] = None
    embed_mode: ExtractModeType = "auto"
```

**After (v3.2.0):**
```python
class DecodeRequest(BaseModel):
    stego_image_base64: str
    reference_photo_base64: str
    passphrase: str = Field(description="Passphrase (v3.2.0: renamed from day_phrase)")
    pin: str = ""
    rsa_key_base64: Optional[str] = None
    rsa_password: Optional[str] = None
    embed_mode: ExtractModeType = "auto"
```

#### 3. GenerateRequest

**Before (v3.1.0):**
```python
class GenerateRequest(BaseModel):
    use_pin: bool = True
    use_rsa: bool = False
    pin_length: int = Field(default=6, ge=MIN_PIN_LENGTH, le=MAX_PIN_LENGTH)
    rsa_bits: int = Field(default=2048)
    words_per_phrase: int = Field(default=3, ge=MIN_PHRASE_WORDS, le=MAX_PHRASE_WORDS)
```

**After (v3.2.0):**
```python
class GenerateRequest(BaseModel):
    use_pin: bool = True
    use_rsa: bool = False
    pin_length: int = Field(default=6, ge=MIN_PIN_LENGTH, le=MAX_PIN_LENGTH)
    rsa_bits: int = Field(default=2048)
    words_per_passphrase: int = Field(
        default=DEFAULT_PASSPHRASE_WORDS,  # = 4, was 3
        ge=MIN_PASSPHRASE_WORDS,
        le=MAX_PASSPHRASE_WORDS,
        description="Words per passphrase (v3.2.0: default increased to 4)"
    )
```

### Response Model Changes

#### 1. GenerateResponse

**Before (v3.1.0):**
```python
class GenerateResponse(BaseModel):
    phrases: dict[str, str]  # Monday -> phrase, Tuesday -> phrase, etc.
    pin: Optional[str] = None
    rsa_key_pem: Optional[str] = None
    entropy: dict[str, int]
```

**After (v3.2.0):**
```python
class GenerateResponse(BaseModel):
    passphrase: str = Field(description="Single passphrase (v3.2.0: no daily rotation)")
    pin: Optional[str] = None
    rsa_key_pem: Optional[str] = None
    entropy: dict[str, int]
    # Legacy field for compatibility
    phrases: Optional[dict[str, str]] = Field(
        default=None,
        description="Deprecated: Use 'passphrase' instead"
    )
```

#### 2. EncodeResponse

**Before (v3.1.0):**
```python
class EncodeResponse(BaseModel):
    stego_image_base64: str
    filename: str
    capacity_used_percent: float
    date_used: str
    day_of_week: str
    embed_mode: str
    output_format: str = "png"
    color_mode: str = "color"
```

**After (v3.2.0):**
```python
class EncodeResponse(BaseModel):
    stego_image_base64: str
    filename: str
    capacity_used_percent: float
    embed_mode: str
    output_format: str = "png"
    color_mode: str = "color"
    # Legacy fields (no longer used in crypto)
    date_used: Optional[str] = Field(
        default=None,
        description="Deprecated: Date no longer used in v3.2.0"
    )
    day_of_week: Optional[str] = Field(
        default=None,
        description="Deprecated: Date no longer used in v3.2.0"
    )
```

### Endpoint Changes

#### 1. POST /encode

**Before (v3.1.0):**
```json
{
  "message": "Secret message",
  "reference_photo_base64": "...",
  "carrier_image_base64": "...",
  "day_phrase": "apple forest thunder",
  "date_str": "2025-01-15",
  "pin": "123456",
  "embed_mode": "lsb"
}
```

**After (v3.2.0):**
```json
{
  "message": "Secret message",
  "reference_photo_base64": "...",
  "carrier_image_base64": "...",
  "passphrase": "apple forest thunder mountain",
  "pin": "123456",
  "embed_mode": "lsb"
}
```

#### 2. POST /decode

**Before (v3.1.0):**
```json
{
  "stego_image_base64": "...",
  "reference_photo_base64": "...",
  "day_phrase": "apple forest thunder",
  "pin": "123456",
  "embed_mode": "auto"
}
```

**After (v3.2.0):**
```json
{
  "stego_image_base64": "...",
  "reference_photo_base64": "...",
  "passphrase": "apple forest thunder mountain",
  "pin": "123456",
  "embed_mode": "auto"
}
```

#### 3. POST /generate

**Response Before (v3.1.0):**
```json
{
  "phrases": {
    "Monday": "apple forest thunder",
    "Tuesday": "banana river lightning",
    ...
  },
  "pin": "123456",
  "rsa_key_pem": null,
  "entropy": {
    "phrase": 33,
    "pin": 20,
    "rsa": 0,
    "total": 53
  }
}
```

**Response After (v3.2.0):**
```json
{
  "passphrase": "apple forest thunder mountain",
  "pin": "123456",
  "rsa_key_pem": null,
  "entropy": {
    "passphrase": 44,
    "pin": 20,
    "rsa": 0,
    "total": 64
  },
  "phrases": null
}
```

#### 4. POST /encode/multipart

**Form Fields Before (v3.1.0):**
- `day_phrase` (required)
- `date_str` (optional)
- `reference_photo` (file)
- `carrier` (file)
- ...

**Form Fields After (v3.2.0):**
- `passphrase` (required) ← renamed from day_phrase
- `reference_photo` (file)
- `carrier` (file)
- ... (date_str removed)

**Response Headers Before (v3.1.0):**
```
X-Stegasoo-Date: 2025-01-15
X-Stegasoo-Day: Wednesday
X-Stegasoo-Capacity-Percent: 25.5
X-Stegasoo-Embed-Mode: lsb
```

**Response Headers After (v3.2.0):**
```
X-Stegasoo-Capacity-Percent: 25.5
X-Stegasoo-Embed-Mode: lsb
X-Stegasoo-Output-Format: png
X-Stegasoo-Color-Mode: color
X-Stegasoo-Version: 3.2.0
```

### New Status Endpoint Information

#### GET /

**Added to response:**
```json
{
  "version": "3.2.0",
  ...
  "breaking_changes": {
    "date_removed": "No date_str parameter needed - encode/decode anytime",
    "passphrase_renamed": "day_phrase → passphrase (single passphrase, no daily rotation)",
    "format_version": 4,
    "backward_compatible": false
  }
}
```

## Migration Guide for API Clients

### 1. Update Request Bodies

**Find and replace in client code:**
```javascript
// Before
{
  day_phrase: "apple forest thunder",
  date_str: "2025-01-15"
}

// After
{
  passphrase: "apple forest thunder mountain"
}
```

### 2. Update Response Handling

**Before:**
```javascript
const response = await fetch('/encode', {
  method: 'POST',
  body: JSON.stringify({
    message: "secret",
    day_phrase: "words",
    date_str: "2025-01-15",
    ...
  })
});

const data = await response.json();
console.log(data.date_used);  // "2025-01-15"
console.log(data.day_of_week);  // "Wednesday"
```

**After:**
```javascript
const response = await fetch('/encode', {
  method: 'POST',
  body: JSON.stringify({
    message: "secret",
    passphrase: "longer words here now",
    // date_str removed
    ...
  })
});

const data = await response.json();
// date_used and day_of_week are null in v3.2.0
```

### 3. Update Generate Endpoint Usage

**Before:**
```javascript
const creds = await fetch('/generate', {
  method: 'POST',
  body: JSON.stringify({ use_pin: true })
}).then(r => r.json());

// Use Monday's phrase
const mondayPhrase = creds.phrases['Monday'];
```

**After:**
```javascript
const creds = await fetch('/generate', {
  method: 'POST',
  body: JSON.stringify({ use_pin: true })
}).then(r => r.json());

// Use single passphrase
const passphrase = creds.passphrase;
```

### 4. Update Multipart Requests

**Before (JavaScript fetch):**
```javascript
const formData = new FormData();
formData.append('day_phrase', 'apple forest thunder');
formData.append('date_str', '2025-01-15');
formData.append('reference_photo', refPhotoFile);
formData.append('carrier', carrierFile);
formData.append('message', 'secret');
formData.append('pin', '123456');

const response = await fetch('/encode/multipart', {
  method: 'POST',
  body: formData
});
```

**After (JavaScript fetch):**
```javascript
const formData = new FormData();
formData.append('passphrase', 'apple forest thunder mountain');
// date_str removed
formData.append('reference_photo', refPhotoFile);
formData.append('carrier', carrierFile);
formData.append('message', 'secret');
formData.append('pin', '123456');

const response = await fetch('/encode/multipart', {
  method: 'POST',
  body: formData
});
```

## Testing Checklist

### Endpoints to Test

- [ ] GET / - Returns v3.2.0 with breaking_changes info
- [ ] GET /modes - Returns mode information
- [ ] POST /generate - Returns single passphrase
- [ ] POST /encode - Works without date_str
- [ ] POST /encode/file - Works without date_str
- [ ] POST /decode - Works without date_str
- [ ] POST /encode/multipart - Accepts passphrase instead of day_phrase
- [ ] POST /decode/multipart - Accepts passphrase instead of day_phrase
- [ ] POST /compare - Still works
- [ ] POST /will-fit - Still works
- [ ] POST /image/info - Still works
- [ ] POST /extract-key-from-qr - Still works

### Validation Tests

- [ ] Reject requests with `day_phrase` field (should get validation error)
- [ ] Reject requests with `date_str` field (should be ignored or error)
- [ ] Accept requests with `passphrase` field
- [ ] Generate response includes `passphrase` field
- [ ] Generate response has `phrases` as null
- [ ] Encode response has `date_used` and `day_of_week` as null
- [ ] Multipart encode works with new field names
- [ ] Response headers updated correctly

## OpenAPI/Swagger Documentation

The FastAPI auto-generated documentation (/docs and /redoc) will automatically reflect the changes:

1. **Models updated** - Request/response schemas show new field names
2. **Descriptions updated** - Field descriptions mention v3.2.0 changes
3. **Examples updated** - Interactive API explorer uses new field names

Users can browse to `/docs` to see the updated API specification.

## Backward Compatibility

**Breaking Change:** API v3.2.0 is NOT backward compatible with v3.1.0

Clients using the old API will encounter:
1. **Validation errors** - Missing required `passphrase` field
2. **Unexpected responses** - `phrases` field will be null
3. **Changed behavior** - Date fields no longer populated

### Migration Timeline Recommendation

1. **Deploy v3.2.0 API** to staging
2. **Update client applications** to use new field names
3. **Test thoroughly** with staging API
4. **Deploy v3.2.0 API** to production
5. **Notify users** of breaking changes

Alternatively, run v3.1.0 and v3.2.0 APIs side-by-side on different paths:
- `/api/v3.1/` - Old API
- `/api/v3.2/` - New API

## Constants Updates

Used in validation:
```python
from stegasoo.constants import (
    MIN_PASSPHRASE_WORDS,  # = 3
    MAX_PASSPHRASE_WORDS,  # = 12
    DEFAULT_PASSPHRASE_WORDS,  # = 4 (increased from 3)
)
```

## Error Messages

All error messages updated:
- "day_phrase is required" → "passphrase is required"
- References to "phrase" now mean "passphrase"

## Implementation Status

✅ All request models updated
✅ All response models updated
✅ All endpoints updated
✅ Multipart endpoints updated
✅ Status endpoint shows breaking changes
✅ Constants imported correctly
✅ Error handling updated
✅ No references to day_phrase in user-facing text
✅ No date_str parameters accepted

Ready for deployment!
