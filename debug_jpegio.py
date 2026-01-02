#!/usr/bin/env python3
"""
Debug script for DCT/jpegio extraction issues.
Run from the stegasoo directory.
"""

import sys
import struct
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / 'src'))

import hashlib
import numpy as np

# Check for jpegio
try:
    import jpegio as jio
    print("✓ jpegio available")
except ImportError:
    print("✗ jpegio NOT available")
    sys.exit(1)

def get_usable_positions(coef_array, min_magnitude=2):
    """Get positions of usable coefficients."""
    positions = []
    h, w = coef_array.shape
    for row in range(h):
        for col in range(w):
            # Skip DC coefficients (top-left of each 8x8 block)
            if (row % 8 == 0) and (col % 8 == 0):
                continue
            if abs(coef_array[row, col]) >= min_magnitude:
                positions.append((row, col))
    return positions

def generate_order(num_positions, seed):
    """Generate pseudo-random order for coefficient selection."""
    hash_bytes = hashlib.sha256(seed + b"jpeg_coef_order").digest()
    rng = np.random.RandomState(int.from_bytes(hash_bytes[:4], 'big'))
    order = list(range(num_positions))
    rng.shuffle(order)
    return order

def extract_bits(coef_array, positions, order, num_bits):
    """Extract bits from coefficients."""
    bits = []
    for i, pos_idx in enumerate(order):
        if i >= num_bits:
            break
        row, col = positions[pos_idx]
        coef = coef_array[row, col]
        bits.append(coef & 1)
    return bits

def bits_to_bytes(bits):
    """Convert list of bits to bytes."""
    result = []
    for i in range(0, len(bits), 8):
        byte_bits = bits[i:i+8]
        if len(byte_bits) == 8:
            byte_val = sum(byte_bits[j] << (7-j) for j in range(8))
            result.append(byte_val)
    return bytes(result)

