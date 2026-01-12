# Postman API Guide for Violet Proxy Server

## Quick Reference

### Base URL
```
https://violet-proxy-bl4w.onrender.com
```

### Authentication Header
```
X-API-Key: <your_api_key>
```

### Common Endpoints

| Operation | Method | Endpoint | Body Type |
|-----------|--------|----------|-----------|
| Query Miner Tasks | GET | `/api/v1/miners/{uid}/tasks?status=assigned` | - |
| Query Validator Tasks | GET | `/api/v1/validators/tasks` | - |
| Submit Task Result | POST | `/api/v1/miner/response` | **form-data** |
| Get File Info | GET | `/api/v1/files/{file_id}` | - |

---

## Authentication

All requests require an API key in the header with proper role permissions:

**Header Name:** `X-API-Key`  
**Header Value:** Your API key (from `MINER_API_KEY` or `VALIDATOR_API_KEY` in `.env` file)

**⚠️ IMPORTANT:** The API key must have **"client"** or **"admin"** role assigned in the proxy server database.

**Where to find your API key:**
- Check your `.env` file in the project root
- Look for `MINER_API_KEY` or `VALIDATOR_API_KEY`
- If not set, add it to `.env` file

**If you get "Client or admin role required" error:**
1. **Verify API key is correct** - Check that the key in `.env` matches what's in the database
2. **Check API key role** - The key must have `role = 'client'` or `role = 'admin'` in the proxy server
3. **Contact admin** - You may need to request a new API key with proper role permissions
4. **Verify header format** - Make sure header name is exactly `X-API-Key` (case-sensitive)
5. **Check for extra spaces** - Ensure no leading/trailing spaces in the API key value

---

## 1. Query Tasks (GET)

### For Miners: Get Assigned Tasks
**Endpoint:** `GET /api/v1/miners/{miner_uid}/tasks`

**URL Example:**
```
https://violet-proxy-bl4w.onrender.com/api/v1/miners/6/tasks?status=assigned
```

**Headers:**
```
X-API-Key: <your_miner_api_key>
Content-Type: application/json
```

**Query Parameters:**
- `status` (optional): `"assigned"` or `"pending"` (default: `"assigned"`)

**Response Example:**
```json
[
  {
    "task_id": "d550c420-e1b0-41cd-a8ba-60222e86622c",
    "task_type": "transcription",
    "status": "assigned",
    "priority": "normal",
    "input_file_id": "abc123-def456-...",
    "input_file": {
      "file_id": "abc123-def456-...",
      "public_url": "https://...",
      "file_size": 86216,
      "content_type": "audio/wav"
    },
    "source_language": "en",
    "model_id": null,
    "created_at": "2026-01-12T15:20:00Z",
    "distributed_at": "2026-01-12T15:21:00Z"
  }
]
```

### For Validators: Get Tasks for Evaluation
**Endpoint:** `GET /api/v1/validators/tasks`

**URL Example:**
```
https://violet-proxy-bl4w.onrender.com/api/v1/validators/tasks
```

**Headers:**
```
X-API-Key: <your_validator_api_key>
Content-Type: application/json
```

**Response Example:**
```json
{
  "tasks": [
    {
      "task_id": "d550c420-e1b0-41cd-a8ba-60222e86622c",
      "task_type": "transcription",
      "status": "completed",
      "miner_responses": [...],
      ...
    }
  ]
}
```

---

## 2. Submit Task Results (POST)

### Submit Miner Response
**Endpoint:** `POST /api/v1/miner/response`

**URL:**
```
https://violet-proxy-bl4w.onrender.com/api/v1/miner/response
```

**Headers:**
```
X-API-Key: <your_miner_api_key>
Content-Type: application/x-www-form-urlencoded
```

**⚠️ IMPORTANT:** This endpoint uses **Form Data**, not JSON!

**Request Body (Form Data):**

#### Transcription Task Response:
```
task_id: d550c420-e1b0-41cd-a8ba-60222e86622c
miner_uid: 6
response_data: {"transcript": "This is the transcribed text from the audio file.", "confidence": 0.95, "processing_time": 5.23, "model_id": "whisper-large-v3", "language": "en"}
processing_time: 5.23
accuracy_score: 0.95
speed_score: 0.85
```

**Note:** `response_data` should be a JSON string (not a JSON object).

