# HuggingFace Token Configuration

## Overview

The miner now supports HuggingFace tokens for accessing private or gated models. All pipelines automatically check for and use the HF token if available.

## Setup

1. **Create a `.env` file** in the project root (copy from `.env.example`):
   ```bash
   cp .env.example .env
   ```

2. **Add your HuggingFace token** to the `.env` file:
   ```env
   HF_TOKEN=your_huggingface_token_here
   ```

3. **Get your token** from: https://huggingface.co/settings/tokens

## How It Works

- The `.env` file is automatically loaded when the miner starts
- All pipelines (transcription, summarization, translation) check for the token
- If a token is found, it's used for all `from_pretrained()` calls
- If no token is found, the system works normally with public models

## Environment Variable Name

The system uses **only** the `HF_TOKEN` environment variable for consistency across all pipelines.

## Security

- The `.env` file is already in `.gitignore` - it won't be committed to git
- Never share your HF token publicly
- Use read-only tokens when possible

## Testing

To verify the token is loaded:
```python
from template.utils.hf_token import get_hf_token, get_hf_token_dict

token = get_hf_token()
if token:
    print(f"✅ Token loaded: {len(token)} chars")
else:
    print("ℹ️ No token found")
```

## Notes

- **Optional**: The token is only needed for private/gated models
- **Public models**: Work fine without a token
- **All current models**: Are public and don't require tokens
- **Future-proof**: Ready for private models when needed
