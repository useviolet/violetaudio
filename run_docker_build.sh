#!/bin/bash
# Simple Docker build script

cd "$(dirname "$0")"

echo "🚀 Starting Docker build for bateesa/violet-proxy..."
echo "⏰ This will take 30-60 minutes. Progress will be saved to docker_build.log"
echo ""

# Run build and save output
docker build --progress=plain -t bateesa/violet-proxy . 2>&1 | tee docker_build.log

if [ ${PIPESTATUS[0]} -eq 0 ]; then
    echo ""
    echo "✅ Build completed successfully!"
    docker images | grep bateesa/violet-proxy
else
    echo ""
    echo "❌ Build failed. Check docker_build.log for details."
    exit 1
fi
