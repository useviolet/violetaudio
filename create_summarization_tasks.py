#!/usr/bin/env python3
"""
Create multiple summarization tasks using different models
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
TEXT = """## **Bobi Wine: From Ghetto Star to Uganda's Leading Opposition Voice**

Robert Kyagulanyi Ssentamu—better known by his stage name **Bobi Wine**—is one of East Africa's most compelling cultural and political figures. A musician turned politician and activist, his life story reflects both the struggles and aspirations of Uganda's youth. ([Encyclopedia Britannica][1])

### **Early Life and Rise in Music**

Born on **February 12, 1982** in **Nkozi** in central Uganda, Kyagulanyi grew up in the impoverished Kamwokya neighbourhood of Kampala. Music became his path out of hardship. He adopted the name *Bobi Wine*—a nod to musical icons and his belief in maturing with age—and rose to fame in the early 2000s with hits in genres like reggae, Afrobeat, dancehall, and *kidandali* that spoke to everyday life in Uganda. ([Encyclopedia Britannica][1])

Early songs touched on love and social celebration, but he gradually used his art to address deeper issues—poverty, corruption, injustice, sanitation, and domestic violence—a style he dubbed "edutainment." His music resonated widely, earning him the nickname **"Ghetto President."** ([Encyclopedia Britannica][1])

One of his songs, *"Kiwani,"* even reached global audiences after being featured on the soundtrack of the Disney film *Queen of Katwe* (2016). ([Encyclopedia Britannica][1])

### **Art and Activism**

Bobi Wine's music isn't just entertainment—it has long been a social commentary on life in Uganda. Tracks like *"Ghetto"* and *"Time Bomb"* critiqued political and economic inequalities. He also ventured into acting and television, appearing in films like *Situka* and hosting *The Ghetto President* reality show. ([Encyclopedia Britannica][1])

His transition from entertainment to activism drew attention both within and outside Uganda, sometimes earning him censorship or travel restrictions due to controversial lyrics earlier in his career. ([TIME][2])

### **Political Career and Opposition Leadership**

Bobi Wine entered formal politics in **2017** when he won a parliamentary seat representing **Kyadondo East** with a landslide victory. His popularity stemmed from his identification with Uganda's youth, who make up more than three‑quarters of the population and feel marginalized by the country's longstanding leadership. ([Encyclopedia Britannica][1])

He founded the **People Power movement**, a grassroots political force symbolized by the red beret, and later became leader of the **National Unity Platform (NUP)**—now Uganda's main opposition party. ([Encyclopedia Britannica][1])

Bobi Wine challenged President **Yoweri Museveni**, who has ruled Uganda since **1986**, in the **2021 presidential election**. While official results declared Museveni the winner, Wine and his supporters alleged widespread fraud and intimidation. ([Encyclopedia Britannica][1])

### **Ongoing Struggle and 2026 Election**

As of early **2026**, Bobi Wine remains at the centre of Ugandan politics. The country's **January 15, 2026 presidential election** has been marred by violence, internet blackouts, security raids, and contested results. Wine rejected the official outcome and called for Ugandans to reject what he described as "fake" results, citing ballot stuffing and repression of his supporters. ([The Times][3])

His campaign has faced repeated crackdowns from state security forces. Reports indicate his home was raided on election day, forcing him into hiding amid threats and allegations of human rights violations. Many of his allies have been arrested. ([The Times][3])

Despite these dangers, Wine's political influence has grown through his unyielding message on democratic reform, youth empowerment, and fighting corruption—a remarkable evolution for a pop star from the slums of Kampala. ([Reuters][4])

### **Legacy and Global Recognition**

Bobi Wine's life and struggle were chronicled in the documentary *Bobi Wine: The People's President*, which has drawn international praise and recognition, including a nomination for Best Documentary Feature at the **2024 Oscars**. ([Pulse Uganda][5])

From **music icon to opposition leader**, Bobi Wine's journey is a testament to the power of art, resilience, and the quest for political change in Africa. ([Encyclopedia Britannica][1])

[1]: https://www.britannica.com/biography/Bobi-Wine?utm_source=chatgpt.com "Bobi Wine | Biography, Songs, Kiwani, Family, Arua, People's President, Ghetto President, Film, & Facts | Britannica"
[2]: https://time.com/5913625/bobi-wine-uganda-presidential-candidate/?utm_source=chatgpt.com "Uganda's Reggae Star Politician Bobi Wine Wants a Revolution | TIME"
[3]: https://www.thetimes.com/world/africa/article/uganda-presidential-election-2026-bobi-wine-pgbvhdtpz?utm_source=chatgpt.com "They threatened to behead me. Then they stormed my home on election day"
[4]: https://www.reuters.com/world/africa/pop-star-bobi-wine-sets-sights-ugandan-presidency-despite-campaign-violence-2026-01-13/?utm_source=chatgpt.com "Pop star Bobi Wine sets sights on Ugandan presidency despite campaign violence"
[5]: https://www.pulse.ug/articles/celebrities/bobi-wine-biography-education-age-parents-career-children-politics-2024092710451001088?utm_source=chatgpt.com "Bobi Wine biography: Education, age, parents, career, children, politics | Pulse Uganda"
"""

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
    print("  SUMMARIZATION TASK CREATION SCRIPT - MULTIPLE MODELS")
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
    else:
        print("\n❌ No tasks were created successfully")

if __name__ == "__main__":
    main()
