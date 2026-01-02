#!/usr/bin/env python3
"""
Stegasoo REST API (v4.0.0)

FastAPI-based REST API for steganography operations.
Supports both text messages and file embedding.

CHANGES in v4.0.0:
- Updated from v3.2.0 with no functional API changes
- Internal: JPEG normalization for jpegio compatibility
- Internal: Python 3.12 recommended

CHANGES in v3.2.0:
- Removed date dependency from all operations
- Renamed day_phrase → passphrase
- No date_str parameters needed
- Simplified API for asynchronous communications

NEW in v3.0: LSB and DCT embedding modes.
NEW in v3.0.1: DCT color mode and JPEG output format.
"""

import io
import sys
import base64
from pathlib import Path
from typing import Optional, Literal
from datetime import date

from fastapi import FastAPI, HTTPException, UploadFile, File, Form, Query
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import stegasoo
from stegasoo import (
    encode, decode, generate_credentials,
    validate_image,
    __version__,
    StegasooError, DecryptionError, CapacityError,
    has_argon2,
    FilePayload,
    MAX_FILE_PAYLOAD_SIZE,
    # Embedding modes
    EMBED_MODE_LSB,
    EMBED_MODE_DCT,
    EMBED_MODE_AUTO,
    has_dct_support,
    compare_modes,
    will_fit_by_mode,
    calculate_capacity_by_mode,
)
from stegasoo.constants import (
    MIN_PIN_LENGTH, MAX_PIN_LENGTH,
    MIN_PASSPHRASE_WORDS, MAX_PASSPHRASE_WORDS,
    DEFAULT_PASSPHRASE_WORDS,
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

- **Python 3.12 recommended** - jpegio compatibility improvements
- **JPEG normalization** - Handles quality=100 images automatically

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
        description="Words per passphrase (v3.2.0: default increased to 4)"
    )


class GenerateResponse(BaseModel):
    passphrase: str = Field(description="Single passphrase (v3.2.0: no daily rotation)")
    pin: Optional[str] = None
    rsa_key_pem: Optional[str] = None
    entropy: dict[str, int]
    # Legacy field for compatibility
    phrases: Optional[dict[str, str]] = Field(
        default=None,
        description="Deprecated: Use 'passphrase' instead"
    )


class EncodeRequest(BaseModel):
    message: str
    reference_photo_base64: str
    carrier_image_base64: str
    passphrase: str = Field(description="Passphrase (v3.2.0: renamed from day_phrase)")
    pin: str = ""
    rsa_key_base64: Optional[str] = None
    rsa_password: Optional[str] = None
    # date_str removed in v3.2.0
    embed_mode: EmbedModeType = Field(
        default="lsb",
        description="Embedding mode: 'lsb' (default, color) or 'dct' (requires scipy)"
    )
    # NEW in v3.0.1
    dct_output_format: DctOutputFormatType = Field(
        default="png",
        description="DCT output format: 'png' (lossless) or 'jpeg' (smaller). Only applies to DCT mode."
    )
    dct_color_mode: DctColorModeType = Field(
        default="grayscale",
        description="DCT color mode: 'grayscale' (default) or 'color' (preserves colors). Only applies to DCT mode."
    )


class EncodeFileRequest(BaseModel):
    """Request for embedding a file (base64-encoded)."""
    file_data_base64: str
    filename: str
    mime_type: Optional[str] = None
    reference_photo_base64: str
    carrier_image_base64: str
    passphrase: str = Field(description="Passphrase (v3.2.0: renamed from day_phrase)")
    pin: str = ""
    rsa_key_base64: Optional[str] = None
    rsa_password: Optional[str] = None
    # date_str removed in v3.2.0
    embed_mode: EmbedModeType = Field(
        default="lsb",
        description="Embedding mode: 'lsb' (default, color) or 'dct' (requires scipy)"
    )
    # NEW in v3.0.1
    dct_output_format: DctOutputFormatType = Field(
        default="png",
        description="DCT output format: 'png' (lossless) or 'jpeg' (smaller). Only applies to DCT mode."
    )
    dct_color_mode: DctColorModeType = Field(
        default="grayscale",
        description="DCT color mode: 'grayscale' (default) or 'color' (preserves colors). Only applies to DCT mode."
    )


