#!/usr/bin/env python3
"""
Stegasoo Subprocess Worker (v4.0.0)

This script runs in a subprocess and handles encode/decode operations.
If it crashes due to jpeglib/scipy issues, the parent Flask process survives.

CHANGES in v4.0.0:
- Added channel_key support for encode/decode operations
- New channel_status operation

Communication is via JSON over stdin/stdout:
- Input: JSON object with operation parameters
- Output: JSON object with results or error

Usage:
    echo '{"operation": "encode", ...}' | python stego_worker.py
"""

import base64
import json
import sys
import traceback
from pathlib import Path

# Ensure stegasoo is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent))


def _resolve_channel_key(channel_key_param):
    """
    Resolve channel_key parameter to value for stegasoo.

    Args:
        channel_key_param: 'auto', 'none', explicit key, or None

    Returns:
        None (auto), "" (public), or explicit key string
    """
    if channel_key_param is None or channel_key_param == "auto":
        return None  # Auto mode - use server config
    elif channel_key_param == "none":
        return ""  # Public mode
    else:
        return channel_key_param  # Explicit key


def _get_channel_info(resolved_key):
    """
    Get channel mode and fingerprint for response.

    Returns:
        (mode, fingerprint) tuple
    """
    from stegasoo import get_channel_status, has_channel_key

    if resolved_key == "":
        return "public", None

    if resolved_key is not None:
        # Explicit key
        fingerprint = f"{resolved_key[:4]}-••••-••••-••••-••••-••••-••••-{resolved_key[-4:]}"
        return "private", fingerprint

    # Auto mode - check server config
    if has_channel_key():
        status = get_channel_status()
        return "private", status.get("fingerprint")

    return "public", None


def encode_operation(params: dict) -> dict:
    """Handle encode operation."""
    from stegasoo import FilePayload, encode

    # Decode base64 inputs
    carrier_data = base64.b64decode(params["carrier_b64"])
    reference_data = base64.b64decode(params["reference_b64"])

    # Optional RSA key
    rsa_key_data = None
    if params.get("rsa_key_b64"):
        rsa_key_data = base64.b64decode(params["rsa_key_b64"])

    # Determine payload type
    if params.get("file_b64"):
        file_data = base64.b64decode(params["file_b64"])
        payload = FilePayload(
            data=file_data,
            filename=params.get("file_name", "file"),
            mime_type=params.get("file_mime", "application/octet-stream"),
        )
    else:
        payload = params.get("message", "")

    # Resolve channel key (v4.0.0)
    resolved_channel_key = _resolve_channel_key(params.get("channel_key", "auto"))

    # Call encode with correct parameter names
    result = encode(
        message=payload,
        reference_photo=reference_data,
        carrier_image=carrier_data,
        passphrase=params.get("passphrase", ""),
        pin=params.get("pin"),
        rsa_key_data=rsa_key_data,
        rsa_password=params.get("rsa_password"),
        embed_mode=params.get("embed_mode", "lsb"),
        dct_output_format=params.get("dct_output_format", "png"),
        dct_color_mode=params.get("dct_color_mode", "color"),
        channel_key=resolved_channel_key,  # v4.0.0
        progress_file=params.get("progress_file"),  # v4.1.2
    )

    # Build stats dict if available
    stats = None
    if hasattr(result, "stats") and result.stats:
        stats = {
            "pixels_modified": getattr(result.stats, "pixels_modified", 0),
            "capacity_used": getattr(result.stats, "capacity_used", 0),
            "bytes_embedded": getattr(result.stats, "bytes_embedded", 0),
        }

    # Get channel info for response (v4.0.0)
    channel_mode, channel_fingerprint = _get_channel_info(resolved_channel_key)

    return {
        "success": True,
        "stego_b64": base64.b64encode(result.stego_image).decode("ascii"),
        "filename": getattr(result, "filename", None),
        "stats": stats,
        "channel_mode": channel_mode,
        "channel_fingerprint": channel_fingerprint,
    }


