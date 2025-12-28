#!/usr/bin/env python3
"""
Stegasoo Web Frontend

Flask-based web UI for steganography operations.
This is a thin wrapper around the stegasoo library.
"""

import io
import sys
import time
import secrets
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
    get_today_day, generate_filename,
    DAY_NAMES, __version__,
    StegasooError, DecryptionError, CapacityError,
    has_argon2,
)
from stegasoo.constants import (
    MAX_MESSAGE_SIZE, MIN_PIN_LENGTH, MAX_PIN_LENGTH,
    VALID_RSA_SIZES,
)


# ============================================================================
# FLASK APP CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload

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
            return render_template('generate.html', generated=False, has_ml=False)
        
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
                has_ml=False
            )
        except Exception as e:
            flash(f'Error generating credentials: {e}', 'error')
            return render_template('generate.html', generated=False, has_ml=False)
    
    return render_template('generate.html', generated=False, has_ml=False)


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
    
    if request.method == 'POST':
        try:
            # Get files
            ref_photo = request.files.get('reference_photo')
            carrier = request.files.get('carrier')
            rsa_key_file = request.files.get('rsa_key')
            
            if not ref_photo or not carrier:
                flash('Both reference photo and carrier image are required', 'error')
                return render_template('encode.html', day_of_week=day_of_week)
            
            if not allowed_image(ref_photo.filename) or not allowed_image(carrier.filename):
                flash('Invalid file type. Use PNG, JPG, or BMP', 'error')
                return render_template('encode.html', day_of_week=day_of_week)
            
            # Get form data
            message = request.form.get('message', '')
            day_phrase = request.form.get('day_phrase', '')
            pin = request.form.get('pin', '').strip()
            rsa_password = request.form.get('rsa_password', '')
            
            # Validate message
            result = validate_message(message)
            if not result.is_valid:
                flash(result.error_message, 'error')
                return render_template('encode.html', day_of_week=day_of_week)
            
            if not day_phrase:
                flash('Day phrase is required', 'error')
                return render_template('encode.html', day_of_week=day_of_week)
            
            # Read files
            ref_data = ref_photo.read()
            carrier_data = carrier.read()
            rsa_key_data = rsa_key_file.read() if rsa_key_file and rsa_key_file.filename else None
            
            # Validate security factors
            result = validate_security_factors(pin, rsa_key_data)
            if not result.is_valid:
                flash(result.error_message, 'error')
                return render_template('encode.html', day_of_week=day_of_week)
            
            # Validate PIN if provided
            if pin:
                result = validate_pin(pin)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('encode.html', day_of_week=day_of_week)
            
            # Validate RSA key if provided
            if rsa_key_data:
                result = validate_rsa_key(rsa_key_data, rsa_password if rsa_password else None)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('encode.html', day_of_week=day_of_week)
            
            # Validate carrier image
            result = validate_image(carrier_data, "Carrier image")
            if not result.is_valid:
                flash(result.error_message, 'error')
                return render_template('encode.html', day_of_week=day_of_week)
            
            # Get date
            client_date = request.form.get('client_date', '').strip()
            if client_date and len(client_date) == 10 and client_date[4] == '-' and client_date[7] == '-':
                date_str = client_date
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')
            
            # Encode
            encode_result = encode(
                message=message,
                reference_photo=ref_data,
                carrier_image=carrier_data,
                day_phrase=day_phrase,
                pin=pin,
                rsa_key_data=rsa_key_data,
                rsa_password=rsa_password if rsa_password else None,
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
            return render_template('encode.html', day_of_week=day_of_week)
        except StegasooError as e:
            flash(str(e), 'error')
            return render_template('encode.html', day_of_week=day_of_week)
        except Exception as e:
            flash(f'Error: {e}', 'error')
            return render_template('encode.html', day_of_week=day_of_week)
    
    return render_template('encode.html', day_of_week=day_of_week)


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
def encode_file(file_id):
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
                return render_template('decode.html')
            
            # Get form data
            day_phrase = request.form.get('day_phrase', '')
            pin = request.form.get('pin', '').strip()
            rsa_password = request.form.get('rsa_password', '')
            
            if not day_phrase:
                flash('Day phrase is required', 'error')
                return render_template('decode.html')
            
            # Read files
            ref_data = ref_photo.read()
            stego_data = stego_image.read()
            rsa_key_data = rsa_key_file.read() if rsa_key_file and rsa_key_file.filename else None
            
            # Validate security factors
            result = validate_security_factors(pin, rsa_key_data)
            if not result.is_valid:
                flash(result.error_message, 'error')
                return render_template('decode.html')
            
            # Validate PIN if provided
            if pin:
                result = validate_pin(pin)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('decode.html')
            
            # Validate RSA key if provided
            if rsa_key_data:
                result = validate_rsa_key(rsa_key_data, rsa_password if rsa_password else None)
                if not result.is_valid:
                    flash(result.error_message, 'error')
                    return render_template('decode.html')
            
            # Decode
            message = decode(
                stego_image=stego_data,
                reference_photo=ref_data,
                day_phrase=day_phrase,
                pin=pin,
                rsa_key_data=rsa_key_data,
                rsa_password=rsa_password if rsa_password else None
            )
            
            return render_template('decode.html', decoded_message=message)
            
        except DecryptionError:
            flash('Decryption failed. Check your phrase, PIN, RSA key, and reference photo.', 'error')
            return render_template('decode.html')
        except StegasooError as e:
            flash(str(e), 'error')
            return render_template('decode.html')
        except Exception as e:
            flash(f'Error: {e}', 'error')
            return render_template('decode.html')
    
    return render_template('decode.html')


@app.route('/about')
def about():
    return render_template('about.html', has_argon2=has_argon2())


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
