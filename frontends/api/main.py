#!/usr/bin/env python3
"""
Stegasoo REST API (v4.0.0)

FastAPI-based REST API for steganography operations.
Supports both text messages and file embedding.

CHANGES in v4.0.0:
- Added channel key support for deployment/group isolation
- New /channel endpoints for key management
- channel_key parameter on encode/decode endpoints
- Messages encoded with channel key require same key to decode

CHANGES in v3.2.0:
- Removed date dependency from all operations
- Renamed day_phrase → passphrase
- No date_str parameters needed
- Simplified API for asynchronous communications

NEW in v3.0: LSB and DCT embedding modes.
NEW in v3.0.1: DCT color mode and JPEG output format.
"""

import base64
import sys
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from stegasoo import (
    MAX_FILE_PAYLOAD_SIZE,
    CapacityError,
    DecryptionError,
    FilePayload,
    StegasooError,
    __version__,
    calculate_capacity_by_mode,
    clear_channel_key,
    compare_modes,
    decode,
    encode,
    generate_channel_key,
    generate_credentials,
    get_channel_status,
    has_argon2,
    has_channel_key,
    has_dct_support,
    set_channel_key,
    validate_channel_key,
    validate_image,
    will_fit_by_mode,
)
from stegasoo.constants import (
    DEFAULT_PASSPHRASE_WORDS,
    MAX_PASSPHRASE_WORDS,
    MAX_PIN_LENGTH,
    MIN_PASSPHRASE_WORDS,
    MIN_PIN_LENGTH,
    VALID_RSA_SIZES,
)

# QR Code utilities
try:
    from stegasoo.qr_utils import (
        extract_key_from_qr,
        has_qr_read,
    )

    HAS_QR_READ = has_qr_read()
except ImportError:
    HAS_QR_READ = False
    extract_key_from_qr = None


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Stegasoo API",
    description="""
Secure steganography with hybrid authentication. Supports text messages and file embedding.

## Version 4.0.0 Changes

- **Channel key support** - Deployment/group isolation for messages
- **New /channel endpoints** - Generate, view, and manage channel keys
- **channel_key parameter** - Added to encode/decode endpoints

## Version 3.2.0 Changes

- **No date parameters needed** - Encode and decode anytime without tracking dates
- **Single passphrase** - No daily rotation, just use your passphrase
- **True asynchronous communications** - Perfect for dead drops and delayed delivery

## Embedding Modes (v3.0)

- **LSB mode** (default): Spatial LSB embedding, full color output, higher capacity
- **DCT mode**: Frequency domain embedding, ~20% capacity, better stealth

## DCT Options (v3.0.1)

- **dct_color_mode**: 'grayscale' (default) or 'color' (preserves original colors)
- **dct_output_format**: 'png' (lossless) or 'jpeg' (smaller, more natural)

Use the `/modes` endpoint to check availability and `/compare` to compare capacities.
""",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============================================================================
# TYPE ALIASES
# ============================================================================

EmbedModeType = Literal["lsb", "dct"]
ExtractModeType = Literal["auto", "lsb", "dct"]
DctColorModeType = Literal["grayscale", "color"]
DctOutputFormatType = Literal["png", "jpeg"]


# ============================================================================
# MODELS
# ============================================================================


class GenerateRequest(BaseModel):
    use_pin: bool = True
    use_rsa: bool = False
    pin_length: int = Field(default=6, ge=MIN_PIN_LENGTH, le=MAX_PIN_LENGTH)
    rsa_bits: int = Field(default=2048)
    words_per_passphrase: int = Field(
        default=DEFAULT_PASSPHRASE_WORDS,
        ge=MIN_PASSPHRASE_WORDS,
        le=MAX_PASSPHRASE_WORDS,
        description="Words per passphrase (v3.2.0: default increased to 4)",
    )


class GenerateResponse(BaseModel):
    passphrase: str = Field(description="Single passphrase (v3.2.0: no daily rotation)")
    pin: str | None = None
    rsa_key_pem: str | None = None
    entropy: dict[str, int]
    # Legacy field for compatibility
    phrases: dict[str, str] | None = Field(
        default=None, description="Deprecated: Use 'passphrase' instead"
    )


class EncodeRequest(BaseModel):
    message: str
    reference_photo_base64: str
    carrier_image_base64: str
    passphrase: str = Field(description="Passphrase (v3.2.0: renamed from day_phrase)")
    pin: str = ""
    rsa_key_base64: str | None = None
    rsa_password: str | None = None
    # Channel key (v4.0.0)
    channel_key: str | None = Field(
        default=None,
        description="Channel key for deployment isolation. null=auto (use server config), ''=public mode, 'XXXX-...'=explicit key",
    )
    embed_mode: EmbedModeType = Field(
        default="lsb",
        description="Embedding mode: 'lsb' (default, color) or 'dct' (requires scipy)",
    )
    dct_output_format: DctOutputFormatType = Field(
        default="png",
        description="DCT output format: 'png' (lossless) or 'jpeg' (smaller). Only applies to DCT mode.",
    )
    dct_color_mode: DctColorModeType = Field(
        default="grayscale",
        description="DCT color mode: 'grayscale' (default) or 'color' (preserves colors). Only applies to DCT mode.",
    )


