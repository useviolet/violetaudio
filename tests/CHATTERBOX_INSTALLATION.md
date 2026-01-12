# Chatterbox TTS Installation Guide

## Issue: Python 3.12 Compatibility

The `chatterbox-tts` package requires `numpy<1.26.0,>=1.24.0`. When installing on Python 3.12, you may encounter this error:

```
AttributeError: module 'pkgutil' has no attribute 'ImpImporter'
```

This occurs because:
- `numpy 1.25.2` needs to be built from source for Python 3.12
- The build process uses an old version of `setuptools/pkg_resources` that's incompatible with Python 3.12
- `pkgutil.ImpImporter` was removed in Python 3.12

## Solutions

### Option 1: Use Python 3.11 (Recommended)

The easiest solution is to use Python 3.11, which is fully supported:

```bash
# Install Python 3.11 (if not already installed)
# On macOS with Homebrew:
brew install python@3.11

# Create a virtual environment with Python 3.11
python3.11 -m venv venv_chatterbox
source venv_chatterbox/bin/activate  # On macOS/Linux
# or
venv_chatterbox\Scripts\activate  # On Windows

# Install dependencies
pip install --upgrade pip setuptools wheel
pip install torchaudio chatterbox-tts
```

### Option 2: Use Installation Helper Script

Run the installation helper script which attempts workarounds for Python 3.12:

```bash
python tests/install_chatterbox.py
```

This script will:
1. Upgrade build tools (pip, setuptools, wheel)
2. Try to install numpy with pre-built wheels
3. Install chatterbox-tts with `--no-build-isolation` flag (uses current environment's setuptools)

### Option 3: Manual Installation with Workarounds

If the helper script doesn't work, try manual installation:

```bash
# Upgrade build tools
pip install --upgrade pip setuptools>=68 wheel

# Install numpy separately (try pre-built wheel first)
pip install 'numpy>=1.26.0,<1.27.0' --only-binary :all:

# Install chatterbox-tts without build isolation
pip install chatterbox-tts --no-build-isolation
```

**Note:** If numpy 1.26+ doesn't work with chatterbox-tts, you may need to:
1. Use Python 3.11, or
2. Wait for chatterbox-tts to update its numpy requirements

## Testing

After installation, test the Chatterbox TTS model:

```bash
python tests/test_chatterbox_tts.py
```

This will:
- Check if dependencies are installed
- Test basic text-to-speech generation
- Test emotion control (if supported)
- Save output audio files to `tests/chatterbox_output.wav`

## Usage Example

```python
import torchaudio as ta
from chatterbox.tts import ChatterboxTTS

# Load the model
model = ChatterboxTTS.from_pretrained(device="cuda")  # or "cpu"

# Generate speech
text = "Hello, this is a test of the Chatterbox text-to-speech model."
wav = model.generate(text)

# Save output
ta.save("output.wav", wav, model.sr)
```

## References

- [Chatterbox GitHub Repository](https://github.com/resemble-ai/chatterbox)
- [Resemble AI Chatterbox Documentation](https://www.resemble.ai/chatterbox/)

