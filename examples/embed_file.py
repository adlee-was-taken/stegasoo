#!/usr/bin/env python3
"""
File Embedding Example

This example demonstrates how to embed a file (like a document or image)
inside a carrier image using Stegasoo.
"""

from pathlib import Path

import stegasoo
from stegasoo.models import FilePayload


def main():
    # Load images
    reference_photo = Path("my_secret_photo.png").read_bytes()
    carrier_image = Path("carrier.png").read_bytes()

    # Load the file to embed
    secret_file = Path("secret_document.pdf")
    file_data = secret_file.read_bytes()

    # Create a FilePayload
    payload = FilePayload(
        filename=secret_file.name,
        data=file_data,
        mime_type="application/pdf",
    )

    # Credentials
    passphrase = "correct horse battery staple"
    pin = "123456"

    # Check capacity first
    capacity = stegasoo.calculate_capacity(carrier_image)
    print(f"Carrier capacity: {capacity['capacity_bytes']:,} bytes")
    print(f"File size: {len(file_data):,} bytes")

    if len(file_data) > capacity["capacity_bytes"]:
        print("Error: File too large for this carrier!")
        return

    # Encode the file
    print("\nEmbedding file...")
    result = stegasoo.encode(
        file_payload=payload,
        reference_photo=reference_photo,
        carrier_image=carrier_image,
        passphrase=passphrase,
        pin=pin,
    )

    output_path = Path(f"contains_file_{result.suggested_filename}")
    output_path.write_bytes(result.stego_image)
    print(f"Saved to: {output_path}")

    # Decode and extract the file
    print("\nExtracting file...")
    decoded = stegasoo.decode(
        stego_image=output_path.read_bytes(),
        reference_photo=reference_photo,
        passphrase=passphrase,
        pin=pin,
    )

    if decoded.payload_type == "file":
        extracted_path = Path(f"extracted_{decoded.filename}")
        extracted_path.write_bytes(decoded.file_data)
        print(f"Extracted: {extracted_path}")
        print(f"Original filename: {decoded.filename}")
        print(f"MIME type: {decoded.mime_type}")
    else:
        print(f"Unexpected payload type: {decoded.payload_type}")


if __name__ == "__main__":
    main()
