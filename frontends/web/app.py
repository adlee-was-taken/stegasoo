#!/usr/bin/env python3
"""
Stegasoo Web Frontend (v3.2.0)

Flask-based web UI for steganography operations.
Supports both text messages and file embedding.

CHANGES in v3.2.0:
- Removed date dependency from all operations
- Renamed day_phrase → passphrase
- No date selection or tracking needed
- Simplified user experience for asynchronous communications

NEW in v3.0: LSB and DCT embedding modes with advanced options.
NEW in v3.0.1: DCT output format selection (PNG or JPEG) and color mode (grayscale or color).
"""

import io
import sys
import time
import secrets
import mimetypes
from pathlib import Path
from datetime import datetime
from PIL import Image

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
    validate_file_payload, validate_passphrase,
    generate_filename,
    StegasooError, DecryptionError, CapacityError,
    has_argon2,
    FilePayload,
    # Embedding modes
    EMBED_MODE_LSB,
    EMBED_MODE_DCT,
    EMBED_MODE_AUTO,
    has_dct_support,
    compare_modes,
    will_fit_by_mode,
)
from stegasoo.constants import (
    __version__,
    MAX_MESSAGE_SIZE, MAX_MESSAGE_CHARS,
    MIN_PIN_LENGTH, MAX_PIN_LENGTH,
    MIN_PASSPHRASE_WORDS, RECOMMENDED_PASSPHRASE_WORDS,
    DEFAULT_PASSPHRASE_WORDS,
    VALID_RSA_SIZES, MAX_FILE_SIZE,
    MAX_FILE_PAYLOAD_SIZE, MAX_UPLOAD_SIZE,
    TEMP_FILE_EXPIRY, TEMP_FILE_EXPIRY_MINUTES,
    THUMBNAIL_SIZE, THUMBNAIL_QUALITY,
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
app.config['MAX_CONTENT_LENGTH'] = MAX_FILE_SIZE

# Temporary file storage for sharing (file_id -> {data, timestamp, filename})
TEMP_FILES: dict[str, dict] = {}
THUMBNAIL_FILES: dict[str, bytes] = {}


# ============================================================================
# TEMPLATE CONTEXT PROCESSOR
# ============================================================================

@app.context_processor
def inject_globals():
    """Inject global variables into all templates."""
    return {
        'version': __version__,
        'max_message_chars': MAX_MESSAGE_CHARS,
        'max_payload_kb': MAX_FILE_PAYLOAD_SIZE // 1024,
        'max_upload_mb': MAX_UPLOAD_SIZE // (1024 * 1024),
        'temp_file_expiry_minutes': TEMP_FILE_EXPIRY_MINUTES,
        'min_pin_length': MIN_PIN_LENGTH,
        'max_pin_length': MAX_PIN_LENGTH,
        # NEW in v3.2.0
        'min_passphrase_words': MIN_PASSPHRASE_WORDS,
        'recommended_passphrase_words': RECOMMENDED_PASSPHRASE_WORDS,
        'default_passphrase_words': DEFAULT_PASSPHRASE_WORDS,
        # NEW in v3.0
        'has_dct': has_dct_support(),
    }


# ============================================================================
# CONFIGURATION
# ============================================================================

try:
    print(f"Stegasoo v{__version__} - Web Frontend")
    print(f"Current MAX_FILE_SIZE: {MAX_FILE_SIZE}")
    print(f"Current MAX_FILE_PAYLOAD_SIZE: {MAX_FILE_PAYLOAD_SIZE}")
    print(f"DCT support: {has_dct_support()}")
    print(f"QR code support: write={HAS_QRCODE}, read={HAS_QRCODE_READ}")
    
    DESIRED_PAYLOAD_SIZE = 2 * 1024 * 1024  # 2MB
    
    if hasattr(stegasoo, 'MAX_FILE_PAYLOAD_SIZE'):
        print(f"Overriding MAX_FILE_PAYLOAD_SIZE to {DESIRED_PAYLOAD_SIZE}")
        stegasoo.MAX_FILE_PAYLOAD_SIZE = DESIRED_PAYLOAD_SIZE
    
except Exception as e:
    print(f"Could not override stegasoo limits: {e}")


def generate_thumbnail(image_data: bytes, size: tuple = THUMBNAIL_SIZE) -> bytes:
    """Generate thumbnail from image data."""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # Convert to RGB if necessary (handle grayscale too)
            if img.mode in ('RGBA', 'LA', 'P'):
                # Create white background for transparent images
                background = Image.new('RGB', img.size, (255, 255, 255))
                if img.mode == 'P':
                    img = img.convert('RGBA')
                background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                img = background
            elif img.mode == 'L':
                # Convert grayscale to RGB for thumbnail
                img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            
            # Create thumbnail
            img.thumbnail(size, Image.Resampling.LANCZOS)
            
            # Save to bytes
            buffer = io.BytesIO()
            img.save(buffer, format='JPEG', quality=THUMBNAIL_QUALITY, optimize=True)
            return buffer.getvalue()
    except Exception as e:
        print(f"Thumbnail generation error: {e}")
        return None


def cleanup_temp_files():
    """Remove expired temporary files."""
    now = time.time()
    expired = [fid for fid, info in TEMP_FILES.items() if now - info['timestamp'] > TEMP_FILE_EXPIRY]
    
    for fid in expired:
        TEMP_FILES.pop(fid, None)
        # Also clean up corresponding thumbnail
        thumb_id = f"{fid}_thumb"
        THUMBNAIL_FILES.pop(thumb_id, None)


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
        # v3.2.0: Changed from words_per_phrase to words_per_passphrase, default increased to 4
        words_per_passphrase = int(request.form.get('words_per_passphrase', DEFAULT_PASSPHRASE_WORDS))
        use_pin = request.form.get('use_pin') == 'on'
        use_rsa = request.form.get('use_rsa') == 'on'
        
        if not use_pin and not use_rsa:
            flash('You must select at least one security factor (PIN or RSA Key)', 'error')
            return render_template('generate.html', generated=False, has_qrcode=HAS_QRCODE)
        
        pin_length = int(request.form.get('pin_length', 6))
        rsa_bits = int(request.form.get('rsa_bits', 2048))
        
        # Clamp values
        words_per_passphrase = max(MIN_PASSPHRASE_WORDS, min(12, words_per_passphrase))
        pin_length = max(MIN_PIN_LENGTH, min(MAX_PIN_LENGTH, pin_length))
        if rsa_bits not in VALID_RSA_SIZES:
            rsa_bits = 2048
        
        try:
            creds = generate_credentials(
                use_pin=use_pin,
                use_rsa=use_rsa,
                pin_length=pin_length,
                rsa_bits=rsa_bits,
                words_per_passphrase=words_per_passphrase
            )
            
            # Store RSA key temporarily for QR generation
            qr_token = None
            qr_needs_compression = False
            qr_too_large = False
            
            if creds.rsa_key_pem and HAS_QRCODE:
                # Check if key fits in QR code
                if can_fit_in_qr(creds.rsa_key_pem, compress=True):
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
            
            # v3.2.0: Single passphrase instead of daily phrases
            return render_template('generate.html',
                passphrase=creds.passphrase,  # v3.2.0: Single passphrase
                pin=creds.pin,
                generated=True,
                words_per_passphrase=words_per_passphrase,
                pin_length=pin_length if use_pin else None,
                use_pin=use_pin,
                use_rsa=use_rsa,
                rsa_bits=rsa_bits,
                rsa_key_pem=creds.rsa_key_pem,
                passphrase_entropy=creds.passphrase_entropy,
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
    password = request.form.get('key_password', '')

    if not key_pem:
        flash('No key to download', 'error')
        return redirect(url_for('generate'))

    if not password or len(password) < 8:
        flash('Password must be at least 8 characters', 'error')
        return redirect(url_for('generate'))

    try:
        private_key = load_rsa_key(key_pem.encode('utf-8'))
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


# ============================================================================
# NEW in v3.0 - CAPACITY COMPARISON API
# ============================================================================

@app.route('/api/compare-capacity', methods=['POST'])
def api_compare_capacity():
    """
    Compare LSB and DCT capacity for an uploaded carrier image.
    Returns JSON with capacity info for both modes.
    """
    carrier = request.files.get('carrier')
    if not carrier:
        return jsonify({'error': 'No carrier image provided'}), 400
    
    try:
        carrier_data = carrier.read()
        comparison = compare_modes(carrier_data)
        
        return jsonify({
            'success': True,
            'width': comparison['width'],
            'height': comparison['height'],
            'lsb': {
                'capacity_bytes': comparison['lsb']['capacity_bytes'],
                'capacity_kb': round(comparison['lsb']['capacity_kb'], 1),
                'output': comparison['lsb']['output'],
            },
            'dct': {
                'capacity_bytes': comparison['dct']['capacity_bytes'],
                'capacity_kb': round(comparison['dct']['capacity_kb'], 1),
                'output': comparison['dct']['output'],
                'available': comparison['dct']['available'],
                'ratio': round(comparison['dct']['ratio_vs_lsb'], 1),
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/check-fit', methods=['POST'])
def api_check_fit():
    """
    Check if a payload will fit in the carrier with selected mode.
    Returns JSON with fit status and details.
    """
    carrier = request.files.get('carrier')
    payload_size = request.form.get('payload_size', type=int)
    embed_mode = request.form.get('embed_mode', 'lsb')
    
    if not carrier or payload_size is None:
        return jsonify({'error': 'Missing carrier or payload_size'}), 400
    
    if embed_mode not in ('lsb', 'dct'):
        return jsonify({'error': 'Invalid embed_mode'}), 400
    
    if embed_mode == 'dct' and not has_dct_support():
        return jsonify({'error': 'DCT mode requires scipy'}), 400
    
    try:
        carrier_data = carrier.read()
        result = will_fit_by_mode(payload_size, carrier_data, embed_mode=embed_mode)
        
        return jsonify({
            'success': True,
            'fits': result['fits'],
            'payload_size': result['payload_size'],
            'capacity': result['capacity'],
            'usage_percent': round(result['usage_percent'], 1),
            'headroom': result['headroom'],
            'mode': embed_mode,
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500


# ============================================================================
# ENCODE
# ============================================================================

@app.route('/encode', methods=['GET', 'POST'])
def encode_page():
    if request.method == 'POST':
        try:
            # Get files
            ref_photo = request.files.get('reference_photo')
            carrier = request.files.get('carrier')
            rsa_key_file = request.files.get('rsa_key')
            payload_file = request.files.get('payload_file')
            
            if not ref_photo or not carrier:
                flash('Both reference photo and carrier image are required', 'error')
                return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            if not allowed_image(ref_photo.filename) or not allowed_image(carrier.filename):
                flash('Invalid file type. Use PNG, JPG, or BMP', 'error')
                return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Get form data - v3.2.0: renamed from day_phrase to passphrase
            message = request.form.get('message', '')
            passphrase = request.form.get('passphrase', '')  # v3.2.0: Renamed
            pin = request.form.get('pin', '').strip()
            rsa_password = request.form.get('rsa_password', '')
            payload_type = request.form.get('payload_type', 'text')
            
            # NEW in v3.0 - Embedding mode
            embed_mode = request.form.get('embed_mode', 'lsb')
            if embed_mode not in ('lsb', 'dct'):
                embed_mode = 'lsb'
            
            # NEW in v3.0.1 - DCT output format
            dct_output_format = request.form.get('dct_output_format', 'png')
            if dct_output_format not in ('png', 'jpeg'):
                dct_output_format = 'png'
            
            # NEW in v3.0.1 - DCT color mode
            dct_color_mode = request.form.get('dct_color_mode', 'color')
            if dct_color_mode not in ('grayscale', 'color'):
                dct_color_mode = 'color'
            
            # Check DCT availability
            if embed_mode == 'dct' and not has_dct_support():
                flash('DCT mode requires scipy. Install with: pip install scipy', 'error')
                return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Determine payload
            if payload_type == 'file' and payload_file and payload_file.filename:
                # File payload
                file_data = payload_file.read()
                
                result = validate_file_payload(file_data, payload_file.filename)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
                
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
                    return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
                payload = message
            
            # v3.2.0: Renamed from day_phrase
            if not passphrase:
                flash('Passphrase is required', 'error')
                return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # v3.2.0: Validate passphrase
            result = validate_passphrase(passphrase)
            if not result.is_valid:
                flash(result.error_message, 'error')
                return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Show warning if passphrase is short
            if result.warning:
                flash(result.warning, 'warning')
            
            # Read files
            ref_data = ref_photo.read()
            carrier_data = carrier.read()
            
            # Handle RSA key - can come from .pem file or QR code image
            rsa_key_data = None
            rsa_key_qr = request.files.get('rsa_key_qr')
            rsa_key_from_qr = False
            
            if rsa_key_file and rsa_key_file.filename:
                rsa_key_data = rsa_key_file.read()
            elif rsa_key_qr and rsa_key_qr.filename and HAS_QRCODE_READ:
                qr_image_data = rsa_key_qr.read()
                key_pem = extract_key_from_qr(qr_image_data)
                if key_pem:
                    rsa_key_data = key_pem.encode('utf-8')
                    rsa_key_from_qr = True
                else:
                    flash('Could not extract RSA key from QR code image.', 'error')
                    return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Validate security factors
            result = validate_security_factors(pin, rsa_key_data)
            if not result.is_valid:
                flash(result.error_message, 'error')
                return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Validate PIN if provided
            if pin:
                result = validate_pin(pin)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Determine key password
            key_password = None if rsa_key_from_qr else (rsa_password if rsa_password else None)
            
            # Validate RSA key if provided
            if rsa_key_data:
                result = validate_rsa_key(rsa_key_data, key_password)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Validate carrier image
            result = validate_image(carrier_data, "Carrier image")
            if not result.is_valid:
                flash(result.error_message, 'error')
                return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # v3.2.0: No date parameter needed
            encode_result = encode(
                message=payload,
                reference_photo=ref_data,
                carrier_image=carrier_data,
                passphrase=passphrase,  # v3.2.0: Renamed from day_phrase
                pin=pin,
                rsa_key_data=rsa_key_data,
                rsa_password=key_password,
                # date_str removed in v3.2.0
                embed_mode=embed_mode,
                dct_output_format=dct_output_format if embed_mode == 'dct' else None,
                dct_color_mode=dct_color_mode if embed_mode == 'dct' else None,
            )
            
            # Determine actual output format for filename and storage
            if embed_mode == 'dct' and dct_output_format == 'jpeg':
                output_ext = '.jpg'
                output_mime = 'image/jpeg'
                filename = encode_result.filename
                if filename.endswith('.png'):
                    filename = filename[:-4] + '.jpg'
            else:
                output_ext = '.png'
                output_mime = 'image/png'
                filename = encode_result.filename
            
            # Store temporarily
            file_id = secrets.token_urlsafe(16)
            cleanup_temp_files()
            TEMP_FILES[file_id] = {
                'data': encode_result.stego_image,
                'filename': filename,
                'timestamp': time.time(),
                'embed_mode': embed_mode,
                'output_format': dct_output_format if embed_mode == 'dct' else 'png',
                'color_mode': dct_color_mode if embed_mode == 'dct' else None,
                'mime_type': output_mime,
            }
            
            return redirect(url_for('encode_result', file_id=file_id))
            
        except CapacityError as e:
            flash(str(e), 'error')
            return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
        except StegasooError as e:
            flash(str(e), 'error')
            return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
        except Exception as e:
            flash(f'Error: {e}', 'error')
            return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)
    
    return render_template('encode.html', has_qrcode_read=HAS_QRCODE_READ)


@app.route('/encode/result/<file_id>')
def encode_result(file_id):
    if file_id not in TEMP_FILES:
        flash('File expired or not found. Please encode again.', 'error')
        return redirect(url_for('encode_page'))
    
    file_info = TEMP_FILES[file_id]
    
    # Generate thumbnail
    thumbnail_data = generate_thumbnail(file_info['data'])
    thumbnail_id = None
    
    if thumbnail_data:
        thumbnail_id = f"{file_id}_thumb"
        THUMBNAIL_FILES[thumbnail_id] = thumbnail_data
    
    return render_template('encode_result.html',
        file_id=file_id,
        filename=file_info['filename'],
        thumbnail_url=url_for('encode_thumbnail', thumb_id=thumbnail_id) if thumbnail_id else None,
        embed_mode=file_info.get('embed_mode', 'lsb'),
        output_format=file_info.get('output_format', 'png'),
        color_mode=file_info.get('color_mode'),
    )


@app.route('/encode/thumbnail/<thumb_id>')
def encode_thumbnail(thumb_id):
    """Serve thumbnail image."""
    if thumb_id not in THUMBNAIL_FILES:
        return "Thumbnail not found", 404
    
    return send_file(
        io.BytesIO(THUMBNAIL_FILES[thumb_id]),
        mimetype='image/jpeg',
        as_attachment=False
    )


@app.route('/encode/download/<file_id>')
def encode_download(file_id):
    if file_id not in TEMP_FILES:
        flash('File expired or not found.', 'error')
        return redirect(url_for('encode_page'))
    
    file_info = TEMP_FILES[file_id]
    mime_type = file_info.get('mime_type', 'image/png')
    
    return send_file(
        io.BytesIO(file_info['data']),
        mimetype=mime_type,
        as_attachment=True,
        download_name=file_info['filename']
    )


@app.route('/encode/file/<file_id>')
def encode_file_route(file_id):
    """Serve file for Web Share API."""
    if file_id not in TEMP_FILES:
        return "Not found", 404
    
    file_info = TEMP_FILES[file_id]
    mime_type = file_info.get('mime_type', 'image/png')
    
    return send_file(
        io.BytesIO(file_info['data']),
        mimetype=mime_type,
        as_attachment=False,
        download_name=file_info['filename']
    )


@app.route('/encode/cleanup/<file_id>', methods=['POST'])
def encode_cleanup(file_id):
    """Manually cleanup a file after sharing."""
    TEMP_FILES.pop(file_id, None)
    
    # Also cleanup thumbnail if exists
    thumb_id = f"{file_id}_thumb"
    THUMBNAIL_FILES.pop(thumb_id, None)
    
    return jsonify({'status': 'ok'})


# ============================================================================
# DECODE
# ============================================================================

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
            
            # Get form data - v3.2.0: renamed from day_phrase to passphrase
            passphrase = request.form.get('passphrase', '')  # v3.2.0: Renamed
            pin = request.form.get('pin', '').strip()
            rsa_password = request.form.get('rsa_password', '')
            
            # NEW in v3.0 - Extraction mode
            embed_mode = request.form.get('embed_mode', 'auto')
            if embed_mode not in ('auto', 'lsb', 'dct'):
                embed_mode = 'auto'
            
            # Check DCT availability
            if embed_mode == 'dct' and not has_dct_support():
                flash('DCT mode requires scipy. Install with: pip install scipy', 'error')
                return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # v3.2.0: Removed date handling (no stego_date needed)
            
            # v3.2.0: Renamed from day_phrase
            if not passphrase:
                flash('Passphrase is required', 'error')
                return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # Read files
            ref_data = ref_photo.read()
            stego_data = stego_image.read()
            
            # Handle RSA key - can come from .pem file or QR code image
            rsa_key_data = None
            rsa_key_qr = request.files.get('rsa_key_qr')
            rsa_key_from_qr = False
            
            if rsa_key_file and rsa_key_file.filename:
                rsa_key_data = rsa_key_file.read()
            elif rsa_key_qr and rsa_key_qr.filename and HAS_QRCODE_READ:
                qr_image_data = rsa_key_qr.read()
                key_pem = extract_key_from_qr(qr_image_data)
                if key_pem:
                    rsa_key_data = key_pem.encode('utf-8')
                    rsa_key_from_qr = True
                else:
                    flash('Could not extract RSA key from QR code image.', 'error')
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
            
            # Determine key password
            key_password = None if rsa_key_from_qr else (rsa_password if rsa_password else None)
            
            # Validate RSA key if provided
            if rsa_key_data:
                result = validate_rsa_key(rsa_key_data, key_password)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('decode.html', has_qrcode_read=HAS_QRCODE_READ)
            
            # v3.2.0: No date_str parameter needed
            decode_result = decode(
                stego_image=stego_data,
                reference_photo=ref_data,
                passphrase=passphrase,  # v3.2.0: Renamed from day_phrase
                pin=pin,
                rsa_key_data=rsa_key_data,
                rsa_password=key_password,
                # date_str removed in v3.2.0
                embed_mode=embed_mode,
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
            flash('Decryption failed. Check your passphrase, PIN, RSA key, and reference photo.', 'error')
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
        has_qrcode_read=HAS_QRCODE_READ
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
