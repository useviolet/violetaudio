#!/usr/bin/env python3
"""
Simple test script for Chatterbox TTS - tests if it can run in current environment
"""

import sys
import os

def test_chatterbox_import():
    """Test if chatterbox can be imported"""
    print("="*80)
    print("🧪 Testing Chatterbox TTS Import")
    print("="*80)
    
    try:
        from chatterbox.tts import ChatterboxTTS
        print("✅ chatterbox-tts imported successfully")
        return True
    except ImportError as e:
        print(f"❌ chatterbox-tts import failed: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error importing chatterbox-tts: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_chatterbox_initialization():
    """Test if chatterbox can be initialized"""
    print("\n" + "="*80)
    print("🧪 Testing Chatterbox TTS Initialization")
    print("="*80)
    
    try:
        from chatterbox.tts import ChatterboxTTS
        import torch
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"📱 Using device: {device}")
        
        print("⏳ Initializing Chatterbox TTS model...")
        model = ChatterboxTTS.from_pretrained(device=device)
        print("✅ Model initialized successfully")
        print(f"   Sample rate: {model.sr} Hz")
        return True, model
    except Exception as e:
        print(f"❌ Model initialization failed: {e}")
        import traceback
        traceback.print_exc()
        return False, None

def test_chatterbox_generation(model):
    """Test if chatterbox can generate speech"""
    print("\n" + "="*80)
    print("🧪 Testing Chatterbox TTS Generation")
    print("="*80)
    
    if model is None:
        print("❌ Cannot test generation - model not initialized")
        return False
    
    try:
        test_text = "Hello, this is a test of the Chatterbox text-to-speech model."
        print(f"📝 Test text: {test_text}")
        
        print("⏳ Generating speech...")
        wav = model.generate(test_text)
        print(f"✅ Speech generated successfully")
        print(f"   Audio shape: {wav.shape}")
        print(f"   Audio dtype: {wav.dtype}")
        
        # Try to save using soundfile (more compatible than torchaudio)
        try:
            import soundfile as sf
            output_path = "tests/chatterbox_test_output.wav"
            os.makedirs("tests", exist_ok=True)
            sf.write(output_path, wav.cpu().numpy().T if hasattr(wav, 'cpu') else wav.T, model.sr)
            print(f"✅ Audio saved to: {output_path}")
            return True
        except ImportError:
            print("⚠️  soundfile not available, trying torchaudio...")
            try:
                import torchaudio as ta
                output_path = "tests/chatterbox_test_output.wav"
                os.makedirs("tests", exist_ok=True)
                ta.save(output_path, wav, model.sr)
                print(f"✅ Audio saved to: {output_path}")
                return True
            except Exception as e2:
                print(f"⚠️  Could not save audio: {e2}")
                print("   But generation worked!")
                return True  # Generation worked, saving is secondary
    except Exception as e:
        print(f"❌ Speech generation failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("\n" + "="*80)
    print("🧪 Chatterbox TTS Simple Test")
    print("="*80)
    
    # Test import
    import_success = test_chatterbox_import()
    if not import_success:
        print("\n❌ Cannot proceed - chatterbox-tts not available")
        print("💡 Try: pip install --no-deps chatterbox-tts")
        sys.exit(1)
    
    # Test initialization
    init_success, model = test_chatterbox_initialization()
    if not init_success:
        print("\n❌ Cannot proceed - model initialization failed")
        sys.exit(1)
    
    # Test generation
    gen_success = test_chatterbox_generation(model)
    
    print("\n" + "="*80)
    print("📊 Test Results:")
    print(f"   Import: {'✅ PASSED' if import_success else '❌ FAILED'}")
    print(f"   Initialization: {'✅ PASSED' if init_success else '❌ FAILED'}")
    print(f"   Generation: {'✅ PASSED' if gen_success else '❌ FAILED'}")
    print("="*80)
    
    if import_success and init_success and gen_success:
        print("\n✅ All tests passed! Chatterbox TTS is working.")
        sys.exit(0)
    else:
        print("\n❌ Some tests failed.")
        sys.exit(1)

