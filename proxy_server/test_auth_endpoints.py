#!/usr/bin/env python3
"""
End-to-End Test Script for Role-Based Authentication
Tests all endpoints with different roles and API keys
"""

import requests
import json
import time
from typing import Dict, Optional, Any

# Configuration
BASE_URL = "http://localhost:8000"
# BASE_URL = "https://violet-proxy-bl4w.onrender.com"  # Uncomment for production testing

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

class AuthTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.test_results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }
        self.api_keys = {
            'client': None,
            'miner': None,
            'validator': None,
            'admin': None
        }
    
    def log(self, message: str, color: str = Colors.RESET):
        """Print colored log message"""
        print(f"{color}{message}{Colors.RESET}")
    
    def test(self, name: str, func, *args, **kwargs):
        """Run a test and track results"""
        try:
            self.log(f"\n{'='*60}", Colors.BLUE)
            self.log(f"TEST: {name}", Colors.BLUE)
            self.log(f"{'='*60}", Colors.BLUE)
            result = func(*args, **kwargs)
            if result:
                self.test_results['passed'] += 1
                self.log(f"✅ PASSED: {name}", Colors.GREEN)
            else:
                self.test_results['failed'] += 1
                self.log(f"❌ FAILED: {name}", Colors.RED)
            return result
        except Exception as e:
            self.test_results['failed'] += 1
            self.test_results['errors'].append(f"{name}: {str(e)}")
            self.log(f"❌ ERROR in {name}: {str(e)}", Colors.RED)
            import traceback
            traceback.print_exc()
            return False
    
    def register_client(self) -> bool:
        """Test client registration"""
        email = f"test_client_{int(time.time())}@example.com"
        payload = {
            "email": email,
            "role": "client"
        }
        
        response = requests.post(
            f"{self.base_url}/api/v1/auth/register",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            self.api_keys['client'] = data.get('api_key')
            self.log(f"   Client registered: {email}", Colors.GREEN)
            self.log(f"   API Key: {self.api_keys['client'][:20]}...", Colors.YELLOW)
            return True
        else:
            self.log(f"   Status: {response.status_code}", Colors.RED)
            self.log(f"   Response: {response.text}", Colors.RED)
            return False
    
    def register_miner(self) -> bool:
        """Test miner registration (requires valid Bittensor credentials)"""
        email = f"test_miner_{int(time.time())}@example.com"
        payload = {
            "email": email,
            "role": "miner",
            "hotkey": "5HNKFeHjvppKyKHTA1SK4rN7L2SZWpJeoNjeLo4DDg2FcRKh",
            "coldkey_address": "5FHneW46xGXgs5mUiveU4sbTyGBzmstUspZC92UhjJM694ty",
            "uid": 7,
            "network": "test"
        }
        
        response = requests.post(
            f"{self.base_url}/api/v1/auth/register",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            self.api_keys['miner'] = data.get('api_key')
            self.log(f"   Miner registered: {email}", Colors.GREEN)
            self.log(f"   API Key: {self.api_keys['miner'][:20]}...", Colors.YELLOW)
            return True
        else:
            self.log(f"   Status: {response.status_code}", Colors.YELLOW)
            self.log(f"   Response: {response.text}", Colors.YELLOW)
            self.log(f"   Note: Miner registration may fail if credentials are invalid", Colors.YELLOW)
            return False
    
    def register_admin(self) -> bool:
        """Test admin registration"""
        email = f"test_admin_{int(time.time())}@example.com"
        payload = {
            "email": email,
            "role": "admin"
        }
        
        response = requests.post(
            f"{self.base_url}/api/v1/auth/register",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            self.api_keys['admin'] = data.get('api_key')
            self.log(f"   Admin registered: {email}", Colors.GREEN)
            self.log(f"   API Key: {self.api_keys['admin'][:20]}...", Colors.YELLOW)
            return True
        else:
            self.log(f"   Status: {response.status_code}", Colors.RED)
            self.log(f"   Response: {response.text}", Colors.RED)
            return False
    
    def test_verify_api_key(self, api_key: str, role: str) -> bool:
        """Test API key verification"""
        response = requests.get(
            f"{self.base_url}/api/v1/auth/verify-api-key",
            params={"api_key": api_key},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            if data.get('valid') and data.get('role') == role:
                self.log(f"   ✅ API key verified for {role} role", Colors.GREEN)
                return True
            else:
                self.log(f"   ❌ Role mismatch: expected {role}, got {data.get('role')}", Colors.RED)
                return False
        else:
            self.log(f"   ❌ Verification failed: {response.status_code}", Colors.RED)
            return False
    
    def test_client_endpoint(self, api_key: str) -> bool:
        """Test client endpoint access"""
        headers = {"X-API-Key": api_key}
        
        # Test getting tasks (should work for client)
        response = requests.get(
            f"{self.base_url}/api/v1/tasks",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            self.log(f"   ✅ Client can access /api/v1/tasks", Colors.GREEN)
            return True
        elif response.status_code == 401:
            self.log(f"   ❌ Unauthorized (invalid API key)", Colors.RED)
            return False
        elif response.status_code == 403:
            self.log(f"   ❌ Forbidden (wrong role)", Colors.RED)
            return False
        else:
            self.log(f"   ⚠️  Unexpected status: {response.status_code}", Colors.YELLOW)
            return False
    
    def test_miner_endpoint(self, api_key: str) -> bool:
        """Test miner endpoint access"""
        headers = {"X-API-Key": api_key}
        
        # Test getting miner tasks
        response = requests.get(
            f"{self.base_url}/api/v1/miners/7/tasks",
            headers=headers,
            params={"status": "assigned"},
            timeout=10
        )
        
        if response.status_code == 200:
            self.log(f"   ✅ Miner can access /api/v1/miners/7/tasks", Colors.GREEN)
            return True
        elif response.status_code == 401:
            self.log(f"   ❌ Unauthorized (invalid API key)", Colors.RED)
            return False
        elif response.status_code == 403:
            self.log(f"   ❌ Forbidden (wrong role)", Colors.RED)
            return False
        else:
            self.log(f"   ⚠️  Unexpected status: {response.status_code}", Colors.YELLOW)
            return False
    
    def test_validator_endpoint(self, api_key: str) -> bool:
        """Test validator endpoint access"""
        headers = {"X-API-Key": api_key}
        
        # Test getting validator tasks
        response = requests.get(
            f"{self.base_url}/api/v1/validator/tasks",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            self.log(f"   ✅ Validator can access /api/v1/validator/tasks", Colors.GREEN)
            return True
        elif response.status_code == 401:
            self.log(f"   ❌ Unauthorized (invalid API key)", Colors.RED)
            return False
        elif response.status_code == 403:
            self.log(f"   ❌ Forbidden (wrong role)", Colors.RED)
            return False
        else:
            self.log(f"   ⚠️  Unexpected status: {response.status_code}", Colors.YELLOW)
            return False
    
    def test_admin_access_all(self, api_key: str) -> bool:
        """Test that admin can access all endpoints"""
        headers = {"X-API-Key": api_key}
        all_passed = True
        
        # Test client endpoint
        response = requests.get(
            f"{self.base_url}/api/v1/tasks",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            self.log(f"   ✅ Admin can access client endpoint", Colors.GREEN)
        else:
            self.log(f"   ❌ Admin cannot access client endpoint: {response.status_code}", Colors.RED)
            all_passed = False
        
        # Test miner endpoint
        response = requests.get(
            f"{self.base_url}/api/v1/miners/7/tasks",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            self.log(f"   ✅ Admin can access miner endpoint", Colors.GREEN)
        else:
            self.log(f"   ❌ Admin cannot access miner endpoint: {response.status_code}", Colors.RED)
            all_passed = False
        
        # Test validator endpoint
        response = requests.get(
            f"{self.base_url}/api/v1/validator/tasks",
            headers=headers,
            timeout=10
        )
        if response.status_code == 200:
            self.log(f"   ✅ Admin can access validator endpoint", Colors.GREEN)
        else:
            self.log(f"   ❌ Admin cannot access validator endpoint: {response.status_code}", Colors.RED)
            all_passed = False
        
        return all_passed
    
    def test_fake_key_rejection(self) -> bool:
        """Test that fake/invalid API keys are rejected"""
        fake_keys = [
            "fake_key_12345",
            "invalid_key_abcdefghijklmnop",
            "",
            "admin",  # Common attack
            "miner",  # Common attack
        ]
        
        all_rejected = True
        for fake_key in fake_keys:
            headers = {"X-API-Key": fake_key}
            response = requests.get(
                f"{self.base_url}/api/v1/tasks",
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 401:
                self.log(f"   ✅ Fake key rejected: {fake_key[:20]}...", Colors.GREEN)
            else:
                self.log(f"   ❌ Fake key accepted: {fake_key[:20]}... (status: {response.status_code})", Colors.RED)
                all_rejected = False
        
        return all_rejected
    
    def test_role_isolation(self) -> bool:
        """Test that roles cannot access each other's endpoints"""
        if not self.api_keys['client']:
            self.log(f"   ⚠️  Skipping: No client API key", Colors.YELLOW)
            return True
        
        headers = {"X-API-Key": self.api_keys['client']}
        
        # Client should NOT access miner endpoint
        response = requests.get(
            f"{self.base_url}/api/v1/miners/7/tasks",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 403:
            self.log(f"   ✅ Client correctly blocked from miner endpoint", Colors.GREEN)
            return True
        elif response.status_code == 200:
            self.log(f"   ❌ Client incorrectly allowed access to miner endpoint", Colors.RED)
            return False
        else:
            self.log(f"   ⚠️  Unexpected status: {response.status_code}", Colors.YELLOW)
            return False
    
    def run_all_tests(self):
        """Run all authentication tests"""
        self.log("\n" + "="*60, Colors.BLUE)
        self.log("ROLE-BASED AUTHENTICATION END-TO-END TESTS", Colors.BLUE)
        self.log("="*60, Colors.BLUE)
        
        # Test 1: Register different roles
        self.test("Register Client", self.register_client)
        self.test("Register Miner", self.register_miner)
        self.test("Register Admin", self.register_admin)
        
        # Test 2: Verify API keys
        if self.api_keys['client']:
            self.test("Verify Client API Key", self.test_verify_api_key, self.api_keys['client'], 'client')
        if self.api_keys['admin']:
            self.test("Verify Admin API Key", self.test_verify_api_key, self.api_keys['admin'], 'admin')
        
        # Test 3: Test endpoint access
        if self.api_keys['client']:
            self.test("Client Access to Client Endpoints", self.test_client_endpoint, self.api_keys['client'])
        if self.api_keys['miner']:
            self.test("Miner Access to Miner Endpoints", self.test_miner_endpoint, self.api_keys['miner'])
        if self.api_keys['admin']:
            self.test("Admin Access to All Endpoints", self.test_admin_access_all, self.api_keys['admin'])
        
        # Test 4: Security tests
        self.test("Fake Key Rejection", self.test_fake_key_rejection)
        if self.api_keys['client']:
            self.test("Role Isolation", self.test_role_isolation)
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        self.log("\n" + "="*60, Colors.BLUE)
        self.log("TEST SUMMARY", Colors.BLUE)
        self.log("="*60, Colors.BLUE)
        self.log(f"✅ Passed: {self.test_results['passed']}", Colors.GREEN)
        self.log(f"❌ Failed: {self.test_results['failed']}", Colors.RED)
        
        if self.test_results['errors']:
            self.log("\nErrors:", Colors.RED)
            for error in self.test_results['errors']:
                self.log(f"  - {error}", Colors.RED)
        
        total = self.test_results['passed'] + self.test_results['failed']
        if total > 0:
            success_rate = (self.test_results['passed'] / total) * 100
            self.log(f"\nSuccess Rate: {success_rate:.1f}%", Colors.GREEN if success_rate >= 80 else Colors.YELLOW)

if __name__ == "__main__":
    import sys
    
    # Allow custom base URL
    base_url = sys.argv[1] if len(sys.argv) > 1 else BASE_URL
    
    tester = AuthTester(base_url=base_url)
    tester.run_all_tests()

