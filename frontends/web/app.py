#!/usr/bin/env python3
"""
Stegasoo Web Frontend

Flask-based web UI for steganography operations.
Supports both text messages and file embedding.
"""

import io
import sys
import time
import secrets
import mimetypes
from pathlib import Path
from datetime import datetime

from flask import (
    Flask, render_template, request, send_file,
    jsonify, flash, redirect, url_for
)

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import stegasoo
from stegasoo import (
    encode, decode, generate_credentials,
    export_rsa_key_pem, load_rsa_key,
    validate_pin, validate_message, validate_image,
    validate_rsa_key, validate_security_factors,
    validate_file_payload,
    get_today_day, generate_filename,
    DAY_NAMES, __version__,
    StegasooError, DecryptionError, CapacityError,
    has_argon2,
    FilePayload,
    MAX_FILE_PAYLOAD_SIZE,
)
from stegasoo.constants import (
    MAX_MESSAGE_SIZE, MIN_PIN_LENGTH, MAX_PIN_LENGTH,
    VALID_RSA_SIZES, MAX_FILE_SIZE,
)

# QR Code support
try:
    import qrcode
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

# QR Code reading
try:
    from pyzbar.pyzbar import decode as pyzbar_decode
    HAS_QRCODE_READ = True
except ImportError:
    HAS_QRCODE_READ = False

import zlib
import base64

# Import QR utilities
from stegasoo.qr_utils import (
    compress_data, decompress_data, auto_decompress,
    is_compressed, can_fit_in_qr, needs_compression,
    generate_qr_code, read_qr_code, extract_key_from_qr,
    has_qr_write, has_qr_read,
    QR_MAX_BINARY, COMPRESSION_PREFIX
)


# ============================================================================
# FLASK APP CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE  # 10MB max upload

# Temporary file storage for sharing (file_id -> {data, timestamp, filename})
TEMP_FILES: dict[str, dict] = {}
TEMP_FILE_EXPIRY = 300  # 5 minutes


def cleanup_temp_files():
    """Remove expired temporary files."""
    now = time.time()
    expired = [fid for fid, info in TEMP_FILES.items() if now - info['timestamp'] > TEMP_FILE_EXPIRY]
    for fid in expired:
        TEMP_FILES.pop(fid, None)


def allowed_image(filename: str) -> bool:
    """Check if file has allowed image extension."""
    if not filename or '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in {'png', 'jpg', 'jpeg', 'bmp', 'gif'}


