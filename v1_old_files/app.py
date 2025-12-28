#!/usr/bin/env python3
"""
Stegasoo: Steganography portal for security-minded messaging.

    Aaron D. Lee (w/ vibes)
    2025-12-27

Built as a learning experience with a few LLMs to see if I can make something decent.
"""

import os
import io
import re
import secrets
import hashlib
import struct
import time
from datetime import datetime
from flask import Flask, render_template, request, send_file, jsonify, flash, redirect, url_for
from werkzeug.utils import secure_filename
from PIL import Image
from secureDeleter import SecureDeleter

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import load_pem_private_key

try:
    from argon2.low_level import hash_secret_raw, Type
    HAS_ARGON2 = True
except ImportError:
    HAS_ARGON2 = False
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives import hashes

HAS_ML = False  # Story generator disabled

# ============================================================================
# FLASK APP CONFIGURATION
# ============================================================================

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024  # 5MB max upload per file
app.config['UPLOAD_FOLDER'] = '/tmp/stego_uploads'

# Limits
MAX_IMAGE_PIXELS = 4000000  # 4 megapixels max (e.g., 2000x2000)
MAX_MESSAGE_SIZE = 50000    # 50KB message max
MIN_PIN_LENGTH = 6
MAX_PIN_LENGTH = 9
MIN_RSA_BITS = 2048
VALID_RSA_SIZES = [2048, 3072, 4096]

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'bmp', 'gif'}

# Temporary file storage for sharing (file_id -> {data, timestamp, filename})
TEMP_FILES = {}
TEMP_FILE_EXPIRY = 300  # 5 minutes

# ============================================================================
# CRYPTO CONFIGURATION
# ============================================================================

MAGIC_HEADER = b'\x89ST3'
VERSION = 3
SALT_SIZE = 32
IV_SIZE = 12
TAG_SIZE = 16
ARGON2_TIME_COST = 4
ARGON2_MEMORY_COST = 256 * 1024
ARGON2_PARALLELISM = 4

DAY_NAMES = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']

# BIP-39 wordlist (loaded from file)
BIP39_FILE = os.path.join(os.path.dirname(__file__), 'bip39-words.txt')
with open(BIP39_FILE, 'r') as f:
    BIP39_WORDS = [line.strip() for line in f if line.strip()]

# ============================================================================
# SECURE CLEANUP
# ============================================================================

def secure_cleanup_uploads():
    """Securely delete any stray files in uploads directory."""
    upload_dir = app.config['UPLOAD_FOLDER']
    if os.path.exists(upload_dir):
        for filename in os.listdir(upload_dir):
            filepath = os.path.join(upload_dir, filename)
            if os.path.isfile(filepath) and not filename.startswith('.'):
                try:
                    deleter = SecureDeleter(filepath)
                    deleter.execute()
                except Exception as e:
                    os.remove(filepath)


def cleanup_temp_files():
    """Remove expired temporary files."""
    now = time.time()
    expired = [fid for fid, info in TEMP_FILES.items() if now - info['timestamp'] > TEMP_FILE_EXPIRY]
    for fid in expired:
        TEMP_FILES.pop(fid, None)

# ============================================================================
# VALIDATION FUNCTIONS
# ============================================================================

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def validate_pin(pin):
    """Validate PIN format: 6-9 digits, no leading zeros."""
    if not pin:
        return True, ""  # Empty PIN is valid (if RSA key provided)
    if not pin.isdigit():
        return False, "PIN must contain only digits"
    if len(pin) < MIN_PIN_LENGTH or len(pin) > MAX_PIN_LENGTH:
        return False, f"PIN must be {MIN_PIN_LENGTH}-{MAX_PIN_LENGTH} digits"
    if pin[0] == '0':
        return False, "PIN cannot start with zero"
    return True, ""


