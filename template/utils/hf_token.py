"""
HuggingFace Token Helper
Loads HF token from environment variables (.env file or system environment)
"""

import os
from typing import Optional
from dotenv import load_dotenv
from pathlib import Path

# Load .env file from project root
_project_root = Path(__file__).parent.parent.parent
_env_file = _project_root / ".env"

# Load environment variables from .env file if it exists
if _env_file.exists():
    load_dotenv(_env_file)
    print(f"✅ Loaded .env file from: {_env_file}")
else:
    # Try to load from current directory as fallback
    load_dotenv()
    print(f"⚠️ No .env file found at {_env_file}, using system environment variables")

def get_hf_token() -> Optional[str]:
    """
    Get HuggingFace token from environment variables.
    Uses only HF_TOKEN variable name for consistency.
    
    Returns:
        HF token string if found, None otherwise
    """
    # Use only HF_TOKEN variable name
    token = os.getenv("HF_TOKEN")
    
    # Return None if token is empty string or not set
    if token and token.strip():
        return token.strip()
    
    return None

def get_hf_token_dict() -> dict:
    """
    Get HuggingFace token as a dictionary for use in from_pretrained() calls.
    
    Returns:
        Dictionary with 'token' key if token exists, empty dict otherwise
    """
    token = get_hf_token()
    if token:
        return {"token": token}
    return {}

# Pre-load token at module import time
_hf_token = get_hf_token()
if _hf_token:
    print(f"✅ HuggingFace token loaded (length: {len(_hf_token)} chars)")
else:
    print("ℹ️ No HuggingFace token found - using public models only")

