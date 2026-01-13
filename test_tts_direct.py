#!/usr/bin/env python3
"""
Direct TTS test - runs TTS synthesis without database
"""

import sys
import os
import tempfile
import asyncio
import httpx

# Add project root to path
_project_root = os.path.dirname(os.path.abspath(__file__))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

def print_section(title: str):
    print(f"\n{'=' * 80}")
    print(f"  {title}")
    print(f"{'=' * 80}")

async def test_tts_quality():
    """Test TTS quality by running synthesis directly"""
    print_section("Direct TTS Quality Test")
    
    # Test parameters
    TEST_TEXT = "Hello, this is a quality test for text-to-speech. We want to verify that the voice cloning works correctly and produces natural-sounding speech with proper pronunciation and intonation."
    VOICE_NAME = "english_alice"
    MODEL_ID = "tts_models/multilingual/multi-dataset/xtts_v2"
    LANGUAGE = "en"
    
    # Get speaker WAV URL from database
    print_section("Step 0: Getting Voice Information")
    try:
        from sqlalchemy import create_engine
        from sqlalchemy import text as sql_text
        
        database_url = os.getenv(
            'DATABASE_URL',
            'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
        )
        
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 10,
                "sslmode": "require"
            }
        )
        
        with engine.connect() as conn:
            query = sql_text("""
                SELECT public_url, display_name
                FROM voices
                WHERE voice_name = :voice_name
            """)
            
            result = conn.execute(query, {'voice_name': VOICE_NAME})
            voice = result.fetchone()
            
            if voice:
                SPEAKER_WAV_URL = voice[0]
                display_name = voice[1]
                print(f"✅ Voice found: {display_name}")
                print(f"   URL: {SPEAKER_WAV_URL[:60]}...")
            else:
                print(f"❌ Voice '{VOICE_NAME}' not found in database")
                return
        
        engine.dispose()
        
    except Exception as e:
        print(f"❌ Error getting voice info: {e}")
        import traceback
        traceback.print_exc()
        return
    
    print(f"\n📋 Test Parameters:")
    print(f"   Text: {TEST_TEXT}")
    print(f"   Speaker WAV URL: {SPEAKER_WAV_URL}")
    print(f"   Model: {MODEL_ID}")
    print(f"   Language: {LANGUAGE}")
    
    # Step 1: Download speaker WAV
    print_section("Step 1: Downloading Speaker WAV")
    print(f"Downloading from: {SPEAKER_WAV_URL}")
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            speaker_response = await client.get(SPEAKER_WAV_URL)
            if speaker_response.status_code != 200:
                print(f"❌ Failed to download speaker audio: HTTP {speaker_response.status_code}")
                return
            speaker_audio_data = speaker_response.content
            print(f"✅ Speaker audio downloaded: {len(speaker_audio_data):,} bytes")
    except Exception as e:
        print(f"❌ Error downloading speaker audio: {e}")
        return
    
    # Step 2: Preprocess speaker WAV
    print_section("Step 2: Preprocessing Speaker WAV")
    try:
        import soundfile as sf
        import numpy as np
        import librosa
        
        # Save to temporary file
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as temp_speaker:
            temp_speaker.write(speaker_audio_data)
            temp_speaker_path = temp_speaker.name
        
        # Load audio to check properties
        audio_data, original_sr = sf.read(temp_speaker_path)
        
        print(f"   Original audio properties:")
        print(f"      Sample rate: {original_sr} Hz")
        print(f"      Channels: {len(audio_data.shape)} ({'mono' if len(audio_data.shape) == 1 else 'stereo'})")
        print(f"      Duration: {len(audio_data) / original_sr:.2f}s")
        
        # Convert to mono if stereo
        if len(audio_data.shape) > 1:
            print(f"   Converting stereo to mono...")
            audio_data = np.mean(audio_data, axis=1)
        
        # Resample to 22050 Hz if needed
        target_sr = 22050
        if original_sr != target_sr:
            print(f"   Resampling from {original_sr} Hz to {target_sr} Hz...")
            audio_data = librosa.resample(audio_data, orig_sr=original_sr, target_sr=target_sr)
        
        # Normalize audio
        max_val = np.max(np.abs(audio_data))
        if max_val > 0:
            audio_data = audio_data / max_val * 0.95
            print(f"   Normalized audio (max was {max_val:.4f})")
        
        # Ensure float32
        if audio_data.dtype != np.float32:
            audio_data = audio_data.astype(np.float32)
        
        # Save preprocessed audio
        with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as speaker_file:
            speaker_wav_path = speaker_file.name
        
        sf.write(speaker_wav_path, audio_data, target_sr, format='WAV', subtype='PCM_16')
        
        # Verify
        final_audio, final_sr = sf.read(speaker_wav_path)
        print(f"✅ Speaker audio preprocessed:")
        print(f"   Final sample rate: {final_sr} Hz")
        print(f"   Final channels: {'mono' if len(final_audio.shape) == 1 else 'stereo'}")
        print(f"   Final duration: {len(final_audio) / final_sr:.2f}s")
        
        # Clean up temp file
        if os.path.exists(temp_speaker_path):
            os.unlink(temp_speaker_path)
            
    except Exception as e:
        print(f"❌ Error preprocessing speaker audio: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 3: Initialize TTS
    print_section("Step 3: Initializing TTS Model")
    try:
        from TTS.api import TTS
        import torch
        
        device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"   Device: {device}")
        print(f"   Model: {MODEL_ID}")
        print(f"   Initializing (this may take a moment)...")
        
        # Initialize TTS
        try:
            import inspect
            sig = inspect.signature(TTS.__init__)
            if 'device' in sig.parameters:
                tts = TTS(MODEL_ID, device=device)
            else:
                tts = TTS(MODEL_ID, gpu=(device == "cuda"))
        except Exception as e:
            print(f"   Fallback initialization...")
            tts = TTS(MODEL_ID, gpu=(device == "cuda"))
        
        print(f"✅ TTS initialized successfully")
        
    except Exception as e:
        print(f"❌ Error initializing TTS: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 4: Generate speech
    print_section("Step 4: Generating Speech")
    print(f"   Text: {TEST_TEXT}")
    print(f"   Speaker WAV: {speaker_wav_path}")
    print(f"   Language: {LANGUAGE}")
    print(f"   Generating (this may take 30-60s on CPU)...")
    
    try:
        import time
        output_path = os.path.join(_project_root, "test_output.wav")
        
        synthesis_start = time.time()
        
        # Generate speech
        tts.tts_to_file(
            text=TEST_TEXT,
            file_path=output_path,
            speaker_wav=speaker_wav_path,
            language=LANGUAGE.lower()
        )
        
        processing_time = time.time() - synthesis_start
        print(f"✅ TTS synthesis completed in {processing_time:.2f}s")
        
        # Verify output file
        if os.path.exists(output_path):
            file_size = os.path.getsize(output_path)
            print(f"✅ Output file created:")
            print(f"   Path: {output_path}")
            print(f"   Size: {file_size:,} bytes ({file_size / 1024:.2f} KB)")
            
            # Get audio info
            try:
                output_audio, output_sr = sf.read(output_path)
                duration = len(output_audio) / output_sr
                print(f"   Sample rate: {output_sr} Hz")
                print(f"   Duration: {duration:.2f}s")
                print(f"   Channels: {'mono' if len(output_audio.shape) == 1 else 'stereo'}")
            except:
                pass
        else:
            print(f"❌ Output file was not created")
            return
        
    except Exception as synthesis_error:
        print(f"❌ TTS synthesis failed: {synthesis_error}")
        import traceback
        traceback.print_exc()
        return
    
    # Step 5: Cleanup
    print_section("Step 5: Cleanup")
    try:
        if os.path.exists(speaker_wav_path):
            os.unlink(speaker_wav_path)
            print(f"✅ Cleaned up temporary speaker WAV file")
    except:
        pass
    
    # Final summary
    print_section("✅ TEST COMPLETE")
    print(f"\n🎵 Audio File Generated:")
    print(f"   📁 Path: {output_path}")
    print(f"   💡 You can:")
    print(f"      - Open the file in any audio player")
    print(f"      - Or run: open {output_path}")
    print(f"      - Or run: afplay {output_path}  (on macOS)")
    
    print(f"\n📊 Quality Assessment:")
    print(f"   Listen to the audio and check for:")
    print(f"   ✅ Natural voice quality")
    print(f"   ✅ Proper pronunciation")
    print(f"   ✅ Voice cloning accuracy (should sound like the speaker)")
    print(f"   ✅ Audio clarity")
    print(f"   ✅ Appropriate pacing and intonation")
    print(f"   ✅ No robotic or artificial sounds")
    
    print(f"\n{'=' * 80}")
    
    # Try to open the file automatically (macOS)
    try:
        if sys.platform == "darwin":
            os.system(f"open {output_path}")
            print(f"\n🎵 Opened audio file in default player")
    except:
        pass

if __name__ == "__main__":
    asyncio.run(test_tts_quality())
