#!/usr/bin/env python3
"""
Stegasoo Web Frontend (v4.0.0)

Flask-based web UI for steganography operations.
Supports both text messages and file embedding.

CHANGES in v4.0.0:
- Added channel key support for deployment/group isolation
- New /api/channel/status endpoint
- Channel key selector on encode/decode pages
- Messages encoded with channel key require same key to decode

CHANGES in v3.2.0:
- Removed date dependency from all operations
- Renamed day_phrase → passphrase
- No date selection or tracking needed
- Simplified user experience for asynchronous communications

NEW in v3.0: LSB and DCT embedding modes with advanced options.
NEW in v3.0.1: DCT output format selection (PNG or JPEG) and color mode (grayscale or color).
"""

import io
import mimetypes
import os
import secrets
import sys
import time
from pathlib import Path

from auth import (
    MAX_CHANNEL_KEYS,
    MAX_USERS,
    admin_required,
    can_create_user,
    can_save_channel_key,
    change_password,
    create_admin_user,
    create_user,
    delete_channel_key,
    delete_user,
    generate_temp_password,
    get_all_users,
    get_channel_key_by_id,
    get_current_user,
    get_non_admin_count,
    get_user_by_id,
    get_user_channel_keys,
    get_username,
    has_recovery_key,
    get_recovery_key_hash,
    clear_recovery_key,
    is_admin,
    is_authenticated,
    login_required,
    login_user,
    logout_user,
    reset_user_password,
    save_channel_key,
    set_recovery_key_hash,
    verify_and_reset_admin_password,
    update_channel_key_last_used,
    update_channel_key_name,
    user_exists,
    verify_user_password,
)
from auth import (
    init_app as init_auth,
)
from flask import (
    Flask,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from PIL import Image
from ssl_utils import ensure_certs

os.environ["NUMPY_MADVISE_HUGEPAGE"] = "0"
os.environ["OMP_NUM_THREADS"] = "1"

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

import stegasoo
from stegasoo import (
    CapacityError,
    DecryptionError,
    FilePayload,
    StegasooError,
    export_rsa_key_pem,
    generate_credentials,
    generate_filename,
    get_channel_status,
    has_argon2,
    # Channel key functions (v4.0.0)
    has_dct_support,
    load_rsa_key,
    validate_channel_key,
    validate_file_payload,
    validate_image,
    validate_message,
    validate_passphrase,
    validate_pin,
    validate_rsa_key,
    validate_security_factors,
)
from stegasoo.constants import (
    DEFAULT_PASSPHRASE_WORDS,
    MAX_FILE_PAYLOAD_SIZE,
    MAX_FILE_SIZE,
    MAX_MESSAGE_CHARS,
    MAX_PIN_LENGTH,
    MAX_UPLOAD_SIZE,
    MIN_PASSPHRASE_WORDS,
    MIN_PIN_LENGTH,
    RECOMMENDED_PASSPHRASE_WORDS,
    TEMP_FILE_EXPIRY,
    TEMP_FILE_EXPIRY_MINUTES,
    THUMBNAIL_QUALITY,
    THUMBNAIL_SIZE,
    VALID_RSA_SIZES,
    __version__,
)

# QR Code support
try:
    import qrcode  # noqa: F401
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M  # noqa: F401

    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False

# QR Code reading
try:
    from pyzbar.pyzbar import decode as pyzbar_decode  # noqa: F401

    HAS_QRCODE_READ = True
except ImportError:
    HAS_QRCODE_READ = False


# Import QR utilities
# ============================================================================
# SUBPROCESS ISOLATION FOR STEGASOO OPERATIONS
# ============================================================================
# Runs encode/decode/compare in subprocesses to prevent jpegio/scipy crashes
# from taking down the Flask server.
from subprocess_stego import SubprocessStego

from stegasoo.qr_utils import (
    can_fit_in_qr,
    detect_and_crop_qr,
    extract_key_from_qr,
    generate_qr_code,
)

# Initialize subprocess wrapper (worker script must be in same directory)
subprocess_stego = SubprocessStego(timeout=180)  # 3 minute timeout for large images


# ============================================================================
# FLASK APP CONFIGURATION
# ============================================================================

app = Flask(__name__)

# Persist secret key so sessions survive restarts
_instance_path = Path(app.instance_path)
_instance_path.mkdir(parents=True, exist_ok=True)
_secret_key_file = _instance_path / ".secret_key"
if _secret_key_file.exists():
    app.secret_key = _secret_key_file.read_text().strip()
else:
    app.secret_key = secrets.token_hex(32)
    _secret_key_file.write_text(app.secret_key)
    _secret_key_file.chmod(0o600)

app.config["MAX_CONTENT_LENGTH"] = MAX_FILE_SIZE

# Auth configuration from environment
app.config["AUTH_ENABLED"] = os.environ.get("STEGASOO_AUTH_ENABLED", "true").lower() == "true"
app.config["HTTPS_ENABLED"] = os.environ.get("STEGASOO_HTTPS_ENABLED", "false").lower() == "true"

# Initialize auth module
init_auth(app)

# Temporary file storage for sharing (file_id -> {data, timestamp, filename})
TEMP_FILES: dict[str, dict] = {}
THUMBNAIL_FILES: dict[str, bytes] = {}


# ============================================================================
# TEMPLATE CONTEXT PROCESSOR
# ============================================================================


@app.context_processor
def inject_globals():
    """Inject global variables into all templates."""
    # Get channel status (v4.0.0)
    channel_status = get_channel_status()

    # Get saved channel keys for authenticated users (v4.2.0)
    saved_channel_keys = []
    if is_authenticated():
        current_user = get_current_user()
        if current_user:
            saved_channel_keys = get_user_channel_keys(current_user.id)

    return {
        "version": __version__,
        "max_message_chars": MAX_MESSAGE_CHARS,
        "max_payload_kb": MAX_FILE_PAYLOAD_SIZE // 1024,
        "max_upload_mb": MAX_UPLOAD_SIZE // (1024 * 1024),
        "temp_file_expiry_minutes": TEMP_FILE_EXPIRY_MINUTES,
        "min_pin_length": MIN_PIN_LENGTH,
        "max_pin_length": MAX_PIN_LENGTH,
        # NEW in v3.2.0
        "min_passphrase_words": MIN_PASSPHRASE_WORDS,
        "recommended_passphrase_words": RECOMMENDED_PASSPHRASE_WORDS,
        "default_passphrase_words": DEFAULT_PASSPHRASE_WORDS,
        # NEW in v3.0
        "has_dct": has_dct_support(),
        # NEW in v4.0.0 - Channel key status
        "channel_mode": channel_status["mode"],
        "channel_configured": channel_status["configured"],
        "channel_fingerprint": channel_status.get("fingerprint"),
        "channel_source": channel_status.get("source"),
        # NEW in v4.0.2 - Auth state
        "auth_enabled": app.config.get("AUTH_ENABLED", True),
        "is_authenticated": is_authenticated(),
        "username": get_username() if is_authenticated() else None,
        # NEW in v4.1.0 - Admin state
        "is_admin": is_admin(),
        # NEW in v4.2.0 - Saved channel keys
        "saved_channel_keys": saved_channel_keys,
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

    # Channel key status (v4.0.0)
    channel_status = get_channel_status()
    print(f"Channel key: {channel_status['mode']} mode")
    if channel_status["configured"]:
        print(f"  Fingerprint: {channel_status.get('fingerprint')}")
        print(f"  Source: {channel_status.get('source')}")

    DESIRED_PAYLOAD_SIZE = 2 * 1024 * 1024  # 2MB

    if hasattr(stegasoo, "MAX_FILE_PAYLOAD_SIZE"):
        print(f"Overriding MAX_FILE_PAYLOAD_SIZE to {DESIRED_PAYLOAD_SIZE}")
        stegasoo.MAX_FILE_PAYLOAD_SIZE = DESIRED_PAYLOAD_SIZE

except Exception as e:
    print(f"Could not override stegasoo limits: {e}")


# ============================================================================
# CHANNEL KEY HELPER (v4.0.0)
# ============================================================================


def resolve_channel_key_form(channel_key_value: str) -> str:
    """
    Resolve channel key from form input.

    Wrapper around library's resolve_channel_key for subprocess compatibility.
    Returns string values for subprocess_stego ('auto', 'none', or explicit key).
    """
    from stegasoo.channel import resolve_channel_key

    try:
        result = resolve_channel_key(channel_key_value)
        if result is None:
            return "auto"
        elif result == "":
            return "none"
        else:
            return result
    except (ValueError, FileNotFoundError):
        # Invalid format, fall back to auto
        return "auto"


def generate_thumbnail(image_data: bytes, size: tuple = THUMBNAIL_SIZE) -> bytes:
    """Generate thumbnail from image data."""
    try:
        with Image.open(io.BytesIO(image_data)) as img:
            # Convert to RGB if necessary (handle grayscale too)
            if img.mode in ("RGBA", "LA", "P"):
                # Create white background for transparent images
                background = Image.new("RGB", img.size, (255, 255, 255))
                if img.mode == "P":
                    img = img.convert("RGBA")
                background.paste(img, mask=img.split()[-1] if img.mode == "RGBA" else None)
                img = background
            elif img.mode == "L":
                # Convert grayscale to RGB for thumbnail
                img = img.convert("RGB")
            elif img.mode != "RGB":
                img = img.convert("RGB")

            # Create thumbnail
            img.thumbnail(size, Image.Resampling.LANCZOS)

            # Save to bytes
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=THUMBNAIL_QUALITY, optimize=True)
            return buffer.getvalue()
    except Exception as e:
        print(f"Thumbnail generation error: {e}")
        return None


def cleanup_temp_files():
    """Remove expired temporary files."""
    now = time.time()
    expired = [
        fid for fid, info in TEMP_FILES.items() if now - info["timestamp"] > TEMP_FILE_EXPIRY
    ]

    for fid in expired:
        TEMP_FILES.pop(fid, None)
        # Also clean up corresponding thumbnail
        thumb_id = f"{fid}_thumb"
        THUMBNAIL_FILES.pop(thumb_id, None)


def allowed_image(filename: str) -> bool:
    """Check if file has allowed image extension."""
    if not filename or "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in {"png", "jpg", "jpeg", "bmp", "gif"}


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


@app.route("/")
def index():
    return render_template("index.html")


# ============================================================================
# CHANNEL KEY API (v4.0.0)
# ============================================================================


@app.route("/api/channel/status")
@login_required
def api_channel_status():
    """
    Get current channel key status (v4.0.0).

    Returns JSON with mode, fingerprint, and source.
    """
    # Use subprocess for isolation
    result = subprocess_stego.get_channel_status(reveal=False)

    if result.success:
        return jsonify(
            {
                "success": True,
                "mode": result.mode,
                "configured": result.configured,
                "fingerprint": result.fingerprint,
                "source": result.source,
            }
        )
    else:
        # Fallback to direct call if subprocess fails
        status = get_channel_status()
        return jsonify(
            {
                "success": True,
                "mode": status["mode"],
                "configured": status["configured"],
                "fingerprint": status.get("fingerprint"),
                "source": status.get("source"),
            }
        )


@app.route("/api/channel/validate", methods=["POST"])
@login_required
def api_channel_validate():
    """
    Validate a channel key format (v4.0.0).

    Returns JSON with validation result.
    """
    key = request.form.get("key", "") or (request.json.get("key", "") if request.is_json else "")

    if not key:
        return jsonify({"valid": False, "error": "No key provided"})

    is_valid = validate_channel_key(key)

    if is_valid:
        fingerprint = f"{key[:4]}-••••-••••-••••-••••-••••-••••-{key[-4:]}"
        return jsonify(
            {
                "valid": True,
                "fingerprint": fingerprint,
            }
        )
    else:
        return jsonify(
            {
                "valid": False,
                "error": "Invalid format. Expected: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX",
            }
        )


# ============================================================================
# GENERATE
# ============================================================================


@app.route("/generate", methods=["GET", "POST"])
@login_required
def generate():
    if request.method == "POST":
        # v3.2.0: Changed from words_per_phrase to words_per_passphrase, default increased to 4
        words_per_passphrase = int(
            request.form.get("words_per_passphrase", DEFAULT_PASSPHRASE_WORDS)
        )
        use_pin = request.form.get("use_pin") == "on"
        use_rsa = request.form.get("use_rsa") == "on"

        if not use_pin and not use_rsa:
            flash("You must select at least one security factor (PIN or RSA Key)", "error")
            return render_template("generate.html", generated=False, has_qrcode=HAS_QRCODE)

        pin_length = int(request.form.get("pin_length", 6))
        rsa_bits = int(request.form.get("rsa_bits", 2048))

        # Clamp values
        words_per_passphrase = max(MIN_PASSPHRASE_WORDS, min(12, words_per_passphrase))
        pin_length = max(MIN_PIN_LENGTH, min(MAX_PIN_LENGTH, pin_length))
        if rsa_bits not in VALID_RSA_SIZES:
            rsa_bits = 2048

        try:
            # v3.2.0 FIX: Use correct parameter name 'passphrase_words'
            creds = generate_credentials(
                use_pin=use_pin,
                use_rsa=use_rsa,
                pin_length=pin_length,
                rsa_bits=rsa_bits,
                passphrase_words=words_per_passphrase,  # FIX: was words_per_passphrase=
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
                        "data": creds.rsa_key_pem.encode(),
                        "filename": "rsa_key.pem",
                        "timestamp": time.time(),
                        "type": "rsa_key",
                        "compress": qr_needs_compression,
                    }

            # v3.2.0: Single passphrase instead of daily phrases
            return render_template(
                "generate.html",
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
                qr_too_large=qr_too_large,
            )
        except Exception as e:
            flash(f"Error generating credentials: {e}", "error")
            return render_template("generate.html", generated=False, has_qrcode=HAS_QRCODE)

    return render_template("generate.html", generated=False, has_qrcode=HAS_QRCODE)


@app.route("/generate/qr/<token>")
@login_required
def generate_qr(token):
    """Generate QR code for RSA key."""
    if not HAS_QRCODE:
        return "QR code support not available", 501

    if token not in TEMP_FILES:
        return "Token expired or invalid", 404

    file_info = TEMP_FILES[token]
    if file_info.get("type") != "rsa_key":
        return "Invalid token type", 400

    try:
        key_pem = file_info["data"].decode("utf-8")
        compress = file_info.get("compress", False)
        qr_png = generate_qr_code(key_pem, compress=compress)

        return send_file(io.BytesIO(qr_png), mimetype="image/png", as_attachment=False)
    except Exception as e:
        return f"Error generating QR code: {e}", 500


@app.route("/generate/qr-download/<token>")
@login_required
def generate_qr_download(token):
    """Download QR code as PNG file."""
    if not HAS_QRCODE:
        return "QR code support not available", 501

    if token not in TEMP_FILES:
        return "Token expired or invalid", 404

    file_info = TEMP_FILES[token]
    if file_info.get("type") != "rsa_key":
        return "Invalid token type", 400

    try:
        key_pem = file_info["data"].decode("utf-8")
        compress = file_info.get("compress", False)
        qr_png = generate_qr_code(key_pem, compress=compress)

        return send_file(
            io.BytesIO(qr_png),
            mimetype="image/png",
            as_attachment=True,
            download_name="stegasoo_rsa_key_qr.png",
        )
    except Exception as e:
        return f"Error generating QR code: {e}", 500


@app.route("/qr/crop", methods=["POST"])
@login_required
def qr_crop():
    """
    Detect and crop QR code from an image.

    Useful for extracting QR codes from photos taken at an angle,
    with extra background, etc. Returns the cropped QR as PNG.
    """
    if not HAS_QRCODE_READ:
        return jsonify({"error": "QR code reading not available (install pyzbar)"}), 501

    image_file = request.files.get("image")
    if not image_file:
        return jsonify({"error": "No image provided"}), 400

    try:
        image_data = image_file.read()

        # Use the new crop function
        cropped = detect_and_crop_qr(image_data)

        if cropped is None:
            return jsonify({"error": "No QR code detected in image"}), 404

        # Return as downloadable PNG or inline based on query param
        as_attachment = request.args.get("download", "").lower() in ("1", "true", "yes")

        return send_file(
            io.BytesIO(cropped),
            mimetype="image/png",
            as_attachment=as_attachment,
            download_name="cropped_qr.png",
        )
    except Exception as e:
        return jsonify({"error": f"Error processing image: {e}"}), 500


@app.route("/generate/download-key", methods=["POST"])
@login_required
def download_key():
    """Download RSA key as password-protected PEM file."""
    key_pem = request.form.get("key_pem", "")
    password = request.form.get("key_password", "")

    if not key_pem:
        flash("No key to download", "error")
        return redirect(url_for("generate"))

    if not password or len(password) < 8:
        flash("Password must be at least 8 characters", "error")
        return redirect(url_for("generate"))

    try:
        private_key = load_rsa_key(key_pem.encode("utf-8"))
        encrypted_pem = export_rsa_key_pem(private_key, password=password)

        key_id = secrets.token_hex(4)
        filename = f"stegasoo_key_{private_key.key_size}_{key_id}.pem"

        return send_file(
            io.BytesIO(encrypted_pem),
            mimetype="application/x-pem-file",
            as_attachment=True,
            download_name=filename,
        )
    except Exception as e:
        flash(f"Error creating key file: {e}", "error")
        return redirect(url_for("generate"))


@app.route("/extract-key-from-qr", methods=["POST"])
@login_required
def extract_key_from_qr_route():
    """
    Extract RSA key from uploaded QR code image.
    Returns JSON with the extracted key or error.
    """
    if not HAS_QRCODE_READ:
        return (
            jsonify(
                {
                    "success": False,
                    "error": "QR code reading not available. Install pyzbar and libzbar.",
                }
            ),
            501,
        )

    qr_image = request.files.get("qr_image")
    if not qr_image:
        return jsonify({"success": False, "error": "No QR image provided"}), 400

    try:
        image_data = qr_image.read()
        key_pem = extract_key_from_qr(image_data)

        if key_pem:
            return jsonify({"success": True, "key_pem": key_pem})
        else:
            return jsonify({"success": False, "error": "No valid RSA key found in QR code"}), 400

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================================================================
# NEW in v3.0 - CAPACITY COMPARISON API
# ============================================================================


@app.route("/api/compare-capacity", methods=["POST"])
@login_required
def api_compare_capacity():
    """
    Compare LSB and DCT capacity for an uploaded carrier image.
    Returns JSON with capacity info for both modes.
    Uses subprocess isolation to prevent crashes.
    """
    carrier = request.files.get("carrier")
    if not carrier:
        return jsonify({"error": "No carrier image provided"}), 400

    try:
        carrier_data = carrier.read()

        # Use subprocess-isolated compare_modes
        result = subprocess_stego.compare_modes(carrier_data)

        if not result.success:
            return jsonify({"error": result.error or "Comparison failed"}), 500

        return jsonify(
            {
                "success": True,
                "width": result.width,
                "height": result.height,
                "lsb": {
                    "capacity_bytes": result.lsb["capacity_bytes"],
                    "capacity_kb": round(result.lsb["capacity_kb"], 1),
                    "output": result.lsb.get("output", "PNG"),
                },
                "dct": {
                    "capacity_bytes": result.dct["capacity_bytes"],
                    "capacity_kb": round(result.dct["capacity_kb"], 1),
                    "output": result.dct.get("output", "JPEG"),
                    "available": result.dct.get("available", True),
                    "ratio": round(result.dct.get("ratio_vs_lsb", 0), 1),
                },
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/check-fit", methods=["POST"])
@login_required
def api_check_fit():
    """
    Check if a payload will fit in the carrier with selected mode.
    Returns JSON with fit status and details.
    Uses subprocess isolation to prevent crashes.
    """
    carrier = request.files.get("carrier")
    payload_size = request.form.get("payload_size", type=int)
    embed_mode = request.form.get("embed_mode", "lsb")

    if not carrier or payload_size is None:
        return jsonify({"error": "Missing carrier or payload_size"}), 400

    if embed_mode not in ("lsb", "dct"):
        return jsonify({"error": "Invalid embed_mode"}), 400

    if embed_mode == "dct" and not has_dct_support():
        return jsonify({"error": "DCT mode requires scipy"}), 400

    try:
        carrier_data = carrier.read()

        # Use subprocess-isolated capacity check
        result = subprocess_stego.check_capacity(
            carrier_data=carrier_data,
            payload_size=payload_size,
            embed_mode=embed_mode,
        )

        if not result.success:
            return jsonify({"error": result.error or "Capacity check failed"}), 500

        return jsonify(
            {
                "success": True,
                "fits": result.fits,
                "payload_size": result.payload_size,
                "capacity": result.capacity,
                "usage_percent": round(result.usage_percent, 1),
                "headroom": result.headroom,
                "mode": result.mode,
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# ENCODE
# ============================================================================


@app.route("/encode", methods=["GET", "POST"])
@login_required
def encode_page():
    if request.method == "POST":
        try:
            # Get files
            ref_photo = request.files.get("reference_photo")
            carrier = request.files.get("carrier")
            rsa_key_file = request.files.get("rsa_key")
            payload_file = request.files.get("payload_file")

            if not ref_photo or not carrier:
                flash("Both reference photo and carrier image are required", "error")
                return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            if not allowed_image(ref_photo.filename) or not allowed_image(carrier.filename):
                flash("Invalid file type. Use PNG, JPG, or BMP", "error")
                return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Get form data - v3.2.0: renamed from day_phrase to passphrase
            message = request.form.get("message", "")
            passphrase = request.form.get("passphrase", "")  # v3.2.0: Renamed
            pin = request.form.get("pin", "").strip()
            rsa_password = request.form.get("rsa_password", "")
            payload_type = request.form.get("payload_type", "text")

            # NEW in v3.0 - Embedding mode
            embed_mode = request.form.get("embed_mode", "lsb")
            if embed_mode not in ("lsb", "dct"):
                embed_mode = "lsb"

            # NEW in v3.0.1 - DCT output format
            dct_output_format = request.form.get("dct_output_format", "png")
            if dct_output_format not in ("png", "jpeg"):
                dct_output_format = "png"

            # NEW in v3.0.1 - DCT color mode
            dct_color_mode = request.form.get("dct_color_mode", "color")
            if dct_color_mode not in ("grayscale", "color"):
                dct_color_mode = "color"

            # NEW in v4.0.0 - Channel key
            channel_key = resolve_channel_key_form(request.form.get("channel_key", "auto"))

            # Check DCT availability
            if embed_mode == "dct" and not has_dct_support():
                flash("DCT mode requires scipy. Install with: pip install scipy", "error")
                return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Determine payload
            if payload_type == "file" and payload_file and payload_file.filename:
                # File payload
                file_data = payload_file.read()

                result = validate_file_payload(file_data, payload_file.filename)
                if not result.is_valid:
                    flash(result.error_message, "error")
                    return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

                mime_type, _ = mimetypes.guess_type(payload_file.filename)
                payload = FilePayload(
                    data=file_data, filename=payload_file.filename, mime_type=mime_type
                )
            else:
                # Text message
                result = validate_message(message)
                if not result.is_valid:
                    flash(result.error_message, "error")
                    return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)
                payload = message

            # v3.2.0: Renamed from day_phrase
            if not passphrase:
                flash("Passphrase is required", "error")
                return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            # v3.2.0: Validate passphrase
            result = validate_passphrase(passphrase)
            if not result.is_valid:
                flash(result.error_message, "error")
                return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Show warning if passphrase is short
            if result.warning:
                flash(result.warning, "warning")

            # Read files
            ref_data = ref_photo.read()
            carrier_data = carrier.read()

            # Handle RSA key - can come from .pem file or QR code image
            rsa_key_data = None
            rsa_key_qr = request.files.get("rsa_key_qr")
            rsa_key_from_qr = False

            if rsa_key_file and rsa_key_file.filename:
                rsa_key_data = rsa_key_file.read()
            elif rsa_key_qr and rsa_key_qr.filename and HAS_QRCODE_READ:
                qr_image_data = rsa_key_qr.read()
                key_pem = extract_key_from_qr(qr_image_data)
                if key_pem:
                    rsa_key_data = key_pem.encode("utf-8")
                    rsa_key_from_qr = True
                else:
                    flash("Could not extract RSA key from QR code image.", "error")
                    return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Validate security factors
            result = validate_security_factors(pin, rsa_key_data)
            if not result.is_valid:
                flash(result.error_message, "error")
                return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Validate PIN if provided
            if pin:
                result = validate_pin(pin)
                if not result.is_valid:
                    flash(result.error_message, "error")
                    return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Determine key password
            key_password = None if rsa_key_from_qr else (rsa_password if rsa_password else None)

            # Validate RSA key if provided
            if rsa_key_data:
                result = validate_rsa_key(rsa_key_data, key_password)
                if not result.is_valid:
                    flash(result.error_message, "error")
                    return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Validate carrier image
            result = validate_image(carrier_data, "Carrier image")
            if not result.is_valid:
                flash(result.error_message, "error")
                return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Pre-check payload capacity BEFORE encode (fail fast)
            from stegasoo.steganography import will_fit_by_mode

            payload_size = len(payload.data) if hasattr(payload, "data") else len(payload.encode("utf-8"))
            fit_check = will_fit_by_mode(payload_size, carrier_data, embed_mode=embed_mode)
            if not fit_check.get("fits", True):
                error_msg = (
                    f"Payload too large for {embed_mode.upper()} mode. "
                    f"Payload: {payload_size:,} bytes, "
                    f"Capacity: {fit_check.get('capacity', 0):,} bytes"
                )
                # Suggest alternative mode
                if embed_mode == "dct":
                    alt_check = will_fit_by_mode(payload_size, carrier_data, embed_mode="lsb")
                    if alt_check.get("fits"):
                        error_msg += " - Try LSB mode instead."
                flash(error_msg, "error")
                return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

            # v4.0.0: Include channel_key parameter
            # Use subprocess-isolated encode to prevent crashes
            if payload_type == "file" and payload_file and payload_file.filename:
                encode_result = subprocess_stego.encode(
                    carrier_data=carrier_data,
                    reference_data=ref_data,
                    file_data=payload.data,
                    file_name=payload.filename,
                    file_mime=payload.mime_type,
                    passphrase=passphrase,
                    pin=pin if pin else None,
                    rsa_key_data=rsa_key_data,
                    rsa_password=key_password,
                    embed_mode=embed_mode,
                    dct_output_format=dct_output_format if embed_mode == "dct" else "png",
                    dct_color_mode=dct_color_mode if embed_mode == "dct" else "color",
                    channel_key=channel_key,  # v4.0.0
                )
            else:
                encode_result = subprocess_stego.encode(
                    carrier_data=carrier_data,
                    reference_data=ref_data,
                    message=payload,
                    passphrase=passphrase,
                    pin=pin if pin else None,
                    rsa_key_data=rsa_key_data,
                    rsa_password=key_password,
                    embed_mode=embed_mode,
                    dct_output_format=dct_output_format if embed_mode == "dct" else "png",
                    dct_color_mode=dct_color_mode if embed_mode == "dct" else "color",
                    channel_key=channel_key,  # v4.0.0
                )

            # Check for subprocess errors
            if not encode_result.success:
                error_msg = encode_result.error or "Encoding failed"
                if "capacity" in error_msg.lower():
                    raise CapacityError(error_msg)
                raise StegasooError(error_msg)

            # Determine actual output format for filename and storage
            if embed_mode == "dct" and dct_output_format == "jpeg":
                output_ext = ".jpg"
                output_mime = "image/jpeg"
            else:
                output_ext = ".png"
                output_mime = "image/png"

            # Use filename from result or generate one
            filename = encode_result.filename
            if not filename:
                filename = generate_filename("stego", output_ext)
            elif embed_mode == "dct" and dct_output_format == "jpeg" and filename.endswith(".png"):
                filename = filename[:-4] + ".jpg"

            # Store temporarily
            file_id = secrets.token_urlsafe(16)
            cleanup_temp_files()
            TEMP_FILES[file_id] = {
                "data": encode_result.stego_data,
                "filename": filename,
                "timestamp": time.time(),
                "embed_mode": embed_mode,
                "output_format": dct_output_format if embed_mode == "dct" else "png",
                "color_mode": dct_color_mode if embed_mode == "dct" else None,
                "mime_type": output_mime,
                # Channel info (v4.0.0)
                "channel_mode": encode_result.channel_mode,
                "channel_fingerprint": encode_result.channel_fingerprint,
            }

            return redirect(url_for("encode_result", file_id=file_id))

        except CapacityError as e:
            flash(str(e), "error")
            return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)
        except StegasooError as e:
            flash(str(e), "error")
            return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)
        except Exception as e:
            flash(f"Error: {e}", "error")
            return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)

    return render_template("encode.html", has_qrcode_read=HAS_QRCODE_READ)


@app.route("/encode/result/<file_id>")
@login_required
def encode_result(file_id):
    if file_id not in TEMP_FILES:
        flash("File expired or not found. Please encode again.", "error")
        return redirect(url_for("encode_page"))

    file_info = TEMP_FILES[file_id]

    # Generate thumbnail
    thumbnail_data = generate_thumbnail(file_info["data"])
    thumbnail_id = None

    if thumbnail_data:
        thumbnail_id = f"{file_id}_thumb"
        THUMBNAIL_FILES[thumbnail_id] = thumbnail_data

    return render_template(
        "encode_result.html",
        file_id=file_id,
        filename=file_info["filename"],
        thumbnail_url=url_for("encode_thumbnail", thumb_id=thumbnail_id) if thumbnail_id else None,
        embed_mode=file_info.get("embed_mode", "lsb"),
        output_format=file_info.get("output_format", "png"),
        color_mode=file_info.get("color_mode"),
        # Channel info (v4.0.0)
        channel_mode=file_info.get("channel_mode", "public"),
        channel_fingerprint=file_info.get("channel_fingerprint"),
    )


@app.route("/encode/thumbnail/<thumb_id>")
@login_required
def encode_thumbnail(thumb_id):
    """Serve thumbnail image."""
    if thumb_id not in THUMBNAIL_FILES:
        return "Thumbnail not found", 404

    return send_file(
        io.BytesIO(THUMBNAIL_FILES[thumb_id]), mimetype="image/jpeg", as_attachment=False
    )


@app.route("/encode/download/<file_id>")
@login_required
def encode_download(file_id):
    if file_id not in TEMP_FILES:
        flash("File expired or not found.", "error")
        return redirect(url_for("encode_page"))

    file_info = TEMP_FILES[file_id]
    mime_type = file_info.get("mime_type", "image/png")

    return send_file(
        io.BytesIO(file_info["data"]),
        mimetype=mime_type,
        as_attachment=True,
        download_name=file_info["filename"],
    )


@app.route("/encode/file/<file_id>")
@login_required
def encode_file_route(file_id):
    """Serve file for Web Share API."""
    if file_id not in TEMP_FILES:
        return "Not found", 404

    file_info = TEMP_FILES[file_id]
    mime_type = file_info.get("mime_type", "image/png")

    return send_file(
        io.BytesIO(file_info["data"]),
        mimetype=mime_type,
        as_attachment=False,
        download_name=file_info["filename"],
    )


@app.route("/encode/cleanup/<file_id>", methods=["POST"])
@login_required
def encode_cleanup(file_id):
    """Manually cleanup a file after sharing."""
    TEMP_FILES.pop(file_id, None)

    # Also cleanup thumbnail if exists
    thumb_id = f"{file_id}_thumb"
    THUMBNAIL_FILES.pop(thumb_id, None)

    return jsonify({"status": "ok"})


# ============================================================================
# DECODE
# ============================================================================


@app.route("/decode", methods=["GET", "POST"])
@login_required
def decode_page():
    if request.method == "POST":
        try:
            # Get files
            ref_photo = request.files.get("reference_photo")
            stego_image = request.files.get("stego_image")
            rsa_key_file = request.files.get("rsa_key")

            if not ref_photo or not stego_image:
                flash("Both reference photo and stego image are required", "error")
                return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Get form data - v3.2.0: renamed from day_phrase to passphrase
            passphrase = request.form.get("passphrase", "")  # v3.2.0: Renamed
            pin = request.form.get("pin", "").strip()
            rsa_password = request.form.get("rsa_password", "")

            # NEW in v3.0 - Extraction mode
            embed_mode = request.form.get("embed_mode", "auto")
            if embed_mode not in ("auto", "lsb", "dct"):
                embed_mode = "auto"

            # NEW in v4.0.0 - Channel key
            channel_key = resolve_channel_key_form(request.form.get("channel_key", "auto"))

            # Check DCT availability
            if embed_mode == "dct" and not has_dct_support():
                flash("DCT mode requires scipy. Install with: pip install scipy", "error")
                return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)

            # v3.2.0: Removed date handling (no stego_date needed)

            # v3.2.0: Renamed from day_phrase
            if not passphrase:
                flash("Passphrase is required", "error")
                return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Read files
            ref_data = ref_photo.read()
            stego_data = stego_image.read()

            # Handle RSA key - can come from .pem file or QR code image
            rsa_key_data = None
            rsa_key_qr = request.files.get("rsa_key_qr")
            rsa_key_from_qr = False

            if rsa_key_file and rsa_key_file.filename:
                rsa_key_data = rsa_key_file.read()
            elif rsa_key_qr and rsa_key_qr.filename and HAS_QRCODE_READ:
                qr_image_data = rsa_key_qr.read()
                key_pem = extract_key_from_qr(qr_image_data)
                if key_pem:
                    rsa_key_data = key_pem.encode("utf-8")
                    rsa_key_from_qr = True
                else:
                    flash("Could not extract RSA key from QR code image.", "error")
                    return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Validate security factors
            result = validate_security_factors(pin, rsa_key_data)
            if not result.is_valid:
                flash(result.error_message, "error")
                return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Validate PIN if provided
            if pin:
                result = validate_pin(pin)
                if not result.is_valid:
                    flash(result.error_message, "error")
                    return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)

            # Determine key password
            key_password = None if rsa_key_from_qr else (rsa_password if rsa_password else None)

            # Validate RSA key if provided
            if rsa_key_data:
                result = validate_rsa_key(rsa_key_data, key_password)
                if not result.is_valid:
                    flash(result.error_message, "error")
                    return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)

            # v4.0.0: Include channel_key parameter
            # Use subprocess-isolated decode to prevent crashes
            decode_result = subprocess_stego.decode(
                stego_data=stego_data,
                reference_data=ref_data,
                passphrase=passphrase,
                pin=pin if pin else None,
                rsa_key_data=rsa_key_data,
                rsa_password=key_password,
                embed_mode=embed_mode,
                channel_key=channel_key,  # v4.0.0
            )

            # Check for subprocess errors
            if not decode_result.success:
                error_msg = decode_result.error or "Decoding failed"
                # Check for channel key related errors
                if "channel key" in error_msg.lower():
                    flash(error_msg, "error")
                    return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)
                if "decrypt" in error_msg.lower() or decode_result.error_type == "DecryptionError":
                    raise DecryptionError(error_msg)
                raise StegasooError(error_msg)

            if decode_result.is_file:
                # File content - store temporarily for download
                file_id = secrets.token_urlsafe(16)
                cleanup_temp_files()

                filename = decode_result.filename or "decoded_file"
                TEMP_FILES[file_id] = {
                    "data": decode_result.file_data,
                    "filename": filename,
                    "mime_type": decode_result.mime_type,
                    "timestamp": time.time(),
                }

                return render_template(
                    "decode.html",
                    decoded_file=True,
                    file_id=file_id,
                    filename=filename,
                    file_size=format_size(len(decode_result.file_data)),
                    mime_type=decode_result.mime_type,
                    has_qrcode_read=HAS_QRCODE_READ,
                )
            else:
                # Text content
                return render_template(
                    "decode.html",
                    decoded_message=decode_result.message,
                    has_qrcode_read=HAS_QRCODE_READ,
                )

        except DecryptionError:
            flash(
                "Decryption failed. Check passphrase, PIN, RSA key, reference photo, and channel key.",
                "error",
            )
            return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)
        except StegasooError as e:
            flash(str(e), "error")
            return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)
        except Exception as e:
            flash(f"Error: {e}", "error")
            return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)

    return render_template("decode.html", has_qrcode_read=HAS_QRCODE_READ)


