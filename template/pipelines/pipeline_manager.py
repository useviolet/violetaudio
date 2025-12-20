"""
Pipeline Manager for Dynamic Model Loading
Manages pipeline instances with different models and caches them for reuse
"""

import logging
from typing import Dict, Optional
# Lazy import - don't import hf_token at module level to avoid side effects
# from template.utils.hf_token import get_hf_token_dict

logger = logging.getLogger(__name__)

class PipelineManager:
    """
    Manages pipeline instances with different models.
    Caches pipelines by model_name to avoid reloading the same model.
    """
    
    def __init__(self):
        self._transcription_pipelines: Dict[str, any] = {}
        self._summarization_pipelines: Dict[str, any] = {}
        self._translation_pipelines: Dict[str, any] = {}
        self._tts_pipelines: Dict[str, any] = {}
        
        # Default models for each pipeline type
        self.default_models = {
            'transcription': 'openai/whisper-tiny',
            'summarization': 'facebook/bart-large-cnn',
            'translation': 't5-small',
            'tts': 'tts_models/multilingual/multi-dataset/your_tts'
        }
    
    def get_transcription_pipeline(self, model_name: Optional[str] = None):
        """Get transcription pipeline with specified model, or default if not specified"""
        import traceback
        import sys
        
        # Debug: Log where this is being called from
        caller = traceback.extract_stack()[-2]
        logger.debug(f"get_transcription_pipeline called from {caller.filename}:{caller.lineno} in {caller.name}")
        
        from template.pipelines.transcription_pipeline import TranscriptionPipeline
        
        # Use default model if not specified
        model_name = model_name or self.default_models['transcription']
        
        # Return cached pipeline if exists
        if model_name in self._transcription_pipelines:
            logger.info(f"✅ Using cached transcription pipeline: {model_name}")
            return self._transcription_pipelines[model_name]
        
        # Create new pipeline with specified model
        logger.info(f"🔄 Creating new transcription pipeline with model: {model_name}")
        try:
            pipeline = TranscriptionPipeline(model_name=model_name)
            self._transcription_pipelines[model_name] = pipeline
            logger.info(f"✅ Transcription pipeline created and cached: {model_name}")
            return pipeline
        except Exception as e:
            logger.error(f"❌ Failed to create transcription pipeline with model {model_name}: {e}")
            # Fallback to default model if specified model fails
            if model_name != self.default_models['transcription']:
                logger.warning(f"⚠️ Falling back to default model: {self.default_models['transcription']}")
                return self.get_transcription_pipeline(self.default_models['transcription'])
            raise
    
    def get_summarization_pipeline(self, model_name: Optional[str] = None):
        """Get summarization pipeline with specified model, or default if not specified"""
        from template.pipelines.summarization_pipeline import SummarizationPipeline
        
        # Use default model if not specified
        model_name = model_name or self.default_models['summarization']
        
        # Return cached pipeline if exists
        if model_name in self._summarization_pipelines:
            logger.info(f"✅ Using cached summarization pipeline: {model_name}")
            return self._summarization_pipelines[model_name]
        
        # Create new pipeline with specified model
        logger.info(f"🔄 Creating new summarization pipeline with model: {model_name}")
        try:
            pipeline = SummarizationPipeline(model_name=model_name)
            self._summarization_pipelines[model_name] = pipeline
            logger.info(f"✅ Summarization pipeline created and cached: {model_name}")
            return pipeline
        except Exception as e:
            logger.error(f"❌ Failed to create summarization pipeline with model {model_name}: {e}")
            # Fallback to default model if specified model fails
            if model_name != self.default_models['summarization']:
                logger.warning(f"⚠️ Falling back to default model: {self.default_models['summarization']}")
                return self.get_summarization_pipeline(self.default_models['summarization'])
            raise
    
    def get_translation_pipeline(self, model_name: Optional[str] = None):
        """Get translation pipeline with specified model, or default if not specified"""
        from template.pipelines.translation_pipeline import TranslationPipeline
        
        # Use default model if not specified
        model_name = model_name or self.default_models['translation']
        
        # Return cached pipeline if exists
        if model_name in self._translation_pipelines:
            logger.info(f"✅ Using cached translation pipeline: {model_name}")
            return self._translation_pipelines[model_name]
        
        # Create new pipeline with specified model
        logger.info(f"🔄 Creating new translation pipeline with model: {model_name}")
        try:
            pipeline = TranslationPipeline(model_name=model_name)
            self._translation_pipelines[model_name] = pipeline
            logger.info(f"✅ Translation pipeline created and cached: {model_name}")
            return pipeline
        except Exception as e:
            logger.error(f"❌ Failed to create translation pipeline with model {model_name}: {e}")
            # Fallback to default model if specified model fails
            if model_name != self.default_models['translation']:
                logger.warning(f"⚠️ Falling back to default model: {self.default_models['translation']}")
                return self.get_translation_pipeline(self.default_models['translation'])
            raise
    
    def get_tts_pipeline(self, model_name: Optional[str] = None):
        """Get TTS pipeline with specified model, or default if not specified"""
        try:
            from template.pipelines.tts_pipeline import TTSPipeline
        except ImportError:
            logger.warning("⚠️ TTS pipeline not available (TTS module not installed)")
            return None
        
        # Use default model if not specified
        model_name = model_name or self.default_models['tts']
        
        # Return cached pipeline if exists
        if model_name in self._tts_pipelines:
            logger.info(f"✅ Using cached TTS pipeline: {model_name}")
            return self._tts_pipelines[model_name]
        
        # Create new pipeline with specified model
        logger.info(f"🔄 Creating new TTS pipeline with model: {model_name}")
        try:
            pipeline = TTSPipeline(model_name=model_name)
            self._tts_pipelines[model_name] = pipeline
            logger.info(f"✅ TTS pipeline created and cached: {model_name}")
            return pipeline
        except Exception as e:
            logger.error(f"❌ Failed to create TTS pipeline with model {model_name}: {e}")
            # Fallback to default model if specified model fails
            if model_name != self.default_models['tts']:
                logger.warning(f"⚠️ Falling back to default model: {self.default_models['tts']}")
                return self.get_tts_pipeline(self.default_models['tts'])
            raise
    
    def clear_cache(self, pipeline_type: Optional[str] = None):
        """Clear pipeline cache for a specific type or all types"""
        if pipeline_type == 'transcription' or pipeline_type is None:
            self._transcription_pipelines.clear()
        if pipeline_type == 'summarization' or pipeline_type is None:
            self._summarization_pipelines.clear()
        if pipeline_type == 'translation' or pipeline_type is None:
            self._translation_pipelines.clear()
        if pipeline_type == 'tts' or pipeline_type is None:
            self._tts_pipelines.clear()
        logger.info(f"🧹 Pipeline cache cleared for: {pipeline_type or 'all'}")
    
    def get_cache_stats(self) -> Dict[str, int]:
        """Get statistics about cached pipelines"""
        return {
            'transcription': len(self._transcription_pipelines),
            'summarization': len(self._summarization_pipelines),
            'translation': len(self._translation_pipelines),
            'tts': len(self._tts_pipelines)
        }

# Global pipeline manager instance (lazy initialization)
# Only created when explicitly accessed to avoid model loading during import
_pipeline_manager_instance = None

def get_pipeline_manager():
    """Get or create the global pipeline manager instance (lazy)"""
    global _pipeline_manager_instance
    if _pipeline_manager_instance is None:
        _pipeline_manager_instance = PipelineManager()
    return _pipeline_manager_instance

# For backward compatibility - but creating new instances is preferred
# This will be None until get_pipeline_manager() is called
pipeline_manager = None