class EncodeResponse(BaseModel):
    stego_image_base64: str
    filename: str
    capacity_used_percent: float
    embed_mode: str = Field(description="Embedding mode used: 'lsb' or 'dct'")
    # NEW in v3.0.1
    output_format: str = Field(
        default="png",
        description="Output format: 'png' or 'jpeg' (for DCT mode)"
    )
    color_mode: str = Field(
        default="color",
        description="Color mode: 'color' (LSB/DCT color) or 'grayscale' (DCT grayscale)"
    )
    # Legacy fields (v3.2.0: no longer used in crypto)
    date_used: Optional[str] = Field(
        default=None,
        description="Deprecated: Date no longer used in v3.2.0"
    )
    day_of_week: Optional[str] = Field(
        default=None,
        description="Deprecated: Date no longer used in v3.2.0"
    )


class DecodeRequest(BaseModel):
    stego_image_base64: str
    reference_photo_base64: str
    passphrase: str = Field(description="Passphrase (v3.2.0: renamed from day_phrase)")
    pin: str = ""
    rsa_key_base64: Optional[str] = None
    rsa_password: Optional[str] = None
    embed_mode: ExtractModeType = Field(
        default="auto",
        description="Extraction mode: 'auto' (default), 'lsb', or 'dct'"
    )


class DecodeResponse(BaseModel):
    """Response for decode - can be text or file."""
    payload_type: str  # 'text' or 'file'
    message: Optional[str] = None  # For text
    file_data_base64: Optional[str] = None  # For file (base64-encoded)
    filename: Optional[str] = None  # For file
    mime_type: Optional[str] = None  # For file


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
    # NEW in v3.0
    modes: Optional[dict[str, ModeCapacity]] = Field(
        default=None,
        description="Capacity by embedding mode (v3.0+)"
    )


class CompareModesRequest(BaseModel):
    """Request for comparing embedding modes."""
    carrier_image_base64: str
    payload_size: Optional[int] = Field(
        default=None,
        description="Optional payload size to check if it fits"
    )


class CompareModesResponse(BaseModel):
    """Response comparing LSB and DCT modes."""
    width: int
    height: int
    lsb: dict
    dct: dict
    payload_check: Optional[dict] = None
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


class ModesResponse(BaseModel):
    """Response showing available embedding modes."""
    lsb: dict
    dct: DctModeInfo


class StatusResponse(BaseModel):
    version: str
    has_argon2: bool
    has_qrcode_read: bool
    has_dct: bool
    max_payload_kb: int
    available_modes: list[str]
    # NEW in v3.0.1
    dct_features: Optional[dict] = Field(
        default=None,
        description="DCT mode features (v3.0.1+)"
    )
    # NEW in v3.2.0
    breaking_changes: dict = Field(
        description="v3.2.0 breaking changes"
    )


class QrExtractResponse(BaseModel):
    success: bool
    key_pem: Optional[str] = None
    error: Optional[str] = None


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
    detail: Optional[str] = None


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
    
    return StatusResponse(
        version=__version__,
        has_argon2=has_argon2(),
        has_qrcode_read=HAS_QR_READ,
        has_dct=has_dct_support(),
        max_payload_kb=MAX_FILE_PAYLOAD_SIZE // 1024,
        available_modes=available_modes,
        dct_features=dct_features,
        breaking_changes={
            "date_removed": "No date_str parameter needed - encode/decode anytime",
            "passphrase_renamed": "day_phrase → passphrase (single passphrase, no daily rotation)",
            "format_version": 4,
            "backward_compatible": False,
        }
    )