def main():
    if len(sys.argv) < 3:
        print("Usage: python debug_jpegio.py <stego_image.jpg> <reference_photo>")
        print("\nOptional: add passphrase, pin, key path")
        print("  python debug_jpegio.py stego.jpg ref.jpg 'passphrase' '123456' key.pem")
        sys.exit(1)

    stego_path = sys.argv[1]
    ref_path = sys.argv[2]
    passphrase = sys.argv[3] if len(sys.argv) > 3 else "test"
    pin = sys.argv[4] if len(sys.argv) > 4 else ""
    key_path = sys.argv[5] if len(sys.argv) > 5 else None

    print(f"\n{'='*60}")
    print("JPEGIO DCT EXTRACTION DEBUG")
    print(f"{'='*60}")
    print(f"Stego image: {stego_path}")
    print(f"Reference:   {ref_path}")
    print(f"Passphrase:  '{passphrase}'")
    print(f"PIN:         '{pin}'")
    print(f"Key:         {key_path}")

    # Load stego image with jpegio
    print(f"\n[1] Loading stego image with jpegio...")
    try:
        jpeg = jio.read(stego_path)
        print(f"    ✓ jpegio.read() succeeded")
        print(f"    Number of components: {len(jpeg.coef_arrays)}")
        for i, arr in enumerate(jpeg.coef_arrays):
            print(f"    Component {i}: shape={arr.shape}, dtype={arr.dtype}")
    except Exception as e:
        print(f"    ✗ Failed: {e}")
        sys.exit(1)

    # Get coefficient array (channel 0)
    coef_array = jpeg.coef_arrays[0]
    print(f"\n[2] Coefficient array analysis...")
    print(f"    Shape: {coef_array.shape}")
    print(f"    Non-zero coefficients: {np.count_nonzero(coef_array)}")
    print(f"    Min value: {coef_array.min()}")
    print(f"    Max value: {coef_array.max()}")

    # Get usable positions
    print(f"\n[3] Finding usable positions (|coef| >= 2, non-DC)...")
    positions = get_usable_positions(coef_array)
    print(f"    Usable positions: {len(positions)}")
    print(f"    Capacity: ~{len(positions) // 8} bytes")

    # Generate seed (this needs to match the encode seed!)
    print(f"\n[4] Generating seed...")

    # Load reference photo
    ref_data = Path(ref_path).read_bytes()
    ref_hash = hashlib.sha256(ref_data).digest()
    print(f"    Reference hash: {ref_hash[:8].hex()}...")

    # Load RSA key if provided
    rsa_component = b""
    if key_path:
        try:
            from stegasoo import load_rsa_key
            key_data = Path(key_path).read_bytes()
            # Try without password first
            try:
                rsa_key = load_rsa_key(key_data, password=None)
            except:
                rsa_key = load_rsa_key(key_data, password="testpass")

            # Get public key bytes for seed
            from cryptography.hazmat.primitives import serialization
            pub_bytes = rsa_key.public_key().public_bytes(
                encoding=serialization.Encoding.DER,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            rsa_component = hashlib.sha256(pub_bytes).digest()
            print(f"    RSA key loaded, hash: {rsa_component[:8].hex()}...")
        except Exception as e:
            print(f"    ✗ Could not load RSA key: {e}")

    # Build seed like stegasoo does
    # This is the critical part - must match encoding!
    seed_parts = [
        ref_hash,
        passphrase.encode('utf-8'),
        pin.encode('utf-8') if pin else b"",
        rsa_component,
    ]
    seed = hashlib.sha256(b"".join(seed_parts)).digest()
    print(f"    Combined seed: {seed[:8].hex()}...")

    # Generate order
    print(f"\n[5] Generating coefficient order...")
    order = generate_order(len(positions), seed)
    print(f"    First 10 indices: {order[:10]}")

    # Try to extract header
    print(f"\n[6] Extracting header (first 80 bits = 10 bytes)...")
    HEADER_SIZE = 10
    header_bits = extract_bits(coef_array, positions, order, HEADER_SIZE * 8)
    header_bytes = bits_to_bytes(header_bits)
    print(f"    Raw header bytes: {header_bytes.hex()}")
    print(f"    As ASCII (if printable): {repr(header_bytes)}")

    # Check for JPGS magic
    JPEGIO_MAGIC = b'JPGS'
    if header_bytes[:4] == JPEGIO_MAGIC:
        print(f"    ✓ Found JPEGIO magic bytes!")
        version = header_bytes[4]
        flags = header_bytes[5]
        data_length = struct.unpack('>I', header_bytes[6:10])[0]
        print(f"    Version: {version}")
        print(f"    Flags: {flags}")
        print(f"    Data length: {data_length} bytes")

        if data_length > 0 and data_length < len(positions) // 8:
            print(f"\n[7] Extracting payload ({data_length} bytes)...")
            total_bits = (HEADER_SIZE + data_length) * 8
            all_bits = extract_bits(coef_array, positions, order, total_bits)
            data_bits = all_bits[HEADER_SIZE * 8:]
            payload = bits_to_bytes(data_bits)
            print(f"    Payload (first 64 bytes): {payload[:64].hex()}")
            print(f"    This should be encrypted data starting with salt/IV")
        else:
            print(f"    ✗ Invalid data length: {data_length}")
    else:
        print(f"    ✗ No JPEGIO magic found")
        print(f"    Expected: {JPEGIO_MAGIC.hex()} ('JPGS')")
        print(f"    Got:      {header_bytes[:4].hex()} ('{header_bytes[:4]}')")

        # Try alternate interpretations
        print(f"\n[7] Trying alternate header interpretations...")

        # Maybe it's scipy DCT format?
        DCT_MAGIC = b'DCTS'
        if header_bytes[:4] == DCT_MAGIC:
            print(f"    Found SCIPY DCT magic - wrong extraction method!")
        else:
            # Show bit distribution
            print(f"    First 32 extracted bits: {header_bits[:32]}")

            # Check if bits look random or patterned
            ones = sum(header_bits[:80])
            print(f"    Bit distribution: {ones}/80 ones ({100*ones/80:.1f}%)")

    print(f"\n{'='*60}")
    print("DEBUG COMPLETE")
    print(f"{'='*60}\n")

if __name__ == '__main__':
    main()
