# TTS Task Creation Summary

## Available Voice Found

✅ **Voice Name**: `english_alice`
- Display Name: English Alice
- Language: en
- Created: 2025-12-17

## Task Parameters Ready

- **Text**: "I am Tobius the great man from Iganga and Tanzania Bukoba , kammpala , masaka . We sign great work and make it work all over the world"
- **Model ID**: `tts_models/multilingual/multi-dataset/xtts_v2`
- **Source Language**: `en`
- **Priority**: `normal`
- **Voice Name**: `english_alice`

## API Endpoint Details

**Endpoint**: `POST /api/v1/tts`

**URL**: `https://violet-proxy-bl4w.onrender.com/api/v1/tts`

**Headers**:
```
X-API-Key: <your_api_key_with_client_or_admin_role>
```

**Form Data** (NOT JSON):
```
text: I am Tobius the great man from Iganga and Tanzania Bukoba , kammpala , masaka . We sign great work and make it work all over the world
voice_name: english_alice
model_id: tts_models/multilingual/multi-dataset/xtts_v2
source_language: en
priority: normal
```

## Current Issue

❌ **API Key Permissions**: The current API key doesn't have 'client' or 'admin' role required to create TTS tasks.

**Solution**: 
1. Get an API key with 'client' or 'admin' role from the proxy server admin
2. Update your `.env` file with the new API key
3. Run the script again

## Script Ready to Use

The script `create_tts_task_with_voice.py` is ready and will:
1. ✅ Check database for available voices (found: `english_alice`)
2. ✅ Use the found voice automatically
3. ✅ Create the TTS task with all specified parameters

**To run once you have a valid API key**:
```bash
python3 create_tts_task_with_voice.py
```

**Or specify a different voice**:
```bash
python3 create_tts_task_with_voice.py <voice_name>
```

## Manual Creation via curl

Once you have a valid API key, you can also create the task manually:

```bash
curl -X POST "https://violet-proxy-bl4w.onrender.com/api/v1/tts" \
  -H "X-API-Key: YOUR_API_KEY_HERE" \
  -F "text=I am Tobius the great man from Iganga and Tanzania Bukoba , kammpala , masaka . We sign great work and make it work all over the world" \
  -F "voice_name=english_alice" \
  -F "model_id=tts_models/multilingual/multi-dataset/xtts_v2" \
  -F "source_language=en" \
  -F "priority=normal"
```

## Response Format

On success, you'll receive:
```json
{
  "success": true,
  "task_id": "uuid-here",
  "status": "pending",
  "message": "TTS task submitted successfully"
}
```

## Check Task Result

After creation, check the result at:
```
GET https://violet-proxy-bl4w.onrender.com/api/v1/tts/{task_id}/result
```

