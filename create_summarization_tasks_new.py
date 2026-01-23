#!/usr/bin/env python3
"""
Create multiple summarization tasks using different models with new text
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

# New text for summarization
TEXT = """Artificial intelligence has revolutionized numerous industries and aspects of daily life, transforming how we work, communicate, and solve complex problems. Machine learning algorithms can now process vast amounts of data, identify patterns, and make predictions with remarkable accuracy. From healthcare diagnostics to autonomous vehicles, AI systems are being deployed across diverse domains.

Natural language processing enables computers to understand and generate human language, powering virtual assistants, translation services, and content generation tools. Computer vision allows machines to interpret and analyze visual information, enabling applications in security, manufacturing, and medical imaging. Deep learning neural networks have achieved human-level or superior performance in tasks like image recognition, game playing, and speech recognition.

The development of large language models has opened new possibilities for AI applications. These models can generate coherent text, answer questions, write code, and assist with creative tasks. However, the rapid advancement of AI also raises important questions about ethics, bias, job displacement, and the need for responsible development practices.

As AI continues to evolve, researchers are working on making systems more transparent, fair, and aligned with human values. The future of AI promises even more transformative changes, with potential breakthroughs in areas like general artificial intelligence, quantum computing integration, and human-AI collaboration."""

SOURCE_LANGUAGE = "en"
PRIORITY = "normal"

# Model IDs to test
MODEL_IDS = [
    "facebook/bart-large-cnn",
    "facebook/bart-base",
    "google/pegasus-xsum",
    "t5-small"
]

def create_summarization_task(text, model_id, source_language, priority):
    """Create a summarization task"""
    print("\n" + "=" * 80)
    print(f"  CREATING SUMMARIZATION TASK - {model_id}")
    print("=" * 80)
    
    url = f"{BASE_URL}/api/v1/summarization"
    headers = {
        "X-API-Key": API_KEY
    }
    
    # Form data for summarization endpoint
    form_data = {
        "text": text,
        "model_id": model_id,
        "source_language": source_language,
        "priority": priority
    }
    
    print(f"\n📝 Task Parameters:")
    print(f"   Text: {text[:100]}... (length: {len(text)} chars)")
    print(f"   Model ID: {model_id}")
    print(f"   Source Language: {source_language}")
    print(f"   Priority: {priority}")
    
    try:
        response = requests.post(url, headers=headers, data=form_data, timeout=120)
        response.raise_for_status()
        
        data = response.json()
        if data.get("success"):
            task_id = data.get("task_id")
            print(f"\n✅ Summarization task created successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {data.get('status', 'N/A')}")
            print(f"   Text Length: {data.get('text_length', 'N/A')} characters")
            print(f"   Word Count: {data.get('word_count', 'N/A')} words")
            print(f"\n   You can check the task status at:")
            print(f"   {BASE_URL}/api/v1/summarization/{task_id}/result")
            return task_id
        else:
            print(f"❌ Failed to create task: {data.get('message', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating summarization task: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return None

def main():
    """Main function"""
    print("\n" + "=" * 80)
    print("  SUMMARIZATION TASK CREATION SCRIPT - MULTIPLE MODELS (NEW TEXT)")
    print("=" * 80)
    
    if not API_KEY:
        print("\n❌ Error: API_KEY not found")
        return
    
    print(f"\n🔑 Using API Key: {API_KEY[:20]}...")
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"📝 Text Length: {len(TEXT)} characters")
    print(f"🌍 Source Language: {SOURCE_LANGUAGE}")
    
    # Create tasks for each model
    task_ids = []
    for model_id in MODEL_IDS:
        task_id = create_summarization_task(
            text=TEXT,
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
        print(f"\n✅ Successfully created {len(task_ids)} summarization task(s):\n")
        for model_id, task_id in task_ids:
            print(f"   {model_id}:")
            print(f"      Task ID: {task_id}")
            print(f"      Status URL: {BASE_URL}/api/v1/summarization/{task_id}/result")
            print()
        
        print(f"\n📋 Task IDs for assignment:")
        for model_id, task_id in task_ids:
            print(f"   {task_id}  # {model_id}")
        
        # Return task IDs for assignment
        return [task_id for _, task_id in task_ids]
    else:
        print("\n❌ No tasks were created successfully")
        return []

if __name__ == "__main__":
    task_ids = main()
    if task_ids:
        print(f"\n💡 To assign these tasks to miners, run:")
        print(f"   python assign_task_to_miner.py <task_id> <miner_uid>")
