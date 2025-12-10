# Miner Pipelines Summary

## Overview

The miner has **4 pipelines** for processing different types of tasks:

1. **Transcription Pipeline** - Audio to text
2. **TTS Pipeline** - Text to speech
3. **Summarization Pipeline** - Text summarization
4. **Translation Pipeline** - Text/document translation

---

## 1. Transcription Pipeline

**File:** `template/pipelines/transcription_pipeline.py`

### Model Used:
- **Model:** `openai/whisper-tiny` (default)
- **Framework:** HuggingFace Transformers
- **Components:**
  - `WhisperProcessor` from `transformers`
  - `WhisperForConditionalGeneration` from `transformers`

### Features:
- Supports multiple languages (en, es, fr, de, it, pt, ru, ja, ko, zh, ar, hi)
- Automatic audio chunking for long files (>30 seconds)
- Timestamped transcription support
- GPU/CPU automatic detection

### HuggingFace Token Required?
**NO** - `openai/whisper-tiny` is a public model, no authentication needed.

---

## 2. TTS Pipeline

**File:** `template/pipelines/tts_pipeline.py`

### Model Used:
- **Model:** `tts_models/multilingual/multi-dataset/your_tts` (default)
- **Framework:** Coqui TTS (not HuggingFace)
- **Components:**
  - `TTS` from `TTS.api`

### Features:
- Multilingual text-to-speech
- Supports multiple languages (en, es, fr, de, it, pt, ru, ja, ko, zh, ar, hi, nl, pl, sv, tr)
- Multiple speaker support
- Fallback to multilingual model if primary fails

### HuggingFace Token Required?
**NO** - Coqui TTS models are downloaded from their own repository, not HuggingFace.

**Note:** TTS module requires Python <3.12 (not compatible with Python 3.12+)

---

## 3. Summarization Pipeline

**File:** `template/pipelines/summarization_pipeline.py`

### Model Used:
- **Model:** `facebook/bart-large-cnn` (default)
- **Framework:** HuggingFace Transformers
- **Components:**
  - `AutoTokenizer` from `transformers`
  - `AutoModelForSeq2SeqLM` from `transformers`

### Features:
- Text summarization with configurable length
- Supports multiple languages (en, es, fr, de, it, pt, ru, ja, ko, zh)
- Beam search for quality generation
- Max input length: 1024 tokens

### HuggingFace Token Required?
**NO** - `facebook/bart-large-cnn` is a public model, no authentication needed.

---

## 4. Translation Pipeline

**File:** `template/pipelines/translation_pipeline.py`

### Models Used (with fallback):
1. **Primary:** `t5-small` (HuggingFace)
2. **Fallback 1:** `Helsinki-NLP/opus-mt-en-es` (Marian model)
3. **Fallback 2:** `facebook/mbart-large-50-many-to-many-mmt` (Multilingual)

**Framework:** HuggingFace Transformers
**Components:**
- `AutoTokenizer` from `transformers`
- `AutoModelForSeq2SeqLM` from `transformers`
- `pipeline` from `transformers` (optional)
- `MarianMTModel` and `MarianTokenizer` (for Marian models)

### Features:
- Text translation between multiple languages
- Document translation (PDF, DOCX, TXT)
- Supports 40+ languages
- Automatic chunking for long texts
- Document text extraction using PyMuPDF and python-docx

### HuggingFace Token Required?
**NO** - All fallback models (`t5-small`, `Helsinki-NLP/opus-mt-en-es`, `facebook/mbart-large-50-many-to-many-mmt`) are public models, no authentication needed.

---

## Summary Table

| Pipeline | Model(s) | Framework | HF Token Required? | Status |
|----------|----------|-----------|-------------------|--------|
| **Transcription** | `openai/whisper-tiny` | HuggingFace Transformers | ❌ NO | ✅ Active |
| **TTS** | `tts_models/multilingual/multi-dataset/your_tts` | Coqui TTS | ❌ NO | ⚠️ Optional (Python <3.12) |
| **Summarization** | `facebook/bart-large-cnn` | HuggingFace Transformers | ❌ NO | ✅ Active |
| **Translation** | `t5-small` (with fallbacks) | HuggingFace Transformers | ❌ NO | ✅ Active |

---

## Key Points

1. **Total Pipelines:** 4 pipelines
2. **HuggingFace Token Required:** **NO** - All models are public and don't require authentication
3. **Model Sources:**
   - 3 pipelines use HuggingFace Transformers (public models)
   - 1 pipeline uses Coqui TTS (separate repository)
4. **All models are downloaded automatically** on first use (cached for subsequent runs)

---

## Pipeline Initialization in Miner

From `neurons/miner.py`:

```python
# 1. Transcription Pipeline
self.transcription_pipeline = TranscriptionPipeline()

# 2. TTS Pipeline (optional - may fail if TTS module not installed)
self.tts_pipeline = TTSPipeline()

# 3. Summarization Pipeline
self.summarization_pipeline = SummarizationPipeline()

# 4. Translation Pipeline
self.translation_pipeline = translation_pipeline  # Global instance
```

---

## Dependencies

All pipelines require:
- `torch` (PyTorch)
- `transformers` (HuggingFace)
- `numpy`
- `librosa` (for transcription)
- `soundfile` (for audio processing)
- `PyMuPDF` (for PDF translation)
- `python-docx` (for DOCX translation)
- `TTS` (for TTS pipeline - optional, Python <3.12 only)

---

## Notes

- **TTS Pipeline:** May not be available if Python 3.12+ is used (TTS module incompatibility)
- **All models are public:** No HuggingFace authentication tokens needed
- **Automatic fallbacks:** Translation pipeline has multiple fallback models for reliability
- **GPU Support:** All pipelines automatically detect and use CUDA if available

