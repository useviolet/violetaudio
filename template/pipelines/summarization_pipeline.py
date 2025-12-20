# The MIT License (MIT)
# Copyright © 2023 Yuma Rao
# TODO(developer): Set your name
# Copyright © 2023 <your name>

import time
import torch
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM
from typing import Optional, Tuple
from template.utils.hf_token import get_hf_token_dict


class SummarizationPipeline:
    """
    Text summarization pipeline using HuggingFace transformers.
    Supports multiple languages and model sizes.
    """
    
    def __init__(self, model_name: str = "facebook/bart-large-cnn"):
        """
        Initialize the summarization pipeline.
        
        Args:
            model_name: HuggingFace model name for summarization
        """
        import time
        start_time = time.time()
        
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        print(f"🔄 Loading summarization model: {model_name} on {self.device}...")
        
        try:
            # Get HF token if available
            hf_token_kwargs = get_hf_token_dict()
            
            # Load tokenizer first (faster)
            print(f"   Loading tokenizer...")
            self.tokenizer = AutoTokenizer.from_pretrained(model_name, **hf_token_kwargs)
            print(f"   ✅ Tokenizer loaded")
            
            # Load model (slower, may download if not cached)
            print(f"   Loading model (this may take a while on first run)...")
            self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name, **hf_token_kwargs)
            self.model.to(self.device)
            print(f"   ✅ Model loaded and moved to {self.device}")
            
            load_time = time.time() - start_time
            print(f"✅ Summarization pipeline initialized in {load_time:.2f}s")
        except Exception as e:
            print(f"❌ Failed to load summarization model: {e}")
            import traceback
            print(f"   Traceback: {traceback.format_exc()}")
            raise
        
        # Language code mapping
        self.language_codes = {
            "en": "english",
            "es": "spanish", 
            "fr": "french",
            "de": "german",
            "it": "italian",
            "pt": "portuguese",
            "ru": "russian",
            "ja": "japanese",
            "ko": "korean",
            "zh": "chinese"
        }
    
    def summarize(self, text: str, max_length: int = 130, min_length: int = 30, language: str = "en") -> Tuple[str, float]:
        """
        Summarize text.
        
        Args:
            text: Input text to summarize
            max_length: Maximum length of summary
            min_length: Minimum length of summary
            language: Language code (e.g., 'en', 'es', 'fr')
            
        Returns:
            Tuple of (summary_text, processing_time)
        """
        start_time = time.time()
        
        try:
            # Tokenize input text
            inputs = self.tokenizer(
                text, 
                return_tensors="pt", 
                max_length=1024, 
                truncation=True,
                padding=True
            ).to(self.device)
            
            # Generate summary
            summary_ids = self.model.generate(
                inputs["input_ids"],
                max_length=max_length,
                min_length=min_length,
                length_penalty=2.0,
                num_beams=4,
                early_stopping=True
            )
            
            # Decode summary
            summary = self.tokenizer.decode(summary_ids[0], skip_special_tokens=True)
            
            processing_time = time.time() - start_time
            
            return summary.strip(), processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            raise Exception(f"Summarization failed: {str(e)}")
    
    def get_supported_languages(self) -> list:
        """Get list of supported language codes."""
        return list(self.language_codes.keys())
    
    def validate_language(self, language: str) -> bool:
        """Validate if language is supported."""
        return language in self.language_codes
    
    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "model_name": self.model_name,
            "max_input_length": self.tokenizer.model_max_length,
            "vocab_size": self.tokenizer.vocab_size
        }
