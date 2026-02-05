#!/usr/bin/env python3
"""
Machine Translation Pipeline using HuggingFace models
Supports both text and document translation with robust error handling
"""

import time
import torch
import numpy as np
from transformers import (
    AutoTokenizer, 
    AutoModelForSeq2SeqLM, 
    pipeline,
    MarianMTModel,
    MarianTokenizer
)
import io
import fitz  # PyMuPDF for PDF processing
from docx import Document
import tempfile
import os
from typing import Optional, Tuple, Dict, List, Union
import logging
from template.utils.hf_token import get_hf_token_dict

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TranslationPipeline:
    """
    Machine translation pipeline using HuggingFace models.
    Supports multiple languages and document formats.
    """
    
    def __init__(self, model_name: str = "t5-small"):
        """
        Initialize the translation pipeline.
        
        Args:
            model_name: HuggingFace model name for translation
        """
        self.model_name = model_name
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        # Language code mapping for common languages
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
            "zh": "chinese",
            "ar": "arabic",
            "hi": "hindi",
            "nl": "dutch",
            "pl": "polish",
            "sv": "swedish",
            "tr": "turkish",
            "bg": "bulgarian",
            "ca": "catalan",
            "cs": "czech",
            "da": "danish",
            "el": "greek",
            "et": "estonian",
            "fi": "finnish",
            "hr": "croatian",
            "hu": "hungarian",
            "id": "indonesian",
            "lt": "lithuanian",
            "lv": "latvian",
            "ms": "malay",
            "mt": "maltese",
            "no": "norwegian",
            "ro": "romanian",
            "sk": "slovak",
            "sl": "slovenian",
            "th": "thai",
            "uk": "ukrainian",
            "vi": "vietnamese"
        }
        
        # Get HF token if available
        hf_token_kwargs = get_hf_token_dict()
        
        # Try to load the requested model first
        try:
            logger.info(f"🔄 Loading translation model: {model_name}")
            
            # For Helsinki-NLP Marian models, use MarianMTModel
            if "opus-mt" in model_name.lower() or "marian" in model_name.lower():
                try:
                    from transformers import MarianMTModel, MarianTokenizer
                    self.tokenizer = MarianTokenizer.from_pretrained(model_name, **hf_token_kwargs)
                    self.model = MarianMTModel.from_pretrained(model_name, **hf_token_kwargs)
                    self.model.to(self.device)
                    self.model.eval()  # Set to evaluation mode
                    logger.info(f"✅ Marian model loaded successfully on {self.device}: {model_name}")
                    self.translation_pipeline = None  # Use manual inference for Marian models
                except Exception as e:
                    logger.warning(f"⚠️ Failed to load as Marian model, trying AutoModel: {e}")
                    # Fallback to AutoModel
                    self.tokenizer = AutoTokenizer.from_pretrained(model_name, **hf_token_kwargs)
                    self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name, **hf_token_kwargs)
                    self.model.to(self.device)
                    self.model.eval()
                    logger.info(f"✅ Translation model loaded successfully on {self.device}: {model_name}")
                    self.translation_pipeline = None
            else:
                # For other models (T5, mBART, etc.), use AutoModel
                try:
                    # Load tokenizer first
                    self.tokenizer = AutoTokenizer.from_pretrained(model_name, **hf_token_kwargs)
                    
                    # For mBART models, set src_lang and tgt_lang if available
                    if "mbart" in model_name.lower():
                        # mBART uses language codes like "en_XX", "es_XX", etc.
                        # We'll set these dynamically during translation
                        logger.info(f"📝 mBART model detected: {model_name}")
                    
                    # Load model
                    self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name, **hf_token_kwargs)
                    self.model.to(self.device)
                    self.model.eval()
                    logger.info(f"✅ Translation model loaded successfully on {self.device}: {model_name}")
                    
                    # Try to use pipeline for easier inference (but not for Marian models or mBART)
                    try:
                        # Only use pipeline for T5 models (not Marian, not mBART)
                        if ("opus-mt" not in model_name.lower() and 
                            "marian" not in model_name.lower() and 
                            "mbart" not in model_name.lower()):
                            self.translation_pipeline = pipeline(
                                "translation", 
                                model=model_name, 
                                device=0 if self.device == "cuda" else -1,
                                token=hf_token_kwargs.get("token") if hf_token_kwargs else None
                            )
                            logger.info("✅ Translation pipeline initialized successfully")
                        else:
                            self.translation_pipeline = None
                            logger.info("ℹ️ Using manual inference (model-specific handling required)")
                    except Exception as e:
                        logger.warning(f"⚠️ Pipeline initialization failed, using manual inference: {e}")
                        self.translation_pipeline = None
                except Exception as e:
                    logger.error(f"❌ Failed to load model {model_name}: {e}")
                    raise
                    
        except Exception as e:
            logger.error(f"❌ Failed to load model {model_name}: {e}")
            # Fallback to t5-small if requested model fails
            logger.warning(f"⚠️ Falling back to t5-small")
            fallback_model = "t5-small"
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(fallback_model, **hf_token_kwargs)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(fallback_model, **hf_token_kwargs)
                self.model.to(self.device)
                self.model.eval()
                self.model_name = fallback_model
                logger.info(f"✅ Fallback model loaded successfully on {self.device}: {fallback_model}")
                self.translation_pipeline = None
            except Exception as fallback_error:
                raise Exception(f"Could not load translation model {model_name} or fallback {fallback_model}: {fallback_error}")
        
        # Production settings
        self.max_chunk_size = 1000  # Maximum characters per translation chunk
        self.chunk_overlap = 50     # Characters overlap between chunks
        self.max_concurrent_chunks = 4  # Maximum concurrent chunk processing
        
        # Performance monitoring
        self.processing_stats = {
            'total_translations': 0,
            'total_text_length': 0,
            'total_processing_time': 0.0,
            'memory_usage_samples': []
        }
    
    def translate_text(
        self, 
        text: str, 
        source_language: str, 
        target_language: str,
        max_length: int = 512
    ) -> Tuple[str, float]:
        """
        Translate text from source language to target language.
        
        Args:
            text: Input text to translate
            source_language: Source language code
            target_language: Target language code
            max_length: Maximum length for translation chunks
            
        Returns:
            Tuple of (translated_text, processing_time)
        """
        start_time = time.time()
        
        try:
            logger.info(f"🌐 Translating text from {source_language} to {target_language}")
            logger.info(f"   Text length: {len(text)} characters")
            
            # Handle long texts by chunking
            if len(text) > max_length:
                logger.info(f"📝 Text is long ({len(text)} chars), chunking for translation")
                translated_chunks = []
                
                # Split text into chunks
                chunks = self._chunk_text(text, max_length)
                logger.info(f"   Split into {len(chunks)} chunks")
                
                for i, chunk in enumerate(chunks):
                    logger.info(f"   Translating chunk {i+1}/{len(chunks)} ({len(chunk)} chars)")
                    translated_chunk = self._translate_chunk(chunk, source_language, target_language)
                    translated_chunks.append(translated_chunk)
                
                # Combine translated chunks
                translated_text = " ".join(translated_chunks)
                logger.info(f"✅ Combined {len(translated_chunks)} translated chunks")
                
            else:
                # Direct translation for short texts
                translated_text = self._translate_chunk(text, source_language, target_language)
            
            processing_time = time.time() - start_time
            logger.info(f"✅ Translation completed in {processing_time:.2f}s")
            logger.info(f"   Original length: {len(text)} characters")
            logger.info(f"   Translated length: {len(translated_text)} characters")
            
            return translated_text, processing_time
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Translation failed: {e}")
            raise Exception(f"Translation failed: {str(e)}")
    
    def _translate_chunk(
        self, 
        text: str, 
        source_language: str, 
        target_language: str
    ) -> str:
        """Translate a single chunk of text"""
        try:
            if self.translation_pipeline and "opus-mt" not in self.model_name.lower():
                # Use pipeline if available (but not for Marian models)
                try:
                    result = self.translation_pipeline(text)
                    if isinstance(result, list) and len(result) > 0:
                        if isinstance(result[0], dict):
                            return result[0].get('translation_text', result[0].get('translated_text', ''))
                        else:
                            return str(result[0])
                    return str(result) if result else ""
                except Exception as pipeline_error:
                    logger.warning(f"⚠️ Pipeline translation failed, using manual inference: {pipeline_error}")
                    # Fall through to manual inference
            
            # Manual inference
            # Handle different model types
            if "mbart" in self.model_name.lower():
                # mBART models need special handling with language codes
                try:
                    # mBART uses language codes like "en_XX", "es_XX", etc.
                    mbart_lang_map = {
                        "en": "en_XX", "es": "es_XX", "fr": "fr_XX", "de": "de_XX",
                        "it": "it_XX", "pt": "pt_XX", "ru": "ru_XX", "ja": "ja_XX",
                        "ko": "ko_XX", "zh": "zh_CN", "ar": "ar_XX", "hi": "hi_IN",
                        "nl": "nl_XX", "pl": "pl_XX", "tr": "tr_XX", "vi": "vi_VN",
                        "cs": "cs_CZ", "fi": "fi_FI", "ro": "ro_RO", "uk": "uk_UA"
                    }
                    src_lang_code = mbart_lang_map.get(source_language, f"{source_language}_XX")
                    tgt_lang_code = mbart_lang_map.get(target_language, f"{target_language}_XX")
                    
                    # Set source language
                    if hasattr(self.tokenizer, 'src_lang'):
                        self.tokenizer.src_lang = src_lang_code
                    
                    # Encode text
                    encoded = self.tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)
                    encoded = {k: v.to(self.device) for k, v in encoded.items()}
                    
                    # Get target language token ID
                    forced_bos_token_id = None
                    if hasattr(self.tokenizer, 'lang_code_to_id') and isinstance(self.tokenizer.lang_code_to_id, dict):
                        forced_bos_token_id = self.tokenizer.lang_code_to_id.get(tgt_lang_code)
                    
                    # Generate translation
                    with torch.no_grad():
                        generated_tokens = self.model.generate(
                            **encoded,
                            forced_bos_token_id=forced_bos_token_id,
                            max_length=512,
                            num_beams=4,
                            early_stopping=True
                        )
                    
                    # Decode
                    translated_text = self.tokenizer.decode(generated_tokens[0], skip_special_tokens=True)
                    return translated_text
                except Exception as mbart_error:
                    logger.warning(f"⚠️ mBART-specific translation failed, using generic method: {mbart_error}")
                    # Fall through to generic method
                    input_text = text
            elif "t5" in self.model_name.lower():
                # T5 models need translation prefix
                target_lang_name = self.language_codes.get(target_language, target_language)
                prefix = f"translate {self.language_codes.get(source_language, source_language)} to {target_lang_name}: "
                input_text = prefix + text
            elif "opus-mt" in self.model_name.lower() or "marian" in self.model_name.lower():
                # Marian models work directly - they're already configured for specific language pairs
                input_text = text
            else:
                # Default: use text as-is
                input_text = text
            
            # Tokenize input
            inputs = self.tokenizer(
                input_text, 
                return_tensors="pt", 
                max_length=512, 
                truncation=True,
                padding=True
            )
            
            # Move inputs to device
            inputs = {k: v.to(self.device) for k, v in inputs.items()}
            
            # Generate translation
            with torch.no_grad():  # Disable gradient computation for inference
                outputs = self.model.generate(
                    **inputs,
                    max_length=512,
                    num_beams=4,
                    early_stopping=True,
                    pad_token_id=self.tokenizer.pad_token_id if self.tokenizer.pad_token_id is not None else self.tokenizer.eos_token_id
                )
            
            # Decode output
            translated_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return translated_text
                
        except Exception as e:
            logger.error(f"❌ Chunk translation failed: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            raise
    
    def _chunk_text(self, text: str, max_length: int) -> List[str]:
        """Split text into chunks for translation"""
        words = text.split()
        chunks = []
        current_chunk = []
        current_length = 0
        
        for word in words:
            word_length = len(word) + 1  # +1 for space
            if current_length + word_length > max_length and current_chunk:
                chunks.append(" ".join(current_chunk))
                current_chunk = [word]
                current_length = word_length
            else:
                current_chunk.append(word)
                current_length += word_length
        
        if current_chunk:
            chunks.append(" ".join(current_chunk))
        
        return chunks
    
    def translate_document(
        self, 
        file_data, 
        filename: str,
        source_language: str, 
        target_language: str
    ) -> Tuple[str, float, Dict]:
        """
        Translate document content from source language to target language.
        
        Args:
            file_data: Raw file bytes
            filename: Original filename
            source_language: Source language code
            target_language: Target language code
            
        Returns:
            Tuple of (translated_text, processing_time, metadata)
        """
        start_time = time.time()
        
        try:
            logger.info(f"📄 Translating document: {filename}")
            logger.info(f"   File size: {len(file_data)} bytes")
            logger.info(f"   From {source_language} to {target_language}")
            
            # Extract text from document based on file type
            file_extension = filename.lower().split('.')[-1]
            
            if file_extension == 'pdf':
                extracted_text = self._extract_text_from_pdf(file_data)
            elif file_extension == 'docx':
                extracted_text = self._extract_text_from_docx(file_data)
            elif file_extension in ['txt', 'text']:
                extracted_text = self._extract_text_from_txt(file_data)
            else:
                raise Exception(f"Unsupported file format: {file_extension}")
            
            logger.info(f"✅ Text extracted: {len(extracted_text)} characters")
            
            # Translate the extracted text
            translated_text, translation_time = self.translate_text(
                extracted_text, source_language, target_language
            )
            
            total_time = time.time() - start_time
            
            # Prepare metadata
            metadata = {
                'original_filename': filename,
                'file_extension': file_extension,
                'file_size_bytes': len(file_data),
                'extracted_text_length': len(extracted_text),
                'translated_text_length': len(translated_text),
                'source_language': source_language,
                'target_language': target_language,
                'extraction_time': total_time - translation_time,
                'translation_time': translation_time,
                'total_time': total_time
            }
            
            logger.info(f"✅ Document translation completed in {total_time:.2f}s")
            return translated_text, total_time, metadata
            
        except Exception as e:
            total_time = time.time() - start_time
            logger.error(f"❌ Document translation failed: {e}")
            raise Exception(f"Document translation failed: {str(e)}")
    
    def _extract_text_from_pdf(self, file_data: bytes) -> str:
        """Extract text from PDF file"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name
            
            try:
                # Open PDF and extract text
                doc = fitz.open(temp_file_path)
                text_parts = []
                
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    text = page.get_text()
                    if text.strip():
                        text_parts.append(text.strip())
                
                doc.close()
                
                extracted_text = "\n\n".join(text_parts)
                logger.info(f"✅ PDF text extraction: {len(doc)} pages, {len(extracted_text)} chars")
                return extracted_text
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"❌ PDF text extraction failed: {e}")
            raise Exception(f"PDF text extraction failed: {str(e)}")
    
    def _extract_text_from_docx(self, file_data: bytes) -> str:
        """Extract text from DOCX file"""
        try:
            # Create temporary file
            with tempfile.NamedTemporaryFile(suffix='.docx', delete=False) as temp_file:
                temp_file.write(file_data)
                temp_file_path = temp_file.name
            
            try:
                # Open DOCX and extract text
                doc = Document(temp_file_path)
                text_parts = []
                
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip():
                        text_parts.append(paragraph.text.strip())
                
                # Also extract text from tables
                for table in doc.tables:
                    for row in table.rows:
                        for cell in row.cells:
                            if cell.text.strip():
                                text_parts.append(cell.text.strip())
                
                extracted_text = "\n\n".join(text_parts)
                logger.info(f"✅ DOCX text extraction: {len(text_parts)} paragraphs, {len(extracted_text)} chars")
                return extracted_text
                
            finally:
                # Clean up temporary file
                if os.path.exists(temp_file_path):
                    os.unlink(temp_file_path)
                    
        except Exception as e:
            logger.error(f"❌ DOCX text extraction failed: {e}")
            raise Exception(f"DOCX text extraction failed: {str(e)}")
    
    def _extract_text_from_txt(self, file_data) -> str:
        """Extract text from text file"""
        try:
            # Handle both string and bytes input
            if isinstance(file_data, str):
                # If it's already a string, return it directly
                logger.info(f"✅ Text file already string: {len(file_data)} chars")
                return file_data
            elif isinstance(file_data, bytes):
                # If it's bytes, decode it
                encodings = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1']
                
                for encoding in encodings:
                    try:
                        text = file_data.decode(encoding)
                        logger.info(f"✅ Text file decoded using {encoding}: {len(text)} chars")
                        return text
                    except UnicodeDecodeError:
                        continue
                
                # If all encodings fail, use latin-1 with replacement
                text = file_data.decode('latin-1', errors='replace')
                logger.warning(f"⚠️ Text file decoded with replacement: {len(text)} chars")
                return text
            else:
                # Convert other types to string
                text = str(file_data)
                logger.info(f"✅ Text file converted to string: {len(text)} chars")
                return text
                
        except Exception as e:
            logger.error(f"❌ Text file extraction failed: {e}")
            raise Exception(f"Text file extraction failed: {str(e)}")
    
    def get_supported_languages(self) -> List[str]:
        """Get list of supported language codes"""
        return list(self.language_codes.keys())
    
    def validate_language_pair(self, source_lang: str, target_lang: str) -> bool:
        """Validate if language pair is supported"""
        return source_lang in self.language_codes and target_lang in self.language_codes
    
    def get_model_info(self) -> Dict:
        """Get information about the loaded model"""
        return {
            'model_name': self.model_name,
            'device': self.device,
            'supported_languages': self.get_supported_languages(),
            'model_loaded': self.model is not None,
            'pipeline_available': self.translation_pipeline is not None
        }
    
    def _update_stats(self, text_length: int, processing_time: float):
        """Update processing statistics"""
        self.processing_stats['total_translations'] += 1
        self.processing_stats['total_text_length'] += text_length
        self.processing_stats['total_processing_time'] += processing_time
    
    def _cleanup_memory(self):
        """Clean up memory and perform garbage collection"""
        try:
            # Clear CUDA cache if using GPU
            if self.device == "cuda" and torch.cuda.is_available():
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
            'total_translations': self.processing_stats['total_translations'],
            'total_text_length': self.processing_stats['total_text_length'],
            'total_processing_time': self.processing_stats['total_processing_time'],
            'average_processing_speed': (
                self.processing_stats['total_text_length'] / 
                max(self.processing_stats['total_processing_time'], 0.001)
            ),
            'memory_usage_samples': self.processing_stats['memory_usage_samples'][-10:],  # Last 10 samples
            'model_info': {
                'name': self.model_name,
                'device': self.device,
                'max_chunk_size': self.max_chunk_size,
                'chunk_overlap': self.chunk_overlap,
                'max_concurrent_chunks': self.max_concurrent_chunks
            }
        }
    
    def optimize_for_production(self, target_max_chunk_size: int = 800, target_chunk_overlap: int = 30):
        """Optimize pipeline settings for production use"""
        self.max_chunk_size = target_max_chunk_size
        self.chunk_overlap = target_chunk_overlap
        
        logger.info(f"⚙️ Translation pipeline optimized for production:")
        logger.info(f"   Max chunk size: {target_max_chunk_size} characters")
        logger.info(f"   Chunk overlap: {target_chunk_overlap} characters")
        
        # Force memory cleanup
        self._cleanup_memory()

# Global instance
# Global instance for backward compatibility (lazy initialization)
# Removed immediate instantiation to prevent model loading during import
_translation_pipeline_instance = None

def get_translation_pipeline_instance():
    """Get or create the global translation pipeline instance (lazy)"""
    global _translation_pipeline_instance
    if _translation_pipeline_instance is None:
        _translation_pipeline_instance = TranslationPipeline()
    return _translation_pipeline_instance

# For backward compatibility - but prefer creating new instances
translation_pipeline = None