@app.route("/decode/download/<file_id>")
@login_required
def decode_download(file_id):
    """Download decoded file."""
    if file_id not in TEMP_FILES:
        flash("File expired or not found.", "error")
        return redirect(url_for("decode_page"))

    file_info = TEMP_FILES[file_id]
    mime_type = file_info.get("mime_type", "application/octet-stream")

    return send_file(
        io.BytesIO(file_info["data"]),
        mimetype=mime_type,
        as_attachment=True,
        download_name=file_info["filename"],
    )


@app.route("/about")
def about():
    return render_template("about.html", has_argon2=has_argon2(), has_qrcode_read=HAS_QRCODE_READ)


# ============================================================================
# TOOLS ROUTES (v4.1.0)
# ============================================================================


@app.route("/tools")
@login_required
def tools():
    """Advanced tools page."""
    return render_template("tools.html", has_dct=has_dct_support())


@app.route("/api/tools/capacity", methods=["POST"])
@login_required
def api_tools_capacity():
    """Calculate image capacity for steganography."""
    from stegasoo.dct_steganography import estimate_capacity_comparison

    carrier = request.files.get("image")
    if not carrier:
        return jsonify({"success": False, "error": "No image provided"}), 400

    try:
        image_data = carrier.read()
        result = estimate_capacity_comparison(image_data)
        result["success"] = True
        result["filename"] = carrier.filename
        result["megapixels"] = round((result["width"] * result["height"]) / 1_000_000, 2)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/tools/strip-metadata", methods=["POST"])
