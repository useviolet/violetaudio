# Violet Proxy Server

A distributed task processing proxy server that coordinates between miners and validators for AI-powered transcription, text-to-speech, summarization, and translation tasks.

## Features

- **Multi-Task Support**: Transcription, TTS, Summarization, Text Translation, Document Translation, Video Transcription
- **PostgreSQL Database**: Full PostgreSQL integration for task management, user authentication, and file metadata
- **R2 Storage**: Cloudflare R2 integration for file storage with public URL fallback
- **Load Balancing**: Intelligent task distribution with miner load tracking
- **Multi-Validator Consensus**: Consensus-based validation for miner responses
- **RESTful API**: Comprehensive REST API with FastAPI and automatic OpenAPI documentation

## Quick Start

### Prerequisites

- Python 3.10+ (Python 3.12+ recommended)
- PostgreSQL database
- Cloudflare R2 credentials (optional, for file storage)
- Bittensor network access (for miner/validator authentication)

### Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Configure environment variables in `.env`:
```env
DATABASE_URL=postgresql://user:password@host:port/database
R2_ACCESS_KEY_ID=your_r2_access_key
R2_SECRET_ACCESS_KEY=your_r2_secret_key
R2_BUCKET_NAME=your_bucket_name
R2_ENDPOINT_URL=your_r2_endpoint_url
R2_PUBLIC_URL=your_r2_public_url
```

3. Start the server:
```bash
python main.py
```

The server will start on `http://localhost:8000` by default.

## API Documentation

Once the server is running, visit:
- **Swagger UI**: `http://localhost:8000/docs`
- **ReDoc**: `http://localhost:8000/redoc`
- **OpenAPI JSON**: `http://localhost:8000/openapi.json`

## Working Model IDs

The proxy server supports various model IDs for different task types. Here are the currently supported models:

### Transcription Models

| Model ID | Description | Status |
|----------|-------------|--------|
| `openai/whisper-tiny` | Fast, lightweight Whisper model (default) | ✅ Recommended |
| `openai/whisper-base` | Base Whisper model | ✅ Supported |
| `openai/whisper-small` | Small Whisper model | ✅ Supported |
| `openai/whisper-medium` | Medium Whisper model | ✅ Supported |
| `openai/whisper-large` | Large Whisper model (best quality) | ✅ Supported |
| `openai/whisper-large-v2` | Large Whisper v2 model | ✅ Supported |

**Note**: All Whisper models support multiple languages (en, es, fr, de, it, pt, ru, ja, ko, zh, ar, hi).

### Text-to-Speech (TTS) Models

| Model ID | Description | Status |
|----------|-------------|--------|
| `tts_models/multilingual/multi-dataset/xtts_v2` | Coqui XTTS v2 (multilingual, voice cloning) | ✅ Recommended |
| `tts_models/multilingual/multi-dataset/your_tts` | Coqui YourTTS (multilingual) | ✅ Supported |
| `tts_models/en/ljspeech/tacotron2-DDC` | English TTS (Tacotron2) | ✅ Supported |
| `tts_models/en/vctk/vits` | English multi-speaker TTS | ✅ Supported |

**Note**: TTS models require Coqui TTS library. Voice cloning requires a speaker WAV file.

### Summarization Models

| Model ID | Description | Status |
|----------|-------------|--------|
| `facebook/bart-large-cnn` | BART large model for summarization (default) | ✅ Recommended |
| `facebook/bart-base` | BART base model | ✅ Supported |
| `google/pegasus-xsum` | Google Pegasus for abstractive summarization | ✅ Supported |
| `t5-small` | T5 small model (can be used for summarization) | ✅ Supported |

**Note**: Summarization models work best with English text but support multiple languages.

### Translation Models

| Model ID | Description | Status |
|----------|-------------|--------|
| `facebook/mbart-large-50-many-to-many-mmt` | Multilingual many-to-many translation (default) | ✅ Recommended |
| `t5-small` | T5 small model for translation | ✅ Supported |
| `Helsinki-NLP/opus-mt-en-es` | English to Spanish (Marian model) | ✅ Supported |
| `Helsinki-NLP/opus-mt-en-fr` | English to French | ✅ Supported |
| `Helsinki-NLP/opus-mt-en-de` | English to German | ✅ Supported |
| `Helsinki-NLP/opus-mt-en-zh` | English to Chinese | ✅ Supported |

