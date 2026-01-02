#!/bin/bash
# Stegasoo Build Script
# Usage: ./build.sh [base|fast|full|clean]

set -e

case "${1:-fast}" in
    base)
        # Build base image with all dependencies (run once, or when deps change)
        echo "🔨 Building base image (this takes 5-10 minutes)..."
        docker build -f Dockerfile.base -t stegasoo-base:latest .
        echo "✅ Base image built! Future builds will be fast."
        echo ""
        echo "Optional: Push to registry for team use:"
        echo "  docker tag stegasoo-base:latest yourregistry/stegasoo-base:latest"
        echo "  docker push yourregistry/stegasoo-base:latest"
        ;;
    
    fast)
        # Fast build using pre-built base image
        if ! docker image inspect stegasoo-base:latest >/dev/null 2>&1; then
            echo "⚠️  Base image not found. Building it first (one-time)..."
            $0 base
        fi
        echo "🚀 Fast build using base image..."
        docker-compose build
        echo "✅ Done! Start with: docker-compose up -d"
        ;;
    
    full)
        # Full rebuild from scratch (slow, but no base image needed)
        echo "🐢 Full build from scratch (slow)..."
        docker-compose build --no-cache
        echo "✅ Done! Start with: docker-compose up -d"
        ;;
    
    clean)
        # Clean up everything
        echo "🧹 Cleaning up..."
        docker-compose down --rmi local -v 2>/dev/null || true
        docker rmi stegasoo-base:latest 2>/dev/null || true
        echo "✅ Cleaned!"
        ;;
    
    *)
        echo "Stegasoo Build Script"
        echo ""
        echo "Usage: $0 [command]"
        echo ""
        echo "Commands:"
        echo "  base   Build the base image (one-time, 5-10 min)"
        echo "  fast   Fast build using base image (default, ~10 sec)"
        echo "  full   Full rebuild from scratch (slow, no base needed)"
        echo "  clean  Remove all images and volumes"
        echo ""
        echo "Typical workflow:"
        echo "  1. First time:  $0 base"
        echo "  2. Daily dev:   $0 fast  (or just 'docker-compose build')"
        echo "  3. Deps change: $0 base  (rebuild base image)"
        ;;
esac
