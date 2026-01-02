#!/usr/bin/env python3
"""
Standalone DCT crash diagnostic script.
Run this outside of Flask to isolate the issue.

Usage:
    python test_dct_crash.py /path/to/your/large_image.jpg
"""

import sys
import gc
import traceback
import io

print("=" * 60)
print("DCT CRASH DIAGNOSTIC TOOL")
print("=" * 60)

# Step 1: Check Python and library versions
print("\n[1] ENVIRONMENT INFO")
print(f"Python: {sys.version}")

try:
    import numpy as np
    print(f"NumPy: {np.__version__}")
except ImportError as e:
    print(f"NumPy: NOT INSTALLED - {e}")
    sys.exit(1)

try:
    import scipy
    print(f"SciPy: {scipy.__version__}")
except ImportError as e:
    print(f"SciPy: NOT INSTALLED - {e}")
    sys.exit(1)

try:
    from PIL import Image
    import PIL
    print(f"Pillow: {PIL.__version__}")
except ImportError as e:
    print(f"Pillow: NOT INSTALLED - {e}")
    sys.exit(1)

# Step 2: Check which DCT module we're using
print("\n[2] DCT MODULE CHECK")
try:
    from scipy.fft import dct, idct
    print("Using: scipy.fft (preferred)")
    DCT_MODULE = "scipy.fft"
except ImportError:
    try:
        from scipy.fftpack import dct, idct
        print("Using: scipy.fftpack (legacy)")
        DCT_MODULE = "scipy.fftpack"
    except ImportError:
        print("ERROR: No DCT module available!")
        sys.exit(1)

# Step 3: Test basic DCT on small array
print("\n[3] BASIC DCT TEST (8x8 block)")
try:
    test_block = np.random.rand(8, 8).astype(np.float64)

    # 1D DCT on rows
    result = dct(test_block[0, :], norm='ortho')
    print(f"  1D DCT: OK (output shape: {result.shape})")

    # 1D IDCT
    recovered = idct(result, norm='ortho')
    error = np.max(np.abs(test_block[0, :] - recovered))
    print(f"  1D IDCT: OK (roundtrip error: {error:.2e})")

    # 2D via separable
    temp = np.zeros_like(test_block)
    for i in range(8):
        temp[:, i] = dct(test_block[:, i], norm='ortho')
    result2d = np.zeros_like(temp)
    for i in range(8):
        result2d[i, :] = dct(temp[i, :], norm='ortho')
    print(f"  2D DCT: OK")

    gc.collect()
    print("  GC after basic test: OK")

except Exception as e:
    print(f"  FAILED: {e}")
    traceback.print_exc()

# Step 4: Test with larger arrays (stress test)
print("\n[4] STRESS TEST (many 8x8 blocks)")
try:
    NUM_BLOCKS = 10000
    print(f"  Processing {NUM_BLOCKS} blocks...")

    for i in range(NUM_BLOCKS):
        block = np.random.rand(8, 8).astype(np.float64)

        # Forward DCT
        temp = np.zeros_like(block)
        for j in range(8):
            temp[:, j] = dct(block[:, j], norm='ortho')
        result = np.zeros_like(temp)
        for j in range(8):
            result[j, :] = dct(temp[j, :], norm='ortho')

        # Inverse DCT
        temp2 = np.zeros_like(result)
        for j in range(8):
            temp2[j, :] = idct(result[j, :], norm='ortho')
        recovered = np.zeros_like(temp2)
        for j in range(8):
            recovered[:, j] = idct(temp2[:, j], norm='ortho')

        if i % 1000 == 0:
            gc.collect()
            print(f"    {i}/{NUM_BLOCKS} blocks processed...")

    gc.collect()
    print(f"  Stress test PASSED")

except Exception as e:
    print(f"  FAILED at block {i}: {e}")
    traceback.print_exc()

# Step 5: Test with actual image if provided
if len(sys.argv) > 1:
    image_path = sys.argv[1]
    print(f"\n[5] IMAGE TEST: {image_path}")

    try:
        with open(image_path, 'rb') as f:
            image_data = f.read()
        print(f"  File size: {len(image_data) / 1024 / 1024:.2f} MB")

        img = Image.open(io.BytesIO(image_data))
        width, height = img.size
        print(f"  Dimensions: {width}x{height}")
        print(f"  Format: {img.format}")
        print(f"  Mode: {img.mode}")

        # Convert to grayscale float array
        gray = img.convert('L')
        arr = np.array(gray, dtype=np.float64)
        img.close()
        gray.close()
        print(f"  Array shape: {arr.shape}")
        print(f"  Array dtype: {arr.dtype}")

        # Pad to block boundary
        BLOCK_SIZE = 8
        h, w = arr.shape
        new_h = ((h + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE
        new_w = ((w + BLOCK_SIZE - 1) // BLOCK_SIZE) * BLOCK_SIZE

        if new_h != h or new_w != w:
            padded = np.zeros((new_h, new_w), dtype=np.float64)
            padded[:h, :w] = arr
            arr = padded
            print(f"  Padded to: {arr.shape}")

        blocks_y = arr.shape[0] // BLOCK_SIZE
        blocks_x = arr.shape[1] // BLOCK_SIZE
        total_blocks = blocks_y * blocks_x
        print(f"  Total 8x8 blocks: {total_blocks}")

        # Process ALL blocks
        print(f"  Processing all blocks with DCT...")

        processed = 0
        for by in range(blocks_y):
            for bx in range(blocks_x):
                y = by * BLOCK_SIZE
                x = bx * BLOCK_SIZE

                block = arr[y:y+BLOCK_SIZE, x:x+BLOCK_SIZE].copy()

                # Forward DCT
                temp = np.zeros((8, 8), dtype=np.float64)
                for i in range(8):
                    temp[:, i] = dct(block[:, i], norm='ortho')
                dct_block = np.zeros((8, 8), dtype=np.float64)
                for i in range(8):
                    dct_block[i, :] = dct(temp[i, :], norm='ortho')

                # Inverse DCT
                temp2 = np.zeros((8, 8), dtype=np.float64)
                for i in range(8):
                    temp2[i, :] = idct(dct_block[i, :], norm='ortho')
                recovered = np.zeros((8, 8), dtype=np.float64)
                for i in range(8):
                    recovered[:, i] = idct(temp2[:, i], norm='ortho')

                processed += 1

            # GC after each row of blocks
            if by % 50 == 0:
                gc.collect()
                print(f"    Row {by}/{blocks_y} ({processed}/{total_blocks} blocks)")

        gc.collect()
        print(f"  Image DCT test PASSED ({processed} blocks)")

    except Exception as e:
        print(f"  FAILED: {e}")
        traceback.print_exc()

else:
    print("\n[5] IMAGE TEST: Skipped (no image path provided)")
    print("    Usage: python test_dct_crash.py /path/to/image.jpg")

# Step 6: Final cleanup test
print("\n[6] FINAL CLEANUP TEST")
try:
    gc.collect()
    gc.collect()
    gc.collect()
    print("  Multiple GC cycles: OK")
except Exception as e:
    print(f"  FAILED: {e}")

print("\n" + "=" * 60)
print("If this script completes without 'free(): invalid size',")
print("the issue is likely in PIL/jpegio interaction, not scipy DCT.")
print("=" * 60)

# Keep process alive briefly to catch delayed crashes
import time
print("\nWaiting 2 seconds for delayed crashes...")
time.sleep(2)
print("Done - no crash detected!")
