#!/usr/bin/env python3
"""
Channel Keys Example

Channel keys allow you to create private communication channels.
Only people with the same channel key can decode messages.
"""

from pathlib import Path

import stegasoo
from stegasoo.channel import generate_channel_key, get_channel_fingerprint


def main():
    # Generate a channel key for your group
    channel_key = generate_channel_key()
    fingerprint = get_channel_fingerprint(channel_key)

    print("=== Channel Key Generated ===")
    print(f"Key: {channel_key}")
    print(f"Fingerprint: {fingerprint}")
    print("\nShare this key securely with your group members!")
    print("-" * 40)

    # Load images
    reference_photo = Path("my_secret_photo.png").read_bytes()
    carrier_image = Path("carrier.png").read_bytes()

    # Encode with channel key
    print("\nEncoding message with channel key...")
    result = stegasoo.encode(
        message="Secret group message!",
        reference_photo=reference_photo,
        carrier_image=carrier_image,
        passphrase="correct horse battery staple",
        pin="123456",
        channel_key=channel_key,  # Add the channel key
    )

    stego_data = result.stego_image
    print(f"Encoded successfully!")

    # Decode with correct channel key
    print("\nDecoding with correct channel key...")
    decoded = stegasoo.decode(
        stego_image=stego_data,
        reference_photo=reference_photo,
        passphrase="correct horse battery staple",
        pin="123456",
        channel_key=channel_key,  # Same channel key
    )
    print(f"Message: {decoded.message}")

    # Try to decode with wrong channel key
    print("\nTrying to decode with wrong channel key...")
    wrong_key = generate_channel_key()
    try:
        stegasoo.decode(
            stego_image=stego_data,
            reference_photo=reference_photo,
            passphrase="correct horse battery staple",
            pin="123456",
            channel_key=wrong_key,  # Different channel key
        )
        print("ERROR: Should have failed!")
    except (stegasoo.DecryptionError, stegasoo.ExtractionError):
        print("Correctly rejected - wrong channel key!")


if __name__ == "__main__":
    main()
