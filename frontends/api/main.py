#!/usr/bin/env python3
"""
Stegasoo REST API

FastAPI-based REST API for steganography operations.
Designed for integration with other services and automation.
"""

import io
import sys
import base64
from pathlib import Path
from typing import Optional
from datetime import date

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.responses import Response, JSONResponse
from pydantic import BaseModel, Field

# Add parent to path for development
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))

import stegasoo
from stegasoo import (
    encode, decode, generate_credentials,
    validate_image, calculate_capacity,
    get_day_from_date,
    DAY_NAMES, __version__,
    StegasooError, DecryptionError, CapacityError,
    has_argon2,
)
from stegasoo.constants import (
    MIN_PIN_LENGTH, MAX_PIN_LENGTH,
    MIN_PHRASE_WORDS, MAX_PHRASE_WORDS,
    VALID_RSA_SIZES,
)


# ============================================================================
# FASTAPI APP
# ============================================================================

app = FastAPI(
    title="Stegasoo API",
    description="Secure steganography with hybrid authentication",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ============================================================================
# MODELS
# ============================================================================

class GenerateRequest(BaseModel):
    use_pin: bool = True
    use_rsa: bool = False
    pin_length: int = Field(default=6, ge=MIN_PIN_LENGTH, le=MAX_PIN_LENGTH)
    rsa_bits: int = Field(default=2048)
    words_per_phrase: int = Field(default=3, ge=MIN_PHRASE_WORDS, le=MAX_PHRASE_WORDS)


class GenerateResponse(BaseModel):
    phrases: dict[str, str]
    pin: Optional[str] = None
    rsa_key_pem: Optional[str] = None
    entropy: dict[str, int]


class EncodeRequest(BaseModel):
    message: str
    reference_photo_base64: str
    carrier_image_base64: str
    day_phrase: str
    pin: str = ""
    rsa_key_base64: Optional[str] = None
    rsa_password: Optional[str] = None
    date_str: Optional[str] = None


class EncodeResponse(BaseModel):
    stego_image_base64: str
    filename: str
    capacity_used_percent: float
    date_used: str
    day_of_week: str


class DecodeRequest(BaseModel):
    stego_image_base64: str
    reference_photo_base64: str
    day_phrase: str
    pin: str = ""
    rsa_key_base64: Optional[str] = None
    rsa_password: Optional[str] = None


class DecodeResponse(BaseModel):
    message: str


class ImageInfoResponse(BaseModel):
    width: int
    height: int
    pixels: int
    capacity_bytes: int
    capacity_kb: int


class StatusResponse(BaseModel):
    version: str
    has_argon2: bool
    day_names: list[str]


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None


# ============================================================================
# ROUTES
# ============================================================================

@app.get("/", response_model=StatusResponse)
async def root():
    """Get API status and configuration."""
    return StatusResponse(
        version=__version__,
        has_argon2=has_argon2(),
        day_names=list(DAY_NAMES)
    )


@app.post("/generate", response_model=GenerateResponse)
async def api_generate(request: GenerateRequest):
    """
    Generate credentials for encoding/decoding.
    
    At least one of use_pin or use_rsa must be True.
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
            words_per_phrase=request.words_per_phrase
        )
        
        return GenerateResponse(
            phrases=creds.phrases,
            pin=creds.pin,
            rsa_key_pem=creds.rsa_key_pem,
            entropy={
                "phrase": creds.phrase_entropy,
                "pin": creds.pin_entropy,
                "rsa": creds.rsa_entropy,
                "total": creds.total_entropy
            }
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/encode", response_model=EncodeResponse)
async def api_encode(request: EncodeRequest):
    """
    Encode a secret message into an image.
    
    Images must be base64-encoded. Returns base64-encoded stego image.
    """
    try:
        ref_photo = base64.b64decode(request.reference_photo_base64)
        carrier = base64.b64decode(request.carrier_image_base64)
        rsa_key = base64.b64decode(request.rsa_key_base64) if request.rsa_key_base64 else None
        
        result = encode(
            message=request.message,
            reference_photo=ref_photo,
            carrier_image=carrier,
            day_phrase=request.day_phrase,
            pin=request.pin,
            rsa_key_data=rsa_key,
            rsa_password=request.rsa_password,
            date_str=request.date_str
        )
        
        stego_b64 = base64.b64encode(result.stego_image).decode('utf-8')
        
        # Get day of week from the date used
        day_of_week = get_day_from_date(result.date_used)
        
        return EncodeResponse(
            stego_image_base64=stego_b64,
            filename=result.filename,
            capacity_used_percent=result.capacity_percent,
            date_used=result.date_used,
            day_of_week=day_of_week
        )
        
    except CapacityError as e:
        raise HTTPException(400, str(e))
    except StegasooError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/decode", response_model=DecodeResponse)
async def api_decode(request: DecodeRequest):
    """
    Decode a secret message from a stego image.
    
    Images must be base64-encoded.
    """
    try:
        stego = base64.b64decode(request.stego_image_base64)
        ref_photo = base64.b64decode(request.reference_photo_base64)
        rsa_key = base64.b64decode(request.rsa_key_base64) if request.rsa_key_base64 else None
        
        message = decode(
            stego_image=stego,
            reference_photo=ref_photo,
            day_phrase=request.day_phrase,
            pin=request.pin,
            rsa_key_data=rsa_key,
            rsa_password=request.rsa_password
        )
        
        return DecodeResponse(message=message)
        
    except DecryptionError as e:
        raise HTTPException(401, "Decryption failed. Check credentials.")
    except StegasooError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/encode/multipart")
async def api_encode_multipart(
    message: str = Form(...),
    day_phrase: str = Form(...),
    reference_photo: UploadFile = File(...),
    carrier: UploadFile = File(...),
    pin: str = Form(""),
    rsa_key: Optional[UploadFile] = File(None),
    rsa_password: str = Form(""),
    date_str: str = Form("")
):
    """
    Encode using multipart form data (file uploads).
    
    Returns the stego image directly as PNG with metadata headers.
    """
    try:
        ref_data = await reference_photo.read()
        carrier_data = await carrier.read()
        rsa_key_data = await rsa_key.read() if rsa_key else None
        
        result = encode(
            message=message,
            reference_photo=ref_data,
            carrier_image=carrier_data,
            day_phrase=day_phrase,
            pin=pin,
            rsa_key_data=rsa_key_data,
            rsa_password=rsa_password if rsa_password else None,
            date_str=date_str if date_str else None
        )
        
        # Get day of week from the date used
        day_of_week = get_day_from_date(result.date_used)
        
        return Response(
            content=result.stego_image,
            media_type="image/png",
            headers={
                "Content-Disposition": f"attachment; filename={result.filename}",
                "X-Stegasoo-Date": result.date_used,
                "X-Stegasoo-Day": day_of_week,
                "X-Stegasoo-Capacity-Percent": f"{result.capacity_percent:.1f}"
            }
        )
        
    except CapacityError as e:
        raise HTTPException(400, str(e))
    except StegasooError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/decode/multipart", response_model=DecodeResponse)
async def api_decode_multipart(
    day_phrase: str = Form(...),
    reference_photo: UploadFile = File(...),
    stego_image: UploadFile = File(...),
    pin: str = Form(""),
    rsa_key: Optional[UploadFile] = File(None),
    rsa_password: str = Form("")
):
    """
    Decode using multipart form data (file uploads).
    """
    try:
        ref_data = await reference_photo.read()
        stego_data = await stego_image.read()
        rsa_key_data = await rsa_key.read() if rsa_key else None
        
        message = decode(
            stego_image=stego_data,
            reference_photo=ref_data,
            day_phrase=day_phrase,
            pin=pin,
            rsa_key_data=rsa_key_data,
            rsa_password=rsa_password if rsa_password else None
        )
        
        return DecodeResponse(message=message)
        
    except DecryptionError:
        raise HTTPException(401, "Decryption failed. Check credentials.")
    except StegasooError as e:
        raise HTTPException(400, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/image/info", response_model=ImageInfoResponse)
async def api_image_info(image: UploadFile = File(...)):
    """Get information about an image's capacity."""
    try:
        image_data = await image.read()
        
        result = validate_image(image_data, check_size=False)
        if not result.is_valid:
            raise HTTPException(400, result.error_message)
        
        capacity = calculate_capacity(image_data)
        
        return ImageInfoResponse(
            width=result.details['width'],
            height=result.details['height'],
            pixels=result.details['pixels'],
            capacity_bytes=capacity,
            capacity_kb=capacity // 1024
        )
        
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