def validate_message(message):
    """Validate message size."""
    if not message:
        return False, "Message is required"
    if len(message) > MAX_MESSAGE_SIZE:
        return False, f"Message too long. Max {MAX_MESSAGE_SIZE // 1000}KB allowed"
    return True, ""


def validate_image(image_data, name="Image"):
    """Validate image data and dimensions."""
    try:
        img = Image.open(io.BytesIO(image_data))
        width, height = img.size
        num_pixels = width * height
        
        if num_pixels > MAX_IMAGE_PIXELS:
            max_dim = int(MAX_IMAGE_PIXELS ** 0.5)
            return False, f"{name} too large ({width}x{height} = {num_pixels:,} pixels). Max ~{MAX_IMAGE_PIXELS:,} pixels ({max_dim}x{max_dim})"
        return True, ""
    except Exception as e:
        return False, f"Could not read {name}: {str(e)}"


def validate_rsa_key(key_data, password=None):
    """
    Validate RSA private key.
    Returns (is_valid, error_message, key_size_bits)
    """
    if not key_data:
        return True, "", 0  # Empty key is valid (if PIN provided)
    
    try:
        # Try to load the key
        if password:
            private_key = load_pem_private_key(key_data, password=password.encode(), backend=default_backend())
        else:
            # Try without password first
            try:
                private_key = load_pem_private_key(key_data, password=None, backend=default_backend())
            except TypeError:
                # Key is encrypted but no password provided
                return False, "RSA key is password-protected. Please enter the password.", 0
        
        # Check key size
        key_size = private_key.key_size
        if key_size < MIN_RSA_BITS:
            return False, f"RSA key must be at least {MIN_RSA_BITS} bits (got {key_size})", 0
        
        return True, "", key_size
        
    except ValueError as e:
        if "password" in str(e).lower() or "encrypted" in str(e).lower():
            return False, "Incorrect password for RSA key", 0
        return False, f"Invalid RSA key format: {str(e)}", 0
    except Exception as e:
        return False, f"Could not load RSA key: {str(e)}", 0


def validate_security_factors(pin, rsa_key_data):
    """Ensure at least one security factor is provided."""
    has_pin = bool(pin and pin.strip())
    has_key = bool(rsa_key_data and len(rsa_key_data) > 0)
    
    if not has_pin and not has_key:
        return False, "You must provide at least a PIN or RSA Key"
    return True, ""


# ============================================================================
# RSA KEY GENERATION
# ============================================================================

def generate_rsa_key(bits=2048):
    """Generate RSA private key."""
    if bits not in VALID_RSA_SIZES:
        bits = 2048
    
    private_key = rsa.generate_private_key(
        public_exponent=65537,
        key_size=bits,
        backend=default_backend()
    )
    return private_key


def export_rsa_key_pem(private_key, password=None):
    """Export RSA key to PEM format, optionally encrypted."""
    if password:
        encryption = serialization.BestAvailableEncryption(password.encode())
    else:
        encryption = serialization.NoEncryption()
    
    pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=encryption
    )
    return pem


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def generate_pin(length=6):
    """Generate a random PIN of specified length (6-9 digits)."""
    length = max(MIN_PIN_LENGTH, min(MAX_PIN_LENGTH, length))
    first_digit = str(secrets.randbelow(9) + 1)  # 1-9
    rest = ''.join(str(secrets.randbelow(10)) for _ in range(length - 1))
    return first_digit + rest


def generate_day_phrases(words_per_phrase=3):
    phrases = {}
    for day in DAY_NAMES:
        words = [secrets.choice(BIP39_WORDS) for _ in range(words_per_phrase)]
        phrases[day] = ' '.join(words)
    return phrases


def hash_photo(image_data):
    """Compute deterministic hash of photo content."""
    img = Image.open(io.BytesIO(image_data))
    img = img.convert('RGB')
    pixels = img.tobytes()
    h = hashlib.sha256(pixels).digest()
    h = hashlib.sha256(h + pixels[:1024]).digest()
    return h


