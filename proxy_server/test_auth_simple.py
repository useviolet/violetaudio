#!/usr/bin/env python3
"""
Simple Authentication Test Script
Tests role-based authentication with clear instructions
"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000"

def test_server_connection():
    """Check if server is running"""
    try:
        response = requests.get(f"{BASE_URL}/docs", timeout=5)
        return True
    except:
        return False

def print_instructions():
    """Print usage instructions"""
    print("="*70)
    print("ROLE-BASED AUTHENTICATION TEST GUIDE")
    print("="*70)
    print("\n1. Make sure the proxy server is running:")
    print("   cd proxy_server && python main.py")
    print("\n2. Test endpoints using curl or this script")
    print("\n3. API Key Usage:")
    print("   - Header: X-API-Key: <your_api_key>")
    print("   - Query: ?api_key=<your_api_key>")
    print("\n" + "="*70)

def test_registration():
    """Test user registration"""
    print("\n📝 TESTING USER REGISTRATION")
    print("-"*70)
    
    # Test Client Registration
    print("\n1. Register Client:")
    client_email = f"test_client_{int(time.time())}@example.com"
    payload = {
        "email": client_email,
        "role": "client"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json=payload,
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            api_key = data.get('api_key')
            print(f"   ✅ Client registered successfully")
            print(f"   Email: {client_email}")
            print(f"   API Key: {api_key[:30]}...")
            print(f"\n   Use this API key for client endpoints:")
            print(f"   curl -H 'X-API-Key: {api_key}' {BASE_URL}/api/v1/tasks")
            return api_key
        else:
            print(f"   ❌ Failed: {response.text}")
            return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def test_admin_registration():
    """Test admin registration"""
    print("\n2. Register Admin:")
    admin_email = f"test_admin_{int(time.time())}@example.com"
    payload = {
        "email": admin_email,
        "role": "admin"
    }
    
    try:
        response = requests.post(
            f"{BASE_URL}/api/v1/auth/register",
            json=payload,
            timeout=10
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            api_key = data.get('api_key')
            print(f"   ✅ Admin registered successfully")
            print(f"   Email: {admin_email}")
            print(f"   API Key: {api_key[:30]}...")
            print(f"\n   Use this API key for ALL endpoints (admin has full access)")
            return api_key
        else:
            print(f"   ❌ Failed: {response.text}")
            return None
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return None

def test_api_key_usage(api_key: str, role: str):
    """Test API key usage"""
    print(f"\n🔑 TESTING API KEY USAGE ({role.upper()})")
    print("-"*70)
    
    headers = {"X-API-Key": api_key}
    
    # Test different endpoints based on role
    endpoints = []
    if role == "client":
        endpoints = [
            ("/api/v1/tasks", "Get all tasks"),
            ("/api/v1/miners", "Get miners (client can access)"),
        ]
    elif role == "admin":
        endpoints = [
            ("/api/v1/tasks", "Get all tasks (admin access)"),
            ("/api/v1/miners/7/tasks", "Get miner tasks (admin access)"),
            ("/api/v1/validator/tasks", "Get validator tasks (admin access)"),
        ]
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(
                f"{BASE_URL}{endpoint}",
                headers=headers,
                timeout=10
            )
            status_icon = "✅" if response.status_code == 200 else "❌" if response.status_code == 403 else "⚠️"
            print(f"   {status_icon} {description}")
            print(f"      Status: {response.status_code}")
            if response.status_code == 403:
                print(f"      Message: Access denied (wrong role)")
            elif response.status_code == 401:
                print(f"      Message: Invalid API key")
        except Exception as e:
            print(f"   ❌ Error testing {endpoint}: {e}")

def test_fake_key():
    """Test that fake keys are rejected"""
    print(f"\n🛡️  TESTING SECURITY (Fake Key Rejection)")
    print("-"*70)
    
    fake_key = "fake_invalid_key_12345"
    headers = {"X-API-Key": fake_key}
    
    try:
        response = requests.get(
            f"{BASE_URL}/api/v1/tasks",
            headers=headers,
            timeout=10
        )
        if response.status_code == 401:
            print(f"   ✅ Fake key correctly rejected (401 Unauthorized)")
        else:
            print(f"   ❌ Security issue: Fake key accepted! Status: {response.status_code}")
    except Exception as e:
        print(f"   ⚠️  Error: {e}")

def print_curl_examples(api_key: str):
    """Print curl examples"""
    print(f"\n📋 CURL EXAMPLES")
    print("-"*70)
    print(f"\n1. Get all tasks (Client/Admin):")
    print(f"   curl -H 'X-API-Key: {api_key}' {BASE_URL}/api/v1/tasks")
    
    print(f"\n2. Get tasks using query parameter:")
    print(f"   curl '{BASE_URL}/api/v1/tasks?api_key={api_key}'")
    
    print(f"\n3. Verify API key:")
    print(f"   curl '{BASE_URL}/api/v1/auth/verify-api-key?api_key={api_key}'")
    
    print(f"\n4. Register new user:")
    print(f"   curl -X POST {BASE_URL}/api/v1/auth/register \\")
    print(f"     -H 'Content-Type: application/json' \\")
    print(f"     -d '{{\"email\": \"user@example.com\", \"role\": \"client\"}}'")

if __name__ == "__main__":
    print_instructions()
    
    # Check server connection
    print("\n🔍 Checking server connection...")
    if not test_server_connection():
        print("❌ Server is not running!")
        print(f"\nPlease start the server first:")
        print(f"   cd proxy_server")
        print(f"   python main.py")
        print(f"\nOr if using uvicorn:")
        print(f"   uvicorn proxy_server.main:app --reload --port 8000")
        sys.exit(1)
    
    print("✅ Server is running!")
    
    # Run tests
    client_key = test_registration()
    admin_key = test_admin_registration()
    
    if client_key:
        test_api_key_usage(client_key, "client")
        print_curl_examples(client_key)
    
    if admin_key:
        test_api_key_usage(admin_key, "admin")
    
    test_fake_key()
    
    print("\n" + "="*70)
    print("✅ Testing complete!")
    print("="*70)

