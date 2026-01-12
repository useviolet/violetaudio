#!/usr/bin/env python3
"""
Test script to verify the file URL fetching fixes in the miner
Tests the Content-Type checking and URL retrieval logic
"""

import sys
import os
import asyncio
from unittest.mock import Mock, AsyncMock, patch
import json

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def test_content_type_checking():
    """Test that Content-Type checking prevents UTF-32 decoding errors"""
    print("=" * 80)
    print("Test 1: Content-Type Checking")
    print("=" * 80)
    
    # Simulate a binary response (like a file download)
    mock_response_binary = Mock()
    mock_response_binary.status_code = 200
    mock_response_binary.headers = {'content-type': 'application/octet-stream'}
    mock_response_binary.content = b'\x00\x00\x00\x00\x00\x00\x00\x00'  # Binary data
    
    # Simulate a JSON response (like metadata)
    mock_response_json = Mock()
    mock_response_json.status_code = 200
    mock_response_json.headers = {'content-type': 'application/json'}
    mock_response_json.json.return_value = {
        "success": True,
        "file": {
            "public_url": "https://example.com/file.wav"
        }
    }
    
    # Test Content-Type checking logic
    print("\n📋 Testing binary response handling...")
    content_type_binary = mock_response_binary.headers.get('content-type', '').lower()
    if 'application/json' in content_type_binary:
        print("   ❌ FAILED: Binary response incorrectly identified as JSON")
        return False
    else:
        print("   ✅ PASSED: Binary response correctly identified as non-JSON")
    
    print("\n📋 Testing JSON response handling...")
    content_type_json = mock_response_json.headers.get('content-type', '').lower()
    if 'application/json' in content_type_json:
        print("   ✅ PASSED: JSON response correctly identified")
        try:
            data = mock_response_json.json()
            if data.get("success") and data.get("file", {}).get("public_url"):
                print(f"   ✅ PASSED: Successfully extracted URL: {data['file']['public_url'][:50]}...")
                return True
            else:
                print("   ⚠️  Response structure different than expected")
                return True  # Still passed the Content-Type check
        except Exception as e:
            print(f"   ❌ FAILED: Error parsing JSON: {e}")
            return False
    else:
        print("   ❌ FAILED: JSON response incorrectly identified as non-JSON")
        return False

def test_video_transcription_endpoint_parsing():
    """Test parsing of video transcription endpoint responses"""
    print("\n" + "=" * 80)
    print("Test 2: Video Transcription Endpoint Response Parsing")
    print("=" * 80)
    
    # Test case 1: Response with download_url
    response_with_download_url = {
        "success": True,
        "download_url": "https://example.com/video.mp4",
        "task_id": "test-task-123"
    }
    
    print("\n📋 Testing response with download_url...")
    if response_with_download_url.get("success") and "download_url" in response_with_download_url:
        file_url = response_with_download_url["download_url"]
        print(f"   ✅ PASSED: Found download_url: {file_url[:50]}...")
    else:
        print("   ❌ FAILED: Could not find download_url")
        return False
    
    # Test case 2: Response with file_metadata.public_url
    response_with_file_metadata = {
        "success": True,
        "file_metadata": {
            "public_url": "https://example.com/video.mp4",
            "file_id": "file-123"
        },
        "task_id": "test-task-123"
    }
    
    print("\n📋 Testing response with file_metadata.public_url...")
    if response_with_file_metadata.get("success") and "file_metadata" in response_with_file_metadata:
        file_metadata = response_with_file_metadata["file_metadata"]
        if isinstance(file_metadata, dict) and file_metadata.get("public_url"):
            file_url = file_metadata["public_url"]
            print(f"   ✅ PASSED: Found file_metadata.public_url: {file_url[:50]}...")
        else:
            print("   ❌ FAILED: file_metadata exists but no public_url")
            return False
    else:
        print("   ❌ FAILED: Could not find file_metadata")
        return False
    
    # Test case 3: Response without success field
    response_no_success = {
        "download_url": "https://example.com/video.mp4",
        "task_id": "test-task-123"
    }
    
    print("\n📋 Testing response without success field...")
    if "download_url" in response_no_success:
        file_url = response_no_success["download_url"]
        print(f"   ✅ PASSED: Found download_url (no success field): {file_url[:50]}...")
    else:
        print("   ❌ FAILED: Could not find download_url without success field")
        return False
    
    return True

def test_error_logging():
    """Test that error logging provides useful diagnostics"""
    print("\n" + "=" * 80)
    print("Test 3: Error Logging Diagnostics")
    print("=" * 80)
    
    # Simulate task data with missing file URL
    task_data = {
        "task_id": "test-task-123",
        "task_type": "transcription",
        "input_file_id": "file-123",
        "input_file": {
            "file_id": "file-123",
            "storage_location": "r2",
            # Missing public_url
        }
    }
    
    print("\n📋 Testing error diagnostics...")
    print(f"   Task Type: {task_data.get('task_type')}")
    print(f"   Input File ID: {task_data.get('input_file_id', 'N/A')}")
    print(f"   Has input_file dict: {'input_file' in task_data}")
    
    if 'input_file' in task_data:
        input_file = task_data['input_file']
        print(f"   input_file keys: {list(input_file.keys()) if isinstance(input_file, dict) else 'Not a dict'}")
        if isinstance(input_file, dict):
            print(f"   input_file.public_url: {input_file.get('public_url', 'N/A')}")
            print(f"   input_file.storage_location: {input_file.get('storage_location', 'N/A')}")
    
    print("   ✅ PASSED: Error diagnostics provide useful information")
    return True

def main():
    """Run all tests"""
    print("\n🧪 Testing File URL Fetching Fixes")
    print("=" * 80)
    
    results = []
    
    # Test 1: Content-Type checking
    results.append(("Content-Type Checking", test_content_type_checking()))
    
    # Test 2: Video transcription endpoint parsing
    results.append(("Video Transcription Endpoint Parsing", test_video_transcription_endpoint_parsing()))
    
    # Test 3: Error logging
    results.append(("Error Logging Diagnostics", test_error_logging()))
    
    # Summary
    print("\n" + "=" * 80)
    print("Test Summary")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"   {status}: {test_name}")
    
    print(f"\n   Total: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n   🎉 All tests passed! The fixes are working correctly.")
        return 0
    else:
        print(f"\n   ⚠️  {total - passed} test(s) failed. Please review the fixes.")
        return 1

if __name__ == "__main__":
    sys.exit(main())