def derive_hybrid_key(photo_data, day_phrase, date_str, salt, pin="", rsa_key_data=None):
    """Derive encryption key from photo + phrase + PIN + RSA key + date + salt."""
    photo_hash = hash_photo(photo_data)

    key_material = (
        photo_hash +
        day_phrase.lower().encode() +
        pin.encode() +
        date_str.encode() +
        salt
    )
    
    # Add RSA key hash if provided
    if rsa_key_data:
        key_material += hashlib.sha256(rsa_key_data).digest()

    if HAS_ARGON2:
        key = hash_secret_raw(
            secret=key_material,
            salt=salt[:32],
            time_cost=ARGON2_TIME_COST,
            memory_cost=ARGON2_MEMORY_COST,
            parallelism=ARGON2_PARALLELISM,
            hash_len=32,
            type=Type.ID
        )
    else:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA512(),
            length=32,
            salt=salt,
            iterations=600000,
            backend=default_backend()
        )
        key = kdf.derive(key_material)

    return key


def derive_pixel_key(photo_data, day_phrase, date_str, pin="", rsa_key_data=None):
    """Derive key for pixel selection."""
    photo_hash = hash_photo(photo_data)
    material = photo_hash + day_phrase.lower().encode() + pin.encode() + date_str.encode()
    
    if rsa_key_data:
        material += hashlib.sha256(rsa_key_data).digest()
    
    return hashlib.sha256(material + b"pixel_selection").digest()


def encrypt_message(message, photo_data, day_phrase, date_str, pin="", rsa_key_data=None):
    """Encrypt message using hybrid key derivation."""
    salt = secrets.token_bytes(SALT_SIZE)
    key = derive_hybrid_key(photo_data, day_phrase, date_str, salt, pin, rsa_key_data)
    iv = secrets.token_bytes(IV_SIZE)

    if isinstance(message, str):
        message = message.encode()

    padding_len = secrets.randbelow(256) + 64
    padded_len = ((len(message) + padding_len + 255) // 256) * 256
    padding_needed = padded_len - len(message)
    padding = secrets.token_bytes(padding_needed - 4) + struct.pack('>I', len(message))
    padded_message = message + padding

    cipher = Cipher(algorithms.AES(key), modes.GCM(iv), backend=default_backend())
    encryptor = cipher.encryptor()
    encryptor.authenticate_additional_data(MAGIC_HEADER + bytes([VERSION]))
    ciphertext = encryptor.update(padded_message) + encryptor.finalize()

    date_bytes = date_str.encode()

    return (
        MAGIC_HEADER +
        bytes([VERSION]) +
        bytes([len(date_bytes)]) +
        date_bytes +
        salt +
        iv +
        encryptor.tag +
        ciphertext
    )


def generate_pixel_indices(key, num_pixels, num_needed):
    """Generate pseudo-random pixel indices."""
    if num_needed >= num_pixels // 2:
        nonce = b'\x00' * 16
        cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None, backend=default_backend())
        encryptor = cipher.encryptor()

        indices = list(range(num_pixels))
        random_bytes = encryptor.update(b'\x00' * (num_pixels * 4))

        for i in range(num_pixels - 1, 0, -1):
            j_bytes = random_bytes[(num_pixels - 1 - i) * 4:(num_pixels - i) * 4]
            j = int.from_bytes(j_bytes, 'big') % (i + 1)
            indices[i], indices[j] = indices[j], indices[i]

        return indices[:num_needed]

    selected = []
    used = set()

    nonce = b'\x00' * 16
    cipher = Cipher(algorithms.ChaCha20(key, nonce), mode=None, backend=default_backend())
    encryptor = cipher.encryptor()

    bytes_needed = (num_needed * 2) * 4
    random_bytes = encryptor.update(b'\x00' * bytes_needed)

    byte_offset = 0
    while len(selected) < num_needed and byte_offset < len(random_bytes) - 4:
        idx = int.from_bytes(random_bytes[byte_offset:byte_offset + 4], 'big') % num_pixels
        byte_offset += 4

        if idx not in used:
            used.add(idx)
            selected.append(idx)

    while len(selected) < num_needed:
        extra_bytes = encryptor.update(b'\x00' * 4)
        idx = int.from_bytes(extra_bytes, 'big') % num_pixels
        if idx not in used:
            used.add(idx)
            selected.append(idx)

    return selected


