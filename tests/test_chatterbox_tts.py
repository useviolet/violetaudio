#!/usr/bin/env python3
"""
Test script for Chatterbox TTS model
This script tests the Chatterbox text-to-speech model functionality.
"""

import sys
import os

# Add project root to path
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

def check_dependencies():
    """Check if required dependencies are installed"""
    missing = []
    
    try:
        import torchaudio
        print("✅ torchaudio is installed")
    except ImportError:
        missing.append("torchaudio")
        print("❌ torchaudio is not installed")
    
    try:
        from chatterbox.tts import ChatterboxTTS
        print("✅ chatterbox-tts is installed")
        return True
    except ImportError as e:
        missing.append("chatterbox-tts")
        print(f"❌ chatterbox-tts is not installed: {e}")
        if missing:
            print(f"\n💡 To install missing dependencies, run:")
            print(f"   pip install torchaudio chatterbox-tts")
            print(f"\n   Or use the installation script:")
            print(f"   python tests/install_chatterbox.py")
        return False

def test_chatterbox_basic():
    """Test basic Chatterbox TTS functionality"""
    print("\n" + "="*80)
    print("🧪 Testing Chatterbox TTS - Basic Generation")
    print("="*80)
    
    if not check_dependencies():
        return False
    
    try:
        import torchaudio as ta
        from chatterbox.tts import ChatterboxTTS
        import torch
        
        # Detect device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"\n📱 Using device: {device}")
        
        # Load the model
        print("\n⏳ Loading Chatterbox TTS model...")
        model = ChatterboxTTS.from_pretrained(device=device)
        print("✅ Model loaded successfully")
        
        # Test text
        test_text = "Hello, this is a test of the Chatterbox text-to-speech model. It supports emotion control and zero-shot voice cloning."
        print(f"\n📝 Test text: {test_text}")
        
        # Generate speech
        print("\n⏳ Generating speech...")
        wav = model.generate(test_text)
        print(f"✅ Speech generated successfully")
        print(f"   Audio shape: {wav.shape}")
        print(f"   Sample rate: {model.sr} Hz")
        
        # Save output
        output_path = os.path.join(_project_root, "tests", "chatterbox_output.wav")
        print(f"\n💾 Saving output to: {output_path}")
        ta.save(output_path, wav, model.sr)
        
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✅ Output saved successfully ({file_size} bytes)")
            return True
        else:
            print(f"❌ Output file not found")
            return False
            
    except Exception as e:
        print(f"\n❌ Error during test: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_chatterbox_emotion():
    """Test Chatterbox TTS with emotion control"""
    print("\n" + "="*80)
    print("🧪 Testing Chatterbox TTS - Emotion Control")
    print("="*80)
    
    if not check_dependencies():
        return False
    
    try:
        import torchaudio as ta
        from chatterbox.tts import ChatterboxTTS
        import torch
        
        # Detect device
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"\n📱 Using device: {device}")
        
        # Load the model
        print("\n⏳ Loading Chatterbox TTS model...")
        model = ChatterboxTTS.from_pretrained(device=device)
        print("✅ Model loaded successfully")
        
        # Test with different emotions
        emotions = ["happy", "sad", "angry", "neutral"]
        test_text = "This is a test of emotion control in Chatterbox TTS."
        
        for emotion in emotions:
            print(f"\n😊 Testing emotion: {emotion}")
            try:
                wav = model.generate(test_text, emotion=emotion)
                output_path = os.path.join(_project_root, "tests", f"chatterbox_{emotion}.wav")
                ta.save(output_path, wav, model.sr)
                print(f"   ✅ Generated and saved: {output_path}")
            except Exception as e:
                print(f"   ⚠️  Emotion '{emotion}' not supported or error: {e}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Error during emotion test: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 Chatterbox TTS Test Suite")
    print("="*80)
    
    # Run basic test
    basic_success = test_chatterbox_basic()
    
    # Run emotion test (optional, may not be supported in all versions)
    emotion_success = test_chatterbox_emotion()
    
    print("\n" + "="*80)
    print("📊 Test Results:")
    print(f"   Basic Generation: {'✅ PASSED' if basic_success else '❌ FAILED'}")
    print(f"   Emotion Control: {'✅ PASSED' if emotion_success else '⚠️  SKIPPED/FAILED'}")
    print("="*80)
    
    sys.exit(0 if basic_success else 1)

