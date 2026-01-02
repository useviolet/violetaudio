#!/usr/bin/env python3
"""
Test script to verify miner file URL fetching functionality
Tests the fixes for UTF-32 decoding errors and file URL retrieval
"""

import sys
import os
import asyncio
import httpx
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

async def test_file_metadata_fetching():
    """Test fetching file metadata from proxy server"""
    print("=" * 80)
    print("Testing File Metadata Fetching")
    print("=" * 80)
    
    # Get configuration from environment
    proxy_server_url = os.getenv('PROXY_SERVER_URL', 'http://localhost:8000')
    api_key = os.getenv('MINER_API_KEY', '')
    
    if not api_key:
        print("❌ MINER_API_KEY not set in environment")
        print("   Set it with: export MINER_API_KEY=your_api_key")
        return False
    
    headers = {"X-API-Key": api_key}
    
    # Test 1: Fetch a file metadata (should return JSON)
    print("\n📡 Test 1: Fetching file metadata from /api/v1/files/{file_id}")
    print("-" * 80)
    
    # You'll need to replace this with an actual file_id from your database
    test_file_id = os.getenv('TEST_FILE_ID', '')
    
    if not test_file_id:
        print("⚠️  TEST_FILE_ID not set - skipping file metadata test")
        print("   Set it with: export TEST_FILE_ID=your_file_id")
    else:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{proxy_server_url}/api/v1/files/{test_file_id}",
                    headers=headers
                )
                
                print(f"   Status Code: {response.status_code}")
                print(f"   Content-Type: {response.headers.get('content-type', 'N/A')}")
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' in content_type:
                        try:
                            file_metadata = response.json()
                            print(f"   ✅ Successfully parsed JSON response")
                            print(f"   Response keys: {list(file_metadata.keys())}")
                            
                            if file_metadata.get("success") and file_metadata.get("file", {}).get("public_url"):
                                public_url = file_metadata["file"]["public_url"]
                                print(f"   ✅ Found public_url: {public_url[:60]}...")
                            elif file_metadata.get("file", {}).get("public_url"):
                                public_url = file_metadata["file"]["public_url"]
                                print(f"   ✅ Found public_url (no success field): {public_url[:60]}...")
                            else:
                                print(f"   ⚠️  No public_url found in response")
                                print(f"   File metadata: {json.dumps(file_metadata, indent=2)}")
                        except (ValueError, KeyError) as e:
                            print(f"   ❌ Error parsing JSON: {e}")
                    else:
                        print(f"   ⚠️  Response is not JSON (Content-Type: {content_type})")
                        print(f"   This is expected if the endpoint returns the file directly")
                else:
                    print(f"   ❌ Request failed with status {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Test 2: Fetch transcription task content
    print("\n📡 Test 2: Fetching transcription task content")
    print("-" * 80)
    
    test_task_id = os.getenv('TEST_TRANSCRIPTION_TASK_ID', '')
    
    if not test_task_id:
        print("⚠️  TEST_TRANSCRIPTION_TASK_ID not set - skipping transcription endpoint test")
        print("   Set it with: export TEST_TRANSCRIPTION_TASK_ID=your_task_id")
    else:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{proxy_server_url}/api/v1/miner/transcription/{test_task_id}",
                    headers=headers
                )
                
                print(f"   Status Code: {response.status_code}")
                print(f"   Content-Type: {response.headers.get('content-type', 'N/A')}")
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' in content_type:
                        try:
                            response_data = response.json()
                            print(f"   ✅ Successfully parsed JSON response")
                            print(f"   Response keys: {list(response_data.keys())}")
                            
                            if response_data.get("success") and "audio_url" in response_data:
                                audio_url = response_data["audio_url"]
                                print(f"   ✅ Found audio_url: {audio_url[:60]}...")
                            elif "audio_url" in response_data:
                                audio_url = response_data["audio_url"]
                                print(f"   ✅ Found audio_url (no success field): {audio_url[:60]}...")
                            else:
                                print(f"   ⚠️  No audio_url found in response")
                                print(f"   Response data: {json.dumps(response_data, indent=2)}")
                        except (ValueError, KeyError) as e:
                            print(f"   ❌ Error parsing JSON: {e}")
                    else:
                        print(f"   ⚠️  Response is not JSON (Content-Type: {content_type})")
                else:
                    print(f"   ❌ Request failed with status {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    # Test 3: Fetch video transcription task content
    print("\n📡 Test 3: Fetching video transcription task content")
    print("-" * 80)
    
    test_video_task_id = os.getenv('TEST_VIDEO_TASK_ID', '')
    
    if not test_video_task_id:
        print("⚠️  TEST_VIDEO_TASK_ID not set - skipping video transcription endpoint test")
        print("   Set it with: export TEST_VIDEO_TASK_ID=your_task_id")
    else:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    f"{proxy_server_url}/api/v1/miner/video-transcription/{test_video_task_id}",
                    headers=headers
                )
                
                print(f"   Status Code: {response.status_code}")
                print(f"   Content-Type: {response.headers.get('content-type', 'N/A')}")
                
                if response.status_code == 200:
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' in content_type:
                        try:
                            response_data = response.json()
                            print(f"   ✅ Successfully parsed JSON response")
                            print(f"   Response keys: {list(response_data.keys())}")
                            
                            # Check for download_url
                            if response_data.get("success") and "download_url" in response_data:
                                download_url = response_data["download_url"]
                                print(f"   ✅ Found download_url: {download_url[:60]}...")
                            elif "download_url" in response_data:
                                download_url = response_data["download_url"]
                                print(f"   ✅ Found download_url (no success field): {download_url[:60]}...")
                            # Check for file_metadata.public_url
                            elif "file_metadata" in response_data:
                                file_metadata = response_data["file_metadata"]
                                if isinstance(file_metadata, dict) and file_metadata.get("public_url"):
                                    public_url = file_metadata["public_url"]
                                    print(f"   ✅ Found file_metadata.public_url: {public_url[:60]}...")
                                else:
                                    print(f"   ⚠️  file_metadata exists but no public_url")
                            else:
                                print(f"   ⚠️  No download_url or file_metadata.public_url found")
                                print(f"   Response data: {json.dumps(response_data, indent=2)}")
                        except (ValueError, KeyError) as e:
                            print(f"   ❌ Error parsing JSON: {e}")
                    else:
                        print(f"   ⚠️  Response is not JSON (Content-Type: {content_type})")
                else:
                    print(f"   ❌ Request failed with status {response.status_code}")
                    print(f"   Response: {response.text[:200]}")
        except Exception as e:
            print(f"   ❌ Error: {e}")
    
    print("\n" + "=" * 80)
    print("✅ Testing complete!")
    print("=" * 80)
    
    return True

if __name__ == "__main__":
    asyncio.run(test_file_metadata_fetching())

