#!/bin/bash
# Script to check Python version and TTS compatibility

echo "=== Python Version Check ==="
echo ""

# Check Python version
PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
PYTHON_MAJOR=$(python -c "import sys; print(sys.version_info.major)" 2>/dev/null)
PYTHON_MINOR=$(python -c "import sys; print(sys.version_info.minor)" 2>/dev/null)

echo "Python Version: $PYTHON_VERSION"
echo "Major.Minor: $PYTHON_MAJOR.$PYTHON_MINOR"
echo ""

# Check TTS compatibility
if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 12 ]; then
    echo "✅ TTS CAN be installed (Python $PYTHON_MAJOR.$PYTHON_MINOR is compatible)"
    echo "   Install with: pip install TTS"
else
    echo "❌ TTS CANNOT be installed (Python $PYTHON_MAJOR.$PYTHON_MINOR is not compatible)"
    echo "   TTS requires Python >= 3.9, < 3.12"
    echo "   Your version: Python $PYTHON_MAJOR.$PYTHON_MINOR"
    echo ""
    echo "   Note: This is OK - TTS is optional and the miner will work without it"
fi

echo ""
echo "=== Additional Info ==="
python -c "import sys; print(f'Full version: {sys.version}')" 2>/dev/null