class EncodeFileRequest(BaseModel):
    """Request for embedding a file (base64-encoded)."""

    file_data_base64: str
    filename: str
    mime_type: str | None = None
    reference_photo_base64: str
    carrier_image_base64: str
    passphrase: str = Field(description="Passphrase (v3.2.0: renamed from day_phrase)")
    pin: str = ""
    rsa_key_base64: str | None = None
    rsa_password: str | None = None
    # Channel key (v4.0.0)
    channel_key: str | None = Field(
        default=None,
        description="Channel key for deployment isolation. null=auto (use server config), ''=public mode, 'XXXX-...'=explicit key",
    )
    embed_mode: EmbedModeType = Field(
        default="lsb",
        description="Embedding mode: 'lsb' (default, color) or 'dct' (requires scipy)",
    )
    dct_output_format: DctOutputFormatType = Field(
        default="png",
        description="DCT output format: 'png' (lossless) or 'jpeg' (smaller). Only applies to DCT mode.",
    )
    dct_color_mode: DctColorModeType = Field(
        default="grayscale",
        description="DCT color mode: 'grayscale' (default) or 'color' (preserves colors). Only applies to DCT mode.",
    )


class EncodeResponse(BaseModel):
    stego_image_base64: str
    filename: str
    capacity_used_percent: float
    embed_mode: str = Field(description="Embedding mode used: 'lsb' or 'dct'")
    output_format: str = Field(
        default="png", description="Output format: 'png' or 'jpeg' (for DCT mode)"
    )
    color_mode: str = Field(
        default="color",
        description="Color mode: 'color' (LSB/DCT color) or 'grayscale' (DCT grayscale)",
    )
    # Channel key info (v4.0.0)
    channel_mode: str = Field(default="public", description="Channel mode: 'public' or 'private'")
    channel_fingerprint: str | None = Field(
        default=None, description="Channel key fingerprint (if private mode)"
    )
    # Legacy fields (v3.2.0: no longer used in crypto)
    date_used: str | None = Field(
        default=None, description="Deprecated: Date no longer used in v3.2.0"
    )
    day_of_week: str | None = Field(
        default=None, description="Deprecated: Date no longer used in v3.2.0"
    )


class DecodeRequest(BaseModel):
    stego_image_base64: str
    reference_photo_base64: str
    passphrase: str = Field(description="Passphrase (v3.2.0: renamed from day_phrase)")
    pin: str = ""
    rsa_key_base64: str | None = None
    rsa_password: str | None = None
    # Channel key (v4.0.0)
    channel_key: str | None = Field(
        default=None,
        description="Channel key for decryption. null=auto (use server config), ''=public mode, 'XXXX-...'=explicit key",
    )
    embed_mode: ExtractModeType = Field(
        default="auto", description="Extraction mode: 'auto' (default), 'lsb', or 'dct'"
    )


class DecodeResponse(BaseModel):
    """Response for decode - can be text or file."""

    payload_type: str  # 'text' or 'file'
    message: str | None = None  # For text
    file_data_base64: str | None = None  # For file (base64-encoded)
    filename: str | None = None  # For file
    mime_type: str | None = None  # For file


class ModeCapacity(BaseModel):
    """Capacity info for a single mode."""

    capacity_bytes: int
    capacity_kb: float
    available: bool
    output_format: str


class ImageInfoResponse(BaseModel):
    width: int
    height: int
    pixels: int
    capacity_bytes: int = Field(description="LSB mode capacity (for backwards compatibility)")
    capacity_kb: int = Field(description="LSB mode capacity in KB")
    modes: dict[str, ModeCapacity] | None = Field(
        default=None, description="Capacity by embedding mode (v3.0+)"
    )


class CompareModesRequest(BaseModel):
    """Request for comparing embedding modes."""

    carrier_image_base64: str
    payload_size: int | None = Field(
        default=None, description="Optional payload size to check if it fits"
    )


class CompareModesResponse(BaseModel):
    """Response comparing LSB and DCT modes."""

    width: int
    height: int
    lsb: dict
    dct: dict
    payload_check: dict | None = None
    recommendation: str


class DctModeInfo(BaseModel):
    """Detailed DCT mode information."""

    available: bool
    name: str
    description: str
    output_formats: list[str]
    color_modes: list[str]
    capacity_ratio: str
    requires: str


class ChannelStatusResponse(BaseModel):
    """Response for channel key status (v4.0.0)."""

    mode: str = Field(description="'public' or 'private'")
    configured: bool = Field(description="Whether a channel key is configured")
    fingerprint: str | None = Field(default=None, description="Key fingerprint (partial)")
    source: str | None = Field(default=None, description="Where the key comes from")
    key: str | None = Field(default=None, description="Full key (only if reveal=true)")


class ChannelGenerateResponse(BaseModel):
    """Response for channel key generation (v4.0.0)."""

    key: str = Field(description="Generated channel key")
    fingerprint: str = Field(description="Key fingerprint")
    saved: bool = Field(default=False, description="Whether key was saved to config")
    save_location: str | None = Field(default=None, description="Where key was saved")