def _write_decode_progress(progress_file: str | None, percent: int, phase: str) -> None:
    """Write decode progress to file."""
    if not progress_file:
        return
    try:
        import json
        with open(progress_file, "w") as f:
            json.dump({"percent": percent, "phase": phase}, f)
    except Exception:
        pass  # Best effort


def decode_operation(params: dict) -> dict:
    """Handle decode operation."""
    from stegasoo import decode

    progress_file = params.get("progress_file")

    # Progress: starting
    _write_decode_progress(progress_file, 5, "reading")

    # Decode base64 inputs
    stego_data = base64.b64decode(params["stego_b64"])
    reference_data = base64.b64decode(params["reference_b64"])

    _write_decode_progress(progress_file, 15, "reading")

    # Optional RSA key
    rsa_key_data = None
    if params.get("rsa_key_b64"):
        rsa_key_data = base64.b64decode(params["rsa_key_b64"])

    # Resolve channel key (v4.0.0)
    resolved_channel_key = _resolve_channel_key(params.get("channel_key", "auto"))

    # Library handles progress internally via progress_file parameter
    # Call decode with correct parameter names
    result = decode(
        stego_image=stego_data,
        reference_photo=reference_data,
        passphrase=params.get("passphrase", ""),
        pin=params.get("pin"),
        rsa_key_data=rsa_key_data,
        rsa_password=params.get("rsa_password"),
        embed_mode=params.get("embed_mode", "auto"),
        channel_key=resolved_channel_key,  # v4.0.0
        progress_file=progress_file,  # v4.2.0: pass through for real-time progress
    )
    # Library writes 100% "complete" - no need for worker to write again

    if result.is_file:
        return {
            "success": True,
            "is_file": True,
            "file_b64": base64.b64encode(result.file_data).decode("ascii"),
            "filename": result.filename,
            "mime_type": result.mime_type,
        }
    else:
        return {
            "success": True,
            "is_file": False,
            "message": result.message,
        }


def compare_operation(params: dict) -> dict:
    """Handle compare_modes operation."""
    from stegasoo import compare_modes

    carrier_data = base64.b64decode(params["carrier_b64"])
    result = compare_modes(carrier_data)

    return {
        "success": True,
        "comparison": result,
    }


def capacity_check_operation(params: dict) -> dict:
    """Handle will_fit_by_mode operation."""
    from stegasoo import will_fit_by_mode

    carrier_data = base64.b64decode(params["carrier_b64"])

    result = will_fit_by_mode(
        payload=params["payload_size"],
        carrier_image=carrier_data,
        embed_mode=params.get("embed_mode", "lsb"),
    )

    return {
        "success": True,
        "result": result,
    }


def channel_status_operation(params: dict) -> dict:
    """Handle channel status check (v4.0.0)."""
    from stegasoo import get_channel_status

    status = get_channel_status()
    reveal = params.get("reveal", False)

    return {
        "success": True,
        "status": {
            "mode": status["mode"],
            "configured": status["configured"],
            "fingerprint": status.get("fingerprint"),
            "source": status.get("source"),
            "key": status.get("key") if reveal and status["configured"] else None,
        },
    }


def main():
    """Main entry point - read JSON from stdin, write JSON to stdout."""
    try:
        # Read all input
        input_text = sys.stdin.read()

        if not input_text.strip():
            output = {"success": False, "error": "No input provided"}
        else:
            params = json.loads(input_text)
            operation = params.get("operation")

            if operation == "encode":
                output = encode_operation(params)
            elif operation == "decode":
                output = decode_operation(params)
            elif operation == "compare":
                output = compare_operation(params)
            elif operation == "capacity":
                output = capacity_check_operation(params)
            elif operation == "channel_status":
                output = channel_status_operation(params)
            else:
                output = {"success": False, "error": f"Unknown operation: {operation}"}

    except json.JSONDecodeError as e:
        output = {"success": False, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        output = {
            "success": False,
            "error": str(e),
            "error_type": type(e).__name__,
            "traceback": traceback.format_exc(),
        }

    # Write output as JSON
    print(json.dumps(output), flush=True)


if __name__ == "__main__":
    main()
