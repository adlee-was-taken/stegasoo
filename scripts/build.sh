#!/bin/bash
# Stegasoo Build Script
# Usage: ./build.sh [base|fast|full|clean]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DOCKER_DIR="$PROJECT_DIR/docker"
cd "$PROJECT_DIR"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

# Detect docker compose command
if docker compose version &>/dev/null; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose &>/dev/null; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Error: docker compose not found${NC}"
    exit 1
fi

# Check if we need sudo
SUDO=""
if ! docker ps &>/dev/null; then
    SUDO="sudo"
fi

COMPOSE_FILE="$DOCKER_DIR/docker-compose.yml"

case "${1:-fast}" in
    base)
        echo -e "${YELLOW}Building base image (this takes 5-10 minutes)...${NC}"
        $SUDO docker build -f "$DOCKER_DIR/Dockerfile.base" -t stegasoo-base:latest .
        echo -e "${GREEN}Base image built! Future builds will be fast.${NC}"
        echo ""
        echo "Optional: Push to registry for team use:"
        echo "  docker tag stegasoo-base:latest yourregistry/stegasoo-base:latest"
        echo "  docker push yourregistry/stegasoo-base:latest"
        ;;

    fast)
        if ! $SUDO docker image inspect stegasoo-base:latest >/dev/null 2>&1; then
            echo -e "${YELLOW}Base image not found. Building it first (one-time)...${NC}"
            $0 base
        fi
        echo -e "${CYAN}Fast build using base image...${NC}"
        $SUDO $COMPOSE_CMD -f "$COMPOSE_FILE" build
        echo -e "${GREEN}Done! Start with: $COMPOSE_CMD -f docker/docker-compose.yml up -d${NC}"
        ;;

    full)
        echo -e "${YELLOW}Full build from scratch (slow)...${NC}"
        $SUDO $COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache
        echo -e "${GREEN}Done! Start with: $COMPOSE_CMD -f docker/docker-compose.yml up -d${NC}"
        ;;

    clean)
        echo -e "${YELLOW}Cleaning up...${NC}"
        $SUDO $COMPOSE_CMD -f "$COMPOSE_FILE" down --rmi local -v 2>/dev/null || true
        $SUDO docker rmi stegasoo-base:latest 2>/dev/null || true
        echo -e "${GREEN}Cleaned!${NC}"
        ;;

    rebuild)
        echo -e "${YELLOW}Full rebuild from scratch (no cache)...${NC}"
        $SUDO $COMPOSE_CMD -f "$COMPOSE_FILE" down --rmi local -v 2>/dev/null || true
        $SUDO docker rmi stegasoo-base:latest 2>/dev/null || true
        $SUDO docker build --no-cache -f "$DOCKER_DIR/Dockerfile.base" -t stegasoo-base:latest .
        $SUDO $COMPOSE_CMD -f "$COMPOSE_FILE" build --no-cache
        echo -e "${GREEN}Done! Start with: $COMPOSE_CMD -f docker/docker-compose.yml up -d${NC}"
        ;;

    *)
        echo -e "${CYAN}Stegasoo Build Script${NC}"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  base    Build the base image (one-time, 5-10 min)"
        echo "  fast    Fast build using base image (default, ~10 sec)"
        echo "  full    Rebuild services without cache (uses existing base)"
        echo "  rebuild Complete rebuild with no cache (base + services)"
        echo "  clean   Remove all images and volumes"
        echo ""
        echo "Typical workflow:"
        echo "  1. First time:   $0 base"
        echo "  2. Daily dev:    $0 fast"
        echo "  3. Deps change:  $0 base"
        echo "  4. Nuclear:      $0 rebuild"
        ;;
esac
