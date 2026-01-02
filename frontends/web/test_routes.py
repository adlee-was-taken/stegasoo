"""
Minimal test to isolate the memory corruption crash.

Add this route to your app.py temporarily to test if the crash 
is in Flask/Pillow or in stegasoo code.

Usage:
1. Add this code to app.py
2. Restart the server
3. Use the /test-capacity endpoint instead of /api/compare-capacity
4. If it crashes: Flask or Pillow issue
5. If it works: Stegasoo code issue
"""

# Add these imports at the top of app.py if not present:
# from PIL import Image
# import io

# Add this route to app.py:

@app.route('/test-capacity', methods=['POST'])
def test_capacity():
    """
    Minimal capacity test - no stegasoo code, just PIL.
    """
    carrier = request.files.get('carrier')
    if not carrier:
        return jsonify({'error': 'No carrier image provided'}), 400
    
    try:
        # Read the file data
        carrier_data = carrier.read()
        
        # Method 1: Just get size from PIL
        buffer = io.BytesIO(carrier_data)
        img = Image.open(buffer)
        width, height = img.size
        fmt = img.format
        mode = img.mode
        img.close()
        buffer.close()
        
        # Simple capacity calculation (no scipy, no numpy)
        pixels = width * height
        lsb_bytes = (pixels * 3) // 8
        blocks = (width // 8) * (height // 8)
        dct_bytes = (blocks * 16) // 8 - 10
        
        return jsonify({
            'success': True,
            'width': width,
            'height': height,
            'format': fmt,
            'mode': mode,
            'lsb': {
                'capacity_bytes': lsb_bytes,
                'capacity_kb': round(lsb_bytes / 1024, 1),
            },
            'dct': {
                'capacity_bytes': dct_bytes,
                'capacity_kb': round(dct_bytes / 1024, 1),
            }
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500


# Alternative: completely bypass PIL too
@app.route('/test-capacity-nopil', methods=['POST'])
def test_capacity_nopil():
    """
    Ultra-minimal test - no PIL, no stegasoo.
    """
    carrier = request.files.get('carrier')
    if not carrier:
        return jsonify({'error': 'No carrier image provided'}), 400
    
    try:
        carrier_data = carrier.read()
        
        # Just return size info, no image processing at all
        return jsonify({
            'success': True,
            'data_size': len(carrier_data),
            'first_bytes': carrier_data[:20].hex() if len(carrier_data) >= 20 else carrier_data.hex(),
        })
    except Exception as e:
        import traceback
        return jsonify({'error': str(e), 'trace': traceback.format_exc()}), 500