def embed_in_image(carrier_data, encrypted_data, pixel_key, bits_per_channel=1):
    """Embed encrypted data in carrier image. Returns PNG bytes."""
    img = Image.open(io.BytesIO(carrier_data))
    if img.mode != 'RGB':
        img = img.convert('RGB')

    pixels = list(img.getdata())
    num_pixels = len(pixels)

    bits_per_pixel = 3 * bits_per_channel
    max_bytes = (num_pixels * bits_per_pixel) // 8

    data_with_len = struct.pack('>I', len(encrypted_data)) + encrypted_data

    if len(data_with_len) > max_bytes:
        raise ValueError(f"Carrier too small. Need {len(data_with_len)} bytes, have {max_bytes}")

    binary_data = ''.join(format(b, '08b') for b in data_with_len)
    pixels_needed = (len(binary_data) + bits_per_pixel - 1) // bits_per_pixel

    selected_indices = generate_pixel_indices(pixel_key, num_pixels, pixels_needed)

    new_pixels = list(pixels)
    clear_mask = 0xFF ^ ((1 << bits_per_channel) - 1)

    bit_idx = 0
    for pixel_idx in selected_indices:
        if bit_idx >= len(binary_data):
            break

        r, g, b = new_pixels[pixel_idx]

        for channel_idx, channel_val in enumerate([r, g, b]):
            if bit_idx >= len(binary_data):
                break
            bits = binary_data[bit_idx:bit_idx + bits_per_channel].ljust(bits_per_channel, '0')
            new_val = (channel_val & clear_mask) | int(bits, 2)

            if channel_idx == 0:
                r = new_val
            elif channel_idx == 1:
                g = new_val
            else:
                b = new_val

            bit_idx += bits_per_channel

        new_pixels[pixel_idx] = (r, g, b)

    stego_img = Image.new('RGB', img.size)
    stego_img.putdata(new_pixels)

    output = io.BytesIO()
    stego_img.save(output, 'PNG')
    output.seek(0)

    return output.getvalue(), {
        'pixels_modified': len(selected_indices),
        'total_pixels': num_pixels,
        'capacity_used': len(data_with_len) / max_bytes
    }


def extract_from_image(image_data, pixel_key, bits_per_channel=1):
    """Extract hidden data from image."""
    img = Image.open(io.BytesIO(image_data))
    if img.mode != 'RGB':
        img = img.convert('RGB')

    pixels = list(img.getdata())
    num_pixels = len(pixels)
    bits_per_pixel = 3 * bits_per_channel

    initial_pixels = (32 + bits_per_pixel - 1) // bits_per_pixel + 10
    initial_indices = generate_pixel_indices(pixel_key, num_pixels, initial_pixels)

    binary_data = ''
    for pixel_idx in initial_indices:
        r, g, b = pixels[pixel_idx]
        for channel in [r, g, b]:
            for bit_pos in range(bits_per_channel - 1, -1, -1):
                binary_data += str((channel >> bit_pos) & 1)

    try:
        length_bits = binary_data[:32]
        data_length = struct.unpack('>I', int(length_bits, 2).to_bytes(4, 'big'))[0]
    except:
        return None

    max_possible = (num_pixels * bits_per_pixel) // 8 - 4
    if data_length > max_possible or data_length < 10:
        return None

    total_bits = (4 + data_length) * 8
    pixels_needed = (total_bits + bits_per_pixel - 1) // bits_per_pixel

    selected_indices = generate_pixel_indices(pixel_key, num_pixels, pixels_needed)

    binary_data = ''
    for pixel_idx in selected_indices:
        r, g, b = pixels[pixel_idx]
        for channel in [r, g, b]:
            for bit_pos in range(bits_per_channel - 1, -1, -1):
                binary_data += str((channel >> bit_pos) & 1)

    data_bits = binary_data[32:32 + (data_length * 8)]

    data_bytes = bytearray()
    for i in range(0, len(data_bits), 8):
        byte_bits = data_bits[i:i+8]
        if len(byte_bits) == 8:
            data_bytes.append(int(byte_bits, 2))

    return bytes(data_bytes)


