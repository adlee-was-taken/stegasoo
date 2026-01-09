# Docker Quickstart

Get Stegasoo running in Docker in under 5 minutes.

## Build

```bash
# From project root:

# Build web UI image
sudo docker build -t stegasoo-web --target web -f docker/Dockerfile .

# Or build all targets
sudo docker build -t stegasoo-api --target api -f docker/Dockerfile .
sudo docker build -t stegasoo-cli --target cli -f docker/Dockerfile .

# Or use docker-compose
sudo docker-compose -f docker/docker-compose.yml build
```

## Run (Basic)

```bash
# HTTP only, no auth
sudo docker run -d \
  -p 5000:5000 \
  -e STEGASOO_AUTH_ENABLED=false \
  --name stegasoo \
  stegasoo-web
```

Visit http://localhost:5000

## Run (Production)

```bash
# HTTPS + Auth + Channel Key
sudo docker run -d \
  -p 5000:5000 \
  -e STEGASOO_AUTH_ENABLED=true \
  -e STEGASOO_HTTPS_ENABLED=true \
  -e STEGASOO_HOSTNAME=stegasoo.local \
  -e STEGASOO_CHANNEL_KEY=ABCD-1234-EFGH-5678-IJKL-9012-MNOP-3456 \
  -v stegasoo-data:/opt/stegasoo/frontends/web/instance \
  -v stegasoo-certs:/opt/stegasoo/frontends/web/certs \
  --name stegasoo \
  stegasoo-web
```

Visit https://localhost:5000 (accept self-signed cert warning)

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `STEGASOO_AUTH_ENABLED` | `true` | Require login |
| `STEGASOO_HTTPS_ENABLED` | `false` | Enable HTTPS |
| `STEGASOO_HOSTNAME` | `localhost` | Hostname for SSL cert |
| `STEGASOO_CHANNEL_KEY` | *(none)* | Shared channel key (32 alphanumeric chars with dashes) |

## Docker Compose

Create `.env` file in project root:
```bash
STEGASOO_AUTH_ENABLED=true
STEGASOO_HTTPS_ENABLED=true
STEGASOO_HOSTNAME=stegasoo.local
STEGASOO_CHANNEL_KEY=
```

Run:
```bash
sudo docker-compose -f docker/docker-compose.yml up -d web
```

## Custom SSL Certificates

### Use Your Own Certs

```bash
# Stop container
sudo docker stop stegasoo

# Copy certs to volume
sudo docker run --rm -v stegasoo-certs:/certs -v $(pwd):/src alpine \
  sh -c "cp /src/your-cert.crt /certs/server.crt && cp /src/your-key.key /certs/server.key && chmod 600 /certs/server.key"

# Start container
sudo docker start stegasoo
```

### Use mkcert (Local Development)

```bash
# Install mkcert
brew install mkcert  # macOS
# or: sudo apt install mkcert  # Debian/Ubuntu

# Create local CA and certs
mkcert -install
mkcert -cert-file server.crt -key-file server.key localhost 127.0.0.1 stegasoo.local

# Copy to Docker volume (see above)
```

### Use Let's Encrypt (Public Server)

```bash
# Get cert
sudo certbot certonly --standalone -d yourdomain.com

# Copy to Docker volume
sudo docker run --rm -v stegasoo-certs:/certs alpine \
  sh -c "cp /etc/letsencrypt/live/yourdomain.com/fullchain.pem /certs/server.crt && \
         cp /etc/letsencrypt/live/yourdomain.com/privkey.pem /certs/server.key && \
         chmod 600 /certs/server.key"
```

## Volumes

| Volume | Purpose |
|--------|---------|
| `stegasoo-data` | User database, settings |
| `stegasoo-certs` | SSL certificates |

## Smoke Test

```bash
# Check container logs
sudo docker logs stegasoo

# Test HTTP endpoint
curl -k https://localhost:5000/health

# Expected: {"status":"ok","version":"4.1.7",...}
```

## Troubleshooting

**Container won't start:**
```bash
sudo docker logs stegasoo
```

**Out of memory:**
```bash
# Argon2 needs 256MB+ per operation
sudo docker run --memory=768m ...
```

**Certificate errors:**
```bash
# Regenerate self-signed cert
sudo docker exec stegasoo rm -rf /opt/stegasoo/frontends/web/certs/*
sudo docker restart stegasoo
```

**Reset everything:**
```bash
sudo docker stop stegasoo && sudo docker rm stegasoo
sudo docker volume rm stegasoo-data stegasoo-certs
```
