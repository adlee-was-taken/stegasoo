#!/usr/bin/env python3
"""
Test that mimics the exact /api/compare-capacity flow.
Run with: python test_compare_capacity_flow.py ./xx_2.jpg
"""

import sys
import io
import gc
import json
import time

print("=" * 60)
print("COMPARE-CAPACITY FLOW TEST")
print("=" * 60)

if len(sys.argv) < 2:
    print("Usage: python test_compare_capacity_flow.py <image_path>")
    sys.exit(1)

image_path = sys.argv[1]

# Read the file
with open(image_path, 'rb') as f:
    carrier_data = f.read()
print(f"Loaded {len(carrier_data)} bytes from {image_path}")

# Import everything like Flask does
print("\n[1] Importing modules...")
from PIL import Image
import numpy as np

try:
    import jpegio as jio
    HAS_JPEGIO = True
    print(f"  jpegio: available")
except ImportError:
    HAS_JPEGIO = False
    print(f"  jpegio: NOT available")

try:
    from scipy.fft import dct, idct
    print(f"  scipy.fft: available")
except ImportError:
    from scipy.fftpack import dct, idct
    print(f"  scipy.fftpack: available (fallback)")

print("  Imports complete")

# Simulate the compare_modes function
print("\n[2] Opening image (1st time - for dimensions)...")
img1 = Image.open(io.BytesIO(carrier_data))
width, height = img1.size
print(f"  Size: {width}x{height}")
img1.close()
print("  Closed img1")
gc.collect()

print("\n[3] Opening image (2nd time - for LSB capacity)...")
img2 = Image.open(io.BytesIO(carrier_data))
num_pixels = img2.size[0] * img2.size[1]
lsb_bytes = (num_pixels * 3) // 8 - 69
print(f"  LSB capacity: {lsb_bytes} bytes")
img2.close()
print("  Closed img2")
gc.collect()

print("\n[4] Opening image (3rd time - for DCT capacity)...")
img3 = Image.open(io.BytesIO(carrier_data))
w, h = img3.size
blocks_x = w // 8
blocks_y = h // 8
total_blocks = blocks_x * blocks_y
dct_bits = total_blocks * 16
dct_bytes = dct_bits // 8 - 10
print(f"  DCT capacity: {dct_bytes} bytes ({total_blocks} blocks)")
img3.close()
print("  Closed img3")
gc.collect()

print("\n[5] Building response dict...")
response = {
    'success': True,
    'width': width,
    'height': height,
    'lsb': {
        'capacity_bytes': lsb_bytes,
        'capacity_kb': round(lsb_bytes / 1024, 1),
        'output': 'PNG',
    },
    'dct': {
        'capacity_bytes': dct_bytes,
        'capacity_kb': round(dct_bytes / 1024, 1),
        'output': 'JPEG',
        'available': True,
        'ratio': round(dct_bytes / lsb_bytes * 100, 1),
    }
}
print(f"  Response built")

print("\n[6] Serializing to JSON...")
json_str = json.dumps(response)
print(f"  JSON length: {len(json_str)} bytes")
print(f"  Content: {json_str[:200]}...")

print("\n[7] Simulating Flask response completion...")
# In Flask, after the response is sent, Python may garbage collect
del carrier_data
del response
del json_str
gc.collect()
print("  GC after response simulation")

print("\n[8] Additional cleanup (simulating request end)...")
gc.collect()
gc.collect()
print("  Multiple GC cycles complete")

print("\n[9] Waiting for delayed crash...")
for i in range(3):
    time.sleep(1)
    print(f"  {i+1}s...")
    gc.collect()

print("\n" + "=" * 60)
print("TEST PASSED - No crash detected")
print("=" * 60)

# Now test with jpegio if available
if HAS_JPEGIO:
    print("\n" + "=" * 60)
    print("JPEGIO SPECIFIC TEST")
    print("=" * 60)

    import tempfile
    import os

    # Reload image data
    with open(image_path, 'rb') as f:
        carrier_data = f.read()

    print("\n[J1] Checking if image is JPEG...")
    img = Image.open(io.BytesIO(carrier_data))
    is_jpeg = img.format == 'JPEG'
    img.close()
    print(f"  Is JPEG: {is_jpeg}")

    if is_jpeg:
        print("\n[J2] Writing to temp file...")
        fd, temp_path = tempfile.mkstemp(suffix='.jpg')
        os.write(fd, carrier_data)
        os.close(fd)
        print(f"  Temp file: {temp_path}")

        print("\n[J3] Reading with jpegio...")
        try:
            jpeg = jio.read(temp_path)
            print(f"  jpegio.read() OK")

            print("\n[J4] Accessing coefficient arrays...")
            coef = jpeg.coef_arrays[0]
            print(f"  Coef shape: {coef.shape}, dtype: {coef.dtype}")

            print("\n[J5] Counting usable positions...")
            positions = []
            h, w = coef.shape
            for row in range(h):
                for col in range(w):
                    if (row % 8 == 0) and (col % 8 == 0):
                        continue
                    if abs(coef[row, col]) >= 2:
                        positions.append((row, col))
            print(f"  Usable positions: {len(positions)}")

            print("\n[J6] Cleaning up jpegio object...")
            del coef
            del jpeg
            gc.collect()
            print("  Deleted jpeg object")

            print("\n[J7] Removing temp file...")
            os.unlink(temp_path)
            print("  Temp file removed")

            gc.collect()
            print("\n[J8] Final GC...")

        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

        print("\n[J9] Waiting for delayed crash...")
        for i in range(3):
            time.sleep(1)
            print(f"  {i+1}s...")
            gc.collect()

        print("\n" + "=" * 60)
        print("JPEGIO TEST PASSED - No crash detected")
        print("=" * 60)
    else:
        print("  Skipping jpegio test (not a JPEG)")

print("\n\nAll tests completed successfully!")
