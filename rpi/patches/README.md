# RPi Patches

This directory contains patches for dependencies that need modifications to build on ARM64.

## Structure

```
patches/
  <package>/
    arm64.patch       # Standard unified diff patch file
    apply-patch.sh    # Script with fallback strategies
```

## How It Works

The `apply-patch.sh` script tries multiple strategies in order:

1. **Patch file** - Apply the `.patch` file using `patch -p1`
2. **Sed fallback** - Use sed for simple string replacements
3. **Python fallback** - Use regex for flexible pattern matching

This layered approach handles:
- Exact matches (patch file works)
- Minor upstream changes (sed catches variations)
- Significant changes (Python regex is most flexible)
- Already patched files (detected and skipped)

## Adding a New Patch

1. Create a directory: `patches/<package>/`
2. Create the patch file: `git diff > arm64.patch`
3. Create `apply-patch.sh` with appropriate fallback logic
4. Update `setup.sh` to call the patch script

## jpegio Patch

The jpegio library includes x86-specific `-m64` compiler flags that fail on ARM64.
The patch removes these flags by replacing:

```python
cargs.append('-m64')
```

with:

```python
pass  # ARM64: removed x86-specific -m64 flag
```

## Updating Patches

When upstream changes break a patch:

1. Clone the new version
2. Make the necessary modifications
3. Generate a new patch: `diff -u original modified > arm64.patch`
4. Test on a fresh Pi install
