#!/usr/bin/env python3
"""
Recreate translation tasks for all models and assign to miners
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
TEXT = """Artificial intelligence has revolutionized numerous industries and aspects of daily life. Machine learning algorithms can now process vast amounts of data, recognize patterns, and make predictions with remarkable accuracy. From healthcare diagnostics to autonomous vehicles, AI systems are transforming how we work, communicate, and solve complex problems. Natural language processing enables computers to understand and generate human language, while computer vision allows machines to interpret visual information. As AI technology continues to advance, it promises to unlock new possibilities and reshape the future of technology."""

SOURCE_LANGUAGE = "en"
PRIORITY = "normal"

# Model IDs and their target languages
MODELS = [
    {
        "model_id": "facebook/mbart-large-50-many-to-many-mmt",
        "target_language": "es",  # Spanish
        "description": "Multilingual many-to-many translation (50+ languages)"
    },
    {
        "model_id": "t5-small",
        "target_language": "es",  # Spanish
        "description": "T5 small model for translation"
    },
    {
        "model_id": "Helsinki-NLP/opus-mt-en-es",
        "target_language": "es",  # Spanish (from model name)
        "description": "English to Spanish (Marian model)"
    },
    {
        "model_id": "Helsinki-NLP/opus-mt-en-fr",
        "target_language": "fr",  # French (from model name)
        "description": "English to French"
    },
    {
        "model_id": "Helsinki-NLP/opus-mt-en-de",
        "target_language": "de",  # German (from model name)
        "description": "English to German"
    },
    {
        "model_id": "Helsinki-NLP/opus-mt-en-zh",
        "target_language": "zh",  # Chinese (from model name)
        "description": "English to Chinese"
    }
]

def create_translation_task(text, model_id, source_language, target_language, priority):
    """Create a translation task"""
    print("\n" + "=" * 80)
    print(f"  CREATING TRANSLATION TASK - {model_id}")
    print("=" * 80)
    
    url = f"{BASE_URL}/api/v1/text-translation"
    headers = {
        "X-API-Key": API_KEY
    }
    
    # Form data for translation endpoint
    form_data = {
        "text": text,
        "model_id": model_id,
        "source_language": source_language,
        "target_language": target_language,
        "priority": priority
    }
    
    print(f"\n📝 Task Parameters:")
    print(f"   Text: {text[:100]}... (length: {len(text)} chars)")
    print(f"   Model ID: {model_id}")
    print(f"   Source Language: {source_language}")
    print(f"   Target Language: {target_language}")
    print(f"   Priority: {priority}")
    
    try:
        response = requests.post(url, headers=headers, data=form_data, timeout=120)
        response.raise_for_status()
        
        data = response.json()
        if data.get("success"):
            task_id = data.get("task_id")
            print(f"\n✅ Translation task created successfully!")
            print(f"   Task ID: {task_id}")
            print(f"   Status: {data.get('status', 'N/A')}")
            print(f"   Text Length: {data.get('text_length', 'N/A')} characters")
            print(f"   Word Count: {data.get('word_count', 'N/A')} words")
            print(f"   Source Language: {data.get('source_language', 'N/A')}")
            print(f"   Target Language: {data.get('target_language', 'N/A')}")
            print(f"\n   You can check the task status at:")
            print(f"   {BASE_URL}/api/v1/text-translation/{task_id}/result")
            return task_id
        else:
            print(f"❌ Failed to create task: {data.get('message', 'Unknown error')}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Error creating translation task: {e}")
        if hasattr(e, 'response') and e.response is not None:
            print(f"   Status Code: {e.response.status_code}")
            print(f"   Response: {e.response.text[:500]}")
        return None

def assign_task_to_miner(task_id, miner_uid):
    """Assign a task to a specific miner"""
    from sqlalchemy import create_engine, text
    import os
    from dotenv import load_dotenv
    load_dotenv()
    
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    
    try:
        engine = create_engine(
            database_url,
            pool_pre_ping=True,
            connect_args={
                "connect_timeout": 10,
                "sslmode": "require"
            }
        )
        
        with engine.connect() as conn:
            # Get current assigned miners
            query = text("""
                SELECT assigned_miners
                FROM tasks
                WHERE task_id = CAST(:task_id AS uuid)
            """)
            result = conn.execute(query, {'task_id': task_id})
            task = result.fetchone()
            
            if not task:
                print(f"   ⚠️  Task {task_id} not found in database")
                return False
            
            assigned_miners = task[0] or []
            
            # Add miner if not already assigned
            if miner_uid not in assigned_miners:
                assigned_miners.append(miner_uid)
                
                # Update task
                update_query = text("""
                    UPDATE tasks
                    SET 
                        assigned_miners = :assigned_miners,
                        status = CAST('ASSIGNED' AS taskstatusenum),
                        updated_at = NOW()
                    WHERE task_id = CAST(:task_id AS uuid)
                """)
                conn.execute(update_query, {
                    'task_id': task_id,
                    'assigned_miners': assigned_miners
                })
                conn.commit()
                print(f"   ✅ Assigned to miner UID {miner_uid}")
                return True
            else:
                print(f"   ℹ️  Already assigned to miner UID {miner_uid}")
                return True
        
        engine.dispose()
        
    except Exception as e:
        print(f"   ❌ Error assigning task: {e}")
        return False

def main():
    """Main function"""
    print("\n" + "=" * 80)
    print("  RECREATE TRANSLATION TASKS - MULTIPLE MODELS")
    print("=" * 80)
    
    if not API_KEY:
        print("\n❌ Error: API_KEY not found")
        return
    
    print(f"\n🔑 Using API Key: {API_KEY[:20]}...")
    print(f"🌐 Base URL: {BASE_URL}")
    print(f"📝 Text Length: {len(TEXT)} characters")
    print(f"🌍 Source Language: {SOURCE_LANGUAGE}")
    print(f"📋 Models to test: {len(MODELS)}")
    
    # Create tasks for each model
    task_ids = []
    for model_config in MODELS:
        model_id = model_config["model_id"]
        target_language = model_config["target_language"]
        description = model_config["description"]
        
        print(f"\n{'─' * 80}")
        print(f"Model: {model_id}")
        print(f"Description: {description}")
        print(f"Target Language: {target_language}")
        
        task_id = create_translation_task(
            text=TEXT,
            model_id=model_id,
            source_language=SOURCE_LANGUAGE,
            target_language=target_language,
            priority=PRIORITY
        )
        if task_id:
            task_ids.append((model_id, task_id, target_language))
            
            # Assign to miners 6 and 16
            print(f"\n   Assigning to miners...")
            assign_task_to_miner(task_id, 6)
            assign_task_to_miner(task_id, 16)
    
    # Summary
    print("\n" + "=" * 80)
    print("  SUMMARY")
    print("=" * 80)
    
    if task_ids:
        print(f"\n✅ Successfully created {len(task_ids)} translation task(s):\n")
        for model_id, task_id, target_lang in task_ids:
            print(f"   {model_id} (en → {target_lang}):")
            print(f"      Task ID: {task_id}")
            print(f"      Status URL: {BASE_URL}/api/v1/text-translation/{task_id}/result")
            print()
        
        print(f"\n📋 Task IDs for reference:")
        for model_id, task_id, target_lang in task_ids:
            print(f"   {task_id}  # {model_id} (en → {target_lang})")
        
        print(f"\n✅ All tasks assigned to miners 6 and 16")
        print(f"\n💡 Note: Make sure sentencepiece is installed:")
        print(f"   pip install sentencepiece>=0.1.99")
    else:
        print("\n❌ No tasks were created successfully")

if __name__ == "__main__":
    main()