class ChannelSetRequest(BaseModel):
    """Request to set channel key (v4.0.0)."""

    key: str = Field(description="Channel key to set")
    location: str = Field(default="user", description="'user' or 'project'")


class ModesResponse(BaseModel):
    """Response showing available embedding modes."""

    lsb: dict
    dct: DctModeInfo
    # Channel key status (v4.0.0)
    channel: dict | None = Field(default=None, description="Channel key status (v4.0.0)")


class StatusResponse(BaseModel):
    version: str
    has_argon2: bool
    has_qrcode_read: bool
    has_dct: bool
    max_payload_kb: int
    available_modes: list[str]
    dct_features: dict | None = Field(default=None, description="DCT mode features (v3.0.1+)")
    # Channel key status (v4.0.0)
    channel: dict | None = Field(default=None, description="Channel key status (v4.0.0)")
    breaking_changes: dict = Field(description="v4.0.0 breaking changes")


class QrExtractResponse(BaseModel):
    success: bool
    key_pem: str | None = None
    error: str | None = None


class WillFitRequest(BaseModel):
    """Request to check if payload will fit."""

    carrier_image_base64: str
    payload_size: int
    embed_mode: EmbedModeType = "lsb"


class WillFitResponse(BaseModel):
    """Response for will_fit check."""

    fits: bool
    payload_size: int
    capacity: int
    usage_percent: float
    headroom: int
    mode: str


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None


# ============================================================================
# HELPER: RESOLVE CHANNEL KEY
# ============================================================================


def _resolve_channel_key(channel_key: str | None) -> str | None:
    """
    Resolve channel key from API parameter.

    Args:
        channel_key: API parameter value
            - None: Use server-configured key (auto mode)
            - "": Public mode (no channel key)
            - "XXXX-...": Explicit key

    Returns:
        Resolved channel key to pass to encode/decode

    Raises:
        HTTPException: If key format is invalid
    """
    if channel_key is None:
        # Auto mode - use server config
        return None

    if channel_key == "":
        # Public mode
        return ""

    # Explicit key - validate format
    if not validate_channel_key(channel_key):
        raise HTTPException(
            400, "Invalid channel key format. Expected: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX"
        )

    return channel_key


def _get_channel_info(channel_key: str | None) -> tuple[str, str | None]:
    """
    Get channel mode and fingerprint for response.

    Returns:
        (mode, fingerprint) tuple
    """
    if channel_key == "":
        return "public", None

    if channel_key is not None:
        # Explicit key
        fingerprint = f"{channel_key[:4]}-••••-••••-••••-••••-••••-••••-{channel_key[-4:]}"
        return "private", fingerprint

    # Auto mode - check server config
    if has_channel_key():
        status = get_channel_status()
        return "private", status.get("fingerprint")

    return "public", None


# ============================================================================
# ROUTES - STATUS & INFO
# ============================================================================


@app.get("/", response_model=StatusResponse)
async def root():
    """Get API status and configuration."""
    available_modes = ["lsb"]
    dct_features = None

    if has_dct_support():
        available_modes.append("dct")
        dct_features = {
            "output_formats": ["png", "jpeg"],
            "color_modes": ["grayscale", "color"],
            "default_output_format": "png",
            "default_color_mode": "grayscale",
        }

    # Channel key status (v4.0.0)
    channel_status = get_channel_status()
    channel_info = {
        "mode": channel_status["mode"],
        "configured": channel_status["configured"],
        "fingerprint": channel_status.get("fingerprint"),
        "source": channel_status.get("source"),
    }

    return StatusResponse(
        version=__version__,
        has_argon2=has_argon2(),
        has_qrcode_read=HAS_QR_READ,
        has_dct=has_dct_support(),
        max_payload_kb=MAX_FILE_PAYLOAD_SIZE // 1024,
        available_modes=available_modes,
        dct_features=dct_features,
        channel=channel_info,
        breaking_changes={
            "v4_channel_key": "Messages encoded with channel key require same key to decode",
            "format_version": 5,
            "backward_compatible": False,
            "v3_notes": {
                "date_removed": "No date_str parameter needed - encode/decode anytime",
                "passphrase_renamed": "day_phrase → passphrase (single passphrase, no daily rotation)",
            },
        },
    )


@app.get("/modes", response_model=ModesResponse)
async def api_modes():
    """
    Get available embedding modes and their status.

    v4.0.0: Also includes channel key status.
    """
    # Channel status
    channel_status = get_channel_status()
    channel_info = {
        "mode": channel_status["mode"],
        "configured": channel_status["configured"],
        "fingerprint": channel_status.get("fingerprint"),
    }

    return ModesResponse(
        lsb={
            "available": True,
            "name": "Spatial LSB",
            "description": "Embed in pixel LSBs, outputs PNG/BMP",
            "output_format": "PNG (color)",
            "capacity_ratio": "100%",
        },
        dct=DctModeInfo(
            available=has_dct_support(),
            name="DCT Domain",
            description="Embed in DCT coefficients, frequency domain steganography",
            output_formats=["png", "jpeg"],
            color_modes=["grayscale", "color"],
            capacity_ratio="~20% of LSB",
            requires="scipy",
        ),
        channel=channel_info,
    )