@app.get("/modes", response_model=ModesResponse)
async def api_modes():
    """
    Get available embedding modes and their status.
    
    NEW in v3.0: Shows LSB and DCT mode availability.
    NEW in v3.0.1: Shows DCT color modes and output formats.
    """
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
        )
    )


@app.post("/compare", response_model=CompareModesResponse)
async def api_compare_modes(request: CompareModesRequest):
    """
    Compare LSB and DCT embedding modes for a carrier image.
    
    NEW in v3.0: Returns capacity for both modes and recommendation.
    Optionally checks if a specific payload size would fit.
    """
    try:
        carrier = base64.b64decode(request.carrier_image_base64)
        comparison = compare_modes(carrier)
        
        response = CompareModesResponse(
            width=comparison['width'],
            height=comparison['height'],
            lsb={
                "capacity_bytes": comparison['lsb']['capacity_bytes'],
                "capacity_kb": round(comparison['lsb']['capacity_kb'], 1),
                "available": True,
                "output_format": comparison['lsb']['output'],
            },
            dct={
                "capacity_bytes": comparison['dct']['capacity_bytes'],
                "capacity_kb": round(comparison['dct']['capacity_kb'], 1),
                "available": comparison['dct']['available'],
                "output_formats": ["png", "jpeg"],
                "color_modes": ["grayscale", "color"],
                "ratio_vs_lsb_percent": round(comparison['dct']['ratio_vs_lsb'], 1),
            },
            recommendation="lsb" if not comparison['dct']['available'] else "dct for stealth, lsb for capacity"
        )
        
        if request.payload_size:
            fits_lsb = request.payload_size <= comparison['lsb']['capacity_bytes']
            fits_dct = request.payload_size <= comparison['dct']['capacity_bytes']
            
            response.payload_check = {
                "size_bytes": request.payload_size,
                "fits_lsb": fits_lsb,
                "fits_dct": fits_dct,
            }
            
            # Update recommendation based on payload
            if fits_dct and comparison['dct']['available']:
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
    
    NEW in v3.0: Supports both LSB and DCT modes.
    """
    try:
        # Validate mode
        if request.embed_mode == "dct" and not has_dct_support():
            raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")
        
        carrier = base64.b64decode(request.carrier_image_base64)
        result = will_fit_by_mode(request.payload_size, carrier, embed_mode=request.embed_mode)
        
        return WillFitResponse(
            fits=result['fits'],
            payload_size=result['payload_size'],
            capacity=result['capacity'],
            usage_percent=round(result['usage_percent'], 1),
            headroom=result['headroom'],
            mode=request.embed_mode
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
        raise HTTPException(
            501,
            "QR code reading not available. Install pyzbar and libzbar."
        )
    
    try:
        image_data = await qr_image.read()
        key_pem = extract_key_from_qr(image_data)
        
        if key_pem:
            return QrExtractResponse(success=True, key_pem=key_pem)
        else:
            return QrExtractResponse(
                success=False,
                error="No valid RSA key found in QR code"
            )
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
        # v3.2.0: Call with passphrase_words parameter
        creds = generate_credentials(
            use_pin=request.use_pin,
            use_rsa=request.use_rsa,
            pin_length=request.pin_length,
            rsa_bits=request.rsa_bits,
            passphrase_words=request.words_per_passphrase,  # Map API field to library parameter
        )
        
        return GenerateResponse(
            passphrase=creds.passphrase,  # v3.2.0: Single passphrase
            pin=creds.pin,
            rsa_key_pem=creds.rsa_key_pem,
            entropy={
                "passphrase": creds.passphrase_entropy,
                "pin": creds.pin_entropy,
                "rsa": creds.rsa_entropy,
                "total": creds.total_entropy
            },
            phrases=None  # Legacy field removed
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
    
    v3.2.0: No date_str parameter needed - encode anytime!
    
    NEW in v3.0: Supports embed_mode parameter ('lsb' or 'dct').
    NEW in v3.0.1: Supports dct_output_format ('png' or 'jpeg') and dct_color_mode ('grayscale' or 'color').
    """
    # Validate mode
    if request.embed_mode == "dct" and not has_dct_support():
        raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")
    
    try:
        ref_photo = base64.b64decode(request.reference_photo_base64)
        carrier = base64.b64decode(request.carrier_image_base64)
        rsa_key = base64.b64decode(request.rsa_key_base64) if request.rsa_key_base64 else None
        
        # Get DCT parameters
        dct_params = _get_dct_params(
            request.embed_mode,
            request.dct_output_format,
            request.dct_color_mode
        )
        
        # v3.2.0: No date_str parameter
        result = encode(
            message=request.message,
            reference_photo=ref_photo,
            carrier_image=carrier,
            passphrase=request.passphrase,  # v3.2.0: Renamed from day_phrase
            pin=request.pin,
            rsa_key_data=rsa_key,
            rsa_password=request.rsa_password,
            # date_str removed in v3.2.0
            embed_mode=request.embed_mode,
            **dct_params,
        )
        
        stego_b64 = base64.b64encode(result.stego_image).decode('utf-8')
        
        output_format, color_mode, _ = _get_output_info(
            request.embed_mode,
            request.dct_output_format,
            request.dct_color_mode
        )
        
        return EncodeResponse(
            stego_image_base64=stego_b64,
            filename=result.filename,
            capacity_used_percent=result.capacity_percent,
            embed_mode=request.embed_mode,
            output_format=output_format,
            color_mode=color_mode,
            date_used=None,  # v3.2.0: No longer used
            day_of_week=None,  # v3.2.0: No longer used
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
    
    v3.2.0: No date_str parameter needed - encode anytime!
    
    NEW in v3.0: Supports embed_mode parameter ('lsb' or 'dct').
    NEW in v3.0.1: Supports dct_output_format and dct_color_mode.
    """
    # Validate mode
    if request.embed_mode == "dct" and not has_dct_support():
        raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")
    
    try:
        file_data = base64.b64decode(request.file_data_base64)
        ref_photo = base64.b64decode(request.reference_photo_base64)
        carrier = base64.b64decode(request.carrier_image_base64)
        rsa_key = base64.b64decode(request.rsa_key_base64) if request.rsa_key_base64 else None
        
        payload = FilePayload(
            data=file_data,
            filename=request.filename,
            mime_type=request.mime_type
        )
        
        # Get DCT parameters
        dct_params = _get_dct_params(
            request.embed_mode,
            request.dct_output_format,
            request.dct_color_mode
        )
        
        # v3.2.0: No date_str parameter
        result = encode(
            message=payload,
            reference_photo=ref_photo,
            carrier_image=carrier,
            passphrase=request.passphrase,  # v3.2.0: Renamed from day_phrase
            pin=request.pin,
            rsa_key_data=rsa_key,
            rsa_password=request.rsa_password,
            # date_str removed in v3.2.0
            embed_mode=request.embed_mode,
            **dct_params,
        )
        
        stego_b64 = base64.b64encode(result.stego_image).decode('utf-8')
        
        output_format, color_mode, _ = _get_output_info(
            request.embed_mode,
            request.dct_output_format,
            request.dct_color_mode
        )
        
        return EncodeResponse(
            stego_image_base64=stego_b64,
            filename=result.filename,
            capacity_used_percent=result.capacity_percent,
            embed_mode=request.embed_mode,
            output_format=output_format,
            color_mode=color_mode,
            date_used=None,  # v3.2.0: No longer used
            day_of_week=None,  # v3.2.0: No longer used
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
    
    v3.2.0: No date_str parameter needed - decode anytime!
    
    NEW in v3.0: Supports embed_mode parameter ('auto', 'lsb', or 'dct').
    With 'auto' (default), tries LSB first then DCT.
    
    Note: Extraction works regardless of whether the image was created with
    color mode or grayscale mode - both use the same Y channel for data.
    """
    # Validate mode
    if request.embed_mode == "dct" and not has_dct_support():
        raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")
    
    try:
        stego = base64.b64decode(request.stego_image_base64)
        ref_photo = base64.b64decode(request.reference_photo_base64)
        rsa_key = base64.b64decode(request.rsa_key_base64) if request.rsa_key_base64 else None
        
        # v3.2.0: No date_str parameter
        result = decode(
            stego_image=stego,
            reference_photo=ref_photo,
            passphrase=request.passphrase,  # v3.2.0: Renamed from day_phrase
            pin=request.pin,
            rsa_key_data=rsa_key,
            rsa_password=request.rsa_password,
            embed_mode=request.embed_mode,
        )
        
        if result.is_file:
            return DecodeResponse(
                payload_type='file',
                file_data_base64=base64.b64encode(result.file_data).decode('utf-8'),
                filename=result.filename,
                mime_type=result.mime_type
            )
        else:
            return DecodeResponse(
                payload_type='text',
                message=result.message
            )
        
    except DecryptionError as e:
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
    payload_file: Optional[UploadFile] = File(None),
    pin: str = Form(""),
    rsa_key: Optional[UploadFile] = File(None),
    rsa_key_qr: Optional[UploadFile] = File(None),
    rsa_password: str = Form(""),
    # date_str removed in v3.2.0
    embed_mode: str = Form("lsb"),
    # NEW in v3.0.1
    dct_output_format: str = Form("png"),
    dct_color_mode: str = Form("grayscale"),
):
    """
    Encode using multipart form data (file uploads).
    
    Provide either 'message' (text) or 'payload_file' (binary file).
    RSA key can be provided as 'rsa_key' (.pem file) or 'rsa_key_qr' (QR code image).
    Returns the stego image directly with metadata headers.
    
    v3.2.0: No date_str parameter needed - encode anytime!
    
    NEW in v3.0: Supports embed_mode parameter ('lsb' or 'dct').
    NEW in v3.0.1: Supports dct_output_format ('png' or 'jpeg') and dct_color_mode ('grayscale' or 'color').
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
                    501,
                    "QR code reading not available. Install pyzbar and libzbar."
                )
            qr_image_data = await rsa_key_qr.read()
            key_pem = extract_key_from_qr(qr_image_data)
            if not key_pem:
                raise HTTPException(400, "Could not extract RSA key from QR code image")
            rsa_key_data = key_pem.encode('utf-8')
            rsa_key_from_qr = True
        
        # QR code keys are never password-protected
        effective_password = None if rsa_key_from_qr else (rsa_password if rsa_password else None)
        
        # Determine payload
        if payload_file and payload_file.filename:
            file_data = await payload_file.read()
            payload = FilePayload(
                data=file_data,
                filename=payload_file.filename,
                mime_type=payload_file.content_type
            )
        elif message:
            payload = message
        else:
            raise HTTPException(400, "Must provide either 'message' or 'payload_file'")
        
        # Get DCT parameters
        dct_params = _get_dct_params(embed_mode, dct_output_format, dct_color_mode)
        
        # v3.2.0: No date_str parameter
        result = encode(
            message=payload,
            reference_photo=ref_data,
            carrier_image=carrier_data,
            passphrase=passphrase,  # v3.2.0: Renamed from day_phrase
            pin=pin,
            rsa_key_data=rsa_key_data,
            rsa_password=effective_password,
            # date_str removed in v3.2.0
            embed_mode=embed_mode,
            **dct_params,
        )
        
        output_format, color_mode, mime_type = _get_output_info(
            embed_mode, dct_output_format, dct_color_mode
        )
        
        return Response(
            content=result.stego_image,
            media_type=mime_type,
            headers={
                "Content-Disposition": f"attachment; filename={result.filename}",
                "X-Stegasoo-Capacity-Percent": f"{result.capacity_percent:.1f}",
                "X-Stegasoo-Embed-Mode": embed_mode,
                "X-Stegasoo-Output-Format": output_format,
                "X-Stegasoo-Color-Mode": color_mode,
                "X-Stegasoo-Version": __version__,
            }
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
    rsa_key: Optional[UploadFile] = File(None),
    rsa_key_qr: Optional[UploadFile] = File(None),
    rsa_password: str = Form(""),
    embed_mode: str = Form("auto"),
):
    """
    Decode using multipart form data (file uploads).
    
    RSA key can be provided as 'rsa_key' (.pem file) or 'rsa_key_qr' (QR code image).
    Returns JSON with payload_type indicating text or file.
    
    v3.2.0: No date_str parameter needed - decode anytime!
    
    NEW in v3.0: Supports embed_mode parameter ('auto', 'lsb', or 'dct').
    
    Note: Extraction works the same regardless of color mode used during encoding.
    """
    # Validate mode
    if embed_mode not in ("auto", "lsb", "dct"):
        raise HTTPException(400, "embed_mode must be 'auto', 'lsb', or 'dct'")
    if embed_mode == "dct" and not has_dct_support():
        raise HTTPException(400, "DCT mode requires scipy. Install with: pip install scipy")
    
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
                    501,
                    "QR code reading not available. Install pyzbar and libzbar."
                )
            qr_image_data = await rsa_key_qr.read()
            key_pem = extract_key_from_qr(qr_image_data)
            if not key_pem:
                raise HTTPException(400, "Could not extract RSA key from QR code image")
            rsa_key_data = key_pem.encode('utf-8')
            rsa_key_from_qr = True
        
        # QR code keys are never password-protected
        effective_password = None if rsa_key_from_qr else (rsa_password if rsa_password else None)
        
        # v3.2.0: No date_str parameter
        result = decode(
            stego_image=stego_data,
            reference_photo=ref_data,
            passphrase=passphrase,  # v3.2.0: Renamed from day_phrase
            pin=pin,
            rsa_key_data=rsa_key_data,
            rsa_password=effective_password,
            embed_mode=embed_mode,
        )
        
        if result.is_file:
            return DecodeResponse(
                payload_type='file',
                file_data_base64=base64.b64encode(result.file_data).decode('utf-8'),
                filename=result.filename,
                mime_type=result.mime_type
            )
        else:
            return DecodeResponse(
                payload_type='text',
                message=result.message
            )
        
    except DecryptionError:
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
    include_modes: bool = Query(True, description="Include capacity by mode (v3.0+)")
):
    """
    Get information about an image's capacity.
    
    NEW in v3.0: Optionally includes capacity for both LSB and DCT modes.
    """
    try:
        image_data = await image.read()
        
        result = validate_image(image_data, check_size=False)
        if not result.is_valid:
            raise HTTPException(400, result.error_message)
        
        capacity = calculate_capacity_by_mode(image_data, 'lsb')
        
        response = ImageInfoResponse(
            width=result.details['width'],
            height=result.details['height'],
            pixels=result.details['pixels'],
            capacity_bytes=capacity,
            capacity_kb=capacity // 1024
        )
        
        # NEW in v3.0 - include mode comparison
        if include_modes:
            comparison = compare_modes(image_data)
            response.modes = {
                "lsb": ModeCapacity(
                    capacity_bytes=comparison['lsb']['capacity_bytes'],
                    capacity_kb=round(comparison['lsb']['capacity_kb'], 1),
                    available=True,
                    output_format=comparison['lsb']['output'],
                ),
                "dct": ModeCapacity(
                    capacity_bytes=comparison['dct']['capacity_bytes'],
                    capacity_kb=round(comparison['dct']['capacity_kb'], 1),
                    available=comparison['dct']['available'],
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
    return JSONResponse(
        status_code=400,
        content={"error": type(exc).__name__, "detail": str(exc)}
    )


# ============================================================================
# MAIN
# ============================================================================

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
