#!/bin/bash
#
# Docker entrypoint for Stegasoo Web UI
# Handles SSL certificate generation and gunicorn startup
#

set -e

CERT_DIR="/app/frontends/web/certs"
CERT_FILE="$CERT_DIR/cert.pem"
KEY_FILE="$CERT_DIR/key.pem"
HOSTNAME="${STEGASOO_HOSTNAME:-localhost}"

# Generate self-signed SSL certificate if HTTPS enabled and certs don't exist
generate_certs() {
    if [ ! -f "$CERT_FILE" ] || [ ! -f "$KEY_FILE" ]; then
        echo "Generating self-signed SSL certificate for $HOSTNAME..."
        mkdir -p "$CERT_DIR"

        openssl req -x509 -newkey rsa:2048 \
            -keyout "$KEY_FILE" \
            -out "$CERT_FILE" \
            -sha256 -days 365 -nodes \
            -subj "/CN=$HOSTNAME" \
            -addext "subjectAltName=DNS:$HOSTNAME,DNS:localhost,IP:127.0.0.1" \
            2>/dev/null

        echo "SSL certificate generated."
    else
        echo "Using existing SSL certificates."
    fi
}

# Start gunicorn with appropriate settings
if [ "${STEGASOO_HTTPS_ENABLED:-false}" = "true" ]; then
    echo "HTTPS mode enabled"
    generate_certs

    exec gunicorn \
        --bind 0.0.0.0:5000 \
        --workers 2 \
        --threads 4 \
        --timeout 120 \
        --certfile "$CERT_FILE" \
        --keyfile "$KEY_FILE" \
        app:app
else
    echo "HTTP mode (HTTPS disabled)"
    exec gunicorn \
        --bind 0.0.0.0:5000 \
        --workers 2 \
        --threads 4 \
        --timeout 120 \
        app:app
fi