# ============================================================================
# ROUTES - CHANNEL KEY (v4.0.0)
# ============================================================================


@app.get("/channel/status", response_model=ChannelStatusResponse)
async def api_channel_status(
    reveal: bool = Query(False, description="Include full key in response")
):
    """
    Get current channel key status.

    v4.0.0: New endpoint for channel key management.

    Returns mode (public/private), fingerprint, and source.
    Use reveal=true to include the full key.
    """
    status = get_channel_status()

    return ChannelStatusResponse(
        mode=status["mode"],
        configured=status["configured"],
        fingerprint=status.get("fingerprint"),
        source=status.get("source"),
        key=status.get("key") if reveal and status["configured"] else None,
    )


@app.post("/channel/generate", response_model=ChannelGenerateResponse)
async def api_channel_generate(
    save: bool = Query(False, description="Save to user config"),
    save_project: bool = Query(False, description="Save to project config"),
):
    """
    Generate a new channel key.

    v4.0.0: New endpoint for channel key management.

    Optionally saves to user config (~/.stegasoo/channel.key) or
    project config (./config/channel.key).
    """
    if save and save_project:
        raise HTTPException(400, "Cannot use both save and save_project")

    key = generate_channel_key()
    fingerprint = f"{key[:4]}-••••-••••-••••-••••-••••-••••-{key[-4:]}"

    saved = False
    save_location = None

    if save:
        set_channel_key(key, location="user")
        saved = True
        save_location = "~/.stegasoo/channel.key"
    elif save_project:
        set_channel_key(key, location="project")
        saved = True
        save_location = "./config/channel.key"

    return ChannelGenerateResponse(
        key=key,
        fingerprint=fingerprint,
        saved=saved,
        save_location=save_location,
    )


@app.post("/channel/set")
async def api_channel_set(request: ChannelSetRequest):
    """
    Set/save a channel key to config.

    v4.0.0: New endpoint for channel key management.
    """
    if not validate_channel_key(request.key):
        raise HTTPException(
            400, "Invalid channel key format. Expected: XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX"
        )

    if request.location not in ("user", "project"):
        raise HTTPException(400, "location must be 'user' or 'project'")

    set_channel_key(request.key, location=request.location)

    status = get_channel_status()
    return {
        "success": True,
        "location": status.get("source"),
        "fingerprint": status.get("fingerprint"),
    }


@app.delete("/channel")
async def api_channel_clear(
    location: str = Query("user", description="'user', 'project', or 'all'")
):
    """
    Clear/remove channel key from config.

    v4.0.0: New endpoint for channel key management.

    Note: Does not affect environment variables.
    """
    if location == "all":
        clear_channel_key(location="user")
        clear_channel_key(location="project")
    elif location in ("user", "project"):
        clear_channel_key(location=location)
    else:
        raise HTTPException(400, "location must be 'user', 'project', or 'all'")

    status = get_channel_status()
    return {
        "success": True,
        "mode": status["mode"],
        "still_configured": status["configured"],
        "remaining_source": status.get("source"),
    }


@app.post("/compare", response_model=CompareModesResponse)
async def api_compare_modes(request: CompareModesRequest):
    """
    Compare LSB and DCT embedding modes for a carrier image.

    Returns capacity for both modes and recommendation.
    Optionally checks if a specific payload size would fit.
    """
    try:
        carrier = base64.b64decode(request.carrier_image_base64)
        comparison = compare_modes(carrier)

        response = CompareModesResponse(
            width=comparison["width"],
            height=comparison["height"],
            lsb={
                "capacity_bytes": comparison["lsb"]["capacity_bytes"],
                "capacity_kb": round(comparison["lsb"]["capacity_kb"], 1),
                "available": True,
                "output_format": comparison["lsb"]["output"],
            },
            dct={
                "capacity_bytes": comparison["dct"]["capacity_bytes"],
                "capacity_kb": round(comparison["dct"]["capacity_kb"], 1),
                "available": comparison["dct"]["available"],
                "output_formats": ["png", "jpeg"],
                "color_modes": ["grayscale", "color"],
                "ratio_vs_lsb_percent": round(comparison["dct"]["ratio_vs_lsb"], 1),
            },
            recommendation=(
                "lsb" if not comparison["dct"]["available"] else "dct for stealth, lsb for capacity"
            ),
        )

        if request.payload_size:
            fits_lsb = request.payload_size <= comparison["lsb"]["capacity_bytes"]
            fits_dct = request.payload_size <= comparison["dct"]["capacity_bytes"]

            response.payload_check = {
                "size_bytes": request.payload_size,
                "fits_lsb": fits_lsb,
                "fits_dct": fits_dct,
            }

            # Update recommendation based on payload
            if fits_dct and comparison["dct"]["available"]:
                response.recommendation = "dct (payload fits, better stealth)"
            elif fits_lsb:
                response.recommendation = "lsb (payload too large for dct)"
            else:
                response.recommendation = "none (payload too large for both modes)"

        return response

    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/will-fit", response_model=WillFitResponse)
