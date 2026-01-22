#!/bin/bash
# Fix Docker issues and build image

set -e

echo "🔧 Checking Docker status..."

# Check if Docker is running
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker daemon is not responding"
    echo "💡 Try:"
    echo "   1. Open Docker Desktop"
    echo "   2. Wait for it to fully start"
    echo "   3. Run this script again"
    exit 1
fi

echo "✅ Docker is running"
echo ""

# Clean up any stuck builds
echo "🧹 Cleaning up..."
docker builder prune -f > /dev/null 2>&1 || true

# Check available disk space
echo "💾 Checking disk space..."
df -h . | tail -1

echo ""
echo "🚀 Starting Docker build for bateesa/violet-proxy..."
echo "⏰ This will take 30-60 minutes due to large dependencies"
echo "📝 Progress will be saved to docker_build.log"
echo ""

# Build with progress
cd "$(dirname "$0")"
docker build --progress=plain -t bateesa/violet-proxy . 2>&1 | tee docker_build.log

BUILD_EXIT=${PIPESTATUS[0]}

if [ $BUILD_EXIT -eq 0 ]; then
    echo ""
    echo "✅ Build completed successfully!"
    echo ""
    echo "📦 Image details:"
    docker images bateesa/violet-proxy
else
    echo ""
    echo "❌ Build failed with exit code: $BUILD_EXIT"
    echo "📋 Check docker_build.log for details"
    exit $BUILD_EXIT
fi
