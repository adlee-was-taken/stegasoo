# Stegasoo Docker Image
# Multi-stage build for smaller image size

# Pin the base image digest for reproducibility
# To update: docker manifest inspect python:3.11-slim -v | jq -r '.[0].Descriptor.digest'
FROM python:3.11-slim@sha256:5501a4fe605abe24de87c2f3d6cf9fd760354416a0cad0296cf284fddcdca9e2 as base

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
# Suppress pip "running as root" warnings during build
ENV PIP_ROOT_USER_ACTION=ignore

# Install system dependencies
# NOTE: g++ is required for jpegio C++ compilation
# NOTE: libjpeg-dev is required for jpegio
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    libc-dev \
    libffi-dev \
    libzbar0 \
    libjpeg-dev \
    && rm -rf /var/lib/apt/lists/*

# ============================================================================
# Builder stage - install Python packages
# ============================================================================
FROM base as builder

WORKDIR /build

# Copy package files (including README.md which pyproject.toml references)
COPY pyproject.toml README.md ./
COPY src/ src/
COPY data/ data/

# Install build dependencies for jpegio, then install the package
# jpegio requires Cython and numpy to compile
RUN pip install --no-cache-dir cython numpy && \
    pip install --no-cache-dir ".[web]"

# ============================================================================
# Production stage - Web UI
# ============================================================================
FROM base as web

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /usr/local/lib/python3.11/site-packages /usr/local/lib/python3.11/site-packages
COPY --from=builder /usr/local/bin /usr/local/bin

# Copy application files
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
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--threads", "4", "--timeout", "60", "app:app"]

# ============================================================================
# API stage - REST API
# ============================================================================
FROM base as api

WORKDIR /app

# Install API extras (includes DCT dependencies)
COPY pyproject.toml README.md ./
COPY src/ src/
COPY data/ data/

# Install build dependencies for jpegio, then install the package
RUN pip install --no-cache-dir cython numpy && \
    pip install --no-cache-dir ".[api]"

# Copy API files
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
FROM base as cli

WORKDIR /app

# Install CLI extras
COPY pyproject.toml README.md ./
COPY src/ src/
COPY data/ data/

# Install build dependencies for jpegio (if dct extras needed), then install
RUN pip install --no-cache-dir cython numpy && \
    pip install --no-cache-dir ".[cli,dct]"

# Copy CLI files
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
