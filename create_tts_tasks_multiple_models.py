#!/usr/bin/env python3
"""
Create multiple TTS tasks using different models
"""

import sys
import os
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
BASE_URL = "https://violet-proxy-bl4w.onrender.com"
API_KEY = "tQlbLPoTF7RRsvJjgCm_4kHiIg-xqoQ6l4utqW56sY0"

# Task parameters
TEXT = """Born on February 12, 1982 in Nkozi in central Uganda, Kyagulanyi grew up in the impoverished Kamwokya neighbourhood of Kampala. Music became his path out of hardship. He adopted the name Bobi Wine—a nod to musical icons and his belief in maturing with age—and rose to fame in the early 2000s with hits in genres like reggae, Afrobeat, dancehall, and kidandali that spoke to everyday life in Uganda.
Early songs touched on love and social celebration, but he gradually used his art to address deeper issues—poverty, corruption, injustice, sanitation, and domestic violence—a style he dubbed "edutainment." His music resonated widely, earning him the nickname "Ghetto President."
One of his songs, "Kiwani," even reached global audiences after being featured on the soundtrack of the Disney film Queen of Katwe (2016)."""

SOURCE_LANGUAGE = "en"
PRIORITY = "normal"
VOICE_NAME = "english_alice"

# Model IDs to test
MODEL_IDS = [
    "tts_models/multilingual/multi-dataset/xtts_v2",
    "tts_models/multilingual/multi-dataset/your_tts",
    "tts_models/en/ljspeech/tacotron2-DDC",
    "tts_models/en/vctk/vits"
]

def create_tts_task(text, voice_name, model_id, source_language, priority):
    """Create a TTS task"""
    print("\n" + "=" * 80)
    print(f"  CREATING TTS TASK - {model_id}")
    print("=" * 80)
    
    url = f"{BASE_URL}/api/v1/tts"
    headers = {
        "X-API-Key": API_KEY
    }
    
    # Form data for TTS endpoint
    form_data = {
        "text": text,
        "voice_name": voice_name,
        "model_id": model_id,
        "source_language": source_language,
        "priority": priority
    }
    
    print(f"\n📝 Task Parameters:")
    print(f"   Text: {text[:80]}... (length: {len(text)} chars)")
    print(f"   Voice Name: {voice_name}")
    print(f"   Model ID: {model_id}")
    print(f"   Source Language: {source_language}")
    print(f"   Priority: {priority}")
    
    try:
        response = requests.post(url, headers=headers, data=form_data, timeout=120)
        response.raise_for_status()
        
        data = response.json()
        if data.get("success"):
            task_id = data.get("task_id")
            print(f"\n✅ TTS task created successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {data.get('status', 'N/A')}")
            print(f"\n   You can check the task status at:")
            print(f"   {BASE_URL}/api/v1/tts/{task_id}/result")
            return task_id
        else:
            print(f"❌ Failed to create task: {data.get('message', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating TTS task: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return None

def main():
    """Main function"""
    print("\n" + "=" * 80)
    print("  TTS TASK CREATION SCRIPT - MULTIPLE MODELS")
    print("=" * 80)
    
    if not API_KEY:
        print("\n❌ Error: API_KEY not found")
        return
    
    print(f"\n🔑 Using API Key: {API_KEY[:20]}...")
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"🎤 Voice: {VOICE_NAME}")
    print(f"📝 Text Length: {len(TEXT)} characters")
    
    # Create tasks for each model
    task_ids = []
    for model_id in MODEL_IDS:
        task_id = create_tts_task(
            text=TEXT,
            voice_name=VOICE_NAME,
            model_id=model_id,
            source_language=SOURCE_LANGUAGE,
            priority=PRIORITY
        )
        if task_id:
            task_ids.append((model_id, task_id))
    
    # Summary
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    
    if task_ids:
        print(f"\n✅ Successfully created {len(task_ids)} TTS task(s):\n")
        for model_id, task_id in task_ids:
            print(f"   {model_id}:")
            print(f"      Task ID: {task_id}")
            print(f"      Status URL: {BASE_URL}/api/v1/tts/{task_id}/result")
            print()
        
        print(f"\n📋 Task IDs for assignment:")
        for model_id, task_id in task_ids:
            print(f"   {task_id}  # {model_id}")
    else:
        print("\n❌ No tasks were created successfully")

if __name__ == "__main__":
    main()
