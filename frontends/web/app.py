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
    change_password,
    create_user,
    get_username,
    is_authenticated,
    login_required,
    user_exists,
    verify_password,
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

    Args:
        channel_key_value: Form value ('auto', 'none', or explicit key)

    Returns:
        Value to pass to subprocess_stego ('auto', 'none', or explicit key)
    """
    if not channel_key_value or channel_key_value == "auto":
        return "auto"
    elif channel_key_value == "none":
        return "none"
    else:
        # Explicit key - validate format
        if validate_channel_key(channel_key_value):
            return channel_key_value
        else:
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
                "Decryption failed. Check your passphrase, PIN, RSA key, reference photo, and channel key.",
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
        password = request.form.get("password", "")
        if verify_password(password):
            session["authenticated"] = True
            session.permanent = True
            flash("Login successful", "success")
            return redirect(url_for("index"))
        else:
            flash("Invalid password", "error")

    return render_template("login.html", username=get_username())


@app.route("/logout")
def logout():
    """Logout and clear session."""
    session.clear()
    flash("Logged out successfully", "success")
    return redirect(url_for("index"))


@app.route("/setup", methods=["GET", "POST"])
def setup():
    """First-run setup page."""
    if not app.config.get("AUTH_ENABLED", True):
        return redirect(url_for("index"))

    if user_exists():
        return redirect(url_for("login"))

    if request.method == "POST":
        username = request.form.get("username", "admin")
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if len(password) < 8:
            flash("Password must be at least 8 characters", "error")
        elif password != password_confirm:
            flash("Passwords do not match", "error")
        else:
            try:
                create_user(username, password)
                session["authenticated"] = True
                session.permanent = True
                flash("Admin account created successfully!", "success")
                return redirect(url_for("index"))
            except Exception as e:
                flash(f"Error creating account: {e}", "error")

    return render_template("setup.html")


@app.route("/account", methods=["GET", "POST"])
@login_required
def account():
    """Account management page."""
    if request.method == "POST":
        current = request.form.get("current_password", "")
        new = request.form.get("new_password", "")
        new_confirm = request.form.get("new_password_confirm", "")

        if new != new_confirm:
            flash("New passwords do not match", "error")
        else:
            success, message = change_password(current, new)
            flash(message, "success" if success else "error")

    return render_template("account.html", username=get_username())


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