def parse_header(encrypted_data):
    """Parse v3 header."""
    if len(encrypted_data) < 10 or encrypted_data[:4] != MAGIC_HEADER:
        return None

    date_len = encrypted_data[5]
    date_str = encrypted_data[6:6+date_len].decode()

    offset = 6 + date_len
    salt = encrypted_data[offset:offset+SALT_SIZE]
    offset += SALT_SIZE
    iv = encrypted_data[offset:offset+IV_SIZE]
    offset += IV_SIZE
    tag = encrypted_data[offset:offset+TAG_SIZE]
    offset += TAG_SIZE
    ciphertext = encrypted_data[offset:]

    return {'date': date_str, 'salt': salt, 'iv': iv, 'tag': tag, 'ciphertext': ciphertext}


def decrypt_message(encrypted_data, photo_data, day_phrase, pin="", rsa_key_data=None):
    """Decrypt message."""
    header = parse_header(encrypted_data)
    if not header:
        return None

    key = derive_hybrid_key(photo_data, day_phrase, header['date'], header['salt'], pin, rsa_key_data)

    cipher = Cipher(
        algorithms.AES(key),
        modes.GCM(header['iv'], header['tag']),
        backend=default_backend()
    )
    decryptor = cipher.decryptor()
    decryptor.authenticate_additional_data(MAGIC_HEADER + bytes([VERSION]))

    try:
        padded_plaintext = decryptor.update(header['ciphertext']) + decryptor.finalize()
        original_length = struct.unpack('>I', padded_plaintext[-4:])[0]
        return padded_plaintext[:original_length].decode('utf-8')
    except:
        return None


