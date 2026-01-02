# Stegasoo Docker Image
# Uses pre-built base image for fast rebuilds
#
# First time setup:
#   docker build -f Dockerfile.base -t stegasoo-base:latest .
#
# Then build normally (fast!):
#   docker-compose build
#
# Or if you don't have the base image, this falls back to building deps
# (slow, but works)

# ============================================================================
# ARG to switch between base image and full build
# ============================================================================
ARG USE_BASE_IMAGE=true

# ============================================================================
# Base stage - use pre-built image if available
# ============================================================================
FROM stegasoo-base:latest AS base-prebuilt

FROM python:3.12-slim AS base-full

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_ROOT_USER_ACTION=ignore

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc-dev \
    libffi-dev \
    libzbar0 \
    libjpeg-dev \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# Install ALL dependencies (slow path)
RUN pip install --no-cache-dir \
    cython numpy scipy>=1.10.0 jpegio>=0.2.0 \
    argon2-cffi>=23.0.0 pillow>=10.0.0 cryptography>=41.0.0 \
    flask>=3.0.0 gunicorn>=21.0.0 \
    fastapi>=0.100.0 "uvicorn[standard]>=0.20.0" python-multipart>=0.0.6 \
    qrcode>=7.3.0 pyzbar>=0.1.9 click>=8.0.0 lz4>=4.0.0

# ============================================================================
# Select which base to use (default: prebuilt)
# ============================================================================
FROM base-prebuilt AS base

# ============================================================================
# Production stage - Web UI
# ============================================================================
FROM base AS web

WORKDIR /app

# Copy application files (this is all that rebuilds normally!)
COPY src/ src/
COPY data/ data/
COPY frontends/web/ frontends/web/

# Create upload directory
RUN mkdir -p /tmp/stego_uploads

# Create non-root user
RUN useradd -m -u 1000 stego && chown -R stego:stego /app /tmp/stego_uploads
USER stego

# Set Python path
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 5000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:5000/')" || exit 1

# Run with gunicorn
WORKDIR /app/frontends/web
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "120", "app:app"]

# ============================================================================
# API stage - REST API
# ============================================================================
FROM base AS api

WORKDIR /app

# Copy application files
COPY src/ src/
COPY data/ data/
COPY frontends/api/ frontends/api/

# Create non-root user
RUN useradd -m -u 1000 stego && chown -R stego:stego /app
USER stego

# Set Python path
ENV PYTHONPATH=/app/src

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Run with uvicorn
WORKDIR /app/frontends/api
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

# ============================================================================
# CLI stage - Command line tool
# ============================================================================
FROM base AS cli

WORKDIR /app

# Copy application files
COPY src/ src/
COPY data/ data/
COPY frontends/cli/ frontends/cli/

# Create non-root user
RUN useradd -m -u 1000 stego && chown -R stego:stego /app
USER stego

# Set Python path
ENV PYTHONPATH=/app/src

# Default to help
WORKDIR /app/frontends/cli
ENTRYPOINT ["python", "main.py"]
CMD ["--help"]
