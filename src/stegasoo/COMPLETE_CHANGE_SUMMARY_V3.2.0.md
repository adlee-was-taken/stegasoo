# Stegasoo v3.2.0 - Complete Change Summary

## Overview

This update makes two major breaking changes to Stegasoo:
1. **Remove date dependency** - Date no longer used in cryptographic operations
2. **Rename day_phrase → passphrase** - Reflects removal of daily rotation requirement

## Version Information

- **Previous**: v3.1.0 (date-dependent, day_phrase)
- **Current**: v3.2.0 (date-independent, passphrase)
- **Format Version**: 3 → 4 (breaking change)
- **Compatibility**: NOT backward compatible with v3.1.0

## Files Modified

### Core Files (MUST UPDATE)

1. **crypto.py** ✅ Updated
   - Removed `date_str` parameter from all functions
   - Renamed `day_phrase` → `passphrase` in all functions
   - Removed date from key derivation material
   - Simplified header format (no date field)
   - Updated error messages

2. **constants.py** ✅ Updated
   - Version: `__version__ = "3.2.0"`
   - Format: `FORMAT_VERSION = 4`
   - Added passphrase constants:
     - `MIN_PASSPHRASE_WORDS = 3`
     - `MAX_PASSPHRASE_WORDS = 12`
     - `DEFAULT_PASSPHRASE_WORDS = 4` (increased from 3)
     - `RECOMMENDED_PASSPHRASE_WORDS = 4`
   - Kept legacy aliases for transition

3. **models.py** ✅ Updated
   - `Credentials`: Changed from `phrases: dict` → `passphrase: str`
   - `EncodeInput`: Renamed `day_phrase` → `passphrase`, removed `date_str`
   - `DecodeInput`: Renamed `day_phrase` → `passphrase`
   - `EncodeResult`: Made `date_used` optional (cosmetic only)
   - `DecodeResult`: `date_encoded` always None in v3.2.0
   - `ValidationResult`: Added `warning` field

4. **validation.py** ✅ Updated
   - Renamed `validate_phrase()` → `validate_passphrase()`
   - Added word count validation with warnings
   - Recommends 4+ words for good security
   - Updated error messages

### Files Needing Updates

5. **__init__.py** - Public API
   - [ ] `encode()`: Remove `date_str`, rename `day_phrase` → `passphrase`
   - [ ] `encode_file()`: Same changes
   - [ ] `encode_bytes()`: Same changes
   - [ ] `decode()`: Remove `date_str`, rename `day_phrase` → `passphrase`
   - [ ] `decode_text()`: Same changes
   - [ ] Update all docstrings

6. **keygen.py** - Key generation
   - [ ] `generate_day_phrases()` → `generate_passphrases()` or keep with new implementation
   - [ ] `generate_credentials()`: Update to use single passphrase
   - [ ] Update `Credentials` creation

7. **batch.py** - Batch operations
   - [ ] `BatchCredentials`: Rename `day_phrase` → `passphrase`
   - [ ] Update all batch functions

8. **cli.py** - Command line
   - [ ] `--phrase` → `--passphrase` (or keep `--phrase` for simplicity)
   - [ ] Update help text
   - [ ] Update credentials dict creation

9. **steganography.py** - No changes needed
   - Uses keys from crypto module, doesn't directly handle phrases/dates

10. **dct_steganography.py** - No changes needed
    - Uses keys from crypto module

### Optional/Documentation Files

11. **utils.py** - Keep as-is (organizational functions)
12. **debug.py** - No changes needed
13. **exceptions.py** - No changes needed
14. **compression.py** - No changes needed
15. **qr_utils.py** - No changes needed

## Key Changes Breakdown

### 1. Function Signatures

**Before (v3.1.0):**
```python
def derive_hybrid_key(
    photo_data: bytes,
    day_phrase: str,
    date_str: str,
    salt: bytes,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None
) -> bytes:
```

**After (v3.2.0):**
```python
def derive_hybrid_key(
    photo_data: bytes,
    passphrase: str,
    salt: bytes,
    pin: str = "",
    rsa_key_data: Optional[bytes] = None
) -> bytes:
```

### 2. Key Derivation Material

**Before:**
```python
key_material = (
    photo_hash +
    day_phrase.lower().encode() +
    pin.encode() +
    date_str.encode() +  # ← REMOVED
    salt
)
```

**After:**
```python
key_material = (
    photo_hash +
    passphrase.lower().encode() +
    pin.encode() +
    salt
)
```

### 3. Header Format

**Before (v3.1.0):** 66+ bytes
```
[Magic:4][Version:1][DateLen:1][Date:10][Salt:32][IV:12][Tag:16][Ciphertext]
```

**After (v3.2.0):** 65 bytes
```
[Magic:4][Version:1][Salt:32][IV:12][Tag:16][Ciphertext]
```

### 4. Public API

**Before:**
```python
# Encoding
result = encode(
    message="Secret",
    reference_photo=photo,
    carrier_image=carrier,
    day_phrase="apple forest thunder",
    pin="123456",
    date_str="2025-01-15"
)

# Decoding
decoded = decode(
    stego_image=stego,
    reference_photo=photo,
    day_phrase="apple forest thunder",
    pin="123456",
    date_str="2025-01-15"
)
```

