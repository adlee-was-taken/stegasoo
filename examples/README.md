# Stegasoo Examples

This directory contains example scripts demonstrating how to use Stegasoo.

## Prerequisites

Install Stegasoo first:

```bash
pip install stegasoo
# Or for development:
pip install -e ".[all]"
```

## Examples

### basic_usage.py

Basic encode/decode workflow with a text message.

```bash
python basic_usage.py
```

### embed_file.py

Embed and extract files (documents, images, etc.) inside carrier images.

```bash
python embed_file.py
```

### channel_keys.py

Use channel keys to create private communication channels for groups.

```bash
python channel_keys.py
```

## Test Images

You'll need to provide your own images:

- `my_secret_photo.png` - Your reference photo (keep this secret!)
- `carrier.png` - The image that will carry your hidden message

For testing, you can use any PNG or BMP image. JPEG carriers are supported with DCT mode.
