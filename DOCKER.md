# Docker Deployment

Stegasoo provides Docker images for both the Web UI and REST API.

## Quick Start

```bash
# Build and start all services
docker-compose up -d

# Check status
docker-compose ps
```

Access:
- **Web UI**: http://localhost:5000
- **REST API**: http://localhost:8000

## Services

| Service | Port | Description |
|---------|------|-------------|
| `web` | 5000 | Flask Web UI with authentication |
| `api` | 8000 | FastAPI REST API |

## Configuration

### Environment Variables

Create a `.env` file or set these variables:

```bash
# Channel key for private group communication (optional)
STEGASOO_CHANNEL_KEY=XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XXXX

# Web UI authentication (default: enabled)
STEGASOO_AUTH_ENABLED=true

# HTTPS support (default: disabled)
STEGASOO_HTTPS_ENABLED=false
STEGASOO_HOSTNAME=localhost
```

### Volume Mounts

Persistent data is stored in Docker volumes:

| Volume | Purpose |
|--------|---------|
| `stegasoo-web-data` | User database, session data |
| `stegasoo-web-certs` | SSL certificates (if HTTPS enabled) |

## Building

### Standard Build (Recommended)

Uses a pre-built base image with all dependencies:

```bash
# First time only: build the base image
docker build -f Dockerfile.base -t stegasoo-base:latest .

# Build services (fast - only copies app code)
docker-compose build
```

### Full Build (No Base Image)

If you don't have the base image, the Dockerfile will build all dependencies (slower):

```bash
docker-compose build
```

## Commands

```bash
# Start services
docker-compose up -d

# View logs
docker-compose logs -f

# Stop services
docker-compose down

# Rebuild after code changes
docker-compose build && docker-compose up -d

# Full rebuild (no cache)
docker-compose build --no-cache
```

## Resource Limits

Each container is configured with:
- **Memory limit**: 768 MB
- **Memory reservation**: 384 MB

This accounts for Argon2id's 256 MB RAM requirement during key derivation.

## Health Checks

Both services include health checks:
- Interval: 30 seconds
- Timeout: 10 seconds
- Start period: 5 seconds
- Retries: 3

Check health status:
```bash
docker-compose ps
```

## Production Deployment

For production, consider:

1. **Enable HTTPS**:
   ```bash
   STEGASOO_HTTPS_ENABLED=true
   STEGASOO_HOSTNAME=your-domain.com
   ```

2. **Use secrets for channel key**:
   ```bash
   # Don't commit .env files with secrets
   export STEGASOO_CHANNEL_KEY=your-key
   docker-compose up -d
   ```

3. **Reverse proxy**: Put behind nginx/traefik for TLS termination

4. **Backup volumes**:
   ```bash
   docker run --rm -v stegasoo-web-data:/data -v $(pwd):/backup \
     alpine tar czf /backup/stegasoo-backup.tar.gz /data
   ```

## Troubleshooting

### Container won't start
```bash
# Check logs
docker-compose logs web
docker-compose logs api
```

### Out of memory
Increase Docker's memory allocation or reduce worker count in Dockerfile.

### Permission errors
The containers run as non-root user `stego` (UID 1000). Ensure volume permissions match.