**After:**
```python
# Encoding
result = encode(
    message="Secret",
    reference_photo=photo,
    carrier_image=carrier,
    passphrase="apple forest thunder mountain",
    pin="123456"
)

# Decoding
decoded = decode(
    stego_image=stego,
    reference_photo=photo,
    passphrase="apple forest thunder mountain",
    pin="123456"
)
```

## Migration Path

### For Users with v3.1.0 Messages

1. **Before upgrading**, decode all messages with v3.1.0:
   ```bash
   # Using v3.1.0
   python decode_all.py
   ```

2. Save the decoded content

3. Upgrade to v3.2.0

4. Re-encode with v3.2.0 if needed

### For Developers

1. Update the 4 core files: crypto.py, constants.py, models.py, validation.py

2. Update remaining files in order:
   - `__init__.py` (public API - critical)
   - `keygen.py` (credential generation)
   - `batch.py` (batch operations)
   - `cli.py` (command line)

3. Run tests to verify:
   ```bash
   pytest tests/ -v
   ```

4. Update documentation and examples

## Benefits

### Simplicity
- ❌ Before: 3 parameters (day_phrase, pin, date)
- ✅ After: 2 parameters (passphrase, pin)

### User Experience
- ❌ Before: "What date did I encode this?" "Which day's phrase?"
- ✅ After: Just use your passphrase

### Asynchronous Ready
- ❌ Before: Must know encoding date
- ✅ After: Decode anytime

### Less Metadata
- ❌ Before: Date stored in header
- ✅ After: No temporal metadata

## Security Considerations

### Entropy Comparison

**v3.1.0:**
- Photo hash: ~128 bits
- Day phrase (3 words): ~33 bits
- PIN (6 digits): ~20 bits
- Date: ~33 bits (10 digits)
- **Total: ~214 bits**

**v3.2.0:**
- Photo hash: ~128 bits
- Passphrase (4 words): ~44 bits
- PIN (6 digits): ~20 bits
- **Total: ~192 bits**

**Mitigation:** Recommend longer passphrases (4-5 words vs 3)

### Best Practices for v3.2.0

1. **Use 4+ word passphrases** (increased from 3)
2. **Keep using PINs** (additional 20 bits)
3. **Protect reference photo** (still critical)
4. **Consider RSA keys** for highest security

## Testing Checklist

- [ ] Unit tests pass
- [ ] Integration tests pass
- [ ] Encode/decode round-trip works
- [ ] File payloads work
- [ ] LSB mode works
- [ ] DCT mode works
- [ ] Batch operations work
- [ ] CLI commands work
- [ ] Error messages are clear
- [ ] Validation works correctly
- [ ] No references to "day_phrase" remain
- [ ] No date parameters remain (except cosmetic)

## Documentation Updates Needed

- [ ] README.md - Update all examples
- [ ] API documentation - Update function signatures
- [ ] Tutorials - Remove date parameters
- [ ] CHANGELOG.md - Add v3.2.0 entry
- [ ] Migration guide - How to upgrade from v3.1.0
- [ ] Examples directory - Update all scripts

## Backward Compatibility Strategy

### Option 1: Clean Break (Recommended)
- No compatibility code
- Clear version separation
- Users must migrate manually

### Option 2: Temporary Wrapper
```python
def encode(
    message,
    reference_photo,
    carrier_image,
    passphrase: str = None,
    day_phrase: str = None,  # Deprecated
    date_str: str = None,     # Deprecated
    pin: str = "",
    ...
):
    if day_phrase and not passphrase:
        import warnings
        warnings.warn("day_phrase deprecated, use passphrase", DeprecationWarning)
        passphrase = day_phrase
    
    if date_str:
        warnings.warn("date_str no longer used", DeprecationWarning)
    
    # ... rest of function
```

## Release Checklist

- [ ] All files updated
- [ ] Tests passing
- [ ] Documentation updated
- [ ] Migration guide written
- [ ] CHANGELOG.md updated
- [ ] Version bumped to 3.2.0
- [ ] Git tag created: v3.2.0
- [ ] PyPI package published
- [ ] Release notes published
- [ ] Users notified of breaking changes

## Quick Reference

### Search and Replace Patterns

Safe to replace globally:
- `day_phrase` → `passphrase`
- `day phrase` → `passphrase`
- `Day phrase` → `Passphrase`
- `DEFAULT_PHRASE_WORDS` → `DEFAULT_PASSPHRASE_WORDS`

Do NOT replace:
- `DAY_NAMES` (keep for utilities)
- `get_day_from_date` (keep for utilities)
- `generate_day_phrases` (rename function itself)

### Error Message Updates

- "Day phrase is required" → "Passphrase is required"
- "Check your phrase, PIN" → "Check your passphrase, PIN"
- "the day's phrase" → "the passphrase"
- "today's passphrase" → "passphrase"

## Support

For issues or questions during migration:
1. Check the migration guide
2. Review the comparison document
3. Look at updated examples
4. File an issue on GitHub

---

**Status:** 
✅ Core files updated (crypto, constants, models, validation)
⏳ Remaining files need updates (__init__, keygen, batch, cli)
📝 Documentation updates pending
