#!/bin/bash
# Docker build script with progress monitoring

set -e

echo "🚀 Starting Docker build for bateesa/violet-proxy..."
echo "⏰ This may take 30-60 minutes due to large dependencies (torch, CUDA, etc.)"
echo ""

# Build with progress output
docker build --progress=plain -t bateesa/violet-proxy . 2>&1 | while IFS= read -r line; do
    echo "$line"
    # Show progress indicators
    if [[ "$line" =~ "Downloading" ]] || [[ "$line" =~ "Installing" ]]; then
        echo "$line" >&2
    fi
done

BUILD_EXIT_CODE=${PIPESTATUS[0]}

if [ $BUILD_EXIT_CODE -eq 0 ]; then
    echo ""
    echo "✅ Docker build completed successfully!"
    echo "📦 Image: bateesa/violet-proxy"
    docker images | grep bateesa/violet-proxy
else
    echo ""
    echo "❌ Docker build failed with exit code: $BUILD_EXIT_CODE"
    exit $BUILD_EXIT_CODE
fi