#### Summarization Task Response:
```
task_id: c9f57380-e6a5-4990-9053-6be9e1e2eb34
miner_uid: 6
response_data: {"summary": "This is a summary of the input text.", "processing_time": 12.45, "model_id": "bart-large-cnn", "text_length": 5000, "summary_length": 250}
processing_time: 12.45
accuracy_score: 0.95
speed_score: 0.60
```

#### TTS Task Response:
```
task_id: abc123-...
miner_uid: 6
response_data: {"output_data": {"audio_file": {"file_id": "xyz789-...", "file_name": "output.wav", "file_size": 123456, "storage_location": "r2", "r2_bucket": "violet-audio", "r2_key": "outputs/xyz789.wav", "public_url": "https://..."}}, "processing_time": 8.90, "model_id": "tts-model", "text_length": 100}
processing_time: 8.90
accuracy_score: 0.90
speed_score: 0.75
```

**In Postman:**
1. Select **Body** tab
2. Select **form-data** (NOT raw JSON)
3. Add each field as a key-value pair:
   - `task_id`: `d550c420-e1b0-41cd-a8ba-60222e86622c`
   - `miner_uid`: `6`
   - `response_data`: `{"transcript": "...", "confidence": 0.95, ...}` (as a string)
   - `processing_time`: `5.23`
   - `accuracy_score`: `0.95`
   - `speed_score`: `0.85`

---

## 3. Create New Tasks (POST)

### Create Transcription Task
**Endpoint:** `POST /api/v1/tasks` (or check backend API documentation)

**URL:**
```
https://violet-proxy-bl4w.onrender.com/api/v1/tasks
```

**Headers:**
```
X-API-Key: <your_api_key>
Content-Type: application/json
```

**Request Body for Transcription:**
```json
{
  "task_type": "transcription",
  "input_file_id": "abc123-def456-ghi789",
  "source_language": "en",
  "model_id": null,
  "priority": "normal",
  "required_miner_count": 3,
  "min_miner_count": 1,
  "max_miner_count": 5
}
```

**Request Body for Summarization:**
```json
{
  "task_type": "summarization",
  "input_text_id": "text123-...",
  "input_text": {
    "text": "This is a long text that needs to be summarized. It contains multiple paragraphs and sentences that should be condensed into a shorter summary.",
    "text_id": "text123-..."
  },
  "language": "en",
  "model_id": null,
  "priority": "normal",
  "required_miner_count": 1,
  "min_miner_count": 1,
  "max_miner_count": 3
}
```

**Request Body for TTS:**
```json
{
  "task_type": "tts",
  "input_text": "Hello, this is a text to speech task.",
  "source_language": "en",
  "voice_name": "default",
  "model_id": null,
  "priority": "normal",
  "required_miner_count": 1
}
```

---

## 4. Get File Information (GET)

**Endpoint:** `GET /api/v1/files/{file_id}`

**URL Example:**
```
https://violet-proxy-bl4w.onrender.com/api/v1/files/abc123-def456-ghi789
```

**Headers:**
```
X-API-Key: <your_api_key>
Content-Type: application/json
```

**Response:**
```json
{
  "success": true,
  "file": {
    "file_id": "abc123-def456-ghi789",
    "original_filename": "audio.wav",
    "safe_filename": "audio.wav",
    "file_type": "audio",
    "content_type": "audio/wav",
    "file_size": 86216,
    "storage_location": "r2",
    "r2_bucket": "violet-audio",
    "r2_key": "uploads/abc123.wav",
    "public_url": "https://pub-xxx.r2.dev/uploads/abc123.wav",
    "created_at": "2026-01-12T15:20:00Z"
  }
}
```

---

## Postman Setup Instructions

### Step 1: Create a New Request
1. Open Postman
2. Click "New" → "HTTP Request"

### Step 2: Set Headers (CRITICAL)
1. Go to "Headers" tab
2. **Add header:**
   - **Key:** `X-API-Key` (exactly as shown, case-sensitive)
   - **Value:** Your API key (from `.env` file: `MINER_API_KEY` or `VALIDATOR_API_KEY`)
   - **⚠️ Make sure:**
     - No spaces before/after the key value
     - Header name is exactly `X-API-Key` (not `x-api-key` or `X-Api-Key`)
     - The API key has "client" or "admin" role in the database

