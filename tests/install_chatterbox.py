#!/usr/bin/env python3
"""
Installation helper script for Chatterbox TTS
This script handles Python 3.12 compatibility issues with chatterbox-tts installation.
"""

import sys
import subprocess
import os

def check_python_version():
    """Check Python version and provide recommendations"""
    version = sys.version_info
    print(f"🐍 Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major == 3 and version.minor == 12:
        print("⚠️  Python 3.12 detected - may have compatibility issues with numpy 1.25.2")
        print("   Recommended: Use Python 3.11 or install with workarounds")
        return True
    elif version.major == 3 and version.minor == 11:
        print("✅ Python 3.11 detected - should work without issues")
        return True
    else:
        print(f"⚠️  Python {version.major}.{version.minor} - compatibility unknown")
        return True

def upgrade_build_tools():
    """Upgrade pip, setuptools, and wheel to latest versions"""
    print("\n" + "="*80)
    print("📦 Upgrading build tools...")
    print("="*80)
    
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--upgrade",
            "pip", "setuptools>=68", "wheel"
        ])
        print("✅ Build tools upgraded successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to upgrade build tools: {e}")
        return False

def install_numpy_prebuilt():
    """Try to install numpy 1.25.2 as a pre-built wheel"""
    print("\n" + "="*80)
    print("📦 Installing numpy 1.25.2 (pre-built wheel preferred)...")
    print("="*80)
    
    try:
        # First, try to install a compatible numpy version
        # For Python 3.12, we might need numpy 1.26+ which has pre-built wheels
        python_version = f"{sys.version_info.major}{sys.version_info.minor}"
        
        if python_version == "312":
            print("💡 Python 3.12 detected - trying numpy 1.26.0+ (has pre-built wheels)")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "numpy>=1.26.0,<1.27.0", "--only-binary", ":all:"
            ])
        else:
            # For Python 3.11, try to get pre-built numpy 1.25.2
            print("💡 Trying to install numpy 1.25.2 with pre-built wheels...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "numpy==1.25.2", "--only-binary", ":all:"
            ])
        
        print("✅ NumPy installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Failed to install pre-built numpy: {e}")
        print("   Will try building from source...")
        return False

def install_chatterbox_with_workaround():
    """Install chatterbox-tts with Python 3.12 workarounds"""
    print("\n" + "="*80)
    print("📦 Installing chatterbox-tts with workarounds...")
    print("="*80)
    
    python_version = f"{sys.version_info.major}{sys.version_info.minor}"
    
    if python_version == "312":
        print("💡 Using Python 3.12 workarounds:")
        print("   1. Installing with --no-build-isolation")
        print("   2. Using current environment's setuptools")
        
        try:
            # Install without build isolation to use current setuptools
            subprocess.check_call([
                sys.executable, "-m", "pip", "install",
                "chatterbox-tts", "--no-build-isolation"
            ])
            print("✅ chatterbox-tts installed successfully with workarounds")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Installation failed: {e}")
            print("\n💡 Alternative solutions:")
            print("   1. Use Python 3.11 in a virtual environment:")
            print("      python3.11 -m venv venv")
            print("      source venv/bin/activate  # On macOS/Linux")
            print("      pip install chatterbox-tts")
            print("\n   2. Install numpy separately first:")
            print("      pip install 'numpy<1.26.0,>=1.24.0' --no-build-isolation")
            print("      pip install chatterbox-tts --no-build-isolation")
            return False
    else:
        # For Python 3.11, normal installation should work
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "chatterbox-tts"
            ])
            print("✅ chatterbox-tts installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Installation failed: {e}")
            return False

def install_torchaudio():
    """Install torchaudio if not already installed"""
    print("\n" + "="*80)
    print("📦 Checking torchaudio...")
    print("="*80)
    
    try:
        import torchaudio
        print("✅ torchaudio is already installed")
        return True
    except ImportError:
        print("📦 Installing torchaudio...")
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "torchaudio"
            ])
            print("✅ torchaudio installed successfully")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install torchaudio: {e}")
            return False

def main():
    """Main installation process"""
    print("\n" + "="*80)
    print("🚀 Chatterbox TTS Installation Helper")
    print("="*80)
    
    # Check Python version
    check_python_version()
    
    # Upgrade build tools
    if not upgrade_build_tools():
        print("⚠️  Continuing despite build tools upgrade failure...")
    
    # Install torchaudio first
    if not install_torchaudio():
        print("⚠️  torchaudio installation failed - some features may not work")
    
    # Try to install numpy with pre-built wheels
    numpy_installed = install_numpy_prebuilt()
    
    # Install chatterbox-tts
    if not install_chatterbox_with_workaround():
        print("\n" + "="*80)
        print("❌ Installation failed")
        print("="*80)
        print("\n💡 Recommended solution for Python 3.12:")
        print("   Create a Python 3.11 virtual environment:")
        print("   ")
        print("   # Install Python 3.11 (if not already installed)")
        print("   # brew install python@3.11  # On macOS")
        print("   ")
        print("   python3.11 -m venv venv_chatterbox")
        print("   source venv_chatterbox/bin/activate")
        print("   pip install --upgrade pip setuptools wheel")
        print("   pip install torchaudio chatterbox-tts")
        return False
    
    # Verify installation
    print("\n" + "="*80)
    print("✅ Verifying installation...")
    print("="*80)
    
    try:
        from chatterbox.tts import ChatterboxTTS
        print("✅ chatterbox-tts imported successfully")
        
        import torchaudio
        print("✅ torchaudio imported successfully")
        
        print("\n✅ Installation complete! You can now run:")
        print("   python tests/test_chatterbox_tts.py")
        return True
    except ImportError as e:
        print(f"❌ Verification failed: {e}")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