# ============================================================================
# FLASK ROUTES
# ============================================================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/generate', methods=['GET', 'POST'])
def generate():
    if request.method == 'POST':
        words_per_phrase = int(request.form.get('words_per_phrase', 3))
        
        # Security factor options
        use_pin = request.form.get('use_pin') == 'on'
        use_rsa = request.form.get('use_rsa') == 'on'
        
        # Validate at least one factor selected
        if not use_pin and not use_rsa:
            flash('You must select at least one security factor (PIN or RSA Key)', 'error')
            return render_template('generate.html', generated=False, has_ml=HAS_ML)
        
        pin_length = int(request.form.get('pin_length', 6))
        rsa_bits = int(request.form.get('rsa_bits', 2048))
        
        # Clamp values to valid ranges
        words_per_phrase = max(3, min(12, words_per_phrase))
        pin_length = max(MIN_PIN_LENGTH, min(MAX_PIN_LENGTH, pin_length))
        if rsa_bits not in VALID_RSA_SIZES:
            rsa_bits = 2048

        phrases = generate_day_phrases(words_per_phrase)
        
        # Generate PIN if selected
        pin = generate_pin(pin_length) if use_pin else None
        
        # Generate RSA key if selected
        rsa_key_pem = None
        if use_rsa:
            private_key = generate_rsa_key(rsa_bits)
            rsa_key_pem = export_rsa_key_pem(private_key, password=None).decode('utf-8')

        # Calculate entropy
        phrase_entropy = words_per_phrase * 11
        pin_entropy = int(pin_length * 3.32) if use_pin else 0
        # RSA key adds significant entropy (conservatively estimate effective security)
        rsa_entropy = min(rsa_bits // 16, 128) if use_rsa else 0  # ~128 bits effective for 2048-bit
        total_entropy = phrase_entropy + pin_entropy + rsa_entropy

        return render_template('generate.html',
                             phrases=phrases,
                             pin=pin,
                             days=DAY_NAMES,
                             generated=True,
                             words_per_phrase=words_per_phrase,
                             pin_length=pin_length if use_pin else None,
                             use_pin=use_pin,
                             use_rsa=use_rsa,
                             rsa_bits=rsa_bits,
                             rsa_key_pem=rsa_key_pem,
                             phrase_entropy=phrase_entropy,
                             pin_entropy=pin_entropy,
                             rsa_entropy=rsa_entropy,
                             total_entropy=total_entropy,
                             has_ml=HAS_ML)
    
    return render_template('generate.html', generated=False, has_ml=HAS_ML)


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
        # Load the unencrypted key
        private_key = load_pem_private_key(key_pem.encode(), password=None, backend=default_backend())
        
        # Re-export with password protection
        encrypted_pem = export_rsa_key_pem(private_key, password=password)
        
        # Generate filename
        key_id = secrets.token_hex(4)
        filename = f'stegasoo_key_{private_key.key_size}_{key_id}.pem'
        
        return send_file(
            io.BytesIO(encrypted_pem),
            mimetype='application/x-pem-file',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        flash(f'Error creating key file: {str(e)}', 'error')
        return redirect(url_for('generate'))


@app.route('/encode', methods=['GET', 'POST'])
def encode():
    day_of_week = datetime.now().strftime("%A")

    if request.method == 'POST':
        try:
            # Get files
            ref_photo = request.files.get('reference_photo')
            carrier = request.files.get('carrier')
            rsa_key_file = request.files.get('rsa_key')

            if not ref_photo or not carrier:
                flash('Both reference photo and carrier image are required', 'error')
                return render_template('encode.html', day_of_week=day_of_week)

            if not allowed_file(ref_photo.filename) or not allowed_file(carrier.filename):
                flash('Invalid file type. Use PNG, JPG, or BMP', 'error')
                return render_template('encode.html', day_of_week=day_of_week)

            # Get form data
            message = request.form.get('message', '')
            day_phrase = request.form.get('day_phrase', '')
            pin = request.form.get('pin', '').strip()
            rsa_password = request.form.get('rsa_password', '')

            # Validate message
            valid, error = validate_message(message)
            if not valid:
                flash(error, 'error')
                return render_template('encode.html', day_of_week=day_of_week)

            if not day_phrase:
                flash('Day phrase is required', 'error')
                return render_template('encode.html', day_of_week=day_of_week)

            # Read files
            ref_data = ref_photo.read()
            carrier_data = carrier.read()
            rsa_key_data = rsa_key_file.read() if rsa_key_file and rsa_key_file.filename else None

            # Validate security factors
            valid, error = validate_security_factors(pin, rsa_key_data)
            if not valid:
                flash(error, 'error')
                return render_template('encode.html', day_of_week=day_of_week)

            # Validate PIN if provided
            if pin:
                valid, error = validate_pin(pin)
                if not valid:
                    flash(error, 'error')
                    return render_template('encode.html', day_of_week=day_of_week)

            # Validate RSA key if provided
            if rsa_key_data:
                valid, error, key_size = validate_rsa_key(rsa_key_data, rsa_password if rsa_password else None)
                if not valid:
                    flash(error, 'error')
                    return render_template('encode.html', day_of_week=day_of_week)

            # Validate carrier image
            valid, error = validate_image(carrier_data, "Carrier image")
            if not valid:
                flash(error, 'error')
                return render_template('encode.html', day_of_week=day_of_week)

            # Get date - use client's local date if provided
            client_date = request.form.get('client_date', '').strip()
            if client_date and len(client_date) == 10 and client_date[4] == '-' and client_date[7] == '-':
                date_str = client_date
            else:
                date_str = datetime.now().strftime('%Y-%m-%d')

            # Encrypt
            encrypted = encrypt_message(message, ref_data, day_phrase, date_str, pin, rsa_key_data)

            # Get pixel key
            pixel_key = derive_pixel_key(ref_data, day_phrase, date_str, pin, rsa_key_data)

            # Embed
            stego_data, stats = embed_in_image(carrier_data, encrypted, pixel_key)

            # Generate filename and file ID
            filename = f'{secrets.token_hex(4)}_{date_str.replace("-", "")}.png'
            file_id = secrets.token_urlsafe(16)

            # Store temporarily for download/share
            cleanup_temp_files()
            TEMP_FILES[file_id] = {
                'data': stego_data,
                'filename': filename,
                'timestamp': time.time()
            }

            return redirect(url_for('encode_result', file_id=file_id))

        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            return render_template('encode.html', day_of_week=day_of_week)

    return render_template('encode.html', day_of_week=day_of_week)


@app.route('/encode/result/<file_id>')
def encode_result(file_id):
    if file_id not in TEMP_FILES:
        flash('File expired or not found. Please encode again.', 'error')
        return redirect(url_for('encode'))

    file_info = TEMP_FILES[file_id]
    return render_template('encode_result.html',
                         file_id=file_id,
                         filename=file_info['filename'])


@app.route('/encode/download/<file_id>')
def encode_download(file_id):
    if file_id not in TEMP_FILES:
        flash('File expired or not found.', 'error')
        return redirect(url_for('encode'))

    file_info = TEMP_FILES[file_id]

    return send_file(
        io.BytesIO(file_info['data']),
        mimetype='image/png',
        as_attachment=True,
        download_name=file_info['filename']
    )


@app.route('/encode/file/<file_id>')
def encode_file(file_id):
    """Serve file for Web Share API (inline, not attachment)."""
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
def decode():
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
            valid, error = validate_security_factors(pin, rsa_key_data)
            if not valid:
                flash(error, 'error')
                return render_template('decode.html')

            # Validate PIN if provided
            if pin:
                valid, error = validate_pin(pin)
                if not valid:
                    flash(error, 'error')
                    return render_template('decode.html')

            # Validate RSA key if provided
            if rsa_key_data:
                valid, error, key_size = validate_rsa_key(rsa_key_data, rsa_password if rsa_password else None)
                if not valid:
                    flash(error, 'error')
                    return render_template('decode.html')

            # Try to extract and decrypt
            date_str = datetime.now().strftime('%Y-%m-%d')
            pixel_key = derive_pixel_key(ref_data, day_phrase, date_str, pin, rsa_key_data)

            encrypted = extract_from_image(stego_data, pixel_key)

            if encrypted:
                header = parse_header(encrypted)
                if header and header['date'] != date_str:
                    pixel_key = derive_pixel_key(ref_data, day_phrase, header['date'], pin, rsa_key_data)
                    encrypted = extract_from_image(stego_data, pixel_key)

            if not encrypted:
                flash('Could not extract data. Check your inputs.', 'error')
                return render_template('decode.html')

            message = decrypt_message(encrypted, ref_data, day_phrase, pin, rsa_key_data)

            if message:
                return render_template('decode.html', decoded_message=message)
            else:
                flash('Decryption failed. Wrong phrase, PIN, RSA key, or reference photo.', 'error')
                return render_template('decode.html')

        except Exception as e:
            flash(f'Error: {str(e)}', 'error')
            return render_template('decode.html')

    return render_template('decode.html')


@app.route('/about')
def about():
    return render_template('about.html', has_argon2=HAS_ARGON2)


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