@login_required
def api_tools_strip_metadata():
    """Strip EXIF/metadata from image."""
    import io

    from stegasoo.utils import strip_image_metadata

    image_file = request.files.get("image")
    if not image_file:
        return jsonify({"success": False, "error": "No image provided"}), 400

    try:
        image_data = image_file.read()
        clean_data = strip_image_metadata(image_data, output_format="PNG")

        buffer = io.BytesIO(clean_data)
        filename = image_file.filename.rsplit(".", 1)[0] + "_clean.png"

        return send_file(
            buffer,
            mimetype="image/png",
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/tools/exif", methods=["POST"])
@login_required
def api_tools_exif():
    """Read EXIF metadata from image."""
    from stegasoo.utils import read_image_exif

    image_file = request.files.get("image")
    if not image_file:
        return jsonify({"success": False, "error": "No image provided"}), 400

    try:
        image_data = image_file.read()
        exif = read_image_exif(image_data)

        # Check if it's a JPEG (editable) or not
        is_jpeg = image_data[:2] == b"\xff\xd8"

        return jsonify({
            "success": True,
            "filename": image_file.filename,
            "exif": exif,
            "editable": is_jpeg,
            "field_count": len(exif),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/tools/exif/update", methods=["POST"])
@login_required
def api_tools_exif_update():
    """Update EXIF fields in image."""
    from stegasoo.utils import write_image_exif

    image_file = request.files.get("image")
    if not image_file:
        return jsonify({"success": False, "error": "No image provided"}), 400

    # Get updates from form data
    updates_json = request.form.get("updates", "{}")
    try:
        import json
        updates = json.loads(updates_json)
    except json.JSONDecodeError:
        return jsonify({"success": False, "error": "Invalid updates JSON"}), 400

    if not updates:
        return jsonify({"success": False, "error": "No updates provided"}), 400

    try:
        image_data = image_file.read()
        updated_data = write_image_exif(image_data, updates)

        # Return as downloadable file
        buffer = io.BytesIO(updated_data)
        return send_file(
            buffer,
            mimetype="image/jpeg",
            as_attachment=True,
            download_name=f"exif_{image_file.filename}",
        )
    except ValueError as e:
        return jsonify({"success": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/tools/exif/clear", methods=["POST"])
@login_required
def api_tools_exif_clear():
    """Remove all EXIF metadata from image."""
    from stegasoo.utils import strip_image_metadata

    image_file = request.files.get("image")
    if not image_file:
        return jsonify({"success": False, "error": "No image provided"}), 400

    # Get desired output format (default to PNG for lossless)
    output_format = request.form.get("format", "PNG").upper()
    if output_format not in ("PNG", "JPEG", "BMP"):
        output_format = "PNG"

    try:
        image_data = image_file.read()
        clean_data = strip_image_metadata(image_data, output_format=output_format)

        # Determine extension and mimetype
        ext_map = {"PNG": ("png", "image/png"), "JPEG": ("jpg", "image/jpeg"), "BMP": ("bmp", "image/bmp")}
        ext, mimetype = ext_map.get(output_format, ("png", "image/png"))

        # Return as downloadable file
        stem = image_file.filename.rsplit(".", 1)[0] if "." in image_file.filename else image_file.filename
        buffer = io.BytesIO(clean_data)
        return send_file(
            buffer,
            mimetype=mimetype,
            as_attachment=True,
            download_name=f"{stem}_clean.{ext}",
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# Add these two test routes anywhere in app.py after the app = Flask(...) line:


@app.route("/test-capacity", methods=["POST"])
def test_capacity():
    """Minimal capacity test - no stegasoo code, just PIL."""
    carrier = request.files.get("carrier")
    if not carrier:
        return jsonify({"error": "No carrier image provided"}), 400

    try:
        carrier_data = carrier.read()
        buffer = io.BytesIO(carrier_data)
        img = Image.open(buffer)
        width, height = img.size
        fmt = img.format
        img.close()
        buffer.close()

        pixels = width * height
        lsb_bytes = (pixels * 3) // 8
        dct_bytes = ((width // 8) * (height // 8) * 16) // 8 - 10

        return jsonify(
            {
                "success": True,
                "width": width,
                "height": height,
                "format": fmt,
                "lsb_kb": round(lsb_bytes / 1024, 1),
                "dct_kb": round(dct_bytes / 1024, 1),
            }
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/test-capacity-nopil", methods=["POST"])
def test_capacity_nopil():
    """Ultra-minimal test - no PIL, no stegasoo."""
    carrier = request.files.get("carrier")
    if not carrier:
        return jsonify({"error": "No carrier image provided"}), 400

    carrier_data = carrier.read()
    return jsonify(
        {
            "success": True,
            "data_size": len(carrier_data),
        }
    )


# ============================================================================
# AUTHENTICATION ROUTES (v4.0.2)
# ============================================================================


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login page."""
    if not app.config.get("AUTH_ENABLED", True):
        return redirect(url_for("index"))

    if not user_exists():
        return redirect(url_for("setup"))

    if is_authenticated():
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        user = verify_user_password(username, password)
        if user:
            login_user(user)
            session.permanent = True
            flash("Login successful", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid username or password", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Logout and clear session."""
    logout_user()
    flash("Logged out successfully", "success")
    return redirect(url_for("index"))


@app.route("/setup", methods=["GET", "POST"])
def setup():
    """First-run setup page - create admin account (Step 1)."""
    if not app.config.get("AUTH_ENABLED", True):
        return redirect(url_for("index"))

    if user_exists():
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form.get("username", "admin")
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if password != password_confirm:
            flash("Passwords do not match", "error")
        else:
            success, message = create_admin_user(username, password)
            if success:
                # Auto-login the new admin
                user = verify_user_password(username, password)
                if user:
                    login_user(user)
                    session.permanent = True
                # Redirect to recovery key setup (Step 2)
                return redirect(url_for("setup_recovery"))
            else:
                flash(message, "error")

    return render_template("setup.html")


@app.route("/setup/recovery", methods=["GET", "POST"])
@login_required
def setup_recovery():
    """Recovery key setup page (Step 2 of initial setup)."""
    from stegasoo.recovery import generate_recovery_key, hash_recovery_key, generate_recovery_qr
    import base64

    # Only allow during initial setup (no recovery key yet, first admin)
    if has_recovery_key():
        return redirect(url_for("index"))

    current_user = get_current_user()
    if current_user.role != "admin":
        return redirect(url_for("index"))

    if request.method == "POST":
        action = request.form.get("action")

        if action == "skip":
            # No recovery key - most secure but no way to recover
            flash("Setup complete. No recovery key configured.", "warning")
            return redirect(url_for("index"))

        elif action == "save":
            # User confirmed they saved the key
            recovery_key = request.form.get("recovery_key")
            if recovery_key:
                key_hash = hash_recovery_key(recovery_key)
                set_recovery_key_hash(key_hash)
                flash("Setup complete. Recovery key saved.", "success")
                return redirect(url_for("index"))

    # Generate a new key to show
    recovery_key = generate_recovery_key()

    # Generate QR code as base64
    try:
        qr_bytes = generate_recovery_qr(recovery_key)
        qr_base64 = base64.b64encode(qr_bytes).decode("utf-8")
    except ImportError:
        qr_base64 = None

    return render_template(
        "setup_recovery.html",
        recovery_key=recovery_key,
        qr_base64=qr_base64,
    )


@app.route("/recover", methods=["GET", "POST"])
def recover():
    """Password recovery page - reset password using recovery key."""
    # Don't show if no recovery key configured
    if not get_recovery_key_hash():
        flash("No recovery key configured for this instance", "error")
        return redirect(url_for("login"))

    if request.method == "POST":
        recovery_key = request.form.get("recovery_key", "").strip()
        new_password = request.form.get("new_password", "")
        new_password_confirm = request.form.get("new_password_confirm", "")

        if not recovery_key:
            flash("Please enter your recovery key", "error")
        elif new_password != new_password_confirm:
            flash("Passwords do not match", "error")
        elif len(new_password) < 8:
            flash("Password must be at least 8 characters", "error")
        else:
            success, message = verify_and_reset_admin_password(recovery_key, new_password)
            if success:
                flash("Password reset successfully. Please login.", "success")
                return redirect(url_for("login"))
            else:
                flash(message, "error")

    return render_template("recover.html")


@app.route("/account/recovery/regenerate", methods=["GET", "POST"])
@login_required
@admin_required
def regenerate_recovery():
    """Generate a new recovery key (replaces existing one)."""
    from stegasoo.recovery import generate_recovery_key, hash_recovery_key, generate_recovery_qr
    import base64

    if request.method == "POST":
        action = request.form.get("action")

        if action == "cancel":
            flash("Recovery key generation cancelled", "warning")
            return redirect(url_for("account"))

        elif action == "save":
            # User confirmed they saved the key
            recovery_key = request.form.get("recovery_key")
            if recovery_key:
                key_hash = hash_recovery_key(recovery_key)
                set_recovery_key_hash(key_hash)
                flash("New recovery key saved successfully", "success")
                return redirect(url_for("account"))

    # Generate a new key to show
    recovery_key = generate_recovery_key()

    # Generate QR code as base64
    try:
        qr_bytes = generate_recovery_qr(recovery_key)
        qr_base64 = base64.b64encode(qr_bytes).decode("utf-8")
    except ImportError:
        qr_base64 = None

    return render_template(
        "regenerate_recovery.html",
        recovery_key=recovery_key,
        qr_base64=qr_base64,
        has_existing=has_recovery_key(),
    )


@app.route("/account/recovery/disable", methods=["POST"])
@login_required
@admin_required
def disable_recovery():
    """Disable recovery key (no password reset possible)."""
    if clear_recovery_key():
        flash("Recovery key disabled. Password reset is no longer possible.", "warning")
    else:
        flash("No recovery key was configured", "error")
    return redirect(url_for("account"))


@app.route("/account/recovery/stego-backup", methods=["POST"])
@login_required
@admin_required
def create_stego_backup():
    """Create stego backup - hide recovery key in an image."""
    from stegasoo.recovery import create_stego_backup as make_backup

    recovery_key = request.form.get("recovery_key", "")
    if not recovery_key:
        flash("No recovery key provided", "error")
        return redirect(url_for("regenerate_recovery"))

    if "carrier_image" not in request.files:
        flash("No image uploaded", "error")
        return redirect(url_for("regenerate_recovery"))

    carrier_file = request.files["carrier_image"]
    if not carrier_file.filename:
        flash("No image selected", "error")
        return redirect(url_for("regenerate_recovery"))

    try:
        carrier_data = carrier_file.read()
        stego_data = make_backup(recovery_key, carrier_data)

        # Return as downloadable PNG
        buffer = io.BytesIO(stego_data)
        return send_file(
            buffer,
            mimetype="image/png",
            as_attachment=True,
            download_name="stegasoo-recovery-backup.png",
        )
    except ValueError as e:
        flash(str(e), "error")
        return redirect(url_for("regenerate_recovery"))


@app.route("/recover/stego", methods=["POST"])
def recover_from_stego():
    """Extract recovery key from stego backup image."""
    from stegasoo.recovery import extract_stego_backup

    if "stego_image" not in request.files or "reference_image" not in request.files:
        flash("Both stego image and reference image are required", "error")
        return redirect(url_for("recover"))

    stego_file = request.files["stego_image"]
    reference_file = request.files["reference_image"]

    if not stego_file.filename or not reference_file.filename:
        flash("Both images must be selected", "error")
        return redirect(url_for("recover"))

    try:
        stego_data = stego_file.read()
        reference_data = reference_file.read()

        extracted_key = extract_stego_backup(stego_data, reference_data)

        if extracted_key:
            # Return the key to pre-fill the recovery form
            return render_template("recover.html", prefilled_key=extracted_key)
        else:
            flash("Could not extract recovery key. Check images are correct.", "error")
            return redirect(url_for("recover"))

    except Exception as e:
        flash(f"Extraction failed: {e}", "error")
        return redirect(url_for("recover"))


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Account management page."""
    current_user = get_current_user()

    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        new_confirm = request.form.get("new_password_confirm", "")

        if new != new_confirm:
            flash("New passwords do not match", "error")
        else:
            success, message = change_password(current_user.id, current, new)
            flash(message, "success" if success else "error")

    # Get saved channel keys
    channel_keys = get_user_channel_keys(current_user.id)

    return render_template(
        "account.html",
        username=current_user.username,
        user=current_user,
        is_admin=current_user.is_admin,
        has_recovery=has_recovery_key(),
        channel_keys=channel_keys,
        max_channel_keys=MAX_CHANNEL_KEYS,
        can_save_key=can_save_channel_key(current_user.id),
    )


# ============================================================================
# CHANNEL KEY MANAGEMENT ROUTES (v4.2.0)
# ============================================================================


@app.route("/account/keys/save", methods=["POST"])
@login_required
def account_save_key():
    """Save a new channel key."""
    current_user = get_current_user()
    name = request.form.get("key_name", "").strip()
    channel_key = request.form.get("channel_key", "").strip()

    # Normalize key format (remove dashes if present)
    channel_key = channel_key.replace("-", "").lower()

    success, message, key = save_channel_key(current_user.id, name, channel_key)
    flash(message, "success" if success else "error")
    return redirect(url_for("account"))


@app.route("/account/keys/<int:key_id>/delete", methods=["POST"])
@login_required
def account_delete_key(key_id):
    """Delete a saved channel key."""
    current_user = get_current_user()
    success, message = delete_channel_key(key_id, current_user.id)
    flash(message, "success" if success else "error")
    return redirect(url_for("account"))


@app.route("/account/keys/<int:key_id>/rename", methods=["POST"])
@login_required
def account_rename_key(key_id):
    """Rename a saved channel key."""
    current_user = get_current_user()
    new_name = request.form.get("new_name", "").strip()
    success, message = update_channel_key_name(key_id, current_user.id, new_name)
    flash(message, "success" if success else "error")
    return redirect(url_for("account"))


@app.route("/api/channel/keys")
@login_required
def api_channel_keys():
    """Get saved channel keys for current user (JSON API)."""
    current_user = get_current_user()
    keys = get_user_channel_keys(current_user.id)
    return jsonify({
        "success": True,
        "keys": [
            {
                "id": k.id,
                "name": k.name,
                "fingerprint": f"{k.channel_key[:4]}...{k.channel_key[-4:]}",
                "channel_key": k.channel_key,
                "last_used_at": k.last_used_at,
            }
            for k in keys
        ],
        "can_save": can_save_channel_key(current_user.id),
        "max_keys": MAX_CHANNEL_KEYS,
    })


@app.route("/api/channel/keys/<int:key_id>/use", methods=["POST"])
@login_required
def api_channel_key_use(key_id):
    """Mark a channel key as used (updates last_used_at)."""
    current_user = get_current_user()
    key = get_channel_key_by_id(key_id, current_user.id)
    if not key:
        return jsonify({"success": False, "error": "Key not found"}), 404

    update_channel_key_last_used(key_id, current_user.id)
    return jsonify({"success": True})


# ============================================================================
# ADMIN ROUTES (v4.1.0)
# ============================================================================


@app.route("/admin/users")
@admin_required
def admin_users():
    """User management page (admin only)."""
    users = get_all_users()
    current_user = get_current_user()
    return render_template(
        "admin/users.html",
        users=users,
        current_user=current_user,
        user_count=get_non_admin_count(),
        max_users=MAX_USERS,
        can_create=can_create_user(),
    )


@app.route("/admin/users/new", methods=["GET", "POST"])
@admin_required
def admin_user_new():
    """Create new user (admin only)."""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        success, message, user = create_user(username, password)

        # Check if AJAX request
        if request.headers.get("X-Requested-With") == "XMLHttpRequest":
            if success:
                return jsonify({"success": True, "username": username, "password": password})
            else:
                return jsonify({"success": False, "error": message})

        # Regular form submission fallback
        if success:
            flash(f"User '{username}' created successfully", "success")
            session["temp_password"] = password
            session["temp_username"] = username
            return redirect(url_for("admin_user_created"))
        else:
            flash(message, "error")

    # Generate a temp password for the form
    temp_password = generate_temp_password()
    return render_template("admin/user_new.html", temp_password=temp_password)


@app.route("/admin/users/created")
@admin_required
def admin_user_created():
    """Show created user confirmation with password."""
    username = session.pop("temp_username", None)
    password = session.pop("temp_password", None)

    if not username or not password:
        return redirect(url_for("admin_users"))

    return render_template(
        "admin/user_created.html",
        username=username,
        password=password,
    )


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_user_delete(user_id):
    """Delete a user (admin only)."""
    current_user = get_current_user()
    success, message = delete_user(user_id, current_user.id)
    flash(message, "success" if success else "error")
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/reset-password", methods=["POST"])
@admin_required
def admin_user_reset_password(user_id):
    """Reset a user's password (admin only)."""
    user = get_user_by_id(user_id)
    if not user:
        flash("User not found", "error")
        return redirect(url_for("admin_users"))

    # Generate new password
    new_password = generate_temp_password()
    success, message = reset_user_password(user_id, new_password)

    if success:
        # Store for display
        session["temp_password"] = new_password
        session["temp_username"] = user.username
        return redirect(url_for("admin_user_password_reset"))
    else:
        flash(message, "error")
        return redirect(url_for("admin_users"))


@app.route("/admin/users/password-reset")
@admin_required
def admin_user_password_reset():
    """Show password reset confirmation."""
    username = session.pop("temp_username", None)
    password = session.pop("temp_password", None)

    if not username or not password:
        return redirect(url_for("admin_users"))

    return render_template(
        "admin/password_reset.html",
        username=username,
        password=password,
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    base_dir = Path(__file__).parent

    # HTTPS configuration
    ssl_context = None
    if app.config.get("HTTPS_ENABLED", False):
        hostname = os.environ.get("STEGASOO_HOSTNAME", "localhost")
        cert_path, key_path = ensure_certs(base_dir, hostname)
        ssl_context = (str(cert_path), str(key_path))
        print(f"HTTPS enabled with self-signed certificate for {hostname}")

    # Auth status
    if app.config.get("AUTH_ENABLED", True):
        print("Authentication enabled")
    else:
        print("Authentication disabled")

    port = int(os.environ.get("STEGASOO_PORT", "5000"))
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        ssl_context=ssl_context,
    )
