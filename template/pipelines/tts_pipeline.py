# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# TODO(developer): Set your name
# Copyright © 2023 <your name>

import time
import sys
import torch
import numpy as np
import io
import soundfile as sf
from typing import Optional, Tuple, List, Dict
import gc
import psutil
import logging
from dataclasses import dataclass
import threading
import tempfile
import os

# Python 3.12 compatibility workaround for spacy/pydantic ForwardRef issue
# MUST be applied BEFORE importing TTS to prevent errors
python_version = sys.version_info
is_python_312 = python_version.major == 3 and python_version.minor == 12

if is_python_312:
    try:
        # Patch ForwardRef._evaluate to handle Python 3.12 compatibility
        import typing
        if hasattr(typing, 'ForwardRef'):
            original_evaluate = typing.ForwardRef._evaluate
            def patched_evaluate(self, globalns=None, localns=None, *args, **kwargs):
                # Python 3.12 requires recursive_guard as keyword-only argument
                # Handle calls that don't provide it
                if 'recursive_guard' not in kwargs:
                    # Not provided, add default empty set
                    kwargs['recursive_guard'] = set()
                # Call original with all arguments
                return original_evaluate(self, globalns, localns, *args, **kwargs)
            typing.ForwardRef._evaluate = patched_evaluate
            logger = logging.getLogger(__name__)
            if not logger.handlers:
                logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')
            logger.debug("✅ Applied Python 3.12 ForwardRef compatibility patch (module level)")
    except Exception as patch_error:
        # Can't log yet, just continue
        pass

# Now import TTS after the patch
from TTS.api import TTS

# Configure logging (only if not already configured)
logger = logging.getLogger(__name__)
if not logger.handlers:
    # Only configure if no handlers exist (avoid overriding existing config)
    logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

@dataclass
class TTSSynthesisResult:
    """Result of TTS synthesis with metadata"""
    audio_bytes: bytes
    processing_time: float
    text_length: int
    audio_duration: float
    sample_rate: int
    language: str
    speaker: Optional[str]
    metadata: Dict