3. **For GET requests:** Optional but recommended
   - **Key:** `Content-Type`
   - **Value:** `application/json`

4. **For POST requests:** 
   - **Key:** `Content-Type`
   - **Value:** `application/x-www-form-urlencoded` (for form-data) OR `application/json` (for JSON)

### Step 3: Query Tasks Example
**Method:** `GET`  
**URL:** `https://violet-proxy-bl4w.onrender.com/api/v1/miners/6/tasks?status=assigned`

**Headers:**
```
X-API-Key: your_api_key_here
Content-Type: application/json
```

### Step 4: Submit Task Result Example
**Method:** `POST`  
**URL:** `https://violet-proxy-bl4w.onrender.com/api/v1/miner/response`

**Headers:**
```
X-API-Key: your_api_key_here
```

**Body (form-data, NOT JSON):**
1. Go to **Body** tab
2. Select **form-data** (NOT raw)
3. Add these fields:

| Key | Value | Type |
|-----|-------|------|
| `task_id` | `d550c420-e1b0-41cd-a8ba-60222e86622c` | Text |
| `miner_uid` | `6` | Text |
| `response_data` | `{"transcript": "This is the transcribed text.", "confidence": 0.95, "processing_time": 5.23, "model_id": "whisper-large-v3", "language": "en"}` | Text (JSON string) |
| `processing_time` | `5.23` | Text |
| `accuracy_score` | `0.95` | Text |
| `speed_score` | `0.85` | Text |

**Important:** `response_data` must be a JSON string, not a JSON object!

---

## Common Task Types

| Task Type | Input Field | Output Field |
|-----------|-------------|--------------|
| **transcription** | `input_file_id` | `transcript` |
| **summarization** | `input_text` or `input_text_id` | `summary` |
| **tts** | `input_text` | `output_data.audio_file` |
| **video_transcription** | `input_file_id` | `transcript` |
| **text_translation** | `input_text` | `translated_text` |
| **document_translation** | `input_file_id` | `translated_text` |

---

## Response Status Codes

- **200** - Success
- **400** - Bad Request (invalid data)
- **401** - Unauthorized (missing/invalid API key)
- **404** - Not Found
- **500** - Server Error

---

## Troubleshooting

### Error: "Client or admin role required"

**Problem:** Your API key doesn't have the required role permissions.

**Solutions:**
1. **Verify API key role in database:**
   - The API key must have `role = 'client'` or `role = 'admin'`
   - Contact the proxy server admin to check/update the role

2. **Check API key format:**
   - Make sure you're using the exact key from `.env` file
   - No extra spaces or newlines
   - Copy the entire key value

3. **Verify header in Postman:**
   - Header name must be exactly: `X-API-Key` (case-sensitive)
   - Value must be your complete API key
   - Check "Headers" tab (not "Params" or "Body")

4. **Test with curl to verify:**
   ```bash
   curl -X GET "https://violet-proxy-bl4w.onrender.com/api/v1/miners/6/tasks?status=assigned" \
     -H "X-API-Key: YOUR_API_KEY_HERE"
   ```

### Error: 401 Unauthorized

- API key is missing or incorrect
- Check that `X-API-Key` header is set correctly
- Verify the API key value matches what's in `.env` file

### Error: 404 Not Found

- Check the URL is correct
- Verify the endpoint path is correct
- Make sure you're using the right miner_uid in the URL

---

## Notes

1. **API Key:** Get your API key from the `.env` file:
   - `MINER_API_KEY` for miner operations
   - `VALIDATOR_API_KEY` for validator operations
   - **⚠️ The API key must have "client" or "admin" role in the proxy server database**

2. **File Upload:** For transcription tasks, you typically need to:
   - First upload the file to get `input_file_id`
   - Then create a task with that `input_file_id`

3. **Task Status:** Tasks can have status:
   - `pending` - Not yet assigned
   - `assigned` - Assigned to miners
   - `completed` - Completed by miners
   - `failed` - Failed processing

4. **Language Codes:** Use ISO 639-1 codes (e.g., `en`, `es`, `fr`, `de`)

5. **Header Format:** 
   - Must be exactly `X-API-Key` (case-sensitive)
   - Value must be the complete API key with no spaces
   - Set in "Headers" tab, not "Params" or "Body"

