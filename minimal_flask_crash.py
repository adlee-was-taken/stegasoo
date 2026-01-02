#!/usr/bin/env python3
"""
Minimal Flask app to isolate the crash.
Run with: python minimal_flask_crash.py

Then test with:
  curl -X POST -F "carrier=@xx_2.jpg" http://localhost:5001/test1
  curl -X POST -F "carrier=@xx_2.jpg" http://localhost:5001/test2
  curl -X POST -F "carrier=@xx_2.jpg" http://localhost:5001/test3
"""

import io
import gc
import os
import sys
import tempfile

# Minimal imports first
from flask import Flask, request, jsonify
from PIL import Image
import numpy as np

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB

# Check for jpegio
try:
    import jpegio as jio
    HAS_JPEGIO = True
    print("jpegio: available")
except ImportError:
    HAS_JPEGIO = False
    print("jpegio: NOT available")


@app.route('/test1', methods=['POST'])
def test1_pil_only():
    """Test 1: PIL only, no jpegio, no scipy"""
    carrier = request.files.get('carrier')
    if not carrier:
        return jsonify({'error': 'No carrier'}), 400

    data = carrier.read()
    print(f"[test1] Read {len(data)} bytes")

    img = Image.open(io.BytesIO(data))
    width, height = img.size
    fmt = img.format
    img.close()
    print(f"[test1] Image: {width}x{height} {fmt}")

    gc.collect()
    print("[test1] Returning response...")

    return jsonify({
        'test': 'pil_only',
        'width': width,
        'height': height,
        'format': fmt,
    })


