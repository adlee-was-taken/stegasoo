#!/bin/bash
#
# Docker entrypoint for Stegasoo Web UI
# Handles SSL certificate generation and gunicorn startup
#
# Supports mkcert for browser-trusted certificates (no warning screen)
#

set -e

CERT_DIR="/app/frontends/web/certs"
CERT_FILE="$CERT_DIR/cert.pem"
KEY_FILE="$CERT_DIR/key.pem"
HOSTNAME="${STEGASOO_HOSTNAME:-localhost}"

# Generate SSL certificates
# Priority: 1) Existing certs, 2) mkcert (trusted), 3) openssl (self-signed)
generate_certs() {
    if [ -f "$CERT_FILE" ] && [ -f "$KEY_FILE" ]; then
        echo "Using existing SSL certificates."
        return
    fi

    mkdir -p "$CERT_DIR"

    # Try mkcert first (creates browser-trusted certs)
    if command -v mkcert &> /dev/null; then
        echo "Generating trusted certificate with mkcert for $HOSTNAME..."
        cd "$CERT_DIR"
        mkcert -key-file key.pem -cert-file cert.pem "$HOSTNAME" localhost 127.0.0.1 ::1
        echo "Trusted certificate generated."
        echo ""
        echo "  To trust on other devices, install the CA cert from:"
        echo "  $(mkcert -CAROOT)/rootCA.pem"
        echo ""
        return
    fi

    # Fallback to self-signed (shows browser warning)
    echo "Generating self-signed SSL certificate for $HOSTNAME..."
    echo "(Install mkcert for browser-trusted certs without warnings)"

    openssl req -x509 -newkey rsa:2048 \
        -keyout "$KEY_FILE" \
        -out "$CERT_FILE" \
        -sha256 -days 365 -nodes \
        -subj "/CN=$HOSTNAME" \
        -addext "subjectAltName=DNS:$HOSTNAME,DNS:localhost,IP:127.0.0.1" \
        2>/dev/null

    echo "Self-signed certificate generated."
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
