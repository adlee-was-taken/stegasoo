#!/usr/bin/env python3
"""
Diagnostic script to check for scipy/numpy issues.
Run this BEFORE starting the web app.

Usage:
    python check_scipy.py
"""

import sys
print(f"Python version: {sys.version}")
print()

# Check numpy
try:
    import numpy as np
    print(f"NumPy version: {np.__version__}")
    print(f"NumPy config:")
    np.show_config()
except ImportError as e:
    print(f"NumPy not installed: {e}")
except Exception as e:
    print(f"NumPy error: {e}")

print()
print("-" * 50)
print()

# Check scipy
try:
    import scipy
    print(f"SciPy version: {scipy.__version__}")
except ImportError as e:
    print(f"SciPy not installed: {e}")

print()

# Check PIL
try:
    from PIL import Image
    print(f"Pillow version: {Image.__version__}")
except ImportError as e:
    print(f"Pillow not installed: {e}")

print()
print("-" * 50)
print()

# Test scipy DCT directly
print("Testing scipy DCT...")
try:
    from scipy.fftpack import dct, idct
    import numpy as np

    # Create test array
    test = np.random.rand(8, 8).astype(np.float64)
    print(f"Input array shape: {test.shape}, dtype: {test.dtype}")

    # Test 1D DCT
    row = test[0, :]
    result = dct(row, norm='ortho')
    print(f"1D DCT result shape: {result.shape}, dtype: {result.dtype}")

    # Test 2D DCT (the potentially problematic operation)
    result2d = dct(dct(test.T, norm='ortho').T, norm='ortho')
    print(f"2D DCT result shape: {result2d.shape}, dtype: {result2d.dtype}")

    # Test inverse
    recovered = idct(idct(result2d.T, norm='ortho').T, norm='ortho')
    error = np.max(np.abs(test - recovered))
    print(f"Round-trip error: {error}")

    if error < 1e-10:
        print("✓ scipy DCT working correctly")
    else:
        print("⚠ scipy DCT has precision issues")

except Exception as e:
    print(f"✗ scipy DCT failed: {e}")
    import traceback
    traceback.print_exc()

print()
print("-" * 50)
print()

# Test with larger array (more like real image processing)
print("Testing with larger arrays (512x512)...")
try:
    from scipy.fftpack import dct, idct
    import numpy as np
    import gc

    # Simulate processing many 8x8 blocks
    large_array = np.random.rand(512, 512).astype(np.float64)
    print(f"Large array shape: {large_array.shape}, size: {large_array.nbytes} bytes")

    count = 0
    for y in range(0, 512, 8):
        for x in range(0, 512, 8):
            block = large_array[y:y+8, x:x+8].copy()
            dct_block = dct(dct(block.T, norm='ortho').T, norm='ortho')
            recovered = idct(idct(dct_block.T, norm='ortho').T, norm='ortho')
            large_array[y:y+8, x:x+8] = recovered
            count += 1

    print(f"Processed {count} blocks successfully")

    del large_array
    gc.collect()

    print("✓ Large array processing completed")

except Exception as e:
    print(f"✗ Large array processing failed: {e}")
    import traceback
    traceback.print_exc()

print()
print("-" * 50)
print()

# Test PIL with large image
print("Testing PIL with large image...")
try:
    from PIL import Image
    import io

    # Create a large test image
    img = Image.new('RGB', (4000, 3000), color=(128, 128, 128))

    # Save to bytes
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    img_bytes = buffer.getvalue()
    print(f"Test image size: {len(img_bytes)} bytes")

    # Re-open and process
    buffer2 = io.BytesIO(img_bytes)
    img2 = Image.open(buffer2)
    print(f"Re-opened image: {img2.size}, mode: {img2.mode}")

    # Convert to numpy array
    import numpy as np
    arr = np.array(img2)
    print(f"NumPy array: {arr.shape}, dtype: {arr.dtype}")

    # Clean up
    img.close()
    img2.close()
    buffer.close()
    buffer2.close()
    del arr
    gc.collect()

    print("✓ PIL large image test completed")

except Exception as e:
    print(f"✗ PIL test failed: {e}")
    import traceback
    traceback.print_exc()

print()
print("=" * 50)
print("Diagnostics complete")
print()
print("If no errors above but web app still crashes, try:")
print("1. pip install --upgrade scipy numpy pillow")
print("2. pip install scipy==1.11.4 numpy==1.26.4  # Known stable versions")
print("3. Check if using conda vs pip (mixing can cause issues)")