class TTSPipeline:
    """
    Text-to-Speech pipeline using Coqui TTS models.
    Supports multiple languages and voices.
    """
    
    def __init__(self, model_name: str = "tts_models/multilingual/multi-dataset/your_tts"):
        """
        Initialize the TTS pipeline with a multilingual model.
        
        Args:
            model_name: TTS model name from Coqui TTS (default: multilingual model)
        """
        self.model_name = model_name
        # Re-evaluate the device to ensure it's a string ('cuda' or 'cpu')
        # We will use a new variable name to avoid any lingering shadowing issues with 'device'
        target_device = "cuda" if torch.cuda.is_available() else "cpu"
        self.device = target_device
        
        # Try to use gpu parameter in constructor first (original pattern that worked)
        # This is the pattern that was working in the original test
        try:
            # For XTTS models, using gpu=True in constructor may be more reliable
            if "xtts" in model_name.lower():
                # Try gpu parameter first (original working pattern)
                try:
                    self.tts = TTS(model_name, gpu=(target_device == "cuda"))
                    logger.info(f"✅ Loaded XTTS model: {model_name} with gpu={target_device == 'cuda'}")
                except TypeError:
                    # Fallback to device parameter if gpu doesn't work
                    try:
                        self.tts = TTS(model_name, device=target_device)
                        logger.info(f"✅ Loaded XTTS model: {model_name} with device={target_device}")
                    except TypeError:
                        # Final fallback: initialize then move to device
                        self.tts = TTS(model_name)
                        self.tts.to(target_device)
                        logger.info(f"✅ Loaded XTTS model: {model_name}, moved to {target_device}")
            else:
                # For non-XTTS models, use standard initialization
                self.tts = TTS(model_name)
                self.tts.to(target_device)
                logger.info(f"✅ Loaded TTS model: {model_name} on device: {target_device}")
        except Exception as e:
            # CRITICAL: If the requested model is xtts_v2 (required for voice cloning),
            # don't fallback to your_tts as it doesn't support voice cloning properly
            if "xtts" in model_name.lower():
                logger.error(f"❌ Failed to load XTTS model {model_name} (required for voice cloning): {e}")
                logger.error(f"   XTTS models are required for voice cloning with speaker_wav")
                logger.error(f"   Falling back to your_tts will result in poor quality or babbling audio")
                raise Exception(f"Failed to load XTTS model {model_name} (required for voice cloning): {e}")
            
            logger.warning(f"⚠️ Failed to load {model_name}, trying fallback multilingual model...")
            # Fallback to a known multilingual model (only for non-XTTS models)
            try:
                fallback_model = "tts_models/multilingual/multi-dataset/your_tts"
                self.tts = TTS(fallback_model)
                self.tts.to(target_device)
                self.model_name = fallback_model  # Update model name to fallback
                logger.info(f"✅ Loaded fallback TTS model: {fallback_model} on device: {target_device}")
            except Exception as e2:
                logger.error(f"❌ Failed to load fallback model: {e2}")
                raise Exception(f"Could not load any TTS model: {e}, {e2}")
        
        # Language code mapping for multilingual model
        self.language_codes = {
            "en": "en",
            "es": "es", 
            "fr": "fr-fr",
            "de": "de",
            "it": "it",
            "pt": "pt-br",
            "ru": "ru",
            "ja": "ja",
            "ko": "ko",
            "zh": "zh",
            "ar": "ar",
            "hi": "hi",
            "nl": "nl",
            "pl": "pl",
            "sv": "sv",
            "tr": "tr"
        }
        
        # Check if model is multilingual
        self.is_multilingual = hasattr(self.tts, 'languages') and self.tts.languages is not None
        if self.is_multilingual:
            logger.info(f"✅ Using multilingual TTS model with languages: {self.tts.languages}")
        else:
            logger.warning(f"⚠️ Model may not be multilingual, language parameter may be ignored")
        
        # Detect model capabilities
        self.supports_voice_cloning = self._detect_voice_cloning_support()
        self.is_multi_speaker = hasattr(self.tts, 'speakers') and self.tts.speakers is not None and len(self.tts.speakers) > 0
        
        if self.supports_voice_cloning:
            logger.info(f"✅ Model {self.model_name} supports voice cloning with speaker_wav")
        else:
            logger.info(f"ℹ️  Model {self.model_name} does not support voice cloning - will use preset speakers or default voice")
        
        if self.is_multi_speaker:
            logger.info(f"✅ Model {self.model_name} supports multiple speakers: {len(self.tts.speakers)} available")
        
        # Production settings
        self.max_text_length = 5000  # Maximum characters per synthesis
        self.chunk_overlap = 100     # Characters overlap between chunks
        
        # Performance monitoring
        self.processing_stats = {
            'total_syntheses': 0,
            'total_text_length': 0,
            'total_processing_time': 0.0,
            'memory_usage_samples': []
        }
    
    def _detect_voice_cloning_support(self) -> bool:
        """
        Detect if the current model supports voice cloning with speaker_wav.
        
        Returns:
            True if model supports voice cloning, False otherwise
        """
        model_lower = self.model_name.lower()
        
        # XTTS models explicitly support voice cloning
        if "xtts" in model_lower:
            return True
        
        # YourTTS technically supports it but may not work well in practice
        # We'll mark it as not supporting to avoid poor quality results
        if "your_tts" in model_lower:
            return False
        
        # Tacotron2-DDC and VITS are single or fixed multi-speaker models
        # They don't support voice cloning
        return False
    
    def synthesize(self, text: str, language: str = "en", speaker: Optional[str] = None, speaker_wav: Optional[str] = None) -> Tuple[bytes, float]:
        """
        Synthesize text to speech.
        
        Args:
            text: Input text to synthesize
            language: Language code (e.g., 'en', 'es', 'fr')
            speaker: Speaker name (if model supports multiple speakers)
            speaker_wav: Path to speaker reference audio file for voice cloning (XTTS models only)
            
        Returns:
            Tuple of (audio_bytes, processing_time)
        """
        start_time = time.time()
        
        try:
            # Handle voice cloning for XTTS models
            if speaker_wav and isinstance(speaker_wav, str) and speaker_wav.strip() and self.supports_voice_cloning:
                speaker_wav = speaker_wav.strip()
                logger.info(f"🎤 Using speaker WAV for voice cloning: {speaker_wav}")
                
                # Validate speaker_wav file exists
                if not os.path.exists(speaker_wav):
                    logger.error(f"❌ Speaker WAV file not found: {speaker_wav}")
                    logger.error(f"   Current working directory: {os.getcwd()}")
                    logger.error(f"   Absolute path would be: {os.path.abspath(speaker_wav)}")
                    raise Exception(f"Speaker WAV file not found: {speaker_wav}")
                
                # Validate it's actually a file (not a directory)
                if not os.path.isfile(speaker_wav):
                    logger.error(f"❌ Speaker WAV path is not a file: {speaker_wav}")
                    raise Exception(f"Speaker WAV path is not a file: {speaker_wav}")
                
                logger.debug(f"✅ Speaker WAV file validated: {speaker_wav}")
                logger.info(f"✅ Using XTTS model {self.model_name} for voice cloning")
                
                # Create temporary file for output
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as tmp_file:
                    output_path = tmp_file.name
                
                try:
                    # Prepare parameters for tts_to_file
                    tts_params = {
                        "text": text,
                        "file_path": output_path,
                        "speaker_wav": speaker_wav
                    }
                    
                    # Add language if model is multilingual
                    if self.is_multilingual:
                        tts_params["language"] = language.lower()
                        logger.debug(f"🎵 Using language: {language.lower()} for TTS synthesis")
                    
                    logger.debug(f"🔧 TTS synthesis parameters: text={text[:50]}..., speaker_wav={speaker_wav}, language={tts_params.get('language', 'default')}")
                    
                    # Generate speech using tts_to_file (supports voice cloning)
                    self.tts.tts_to_file(**tts_params)
                    
                    # Read the generated audio file
                    with open(output_path, 'rb') as f:
                        audio_bytes = f.read()
                    
                    # Get audio info for metadata
                    audio_data, sample_rate = sf.read(output_path)
                    audio_duration = len(audio_data) / sample_rate
                    
                    processing_time = time.time() - start_time
                    
                    # Update statistics
                    self._update_stats(len(text), processing_time)
                    
                    logger.info(f"✅ TTS synthesis completed in {processing_time:.2f}s (voice cloning, duration: {audio_duration:.2f}s)")
                    
                    return audio_bytes, processing_time
                    
                finally:
                    # Clean up temporary file
                    if os.path.exists(output_path):
                        os.unlink(output_path)
            
            # Handle non-voice-cloning models (or when speaker_wav is not provided)
            else:
                # If speaker_wav was provided but model doesn't support it, log a warning and continue
                if speaker_wav and isinstance(speaker_wav, str) and speaker_wav.strip():
                    logger.warning(f"⚠️ Model {self.model_name} does not support voice cloning with speaker_wav.")
                    logger.warning(f"   Ignoring speaker_wav parameter and using preset speaker or default voice instead.")
                    logger.info(f"   For voice cloning, please use an XTTS model (xtts_v2 or xtts_v1)")
                
                # Use standard synthesis without voice cloning
                logger.debug(f"Using standard TTS synthesis (model: {self.model_name})")
                
                # Prepare synthesis parameters
                synthesis_params = {"text": text}
                
                # Add language if model is multilingual
                if self.is_multilingual:
                    synthesis_params["language"] = language.lower()
                    logger.debug(f"🎵 Using language: {language.lower()} for TTS synthesis")
                else:
                    logger.debug(f"ℹ️  Model is not multilingual, language parameter may be ignored: {language}")
                
                # Handle speaker selection for multi-speaker models
                if self.is_multi_speaker:
                    if speaker and speaker in self.tts.speakers:
                        synthesis_params["speaker"] = speaker
                        logger.info(f"🎤 Using specified speaker: {speaker}")
                    else:
                        # Auto-select first available speaker
                        default_speaker = self.tts.speakers[0]
                        synthesis_params["speaker"] = default_speaker
                        logger.info(f"🎤 Auto-selected speaker: {default_speaker} (from {len(self.tts.speakers)} available)")
                elif speaker:
                    logger.warning(f"⚠️ Speaker parameter '{speaker}' provided but model {self.model_name} is not multi-speaker. Ignoring speaker parameter.")
                
                logger.debug(f"🔧 TTS synthesis parameters: {synthesis_params}")
                
                # Synthesize audio
                audio_array = self.tts.tts(**synthesis_params)
                
                # Convert to bytes
                audio_bytes = io.BytesIO()
                sf.write(audio_bytes, audio_array, self.tts.synthesizer.output_sample_rate, format='WAV')
                audio_bytes.seek(0)
                
                processing_time = time.time() - start_time
                
                # Update statistics
                self._update_stats(len(text), processing_time)
                
                logger.info(f"✅ TTS synthesis completed in {processing_time:.2f}s (model: {self.model_name})")
                
                return audio_bytes.read(), processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ TTS synthesis error: {str(e)}")
            import traceback
            logger.debug(f"Traceback: {traceback.format_exc()}")
            raise Exception(f"TTS synthesis failed: {str(e)}")
    
    def get_available_models(self) -> list:
        """Get list of available TTS models."""
        return TTS.list_models()
    
    def get_supported_languages(self) -> list:
        """Get list of supported language codes."""
        return list(self.language_codes.keys())
    
    def validate_language(self, language: str) -> bool:
        """Validate if language is supported."""
        return language in self.language_codes
    
    def get_available_speakers(self) -> list:
        """Get list of available speakers (if model supports multiple speakers)."""
        if hasattr(self.tts, 'speakers'):
            return self.tts.speakers
        return []
    
    def _update_stats(self, text_length: int, processing_time: float):
        """Update processing statistics"""
        self.processing_stats['total_syntheses'] += 1
        self.processing_stats['total_text_length'] += text_length
        self.processing_stats['total_processing_time'] += processing_time
    
    def _cleanup_memory(self):
        """Clean up memory and perform garbage collection"""
        try:
            # Clear CUDA cache if using GPU
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
            
            # Force garbage collection
            gc.collect()
            
            # Log memory usage
            process = psutil.Process()
            current_memory = process.memory_info().rss / (1024 * 1024 * 1024)
            self.processing_stats['memory_usage_samples'].append(current_memory)
            logger.info(f"🧹 Memory cleanup completed. Current usage: {current_memory:.2f}GB")
            
        except Exception as e:
            logger.warning(f"⚠️ Memory cleanup failed: {e}")
    
    def get_performance_stats(self) -> Dict:
        """Get performance statistics"""
        return {
            'total_syntheses': self.processing_stats['total_syntheses'],
            'total_text_length': self.processing_stats['total_text_length'],
            'total_processing_time': self.processing_stats['total_processing_time'],
            'average_processing_speed': (
                self.processing_stats['total_text_length'] / 
                max(self.processing_stats['total_processing_time'], 0.001)
            ),
            'memory_usage_samples': self.processing_stats['memory_usage_samples'][-10:],  # Last 10 samples
            'model_info': {
                'name': self.model_name,
                'max_text_length': self.max_text_length,
                'chunk_overlap': self.chunk_overlap
            }
        }
    
    def optimize_for_production(self, target_max_text_length: int = 3000, target_chunk_overlap: int = 50):
        """Optimize pipeline settings for production use"""
        self.max_text_length = target_max_text_length
        self.chunk_overlap = target_chunk_overlap
        
        logger.info(f"⚙️ TTS pipeline optimized for production:")
        logger.info(f"   Max text length: {target_max_text_length} characters")
        logger.info(f"   Chunk overlap: {target_chunk_overlap} characters")
        
        # Force memory cleanup
        self._cleanup_memory()
