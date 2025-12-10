# Task Routing Mechanism: How Miner and Validator Know Which Pipeline to Use

## Overview

Both the **Miner** and **Validator** use a **task_type-based routing system** to determine which pipeline and inference method to trigger when processing a task.

## 1. Task Structure

Every task contains a `task_type` field that specifies what kind of processing is needed:

```python
task_data = {
    "task_id": "abc123",
    "task_type": "transcription",  # ← This determines the pipeline
    "model_id": "openai/whisper-large",  # ← Optional: specific model to use
    "source_language": "en",
    "input_file_id": "file123",
    # ... other fields
}
```

## 2. Supported Task Types

The system supports the following task types:

| Task Type | Pipeline Used | Inference Method |
|-----------|--------------|------------------|
| `transcription` | TranscriptionPipeline | `transcribe()` |
| `video_transcription` | TranscriptionPipeline | `transcribe()` (after audio extraction) |
| `tts` | TTSPipeline | `synthesize()` |
| `summarization` | SummarizationPipeline | `summarize()` |
| `text_translation` | TranslationPipeline | `translate_text()` |
| `document_translation` | TranslationPipeline | `translate_document()` |

## 3. Miner Routing Logic

### Location: `neurons/miner.py` → `process_proxy_task()`

```python
# Step 1: Extract task_type from task data
task_type = task_data.get("task_type")  # e.g., "transcription"

# Step 2: Extract model_id (optional)
model_id = task_data.get("model_id")  # e.g., "openai/whisper-large"

# Step 3: Route based on task_type
if task_type == "transcription":
    result = await self.process_transcription_task(
        input_data, 
        model_id=model_id, 
        language=source_language
    )
elif task_type == "tts":
    result = await self.process_tts_task(
        input_data, 
        model_id=model_id, 
        language=source_language
    )
elif task_type == "summarization":
    result = await self.process_summarization_task(
        input_data, 
        model_id=model_id, 
        language=source_language
    )
elif task_type == "video_transcription":
    result = await self.process_video_transcription_task(
        input_data, 
        task_data, 
        model_id=model_id
    )
elif task_type == "text_translation":
    result = await self.process_text_translation_task(
        task_data, 
        model_id=model_id, 
        source_language=source_language, 
        target_language=target_language
    )
elif task_type == "document_translation":
    result = await self.process_document_translation_task(
        input_data, 
        task_data, 
        model_id=model_id, 
        source_language=source_language, 
        target_language=target_language
    )
```

### Flow Diagram for Miner:

```
Task Received
    ↓
Extract task_type from task_data
    ↓
┌─────────────────────────────────────┐
│  Route Based on task_type           │
│                                     │
│  transcription → process_transcription_task() │
│  tts → process_tts_task()          │
│  summarization → process_summarization_task() │
│  video_transcription → process_video_transcription_task() │
│  text_translation → process_text_translation_task() │
│  document_translation → process_document_translation_task() │
└─────────────────────────────────────┘
    ↓
Each process_*_task method:
    ↓
1. Gets model_id from parameter
    ↓
2. Calls pipeline_manager.get_*_pipeline(model_id)
    ↓
3. Pipeline Manager loads model on-demand (or uses cached)
    ↓
4. Calls appropriate inference method:
   - pipeline.transcribe() for transcription
   - pipeline.synthesize() for TTS
   - pipeline.summarize() for summarization
   - pipeline.translate_text() for translation
```

## 4. Validator Routing Logic

### Location: `neurons/validator.py` → `_execute_pipeline_robust()`

```python
# Step 1: Receive task_type as parameter
async def _execute_pipeline_robust(
    self, 
    task_type: str,  # e.g., "transcription"
    input_data: Any, 
    task_id: str, 
    model_id: Optional[str] = None
) -> Optional[Dict]:
    
    # Step 2: Route based on task_type
    if task_type == 'transcription':
        result = await self.execute_transcription_task({
            'input_data': input_data, 
            'task_id': task_id, 
            'model_id': model_id
        })
    elif task_type == 'video_transcription':
        result = await self.execute_video_transcription_task({
            'input_data': input_data, 
            'task_id': task_id, 
            'model_id': model_id
        })
    elif task_type == 'tts':
        result = await self.execute_tts_task({
            'input_data': input_data, 
            'task_id': task_id, 
            'model_id': model_id
        })
    elif task_type == 'summarization':
        result = await self.execute_summarization_task({
            'input_data': input_data, 
            'task_id': task_id, 
            'model_id': model_id
        })
    elif task_type == 'text_translation':
        result = await self.execute_text_translation_task({
            'input_data': input_data, 
            'task_id': task_id, 
            'model_id': model_id
        })
    elif task_type == 'document_translation':
        result = await self.execute_document_translation_task({
            'input_data': input_data, 
            'task_id': task_id, 
            'model_id': model_id
        })
```

### Flow Diagram for Validator:

```
Task Evaluation
    ↓
Extract task_type from task
    ↓
Call _execute_pipeline_robust(task_type, ...)
    ↓
┌─────────────────────────────────────┐
│  Route Based on task_type           │
│                                     │
│  transcription → execute_transcription_task() │
│  tts → execute_tts_task()          │
│  summarization → execute_summarization_task() │
│  video_transcription → execute_video_transcription_task() │
│  text_translation → execute_text_translation_task() │
│  document_translation → execute_document_translation_task() │
└─────────────────────────────────────┘
    ↓
Each execute_*_task method:
    ↓
1. Gets model_id from task dict
    ↓
2. Calls pipeline_manager.get_*_pipeline(model_id)
    ↓
3. Pipeline Manager loads model on-demand (or uses cached)
    ↓
4. Calls appropriate inference method:
   - pipeline.transcribe() for transcription
   - pipeline.synthesize() for TTS
   - pipeline.summarize() for summarization
   - pipeline.translate_text() for translation
```

## 5. Pipeline Manager: Dynamic Model Loading

### Location: `template/pipelines/pipeline_manager.py`

The Pipeline Manager is responsible for:
1. **Loading models on-demand** when a task is assigned
2. **Caching loaded models** to avoid redundant loading
3. **Returning the correct pipeline instance** based on model_id

```python
# Example: Transcription Pipeline
pipeline = self.pipeline_manager.get_transcription_pipeline(model_id)

# Inside PipelineManager:
def get_transcription_pipeline(self, model_name: Optional[str] = None):
    # Use default model if not specified
    model_name = model_name or self.default_models['transcription']
    
    # Return cached pipeline if exists
    if model_name in self._transcription_pipelines:
        return self._transcription_pipelines[model_name]
    
    # Create new pipeline with specified model
    pipeline = TranscriptionPipeline(model_name=model_name)
    self._transcription_pipelines[model_name] = pipeline
    return pipeline
```

## 6. Complete Flow Example: Transcription Task

### Miner Side:

```
1. Task received from proxy:
   {
       "task_id": "task123",
       "task_type": "transcription",  ← Key field
       "model_id": "openai/whisper-large",
       "source_language": "en",
       "input_file_id": "file456"
   }

2. process_proxy_task() extracts task_type = "transcription"

3. Routes to: process_transcription_task(input_data, model_id="openai/whisper-large", language="en")

4. Inside process_transcription_task():
   - Calls: pipeline = self.pipeline_manager.get_transcription_pipeline("openai/whisper-large")
   - Pipeline Manager loads/caches the model
   - Calls: pipeline.transcribe(audio_data, language="en")
   - Returns: {"transcript": "...", "confidence": 0.95, ...}
```

### Validator Side:

```
1. Task evaluation starts with task_type = "transcription"

2. Calls: _execute_pipeline_robust("transcription", input_data, task_id, model_id)

3. Routes to: execute_transcription_task({'input_data': ..., 'model_id': ...})

4. Inside execute_transcription_task():
   - Calls: pipeline = self.pipeline_manager.get_transcription_pipeline(model_id)
   - Pipeline Manager loads/caches the model (same as miner)
   - Calls: pipeline.transcribe(audio_data, language="en")
   - Returns: Result for comparison with miner output
```

## 7. Key Points

1. **task_type is the primary routing key**: It determines which `process_*_task` or `execute_*_task` method is called.

2. **model_id is optional**: If not specified, the Pipeline Manager uses default models:
   - Transcription: `openai/whisper-tiny`
   - TTS: `tts_models/multilingual/multi-dataset/your_tts`
   - Summarization: `facebook/bart-large-cnn`
   - Translation: `t5-small`

3. **Models load on-demand**: No models are loaded at startup. They're loaded only when:
   - A task is assigned
   - The specific pipeline is requested
   - The model_id is known

4. **Pipeline Manager handles caching**: If the same model is requested again, it returns the cached instance instead of reloading.

5. **Same pipeline, same inference**: Both miner and validator use the exact same pipeline instances and inference methods, ensuring fair comparison.

## 8. Task Type to Pipeline Mapping

| Task Type | Pipeline Class | Inference Method | Input Format | Output Format |
|-----------|---------------|------------------|--------------|---------------|
| `transcription` | `TranscriptionPipeline` | `transcribe(audio, language)` | bytes (audio) | `{"transcript": str, "confidence": float}` |
| `video_transcription` | `TranscriptionPipeline` | `transcribe(audio, language)` | bytes (video) | `{"transcript": str, "video_info": dict}` |
| `tts` | `TTSPipeline` | `synthesize(text, language)` | str (text) | `{"audio_file": dict, "processing_time": float}` |
| `summarization` | `SummarizationPipeline` | `summarize(text, language)` | str (text) | `{"summary": str, "processing_time": float}` |
| `text_translation` | `TranslationPipeline` | `translate_text(text, source_lang, target_lang)` | str (text) | `{"translated_text": str, "processing_time": float}` |
| `document_translation` | `TranslationPipeline` | `translate_document(file_data, filename, source_lang, target_lang)` | bytes (document) | `{"translated_text": str, "metadata": dict}` |

## Summary

The routing mechanism is straightforward:
1. **Task arrives** with `task_type` field
2. **If/elif chain** routes to appropriate `process_*_task` or `execute_*_task` method
3. **Method extracts** `model_id` from task
4. **Pipeline Manager** loads the model on-demand
5. **Inference method** is called on the pipeline instance
6. **Result** is returned and submitted

This design ensures:
- ✅ Clear separation of concerns
- ✅ Easy to add new task types
- ✅ Dynamic model selection
- ✅ Efficient resource usage (on-demand loading)
- ✅ Fair comparison (miner and validator use same pipelines)