def format_size(size_bytes: int) -> str:
    """Format file size for display."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"



# ============================================================================
# ROUTES
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'POST':
        words_per_phrase = int(request.form.get('words_per_phrase', 3))
        use_pin = request.form.get('use_pin') == 'on'
        use_rsa = request.form.get('use_rsa') == 'on'
        
        if not use_pin and not use_rsa:
            flash('You must select at least one security factor (PIN or RSA Key)', 'error')
            return render_template('generate.html', generated=False, has_qrcode=HAS_QRCODE)
        
        pin_length = int(request.form.get('pin_length', 6))
        rsa_bits = int(request.form.get('rsa_bits', 2048))
        
        # Clamp values
        words_per_phrase = max(3, min(12, words_per_phrase))
        pin_length = max(MIN_PIN_LENGTH, min(MAX_PIN_LENGTH, pin_length))
        if rsa_bits not in VALID_RSA_SIZES:
            rsa_bits = 2048
        
        try:
            creds = generate_credentials(
                use_pin=use_pin,
                use_rsa=use_rsa,
                pin_length=pin_length,
                rsa_bits=rsa_bits,
                words_per_phrase=words_per_phrase
            )
            
            # Store RSA key temporarily for QR generation
            qr_token = None
            qr_needs_compression = False
            qr_too_large = False
            
            if creds.rsa_key_pem and HAS_QRCODE:
                # Check if key fits in QR code
                if can_fit_in_qr(creds.rsa_key_pem, compress=False):
                    qr_needs_compression = False
                elif can_fit_in_qr(creds.rsa_key_pem, compress=True):
                    qr_needs_compression = True
                else:
                    qr_too_large = True
                
                if not qr_too_large:
                    qr_token = secrets.token_urlsafe(16)
                    cleanup_temp_files()
                    TEMP_FILES[qr_token] = {
                        'data': creds.rsa_key_pem.encode(),
                        'filename': 'rsa_key.pem',
                        'timestamp': time.time(),
                        'type': 'rsa_key',
                        'compress': qr_needs_compression
                    }
            
            return render_template('generate.html',
                phrases=creds.phrases,
                pin=creds.pin,
                days=DAY_NAMES,
                generated=True,
                words_per_phrase=words_per_phrase,
                pin_length=pin_length if use_pin else None,
                use_pin=use_pin,
                use_rsa=use_rsa,
                rsa_bits=rsa_bits,
                rsa_key_pem=creds.rsa_key_pem,
                phrase_entropy=creds.phrase_entropy,
                pin_entropy=creds.pin_entropy,
                rsa_entropy=creds.rsa_entropy,
                total_entropy=creds.total_entropy,
                has_qrcode=HAS_QRCODE,
                qr_token=qr_token,
                qr_needs_compression=qr_needs_compression,
                qr_too_large=qr_too_large
            )
        except Exception as e:
            flash(f'Error generating credentials: {e}', 'error')
            return render_template('generate.html', generated=False, has_qrcode=HAS_QRCODE)
    
    return render_template('generate.html', generated=False, has_qrcode=HAS_QRCODE)


@app.route('/generate/qr/<token>')
def generate_qr(token):
    """Generate QR code for RSA key."""
    if not HAS_QRCODE:
        return "QR code support not available", 501
    
    if token not in TEMP_FILES:
        return "Token expired or invalid", 404
    
    file_info = TEMP_FILES[token]
    if file_info.get('type') != 'rsa_key':
        return "Invalid token type", 400
    
    try:
        key_pem = file_info['data'].decode('utf-8')
        compress = file_info.get('compress', False)
        qr_png = generate_qr_code(key_pem, compress=compress)
        
        return send_file(
            io.BytesIO(qr_png),
            mimetype='image/png',
            as_attachment=False
        )
    except Exception as e:
        return f"Error generating QR code: {e}", 500


@app.route('/generate/qr-download/<token>')
def generate_qr_download(token):
    """Download QR code as PNG file."""
    if not HAS_QRCODE:
        return "QR code support not available", 501
    
    if token not in TEMP_FILES:
        return "Token expired or invalid", 404
    
    file_info = TEMP_FILES[token]
    if file_info.get('type') != 'rsa_key':
        return "Invalid token type", 400
    
    try:
        key_pem = file_info['data'].decode('utf-8')
        compress = file_info.get('compress', False)
        qr_png = generate_qr_code(key_pem, compress=compress)
        
        return send_file(
            io.BytesIO(qr_png),
            mimetype='image/png',
            as_attachment=True,
            download_name='stegasoo_rsa_key_qr.png'
        )
    except Exception as e:
        return f"Error generating QR code: {e}", 500


@app.route('/generate/download-key', methods=['POST'])
def download_key():
    """Download RSA key as password-protected PEM file."""
    key_pem = request.form.get('key_pem', '')


@app.route('/extract-key-from-qr', methods=['POST'])
def extract_key_from_qr_route():
    """
    Extract RSA key from uploaded QR code image.
    Returns JSON with the extracted key or error.
    """
    if not HAS_QRCODE_READ:
        return jsonify({
            'success': False,
            'error': 'QR code reading not available. Install pyzbar and libzbar.'
        }), 501
    
    qr_image = request.files.get('qr_image')
    if not qr_image:
        return jsonify({
            'success': False,
            'error': 'No QR image provided'
        }), 400
    
    try:
        image_data = qr_image.read()
        key_pem = extract_key_from_qr(image_data)
        
        if key_pem:
            return jsonify({
                'success': True,
                'key_pem': key_pem
            })
        else:
            return jsonify({
                'success': False,
                'error': 'No valid RSA key found in QR code'
            }), 400
            
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    password = request.form.get('key_password', '')
    
    if not key_pem:
        flash('No key to download', 'error')
        return redirect(url_for('generate'))
    
    if not password or len(password) < 8:
        flash('Password must be at least 8 characters', 'error')
        return redirect(url_for('generate'))
    
    try:
        private_key = load_rsa_key(key_pem.encode())
        encrypted_pem = export_rsa_key_pem(private_key, password=password)
        
        key_id = secrets.token_hex(4)
        filename = f'stegasoo_key_{private_key.key_size}_{key_id}.pem'
        
        return send_file(
            io.BytesIO(encrypted_pem),
            mimetype='application/x-pem-file',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error creating key file: {e}', 'error')
        return redirect(url_for('generate'))


@app.route('/encode', methods=['GET', 'POST'])
def encode_page():
    day_of_week = get_today_day()
    max_payload_kb = MAX_FILE_PAYLOAD_SIZE // 1024
    
    if request.method == 'POST':
        try:
            # Get files
            ref_photo = request.files.get('reference_photo')
            carrier = request.files.get('carrier')
            rsa_key_file = request.files.get('rsa_key')
            payload_file = request.files.get('payload_file')
            
            if not ref_photo or not carrier:
                flash('Both reference photo and carrier image are required', 'error')
                return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
            
            if not allowed_image(ref_photo.filename) or not allowed_image(carrier.filename):
                flash('Invalid file type. Use PNG, JPG, or BMP', 'error')
                return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
            
            # Get form data
            message = request.form.get('message', '')
            day_phrase = request.form.get('day_phrase', '')
            pin = request.form.get('pin', '').strip()
            rsa_password = request.form.get('rsa_password', '')
            payload_type = request.form.get('payload_type', 'text')
            
            # Determine payload
            if payload_type == 'file' and payload_file and payload_file.filename:
                # File payload
                file_data = payload_file.read()
                
                result = validate_file_payload(file_data, payload_file.filename)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
                
                mime_type, _ = mimetypes.guess_type(payload_file.filename)
                payload = FilePayload(
                    data=file_data,
                    filename=payload_file.filename,
                    mime_type=mime_type
                )
            else:
                # Text message
                result = validate_message(message)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
                payload = message
            
            if not day_phrase:
                flash('Day phrase is required', 'error')
                return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
            
            # Read files
            ref_data = ref_photo.read()
            carrier_data = carrier.read()
            
            # Handle RSA key - can come from .pem file or QR code image
            rsa_key_data = None
            rsa_key_qr = request.files.get('rsa_key_qr')
            rsa_key_from_qr = False  # Track source for password handling
            
            if rsa_key_file and rsa_key_file.filename:
                # RSA key from .pem file
                rsa_key_data = rsa_key_file.read()
            elif rsa_key_qr and rsa_key_qr.filename and HAS_QRCODE_READ:
                # RSA key from QR code image
                qr_image_data = rsa_key_qr.read()
                key_pem = extract_key_from_qr(qr_image_data)
                if key_pem:
                    rsa_key_data = key_pem.encode('utf-8')
                    rsa_key_from_qr = True  # QR keys are never password-protected
                else:
                    flash('Could not extract RSA key from QR code image. Make sure the image contains a valid QR code.', 'error')
                    return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
            
            # Validate security factors
            result = validate_security_factors(pin, rsa_key_data)
            if not result.is_valid:
                flash(result.error_message, 'error')
                return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
            
            # Validate PIN if provided
            if pin:
                result = validate_pin(pin)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
            
            # Determine key password - QR code keys are never password-protected
            key_password = None if rsa_key_from_qr else (rsa_password if rsa_password else None)
            
            # Validate RSA key if provided
            if rsa_key_data:
                result = validate_rsa_key(rsa_key_data, key_password)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
            
            # Validate carrier image
            result = validate_image(carrier_data, "Carrier image")
            if not result.is_valid:
                flash(result.error_message, 'error')
                return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
            
            # Get date
            client_date = request.form.get('client_date', '').strip()
            if client_date and len(client_date) == 10 and client_date[4] == '-' and client_date[7] == '-':
                date_str = client_date
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            # Encode
            encode_result = encode(
                message=payload,
                reference_photo=ref_data,
                carrier_image=carrier_data,
                day_phrase=day_phrase,
                pin=pin,
                rsa_key_data=rsa_key_data,
                rsa_password=key_password,
                date_str=date_str
            )
            
            # Store temporarily
            file_id = secrets.token_urlsafe(16)
            cleanup_temp_files()
            TEMP_FILES[file_id] = {
                'data': encode_result.stego_image,
                'filename': encode_result.filename,
                'timestamp': time.time()
            }
            
            return redirect(url_for('encode_result', file_id=file_id))
            
        except CapacityError as e:
            flash(str(e), 'error')
            return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
        except StegasooError as e:
            flash(str(e), 'error')
            return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
        except Exception as e:
            flash(f'Error: {e}', 'error')
            return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)
    
    return render_template('encode.html', day_of_week=day_of_week, max_payload_kb=max_payload_kb, has_qrcode_read=HAS_QRCODE_READ)


@app.route('/encode/result/<file_id>')
def encode_result(file_id):
    if file_id not in TEMP_FILES:
        flash('File expired or not found. Please encode again.', 'error')
        return redirect(url_for('encode_page'))
    
    file_info = TEMP_FILES[file_id]
    return render_template('encode_result.html',
        file_id=file_id,
        filename=file_info['filename']
    )


@app.route('/encode/download/<file_id>')
def encode_download(file_id):
    if file_id not in TEMP_FILES:
        flash('File expired or not found.', 'error')
        return redirect(url_for('encode_page'))
    
    file_info = TEMP_FILES[file_id]
    return send_file(
        io.BytesIO(file_info['data']),
        mimetype='image/png',
        as_attachment=True,
        download_name=file_info['filename']
    )


@app.route('/encode/file/<file_id>')
def encode_file_route(file_id):
    """Serve file for Web Share API."""
    if file_id not in TEMP_FILES:
        return "Not found", 404
    
    file_info = TEMP_FILES[file_id]
    return send_file(
        io.BytesIO(file_info['data']),
        mimetype='image/png',
        as_attachment=False,
        download_name=file_info['filename']
    )


@app.route('/encode/cleanup/<file_id>', methods=['POST'])
def encode_cleanup(file_id):
    """Manually cleanup a file after sharing."""
    TEMP_FILES.pop(file_id, None)
    return jsonify({'status': 'ok'})


@app.route('/decode', methods=['GET', 'POST'])
def decode_page():
    if request.method == 'POST':
        try:
            # Get files
            ref_photo = request.files.get('reference_photo')
            stego_image = request.files.get('stego_image')
            rsa_key_file = request.files.get('rsa_key')
            
            if not ref_photo or not stego_image:
                flash('Both reference photo and stego image are required', 'error')
                return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Get form data
            day_phrase = request.form.get('day_phrase', '')
            pin = request.form.get('pin', '').strip()
            rsa_password = request.form.get('rsa_password', '')
            
            if not day_phrase:
                flash('Day phrase is required', 'error')
                return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Read files
            ref_data = ref_photo.read()
            stego_data = stego_image.read()
            
            # Handle RSA key - can come from .pem file or QR code image
            rsa_key_data = None
            rsa_key_qr = request.files.get('rsa_key_qr')
            rsa_key_from_qr = False  # Track source for password handling
            
            if rsa_key_file and rsa_key_file.filename:
                # RSA key from .pem file
                rsa_key_data = rsa_key_file.read()
            elif rsa_key_qr and rsa_key_qr.filename and HAS_QRCODE_READ:
                # RSA key from QR code image
                qr_image_data = rsa_key_qr.read()
                key_pem = extract_key_from_qr(qr_image_data)
                if key_pem:
                    rsa_key_data = key_pem.encode('utf-8')
                    rsa_key_from_qr = True  # QR keys are never password-protected
                else:
                    flash('Could not extract RSA key from QR code image. Make sure the image contains a valid QR code.', 'error')
                    return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Validate security factors
            result = validate_security_factors(pin, rsa_key_data)
            if not result.is_valid:
                flash(result.error_message, 'error')
                return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Validate PIN if provided
            if pin:
                result = validate_pin(pin)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Determine key password - QR code keys are never password-protected
            key_password = None if rsa_key_from_qr else (rsa_password if rsa_password else None)
            
            # Validate RSA key if provided
            if rsa_key_data:
                result = validate_rsa_key(rsa_key_data, key_password)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Decode
            decode_result = decode(
                stego_image=stego_data,
                reference_photo=ref_data,
                day_phrase=day_phrase,
                pin=pin,
                rsa_key_data=rsa_key_data,
                rsa_password=key_password
            )
            
            if decode_result.is_file:
                # File content - store temporarily for download
                file_id = secrets.token_urlsafe(16)
                cleanup_temp_files()
                
                filename = decode_result.filename or 'decoded_file'
                TEMP_FILES[file_id] = {
                    'data': decode_result.file_data,
                    'filename': filename,
                    'mime_type': decode_result.mime_type,
                    'timestamp': time.time()
                }
                
                return render_template('decode.html',
                    decoded_file=True,
                    file_id=file_id,
                    filename=filename,
                    file_size=format_size(len(decode_result.file_data)),
                    mime_type=decode_result.mime_type
                )
            else:
                # Text content
                return render_template('decode.html', decoded_message=decode_result.message)
            
        except DecryptionError:
            flash('Decryption failed. Check your phrase, PIN, RSA key, and reference photo.', 'error')
            return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
        except StegasooError as e:
            flash(str(e), 'error')
            return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
        except Exception as e:
            flash(f'Error: {e}', 'error')
            return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
    
    return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)


@app.route('/decode/download/<file_id>')
def decode_download(file_id):
    """Download decoded file."""
    if file_id not in TEMP_FILES:
        flash('File expired or not found.', 'error')
        return redirect(url_for('decode_page'))
    
    file_info = TEMP_FILES[file_id]
    mime_type = file_info.get('mime_type', 'application/octet-stream')
    
    return send_file(
        io.BytesIO(file_info['data']),
        mimetype=mime_type,
        as_attachment=True,
        download_name=file_info['filename']
    )


@app.route('/about')
def about():
    return render_template('about.html', 
        has_argon2=has_argon2(),
        has_qrcode_read=HAS_QRCODE_READ,
        max_payload_kb=MAX_FILE_PAYLOAD_SIZE // 1024
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