**Important**: Translation tasks **require both** `source_language` and `target_language` parameters. These are stored in the database `tasks` table (`source_language` and `target_language` columns) and are mandatory for all translation endpoints.

**Note**: 
- `facebook/mbart-large-50-many-to-many-mmt` supports 50+ languages and is recommended for multilingual translation tasks.
- Both `source_language` and `target_language` are required parameters and are stored in the database.
- The system validates that source and target languages are different.

### Video Transcription Models

Video transcription uses the same models as audio transcription (Whisper models). The system automatically extracts audio from video files before transcription.

| Model ID | Description | Status |
|----------|-------------|--------|
| `openai/whisper-tiny` | Fast video transcription (default) | ✅ Recommended |
| `openai/whisper-large` | High-quality video transcription | ✅ Supported |

## API Endpoints

### Task Submission

- `POST /api/v1/transcription` - Submit audio transcription task
- `POST /api/v1/tts` - Submit text-to-speech task
- `POST /api/v1/summarization` - Submit text summarization task
- `POST /api/v1/text-translation` - Submit text translation task (requires `source_language` and `target_language`)
- `POST /api/v1/document-translation` - Submit document translation task (requires `source_language` and `target_language`)
- `POST /api/v1/video-transcription` - Submit video transcription task

### Task Status & Results

- `GET /api/v1/task/{task_id}/status` - Get task status
- `GET /api/v1/task/{task_id}/responses` - Get task responses
- `GET /api/v1/transcription/{task_id}/result` - Get transcription result
- `GET /api/v1/tts/{task_id}/result` - Get TTS result
- `GET /api/v1/summarization/{task_id}/result` - Get summarization result

### Miner Endpoints

- `GET /api/v1/miner/transcription/{task_id}` - Get transcription task for miner
- `GET /api/v1/miner/tts/{task_id}` - Get TTS task for miner
- `GET /api/v1/miner/summarization/{task_id}` - Get summarization task for miner
- `GET /api/v1/miner/text-translation/{task_id}` - Get text translation task for miner
- `GET /api/v1/miner/video-transcription/{task_id}` - Get video transcription task for miner
- `GET /api/v1/miner/document-translation/{task_id}` - Get document translation task for miner
- `POST /api/v1/miner/response` - Submit miner response (requires miner API key)
- `POST /api/v1/miner/video-transcription/upload-result` - Upload video transcription result
- `POST /api/v1/miner/text-translation/upload-result` - Upload text translation result
- `POST /api/v1/miner/document-translation/upload-result` - Upload document translation result
- `POST /api/v1/miner/tts/upload` - Upload TTS audio (requires miner API key)
- `POST /api/v1/miner/tts/upload-audio` - Upload TTS audio file

### Validator Endpoints

- `GET /api/v1/validator/tasks` - Get tasks for validation (requires validator API key)
- `POST /api/v1/validator/evaluation` - Submit validator evaluation (requires validator API key)
- `POST /api/v1/validators/miner-status` - Submit miner status report

### File Management

- `GET /api/v1/files/{file_id}` - Get file metadata or download file
- `GET /api/v1/files/{file_id}/download` - Download file
- `GET /api/v1/files/stats` - Get file storage statistics
- `GET /api/v1/files/list/{file_type}` - List files by type
- `GET /api/v1/tts/audio/{file_id}` - Get TTS audio file

### Authentication

- `POST /api/v1/auth/register` - Register new user
- `POST /api/v1/auth/login` - Login user
- `POST /api/v1/auth/generate-api-key` - Generate API key (for role upgrade)
- `GET /api/v1/auth/verify-api-key` - Verify API key
- `POST /api/v1/miner/authenticate` - Authenticate miner
- `POST /api/v1/validator/authenticate` - Authenticate validator

### System & Monitoring

- `GET /health` - Health check
- `GET /api/v1/health` - API health check
- `GET /api/v1/metrics` - System metrics
- `GET /api/v1/metrics/json` - System metrics (JSON)
- `GET /api/v1/miners` - List all miners
- `GET /api/v1/miners/performance` - Get miner performance stats
- `GET /api/v1/miners/network-status` - Get network status
- `GET /api/v1/tasks` - List all tasks
- `GET /api/v1/tasks/completed` - Get completed tasks

## Usage Examples

### Submit Transcription Task

