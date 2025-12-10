#!/usr/bin/env python3
"""
Quick script to check API endpoints for tasks and miners
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8000"

def check_server():
    """Check if server is running"""
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✅ Server is running")
            return True
        else:
            print(f"⚠️  Server returned status {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        print("❌ Server is not reachable")
        return False
    except requests.exceptions.Timeout:
        print("❌ Server request timed out")
        return False
    except Exception as e:
        print(f"❌ Error checking server: {e}")
        return False

def get_tasks():
    """Get tasks from API"""
    try:
        print("\n📋 Fetching tasks...")
        response = requests.get(f"{BASE_URL}/api/v1/tasks", timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            tasks = data.get('tasks', []) if isinstance(data, dict) else data
            print(f"   Found {len(tasks)} tasks")
            
            if tasks:
                print("\n   Task Details:")
                for i, task in enumerate(tasks[:10], 1):  # Show first 10
                    print(f"\n   {i}. Task ID: {task.get('task_id', task.get('id', 'N/A'))}")
                    print(f"      Type: {task.get('task_type', 'N/A')}")
                    print(f"      Status: {task.get('status', 'N/A')}")
                    print(f"      Priority: {task.get('priority', 'N/A')}")
                    if 'created_at' in task:
                        print(f"      Created: {task.get('created_at')}")
            else:
                print("   ⚠️  No tasks found")
            
            return tasks
        else:
            print(f"   ❌ Error: {response.text[:200]}")
            return []
    except requests.exceptions.Timeout:
        print("   ❌ Request timed out")
        return []
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []

def get_miners():
    """Get miners from API"""
    try:
        print("\n⛏️  Fetching miners...")
        response = requests.get(f"{BASE_URL}/api/v1/miners", timeout=10)
        print(f"   Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            miners = data.get('miners', []) if isinstance(data, dict) else data
            print(f"   Found {len(miners)} miners")
            
            if miners:
                print("\n   Miner Details:")
                for i, miner in enumerate(miners[:10], 1):  # Show first 10
                    print(f"\n   {i}. Miner UID: {miner.get('uid', miner.get('id', 'N/A'))}")
                    print(f"      Hotkey: {miner.get('hotkey', 'N/A')}")
                    print(f"      Is Serving: {miner.get('is_serving', False)}")
                    print(f"      Stake: {miner.get('stake', 0)}")
                    if 'last_seen' in miner:
                        print(f"      Last Seen: {miner.get('last_seen')}")
            else:
                print("   ⚠️  No miners found")
            
            return miners
        else:
            print(f"   ❌ Error: {response.text[:200]}")
            return []
    except requests.exceptions.Timeout:
        print("   ❌ Request timed out")
        return []
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return []

def main():
    print("=" * 80)
    print("API Check - Tasks and Miners")
    print("=" * 80)
    
    if not check_server():
        print("\n❌ Cannot proceed - server is not running or not reachable")
        sys.exit(1)
    
    tasks = get_tasks()
    miners = get_miners()
    
    print("\n" + "=" * 80)
    print("Summary")
    print("=" * 80)
    print(f"✅ Tasks: {len(tasks)}")
    print(f"✅ Miners: {len(miners)}")
    print()

if __name__ == "__main__":
    main()

