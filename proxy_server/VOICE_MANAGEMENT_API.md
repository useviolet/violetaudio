# Voice Management API

## Overview
Voice management endpoints have been added to the proxy server to manage TTS voices. These endpoints allow you to add, update, delete, and list voices that can be used for text-to-speech tasks.

## Endpoints

### 1. List All Voices
**GET** `/api/v1/voices`

List all available voices in the system.

**Headers:**
- `X-API-Key: your_api_key`

**Response:**
```json
{
  "success": true,
  "count": 2,
  "voices": [
    {
      "voice_name": "english_alice",
      "display_name": "Alice (English)",
      "language": "en",
      "public_url": "https://...",
      "file_name": "alice.wav",
      "file_size": 123456,
      "file_type": "audio/wav",
      "created_at": "2025-12-18T22:00:00",
      "updated_at": "2025-12-18T22:00:00"
    }
  ]
}
```

**Example:**
```bash
curl -X GET "http://localhost:8000/api/v1/voices" \
  -H "X-API-Key: your_api_key"
```

---

### 2. Add a Voice
**POST** `/api/v1/voices`

Add a new voice for TTS voice cloning.

**Headers:**
- `X-API-Key: your_api_key`

**Form Data:**
- `voice_name` (required): Unique identifier for the voice (e.g., "english_alice")
- `display_name` (required): Human-readable name (e.g., "Alice (English)")
- `language` (optional, default: "en"): Language code (e.g., "en", "es", "fr")
- `audio_file` (required): Audio file (.wav, .mp3, .flac, or .ogg)

**Response:**
```json
{
  "success": true,
  "message": "Voice 'english_alice' added successfully",
  "voice": {
    "voice_name": "english_alice",
    "display_name": "Alice (English)",
    "language": "en",
    "public_url": "https://...",
    "file_id": "uuid-here",
    "file_size": 123456
  }
}
```

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/voices" \
  -H "X-API-Key: your_api_key" \
  -F "voice_name=english_alice" \
  -F "display_name=Alice (English)" \
  -F "language=en" \
  -F "audio_file=@alice.wav"
```

---

### 3. Update a Voice
**PUT** `/api/v1/voices/{voice_name}`

Update an existing voice. You can update the display name, language, and/or audio file.

**Headers:**
- `X-API-Key: your_api_key`

**Path Parameters:**
- `voice_name` (required): The voice name to update

**Form Data (all optional):**
- `display_name`: New display name
- `language`: New language code
- `audio_file`: New audio file

**Response:**
```json
{
  "success": true,
  "message": "Voice 'english_alice' updated successfully",
  "voice": {
    "voice_name": "english_alice",
    "display_name": "Updated Alice (English)",
    "language": "en",
    "public_url": "https://...",
    "file_id": "uuid-here",
    "file_size": 123456
  }
}
```

**Example:**
```bash
# Update display name only
curl -X PUT "http://localhost:8000/api/v1/voices/english_alice" \
  -H "X-API-Key: your_api_key" \
  -F "display_name=Updated Alice (English)"

# Update audio file
curl -X PUT "http://localhost:8000/api/v1/voices/english_alice" \
  -H "X-API-Key: your_api_key" \
  -F "audio_file=@new_alice.wav"
```

---

### 4. Delete a Voice
**DELETE** `/api/v1/voices/{voice_name}`

Delete a voice and its associated audio file.

**Headers:**
- `X-API-Key: your_api_key`

**Path Parameters:**
- `voice_name` (required): The voice name to delete

**Response:**
```json
{
  "success": true,
  "message": "Voice 'english_alice' deleted successfully"
}
```

**Example:**
```bash
curl -X DELETE "http://localhost:8000/api/v1/voices/english_alice" \
  -H "X-API-Key: your_api_key"
```

---

## Creating a TTS Task with a Voice

After adding a voice, you can use it in TTS tasks:

**POST** `/api/v1/tts`

**Form Data:**
- `text` (required): Text to convert to speech
- `voice_name` (required): The voice name to use
- `source_language` (optional, default: "en"): Language code
- `model_id` (optional): TTS model ID
- `priority` (optional, default: "normal"): Task priority

**Example:**
```bash
curl -X POST "http://localhost:8000/api/v1/tts" \
  -H "X-API-Key: your_api_key" \
  -F "text=Hello, this is a test of the text-to-speech system." \
  -F "voice_name=english_alice" \
  -F "source_language=en" \
  -F "model_id=tts_models/multilingual/multi-dataset/xtts_v2" \
  -F "priority=normal"
```

**Response:**
```json
{
  "success": true,
  "task_id": "uuid-here",
  "status": "pending",
  "message": "TTS task submitted successfully"
}
```

---

## Testing

A test script is available at `proxy_server/test_voice_management.py`. To use it:

1. **Start the proxy server** (if testing locally):
   ```bash
   cd proxy_server
   python3 main.py
   ```

2. **Run the test script**:
   ```bash
   cd proxy_server
   python3 test_voice_management.py
   ```

   Or set environment variables:
   ```bash
   export PROXY_URL="http://localhost:8000"  # or your Render URL
   export API_KEY="your_api_key"
   export AUDIO_FILE="/path/to/audio.wav"  # optional
   python3 test_voice_management.py
   ```

The test script will:
1. List existing voices
2. Add a new voice
3. Update the voice
4. Create a TTS task using the voice
5. (Optionally) Delete the voice

---

## Notes

- **Audio File Requirements**: Supported formats are `.wav`, `.mp3`, `.flac`, and `.ogg`
- **Voice Name Uniqueness**: Voice names must be unique. If you try to add a voice with an existing name, you'll get a 400 error.
- **File Storage**: Audio files are stored in R2 storage and associated with the voice record in the database.
- **Authentication**: All endpoints require authentication via `X-API-Key` header.