```bash
curl -X POST "http://localhost:8000/api/v1/transcription" \
  -H "X-API-Key: your_api_key" \
  -F "audio_file=@audio.wav" \
  -F "source_language=en" \
  -F "model_id=openai/whisper-tiny" \
  -F "priority=normal"
```

### Submit TTS Task

```bash
curl -X POST "http://localhost:8000/api/v1/tts" \
  -H "X-API-Key: your_api_key" \
  -F "text=Hello, this is a test" \
  -F "source_language=en" \
  -F "voice_name=english_alice" \
  -F "model_id=tts_models/multilingual/multi-dataset/xtts_v2" \
  -F "priority=normal"
```

### Submit Summarization Task

```bash
curl -X POST "http://localhost:8000/api/v1/summarization" \
  -H "X-API-Key: your_api_key" \
  -F "text=Your long text here..." \
  -F "source_language=en" \
  -F "model_id=facebook/bart-large-cnn" \
  -F "priority=normal"
```

### Submit Translation Task

**Note**: Translation tasks **require both** `source_language` and `target_language` parameters. These are stored in the database and are mandatory.

```bash
curl -X POST "http://localhost:8000/api/v1/text-translation" \
  -H "X-API-Key: your_api_key" \
  -F "text=Hello, world" \
  -F "source_language=en" \
  -F "target_language=es" \
  -F "model_id=facebook/mbart-large-50-many-to-many-mmt" \
  -F "priority=normal"
```

**Document Translation** (also requires both languages):
```bash
curl -X POST "http://localhost:8000/api/v1/document-translation" \
  -H "X-API-Key: your_api_key" \
  -F "document_file=@document.pdf" \
  -F "source_language=en" \
  -F "target_language=es" \
  -F "model_id=facebook/mbart-large-50-many-to-many-mmt" \
  -F "priority=normal"
```

### Get Task Result

```bash
curl -X GET "http://localhost:8000/api/v1/transcription/{task_id}/result" \
  -H "X-API-Key: your_api_key"
```

## Architecture

### Components

- **Main Server** (`main.py`): FastAPI application with all endpoints
- **Database Layer**: PostgreSQL adapter for data persistence
- **File Manager**: R2 storage integration with public URL fallback
- **Task Distributor**: Intelligent task assignment to miners
- **Workflow Orchestrator**: Task lifecycle management
- **Miner Response Handler**: Processes and validates miner responses
- **Multi-Validator Manager**: Consensus-based validation
- **Auth Middleware**: API key and Bittensor credential verification

### Database Schema

The system uses PostgreSQL with the following main tables:
- `users` - User accounts and API keys
- `tasks` - Task definitions and status (includes `source_language` and `target_language` columns - both are stored for translation tasks)
- `files` - File metadata and storage information
- `text_content` - Text content for text-based tasks
- `miner_status` - Miner availability and capabilities
- `task_assignments` - Task-to-miner assignments
- `miner_responses` - Miner task responses
- `validator_reports` - Validator evaluations
- `miner_consensus` - Consensus results

**Note**: For translation tasks, both `source_language` and `target_language` are stored in the `tasks` table. The `target_language` column is nullable for non-translation tasks but is required for translation task types.

## Configuration

### Environment Variables

- `DATABASE_URL`: PostgreSQL connection string
- `R2_ACCESS_KEY_ID`: Cloudflare R2 access key
- `R2_SECRET_ACCESS_KEY`: Cloudflare R2 secret key
- `R2_BUCKET_NAME`: R2 bucket name
- `R2_ENDPOINT_URL`: R2 S3 endpoint URL
- `R2_PUBLIC_URL`: R2 public URL for file access
- `WANDB_API_KEY`: Weights & Biases API key (optional, for monitoring)

### Task Distribution

- Tasks are automatically assigned to available miners based on:
  - Miner availability and load
  - Task type specialization
  - Miner performance history
- Default: 3 miners per task (configurable per task)
- Polling interval: 3 minutes

## Development

### Project Structure

```
proxy_server/
├── main.py                 # FastAPI application
├── database/              # Database adapters and schemas
├── managers/              # Business logic managers
├── orchestrators/         # Task orchestration
├── middleware/            # Authentication middleware
└── utils/                 # Utility functions
```

### Running Tests

The server includes comprehensive endpoint testing. Use the `/docs` interface to test endpoints interactively.

## License

See LICENSE file in the project root.

## Support

For issues and questions, please refer to the main project documentation.
