#!/usr/bin/env python3
"""
Basic Stegasoo Usage Example

This example demonstrates how to encode and decode a secret message
using the Stegasoo library.
"""

from pathlib import Path

import stegasoo


def main():
    # Load your images
    # The reference photo is your "key" - keep it secret!
    reference_photo = Path("my_secret_photo.png").read_bytes()
    carrier_image = Path("carrier.png").read_bytes()

    # Your secret message
    message = "This is my secret message!"

    # Your credentials
    passphrase = "correct horse battery staple"  # Use 4+ words
    pin = "123456"  # 6-9 digits

    # === ENCODE ===
    print("Encoding message...")
    result = stegasoo.encode(
        message=message,
        reference_photo=reference_photo,
        carrier_image=carrier_image,
        passphrase=passphrase,
        pin=pin,
    )

    # Save the stego image
    output_path = Path(f"secret_{result.suggested_filename}")
    output_path.write_bytes(result.stego_image)
    print(f"Saved to: {output_path}")
    print(f"Capacity used: {result.capacity_used_percent:.1f}%")

    # === DECODE ===
    print("\nDecoding message...")
    stego_image = output_path.read_bytes()

    decoded = stegasoo.decode(
        stego_image=stego_image,
        reference_photo=reference_photo,
        passphrase=passphrase,
        pin=pin,
    )

    print(f"Decoded message: {decoded.message}")
    print(f"Message type: {decoded.payload_type}")


if __name__ == "__main__":
    main()
