#!/usr/bin/env python3
"""
Stegasoo Subprocess Worker

This script runs in a subprocess and handles encode/decode operations.
If it crashes due to jpegio/scipy issues, the parent Flask process survives.

Communication is via JSON over stdin/stdout:
- Input: JSON object with operation parameters
- Output: JSON object with results or error

Usage:
    echo '{"operation": "encode", ...}' | python stego_worker.py
"""

import sys
import json
import base64
import traceback
from pathlib import Path

# Ensure stegasoo is importable
sys.path.insert(0, str(Path(__file__).parent.parent.parent / 'src'))
sys.path.insert(0, str(Path(__file__).parent))


def encode_operation(params: dict) -> dict:
    """Handle encode operation."""
    from stegasoo import encode, FilePayload
    
    # Decode base64 inputs
    carrier_data = base64.b64decode(params['carrier_b64'])
    reference_data = base64.b64decode(params['reference_b64'])
    
    # Optional RSA key
    rsa_key_data = None
    if params.get('rsa_key_b64'):
        rsa_key_data = base64.b64decode(params['rsa_key_b64'])
    
    # Determine payload type
    if params.get('file_b64'):
        file_data = base64.b64decode(params['file_b64'])
        payload = FilePayload(
            data=file_data,
            filename=params.get('file_name', 'file'),
            mime_type=params.get('file_mime', 'application/octet-stream'),
        )
    else:
        payload = params.get('message', '')
    
    # Call encode with correct parameter names
    result = encode(
        message=payload,
        reference_photo=reference_data,
        carrier_image=carrier_data,
        passphrase=params.get('passphrase', ''),
        pin=params.get('pin'),
        rsa_key_data=rsa_key_data,
        rsa_password=params.get('rsa_password'),
        embed_mode=params.get('embed_mode', 'lsb'),
        dct_output_format=params.get('dct_output_format', 'png'),
        dct_color_mode=params.get('dct_color_mode', 'color'),
    )
    
    # Build stats dict if available
    stats = None
    if hasattr(result, 'stats') and result.stats:
        stats = {
            'pixels_modified': getattr(result.stats, 'pixels_modified', 0),
            'capacity_used': getattr(result.stats, 'capacity_used', 0),
            'bytes_embedded': getattr(result.stats, 'bytes_embedded', 0),
        }
    
    return {
        'success': True,
        'stego_b64': base64.b64encode(result.stego_image).decode('ascii'),
        'filename': getattr(result, 'filename', None),
        'stats': stats,
    }


def decode_operation(params: dict) -> dict:
    """Handle decode operation."""
    from stegasoo import decode
    
    # Decode base64 inputs
    stego_data = base64.b64decode(params['stego_b64'])
    reference_data = base64.b64decode(params['reference_b64'])
    
    # Optional RSA key
    rsa_key_data = None
    if params.get('rsa_key_b64'):
        rsa_key_data = base64.b64decode(params['rsa_key_b64'])
    
    # Call decode with correct parameter names
    result = decode(
        stego_image=stego_data,
        reference_photo=reference_data,
        passphrase=params.get('passphrase', ''),
        pin=params.get('pin'),
        rsa_key_data=rsa_key_data,
        rsa_password=params.get('rsa_password'),
        embed_mode=params.get('embed_mode', 'auto'),
    )
    
    if result.is_file:
        return {
            'success': True,
            'is_file': True,
            'file_b64': base64.b64encode(result.file_data).decode('ascii'),
            'filename': result.filename,
            'mime_type': result.mime_type,
        }
    else:
        return {
            'success': True,
            'is_file': False,
            'message': result.message,
        }


def compare_operation(params: dict) -> dict:
    """Handle compare_modes operation."""
    from stegasoo import compare_modes
    
    carrier_data = base64.b64decode(params['carrier_b64'])
    result = compare_modes(carrier_data)
    
    return {
        'success': True,
        'comparison': result,
    }


def capacity_check_operation(params: dict) -> dict:
    """Handle will_fit_by_mode operation."""
    from stegasoo import will_fit_by_mode
    
    carrier_data = base64.b64decode(params['carrier_b64'])
    
    result = will_fit_by_mode(
        payload=params['payload_size'],
        carrier_image=carrier_data,
        embed_mode=params.get('embed_mode', 'lsb'),
    )
    
    return {
        'success': True,
        'result': result,
    }


def main():
    """Main entry point - read JSON from stdin, write JSON to stdout."""
    try:
        # Read all input
        input_text = sys.stdin.read()
        
        if not input_text.strip():
            output = {'success': False, 'error': 'No input provided'}
        else:
            params = json.loads(input_text)
            operation = params.get('operation')
            
            if operation == 'encode':
                output = encode_operation(params)
            elif operation == 'decode':
                output = decode_operation(params)
            elif operation == 'compare':
                output = compare_operation(params)
            elif operation == 'capacity':
                output = capacity_check_operation(params)
            else:
                output = {'success': False, 'error': f'Unknown operation: {operation}'}
    
    except json.JSONDecodeError as e:
        output = {'success': False, 'error': f'Invalid JSON: {e}'}
    except Exception as e:
        output = {
            'success': False,
            'error': str(e),
            'error_type': type(e).__name__,
            'traceback': traceback.format_exc(),
        }
    
    # Write output as JSON
    print(json.dumps(output), flush=True)


if __name__ == '__main__':
    main()