@app.route('/test2', methods=['POST'])
def test2_multiple_opens():
    """Test 2: Open image multiple times like compare_modes does"""
    carrier = request.files.get('carrier')
    if not carrier:
        return jsonify({'error': 'No carrier'}), 400

    data = carrier.read()
    print(f"[test2] Read {len(data)} bytes")

    # First open
    img1 = Image.open(io.BytesIO(data))
    width, height = img1.size
    img1.close()
    print(f"[test2] Open 1: {width}x{height}")

    # Second open
    img2 = Image.open(io.BytesIO(data))
    pixels = img2.size[0] * img2.size[1]
    img2.close()
    print(f"[test2] Open 2: {pixels} pixels")

    # Third open
    img3 = Image.open(io.BytesIO(data))
    blocks = (img3.size[0] // 8) * (img3.size[1] // 8)
    img3.close()
    print(f"[test2] Open 3: {blocks} blocks")

    gc.collect()
    print("[test2] Returning response...")

    return jsonify({
        'test': 'multiple_opens',
        'width': width,
        'height': height,
        'pixels': pixels,
        'blocks': blocks,
    })


@app.route('/test3', methods=['POST'])
def test3_with_jpegio():
    """Test 3: Include jpegio operations"""
    if not HAS_JPEGIO:
        return jsonify({'error': 'jpegio not available'}), 501

    carrier = request.files.get('carrier')
    if not carrier:
        return jsonify({'error': 'No carrier'}), 400

    data = carrier.read()
    print(f"[test3] Read {len(data)} bytes")

    # Check if JPEG
    img = Image.open(io.BytesIO(data))
    is_jpeg = img.format == 'JPEG'
    width, height = img.size
    img.close()
    print(f"[test3] Image: {width}x{height}, JPEG: {is_jpeg}")

    if not is_jpeg:
        return jsonify({'error': 'Not a JPEG'}), 400

    # Write to temp file
    fd, temp_path = tempfile.mkstemp(suffix='.jpg')
    os.write(fd, data)
    os.close(fd)
    print(f"[test3] Temp file: {temp_path}")

    try:
        # Read with jpegio
        jpeg = jio.read(temp_path)
        print(f"[test3] jpegio.read() OK")

        coef = jpeg.coef_arrays[0]
        coef_shape = coef.shape
        print(f"[test3] Coef shape: {coef_shape}")

        # Count positions like the real code does
        positions = 0
        h, w = coef.shape
        for row in range(h):
            for col in range(w):
                if (row % 8 == 0) and (col % 8 == 0):
                    continue
                if abs(coef[row, col]) >= 2:
                    positions += 1
        print(f"[test3] Usable positions: {positions}")

        # Cleanup
        del coef
        del jpeg
        print(f"[test3] Deleted jpegio objects")

    finally:
        os.unlink(temp_path)
        print(f"[test3] Removed temp file")

    gc.collect()
    print("[test3] Returning response...")

    return jsonify({
        'test': 'with_jpegio',
        'width': width,
        'height': height,
        'coef_shape': list(coef_shape),
        'positions': positions,
    })


@app.route('/test4', methods=['POST'])
def test4_numpy_array_from_pil():
    """Test 4: Create numpy array from PIL image (like DCT does)"""
    carrier = request.files.get('carrier')
    if not carrier:
        return jsonify({'error': 'No carrier'}), 400

    data = carrier.read()
    print(f"[test4] Read {len(data)} bytes")

    img = Image.open(io.BytesIO(data))
    width, height = img.size
    print(f"[test4] Image: {width}x{height}")

    # Convert to grayscale and numpy array
    gray = img.convert('L')
    arr = np.array(gray, dtype=np.float64, copy=True)
    print(f"[test4] Array: {arr.shape} {arr.dtype}")

    # Close PIL images
    gray.close()
    img.close()
    print(f"[test4] PIL closed")

    # Do some numpy operations
    mean_val = float(np.mean(arr))
    std_val = float(np.std(arr))
    print(f"[test4] Stats: mean={mean_val:.2f}, std={std_val:.2f}")

    # Clear array
    del arr
    gc.collect()
    print("[test4] Returning response...")

    return jsonify({
        'test': 'numpy_from_pil',
        'width': width,
        'height': height,
        'mean': mean_val,
        'std': std_val,
    })


@app.route('/test5', methods=['POST'])
def test5_file_read_keep_reference():
    """Test 5: Keep reference to file data in request scope"""
    carrier = request.files.get('carrier')
    if not carrier:
        return jsonify({'error': 'No carrier'}), 400

    # Don't read into local variable - read directly each time
    # This mimics potential issues with Flask's file handling

    print(f"[test5] File object: {carrier}")

    # Read once
    carrier.seek(0)
    data1 = carrier.read()
    print(f"[test5] First read: {len(data1)} bytes")

    img = Image.open(io.BytesIO(data1))
    width, height = img.size
    img.close()

    # Try to read again (should be empty or need seek)
    data2 = carrier.read()
    print(f"[test5] Second read (no seek): {len(data2)} bytes")

    carrier.seek(0)
    data3 = carrier.read()
    print(f"[test5] Third read (after seek): {len(data3)} bytes")

    gc.collect()
    print("[test5] Returning response...")

    return jsonify({
        'test': 'file_handling',
        'width': width,
        'height': height,
        'read1': len(data1),
        'read2': len(data2),
        'read3': len(data3),
    })


@app.after_request
def after_request(response):
    """Log after each request"""
    print(f"[after_request] Response status: {response.status}")
    return response


@app.teardown_request
def teardown_request(exception):
    """Log during teardown"""
    if exception:
        print(f"[teardown] Exception: {exception}")
    else:
        print("[teardown] Clean teardown")
    gc.collect()


if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("MINIMAL FLASK CRASH TEST")
    print("=" * 60)
    print("\nTest endpoints:")
    print("  /test1 - PIL only")
    print("  /test2 - Multiple PIL opens")
    print("  /test3 - With jpegio")
    print("  /test4 - NumPy array from PIL")
    print("  /test5 - File handling test")
    print("\nUsage:")
    print('  curl -X POST -F "carrier=@xx_2.jpg" http://localhost:5001/test1')
    print("=" * 60 + "\n")

    app.run(host='0.0.0.0', port=5001, debug=False, threaded=False)