async def api_will_fit(request: WillFitRequest):
    """
    Check if a payload of given size will fit in the carrier image.

    Supports both LSB and DCT modes.
    """
    try:
        # Validate mode
        if request.embed_mode == "dct" and not has_dct_support():
            raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")

        carrier = base64.b64decode(request.carrier_image_base64)
        result = will_fit_by_mode(request.payload_size, carrier, embed_mode=request.embed_mode)

        return WillFitResponse(
            fits=result["fits"],
            payload_size=result["payload_size"],
            capacity=result["capacity"],
            usage_percent=round(result["usage_percent"], 1),
            headroom=result["headroom"],
            mode=request.embed_mode,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================================
# ROUTES - QR CODE
# ============================================================================


@app.post("/extract-key-from-qr", response_model=QrExtractResponse)
async def api_extract_key_from_qr(
    qr_image: UploadFile = File(..., description="QR code image containing RSA key")
):
    """
    Extract RSA key from a QR code image.

    Supports both compressed (STEGASOO-Z: prefix) and uncompressed keys.
    Returns the PEM-encoded key if found.
    """
    if not HAS_QR_READ:
        raise HTTPException(501, "QR code reading not available. Install pyzbar and libzbar.")

    try:
        image_data = await qr_image.read()
        key_pem = extract_key_from_qr(image_data)

        if key_pem:
            return QrExtractResponse(success=True, key_pem=key_pem)
        else:
            return QrExtractResponse(success=False, error="No valid RSA key found in QR code")
    except Exception as e:
        return QrExtractResponse(success=False, error=str(e))


# ============================================================================
# ROUTES - GENERATE
# ============================================================================


@app.post("/generate", response_model=GenerateResponse)
async def api_generate(request: GenerateRequest):
    """
    Generate credentials for encoding/decoding.

    At least one of use_pin or use_rsa must be True.

    v3.2.0: Generates single passphrase (no daily rotation).
    Default increased to 4 words for better security.
    """
    if not request.use_pin and not request.use_rsa:
        raise HTTPException(400, "Must enable at least one of use_pin or use_rsa")

    if request.rsa_bits not in VALID_RSA_SIZES:
        raise HTTPException(400, f"rsa_bits must be one of {VALID_RSA_SIZES}")

    try:
        creds = generate_credentials(
            use_pin=request.use_pin,
            use_rsa=request.use_rsa,
            pin_length=request.pin_length,
            rsa_bits=request.rsa_bits,
            passphrase_words=request.words_per_passphrase,
        )

        return GenerateResponse(
            passphrase=creds.passphrase,
            pin=creds.pin,
            rsa_key_pem=creds.rsa_key_pem,
            entropy={
                "passphrase": creds.passphrase_entropy,
                "pin": creds.pin_entropy,
                "rsa": creds.rsa_entropy,
                "total": creds.total_entropy,
            },
            phrases=None,  # Legacy field removed
        )
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================================
# HELPER FUNCTION FOR DCT PARAMETERS
# ============================================================================


def _get_dct_params(embed_mode: str, dct_output_format: str, dct_color_mode: str) -> dict:
    """
    Get DCT-specific parameters if DCT mode is selected.
    Returns kwargs to pass to encode().
    """
    if embed_mode != "dct":
        return {}

    return {
        "dct_output_format": dct_output_format,
        "dct_color_mode": dct_color_mode,
    }


def _get_output_info(embed_mode: str, dct_output_format: str, dct_color_mode: str) -> tuple:
    """
    Get output format and color mode strings for response.
    Returns (output_format, color_mode, mime_type).
    """
    if embed_mode == "dct":
        output_format = dct_output_format
        color_mode = dct_color_mode
        mime_type = "image/jpeg" if dct_output_format == "jpeg" else "image/png"
    else:
        output_format = "png"
        color_mode = "color"
        mime_type = "image/png"

    return output_format, color_mode, mime_type


# ============================================================================
# ROUTES - ENCODE (JSON)
# ============================================================================


@app.post("/encode", response_model=EncodeResponse)
async def api_encode(request: EncodeRequest):
    """
    Encode a text message into an image.

    Images must be base64-encoded. Returns base64-encoded stego image.

    v4.0.0: Added channel_key parameter for deployment isolation.
    v3.2.0: No date_str parameter needed - encode anytime!
    """
    # Validate mode
    if request.embed_mode == "dct" and not has_dct_support():
        raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")

    # Resolve channel key
    resolved_channel_key = _resolve_channel_key(request.channel_key)

    try:
        ref_photo = base64.b64decode(request.reference_photo_base64)
        carrier = base64.b64decode(request.carrier_image_base64)
        rsa_key = base64.b64decode(request.rsa_key_base64) if request.rsa_key_base64 else None

        # Get DCT parameters
        dct_params = _get_dct_params(
            request.embed_mode, request.dct_output_format, request.dct_color_mode
        )

        # v4.0.0: Include channel_key
        result = encode(
            message=request.message,
            reference_photo=ref_photo,
            carrier_image=carrier,
            passphrase=request.passphrase,
            pin=request.pin,
            rsa_key_data=rsa_key,
            rsa_password=request.rsa_password,
            embed_mode=request.embed_mode,
            channel_key=resolved_channel_key,
            **dct_params,
        )

        stego_b64 = base64.b64encode(result.stego_image).decode("utf-8")

        output_format, color_mode, _ = _get_output_info(
            request.embed_mode, request.dct_output_format, request.dct_color_mode
        )

        # Get channel info for response
        channel_mode, channel_fingerprint = _get_channel_info(resolved_channel_key)

        return EncodeResponse(
            stego_image_base64=stego_b64,
            filename=result.filename,
            capacity_used_percent=result.capacity_percent,
            embed_mode=request.embed_mode,
            output_format=output_format,
            color_mode=color_mode,
            channel_mode=channel_mode,
            channel_fingerprint=channel_fingerprint,
            date_used=None,
            day_of_week=None,
        )

    except CapacityError as e:
        raise HTTPException(400, str(e))
    except StegasooError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/encode/file", response_model=EncodeResponse)
async def api_encode_file(request: EncodeFileRequest):
    """
    Encode a file into an image (JSON with base64).

    File data must be base64-encoded.

    v4.0.0: Added channel_key parameter for deployment isolation.
    v3.2.0: No date_str parameter needed - encode anytime!
    """
    # Validate mode
    if request.embed_mode == "dct" and not has_dct_support():
        raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")

    # Resolve channel key
    resolved_channel_key = _resolve_channel_key(request.channel_key)

    try:
        file_data = base64.b64decode(request.file_data_base64)
        ref_photo = base64.b64decode(request.reference_photo_base64)
        carrier = base64.b64decode(request.carrier_image_base64)
        rsa_key = base64.b64decode(request.rsa_key_base64) if request.rsa_key_base64 else None

        payload = FilePayload(
            data=file_data, filename=request.filename, mime_type=request.mime_type
        )

        # Get DCT parameters
        dct_params = _get_dct_params(
            request.embed_mode, request.dct_output_format, request.dct_color_mode
        )

        # v4.0.0: Include channel_key
        result = encode(
            message=payload,
            reference_photo=ref_photo,
            carrier_image=carrier,
            passphrase=request.passphrase,
            pin=request.pin,
            rsa_key_data=rsa_key,
            rsa_password=request.rsa_password,
            embed_mode=request.embed_mode,
            channel_key=resolved_channel_key,
            **dct_params,
        )

        stego_b64 = base64.b64encode(result.stego_image).decode("utf-8")

        output_format, color_mode, _ = _get_output_info(
            request.embed_mode, request.dct_output_format, request.dct_color_mode
        )

        # Get channel info for response
        channel_mode, channel_fingerprint = _get_channel_info(resolved_channel_key)

        return EncodeResponse(
            stego_image_base64=stego_b64,
            filename=result.filename,
            capacity_used_percent=result.capacity_percent,
            embed_mode=request.embed_mode,
            output_format=output_format,
            color_mode=color_mode,
            channel_mode=channel_mode,
            channel_fingerprint=channel_fingerprint,
            date_used=None,
            day_of_week=None,
        )

    except CapacityError as e:
        raise HTTPException(400, str(e))
    except StegasooError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================================
# ROUTES - DECODE (JSON)
# ============================================================================


@app.post("/decode", response_model=DecodeResponse)
async def api_decode(request: DecodeRequest):
    """
    Decode a message or file from a stego image.

    Returns payload_type to indicate if result is text or file.

    v4.0.0: Added channel_key parameter - must match encoding key.
    v3.2.0: No date_str parameter needed - decode anytime!
    """
    # Validate mode
    if request.embed_mode == "dct" and not has_dct_support():
        raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")

    # Resolve channel key
    resolved_channel_key = _resolve_channel_key(request.channel_key)

    try:
        stego = base64.b64decode(request.stego_image_base64)
        ref_photo = base64.b64decode(request.reference_photo_base64)
        rsa_key = base64.b64decode(request.rsa_key_base64) if request.rsa_key_base64 else None

        # v4.0.0: Include channel_key
        result = decode(
            stego_image=stego,
            reference_photo=ref_photo,
            passphrase=request.passphrase,
            pin=request.pin,
            rsa_key_data=rsa_key,
            rsa_password=request.rsa_password,
            embed_mode=request.embed_mode,
            channel_key=resolved_channel_key,
        )

        if result.is_file:
            return DecodeResponse(
                payload_type="file",
                file_data_base64=base64.b64encode(result.file_data).decode("utf-8"),
                filename=result.filename,
                mime_type=result.mime_type,
            )
        else:
            return DecodeResponse(payload_type="text", message=result.message)

    except DecryptionError as e:
        # Provide helpful error message for channel key issues
        error_msg = str(e)
        if "channel key" in error_msg.lower():
            raise HTTPException(401, error_msg)
        raise HTTPException(401, "Decryption failed. Check credentials.")
    except StegasooError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================================
# ROUTES - ENCODE/DECODE (MULTIPART)
# ============================================================================


@app.post("/encode/multipart")
async def api_encode_multipart(
    passphrase: str = Form(..., description="Passphrase (v3.2.0: renamed from day_phrase)"),
    reference_photo: UploadFile = File(...),
    carrier: UploadFile = File(...),
    message: str = Form(""),
    payload_file: UploadFile | None = File(None),
    pin: str = Form(""),
    rsa_key: UploadFile | None = File(None),
    rsa_key_qr: UploadFile | None = File(None),
    rsa_password: str = Form(""),
    # Channel key (v4.0.0)
    channel_key: str = Form(
        "auto", description="Channel key: 'auto'=server config, 'none'=public, 'XXXX-...'=explicit"
    ),
    embed_mode: str = Form("lsb"),
    dct_output_format: str = Form("png"),
    dct_color_mode: str = Form("grayscale"),
):
    """
    Encode using multipart form data (file uploads).

    Provide either 'message' (text) or 'payload_file' (binary file).
    RSA key can be provided as 'rsa_key' (.pem file) or 'rsa_key_qr' (QR code image).
    Returns the stego image directly with metadata headers.

    v4.0.0: Added channel_key parameter for deployment isolation.
            Use 'auto' for server config, 'none' for public mode.
    v3.2.0: No date_str parameter needed - encode anytime!
    """
    # Validate mode
    if embed_mode not in ("lsb", "dct"):
        raise HTTPException(400, "embed_mode must be 'lsb' or 'dct'")
    if embed_mode == "dct" and not has_dct_support():
        raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")

    # Validate DCT options
    if dct_output_format not in ("png", "jpeg"):
        raise HTTPException(400, "dct_output_format must be 'png' or 'jpeg'")
    if dct_color_mode not in ("grayscale", "color"):
        raise HTTPException(400, "dct_color_mode must be 'grayscale' or 'color'")

    # Resolve channel key (v4.0.0)
    # Form data: "auto" = use server config, "none" = public, otherwise explicit key
    if channel_key.lower() == "auto":
        resolved_channel_key = None  # Auto mode
    elif channel_key.lower() == "none":
        resolved_channel_key = ""  # Public mode
    else:
        resolved_channel_key = _resolve_channel_key(channel_key)

    try:
        ref_data = await reference_photo.read()
        carrier_data = await carrier.read()

        # Handle RSA key from .pem file or QR code image
        rsa_key_data = None
        rsa_key_from_qr = False

        if rsa_key and rsa_key.filename:
            rsa_key_data = await rsa_key.read()
        elif rsa_key_qr and rsa_key_qr.filename:
            if not HAS_QR_READ:
                raise HTTPException(
                    501, "QR code reading not available. Install pyzbar and libzbar."
                )
            qr_image_data = await rsa_key_qr.read()
            key_pem = extract_key_from_qr(qr_image_data)
            if not key_pem:
                raise HTTPException(400, "Could not extract RSA key from QR code image")
            rsa_key_data = key_pem.encode("utf-8")
            rsa_key_from_qr = True

        # QR code keys are never password-protected
        effective_password = None if rsa_key_from_qr else (rsa_password if rsa_password else None)

        # Determine payload
        if payload_file and payload_file.filename:
            file_data = await payload_file.read()
            payload = FilePayload(
                data=file_data, filename=payload_file.filename, mime_type=payload_file.content_type
            )
        elif message:
            payload = message
        else:
            raise HTTPException(400, "Must provide either 'message' or 'payload_file'")

        # Get DCT parameters
        dct_params = _get_dct_params(embed_mode, dct_output_format, dct_color_mode)

        # v4.0.0: Include channel_key
        result = encode(
            message=payload,
            reference_photo=ref_data,
            carrier_image=carrier_data,
            passphrase=passphrase,
            pin=pin,
            rsa_key_data=rsa_key_data,
            rsa_password=effective_password,
            embed_mode=embed_mode,
            channel_key=resolved_channel_key,
            **dct_params,
        )

        output_format, color_mode, mime_type = _get_output_info(
            embed_mode, dct_output_format, dct_color_mode
        )

        # Get channel info for headers
        channel_mode, channel_fingerprint = _get_channel_info(resolved_channel_key)

        headers = {
            "Content-Disposition": f"attachment; filename={result.filename}",
            "X-Stegasoo-Capacity-Percent": f"{result.capacity_percent:.1f}",
            "X-Stegasoo-Embed-Mode": embed_mode,
            "X-Stegasoo-Output-Format": output_format,
            "X-Stegasoo-Color-Mode": color_mode,
            "X-Stegasoo-Channel-Mode": channel_mode,
            "X-Stegasoo-Version": __version__,
        }

        if channel_fingerprint:
            headers["X-Stegasoo-Channel-Fingerprint"] = channel_fingerprint

        return Response(
            content=result.stego_image,
            media_type=mime_type,
            headers=headers,
        )

    except CapacityError as e:
        raise HTTPException(400, str(e))
    except StegasooError as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/decode/multipart", response_model=DecodeResponse)
async def api_decode_multipart(
    passphrase: str = Form(..., description="Passphrase (v3.2.0: renamed from day_phrase)"),
    reference_photo: UploadFile = File(...),
    stego_image: UploadFile = File(...),
    pin: str = Form(""),
    rsa_key: UploadFile | None = File(None),
    rsa_key_qr: UploadFile | None = File(None),
    rsa_password: str = Form(""),
    # Channel key (v4.0.0)
    channel_key: str = Form(
        "auto", description="Channel key: 'auto'=server config, 'none'=public, 'XXXX-...'=explicit"
    ),
    embed_mode: str = Form("auto"),
):
    """
    Decode using multipart form data (file uploads).

    RSA key can be provided as 'rsa_key' (.pem file) or 'rsa_key_qr' (QR code image).
    Returns JSON with payload_type indicating text or file.

    v4.0.0: Added channel_key parameter - must match what was used for encoding.
            Use 'auto' for server config, 'none' for public mode.
    v3.2.0: No date_str parameter needed - decode anytime!
    """
    # Validate mode
    if embed_mode not in ("auto", "lsb", "dct"):
        raise HTTPException(400, "embed_mode must be 'auto', 'lsb', or 'dct'")
    if embed_mode == "dct" and not has_dct_support():
        raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")

    # Resolve channel key (v4.0.0)
    if channel_key.lower() == "auto":
        resolved_channel_key = None  # Auto mode
    elif channel_key.lower() == "none":
        resolved_channel_key = ""  # Public mode
    else:
        resolved_channel_key = _resolve_channel_key(channel_key)

    try:
        ref_data = await reference_photo.read()
        stego_data = await stego_image.read()

        # Handle RSA key from .pem file or QR code image
        rsa_key_data = None
        rsa_key_from_qr = False

        if rsa_key and rsa_key.filename:
            rsa_key_data = await rsa_key.read()
        elif rsa_key_qr and rsa_key_qr.filename:
            if not HAS_QR_READ:
                raise HTTPException(
                    501, "QR code reading not available. Install pyzbar and libzbar."
                )
            qr_image_data = await rsa_key_qr.read()
            key_pem = extract_key_from_qr(qr_image_data)
            if not key_pem:
                raise HTTPException(400, "Could not extract RSA key from QR code image")
            rsa_key_data = key_pem.encode("utf-8")
            rsa_key_from_qr = True

        # QR code keys are never password-protected
        effective_password = None if rsa_key_from_qr else (rsa_password if rsa_password else None)

        # v4.0.0: Include channel_key
        result = decode(
            stego_image=stego_data,
            reference_photo=ref_data,
            passphrase=passphrase,
            pin=pin,
            rsa_key_data=rsa_key_data,
            rsa_password=effective_password,
            embed_mode=embed_mode,
            channel_key=resolved_channel_key,
        )

        if result.is_file:
            return DecodeResponse(
                payload_type="file",
                file_data_base64=base64.b64encode(result.file_data).decode("utf-8"),
                filename=result.filename,
                mime_type=result.mime_type,
            )
        else:
            return DecodeResponse(payload_type="text", message=result.message)

    except DecryptionError as e:
        error_msg = str(e)
        if "channel key" in error_msg.lower():
            raise HTTPException(401, error_msg)
        raise HTTPException(401, "Decryption failed. Check credentials.")
    except StegasooError as e:
        raise HTTPException(400, str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================================
# ROUTES - IMAGE INFO
# ============================================================================


@app.post("/image/info", response_model=ImageInfoResponse)
async def api_image_info(
    image: UploadFile = File(...),
    include_modes: bool = Query(True, description="Include capacity by mode (v3.0+)"),
):
    """
    Get information about an image's capacity.

    Optionally includes capacity for both LSB and DCT modes.
    """
    try:
        image_data = await image.read()

        result = validate_image(image_data, check_size=False)
        if not result.is_valid:
            raise HTTPException(400, result.error_message)

        capacity = calculate_capacity_by_mode(image_data, "lsb")

        response = ImageInfoResponse(
            width=result.details["width"],
            height=result.details["height"],
            pixels=result.details["pixels"],
            capacity_bytes=capacity,
            capacity_kb=capacity // 1024,
        )

        if include_modes:
            comparison = compare_modes(image_data)
            response.modes = {
                "lsb": ModeCapacity(
                    capacity_bytes=comparison["lsb"]["capacity_bytes"],
                    capacity_kb=round(comparison["lsb"]["capacity_kb"], 1),
                    available=True,
                    output_format=comparison["lsb"]["output"],
                ),
                "dct": ModeCapacity(
                    capacity_bytes=comparison["dct"]["capacity_bytes"],
                    capacity_kb=round(comparison["dct"]["capacity_kb"], 1),
                    available=comparison["dct"]["available"],
                    output_format="PNG/JPEG (grayscale or color)",
                ),
            }

        return response

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


# ============================================================================
# ERROR HANDLERS
# ============================================================================


@app.exception_handler(StegasooError)
async def stegasoo_error_handler(request, exc):
    return JSONResponse(status_code=400, content={"error": type(exc).__name__, "detail": str(exc)})


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
