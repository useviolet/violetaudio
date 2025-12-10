#!/usr/bin/env python3
"""
Comprehensive test suite for all proxy server endpoints
Tests all 44 endpoints to identify issues
"""

import requests
import json
import uuid
import time
from typing import Dict, List, Tuple, Optional, Union
from pathlib import Path
import io

# Configuration
BASE_URL = "http://localhost:8000"
# For production testing, use: BASE_URL = "https://violet-proxy-bl4w.onrender.com"

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    RESET = '\033[0m'

class EndpointTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url.rstrip('/')
        self.results = []
        self.test_task_id = None
        self.test_file_id = None
        self.test_miner_uid = 6
        
    def log_result(self, endpoint: str, method: str, status: str, details: str = ""):
        """Log test result"""
        self.results.append({
            'endpoint': endpoint,
            'method': method,
            'status': status,
            'details': details
        })
        
        color = Colors.GREEN if status == "PASS" else Colors.RED if status == "FAIL" else Colors.YELLOW
        print(f"{color}[{status}]{Colors.RESET} {method:6} {endpoint}")
        if details:
            print(f"         {details}")
    
    def test_get(self, endpoint: str, expected_status: Union[int, List[int]] = 200, params: Optional[Dict] = None, timeout: int = 30) -> Tuple[bool, Dict]:
        """Test GET endpoint"""
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.get(url, params=params, timeout=timeout)
            
            expected_codes = expected_status if isinstance(expected_status, list) else [expected_status]
            if response.status_code in expected_codes:
                try:
                    data = response.json()
                    self.log_result(endpoint, "GET", "PASS", f"Status: {response.status_code}")
                    return True, data
                except:
                    self.log_result(endpoint, "GET", "PASS", f"Status: {response.status_code} (no JSON)")
                    return True, {}
            else:
                self.log_result(endpoint, "GET", "FAIL", f"Expected {expected_status}, got {response.status_code}: {response.text[:100]}")
                return False, {}
        except requests.exceptions.ConnectionError:
            self.log_result(endpoint, "GET", "SKIP", "Server not reachable")
            return False, {}
        except Exception as e:
            self.log_result(endpoint, "GET", "FAIL", f"Error: {str(e)[:100]}")
            return False, {}
    
    def test_post(self, endpoint: str, data: Optional[Dict] = None, files: Optional[Dict] = None, 
                  expected_status: int = 200, form_data: Optional[Dict] = None) -> Tuple[bool, Dict]:
        """Test POST endpoint"""
        try:
            url = f"{self.base_url}{endpoint}"
            
            if files:
                response = requests.post(url, files=files, data=form_data or data, timeout=30)
            elif form_data:
                response = requests.post(url, data=form_data, timeout=30)
            elif data:
                response = requests.post(url, json=data, timeout=30)
            else:
                response = requests.post(url, timeout=30)
            
            expected_codes = expected_status if isinstance(expected_status, list) else [expected_status]
            if response.status_code in expected_codes:
                try:
                    result = response.json()
                    self.log_result(endpoint, "POST", "PASS", f"Status: {response.status_code}")
                    return True, result
                except:
                    self.log_result(endpoint, "POST", "PASS", f"Status: {response.status_code} (no JSON)")
                    return True, {}
            else:
                self.log_result(endpoint, "POST", "FAIL", f"Expected {expected_status}, got {response.status_code}: {response.text[:100]}")
                return False, {}
        except requests.exceptions.ConnectionError:
            self.log_result(endpoint, "POST", "SKIP", "Server not reachable")
            return False, {}
        except Exception as e:
            self.log_result(endpoint, "POST", "FAIL", f"Error: {str(e)[:100]}")
            return False, {}
    
    def test_put(self, endpoint: str, data: Optional[Dict] = None, expected_status: int = 200) -> Tuple[bool, Dict]:
        """Test PUT endpoint"""
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.put(url, json=data, timeout=10)
            
            if response.status_code == expected_status:
                try:
                    result = response.json()
                    self.log_result(endpoint, "PUT", "PASS", f"Status: {response.status_code}")
                    return True, result
                except:
                    self.log_result(endpoint, "PUT", "PASS", f"Status: {response.status_code} (no JSON)")
                    return True, {}
            else:
                self.log_result(endpoint, "PUT", "FAIL", f"Expected {expected_status}, got {response.status_code}: {response.text[:100]}")
                return False, {}
        except requests.exceptions.ConnectionError:
            self.log_result(endpoint, "PUT", "SKIP", "Server not reachable")
            return False, {}
        except Exception as e:
            self.log_result(endpoint, "PUT", "FAIL", f"Error: {str(e)[:100]}")
            return False, {}
    
    def test_delete(self, endpoint: str, expected_status: int = 200) -> Tuple[bool, Dict]:
        """Test DELETE endpoint"""
        try:
            url = f"{self.base_url}{endpoint}"
            response = requests.delete(url, timeout=10)
            
            if response.status_code == expected_status:
                try:
                    result = response.json()
                    self.log_result(endpoint, "DELETE", "PASS", f"Status: {response.status_code}")
                    return True, result
                except:
                    self.log_result(endpoint, "DELETE", "PASS", f"Status: {response.status_code} (no JSON)")
                    return True, {}
            else:
                self.log_result(endpoint, "DELETE", "FAIL", f"Expected {expected_status}, got {response.status_code}: {response.text[:100]}")
                return False, {}
        except requests.exceptions.ConnectionError:
            self.log_result(endpoint, "DELETE", "SKIP", "Server not reachable")
            return False, {}
        except Exception as e:
            self.log_result(endpoint, "DELETE", "FAIL", f"Error: {str(e)[:100]}")
            return False, {}
    
    def create_test_audio_file(self) -> io.BytesIO:
        """Create a minimal test audio file"""
        # Create a minimal WAV file header (44 bytes) + some dummy data
        wav_data = b'RIFF' + b'\x24\x00\x00\x00' + b'WAVE' + b'fmt ' + b'\x10\x00\x00\x00' + \
                   b'\x01\x00\x01\x00' + b'\x44\xac\x00\x00' + b'\x88\x58\x01\x00' + \
                   b'\x02\x00\x10\x00' + b'data' + b'\x00\x00\x00\x00'
        return io.BytesIO(wav_data)
    
    def run_all_tests(self):
        """Run all endpoint tests"""
        print(f"{Colors.BLUE}{'='*80}{Colors.RESET}")
        print(f"{Colors.BLUE}Testing Proxy Server Endpoints{Colors.RESET}")
        print(f"{Colors.BLUE}Base URL: {self.base_url}{Colors.RESET}")
        print(f"{Colors.BLUE}{'='*80}{Colors.RESET}\n")
        
        # Test 1: Health endpoints
        print(f"{Colors.YELLOW}=== Health & Status Endpoints ==={Colors.RESET}")
        self.test_get("/health")
        self.test_get("/api/v1/health")
        print()
        
        # Test 2: Task creation endpoints
        print(f"{Colors.YELLOW}=== Task Creation Endpoints ==={Colors.RESET}")
        
        # Transcription
        success, result = self.test_post("/api/v1/transcription", 
            files={"audio_file": ("test.wav", self.create_test_audio_file(), "audio/wav")},
            form_data={"source_language": "en", "priority": "normal"},
            expected_status=200)
        if success and result.get("task_id"):
            self.test_task_id = result["task_id"]
        
        # TTS - Need at least 10 characters
        success, result = self.test_post("/api/v1/tts",
            data={"text": "This is a test text for TTS conversion that is long enough.", "source_language": "en", "priority": "normal"},
            expected_status=200)
        if success and result.get("task_id"):
            self.test_task_id = result.get("task_id")
        
        # Summarization
        success, result = self.test_post("/api/v1/summarization",
            data={"text": "This is a test text for summarization. " * 20, "source_language": "en", "priority": "normal"},
            expected_status=200)
        if success and result.get("task_id"):
            self.test_task_id = result.get("task_id")
        
        # Video transcription
        # Video transcription will fail without Firebase - expect 503
        success, result = self.test_post("/api/v1/video-transcription",
            files={"video_file": ("test.mp4", self.create_test_audio_file(), "video/mp4")},
            form_data={"source_language": "en", "priority": "normal"},
            expected_status=503)  # 503 if Firebase not configured
        
        # Text translation
        success, result = self.test_post("/api/v1/text-translation",
            data={"text": "Hello world", "source_language": "en", "target_language": "es", "priority": "normal"},
            expected_status=200)
        
        # Document translation will fail without Firebase - expect 503
        success, result = self.test_post("/api/v1/document-translation",
            files={"document_file": ("test.txt", io.BytesIO(b"Test document content for translation"), "text/plain")},
            form_data={"source_language": "en", "target_language": "es", "priority": "normal"},
            expected_status=503)  # 503 if Firebase not configured
        print()
        
        # Test 3: Miner endpoints (GET)
        print(f"{Colors.YELLOW}=== Miner GET Endpoints ==={Colors.RESET}")
        if self.test_task_id:
            self.test_get(f"/api/v1/miner/summarization/{self.test_task_id}")
            # These will fail if task is not the right type - that's expected
            self.test_get(f"/api/v1/miner/tts/{self.test_task_id}", expected_status=400)
            self.test_get(f"/api/v1/miner/video-transcription/{self.test_task_id}", expected_status=400)
            self.test_get(f"/api/v1/miner/text-translation/{self.test_task_id}", expected_status=400)
            self.test_get(f"/api/v1/miner/document-translation/{self.test_task_id}", expected_status=400)
        else:
            test_id = str(uuid.uuid4())
            # Test with non-existent task - expect 404
            self.test_get(f"/api/v1/miner/summarization/{test_id}", expected_status=404)
            self.test_get(f"/api/v1/miner/tts/{test_id}", expected_status=404)
            self.test_get(f"/api/v1/miner/video-transcription/{test_id}", expected_status=404)
            self.test_get(f"/api/v1/miner/text-translation/{test_id}", expected_status=404)
            self.test_get(f"/api/v1/miner/document-translation/{test_id}", expected_status=404)
        print()
        
        # Test 4: Miner upload endpoints
        print(f"{Colors.YELLOW}=== Miner Upload Endpoints ==={Colors.RESET}")
        # These will fail without Firebase or with non-existent tasks - that's expected
        self.test_post("/api/v1/miner/tts/upload-audio",
            files={"audio_file": ("test.wav", self.create_test_audio_file(), "audio/wav")},
            form_data={"task_id": str(uuid.uuid4()), "miner_uid": str(self.test_miner_uid)},
            expected_status=503)  # 503 if Firebase not configured, 404 if task doesn't exist
        
        # These will fail with non-existent tasks - expect 404
        self.test_post("/api/v1/miner/video-transcription/upload-result",
            data={"task_id": str(uuid.uuid4()), "miner_uid": self.test_miner_uid, "transcript": "Test transcription result", "processing_time": 1.5},
            expected_status=404)
        
        self.test_post("/api/v1/miner/text-translation/upload-result",
            data={"task_id": str(uuid.uuid4()), "miner_uid": self.test_miner_uid, "translated_text": "Test translation result", "source_language": "en", "target_language": "es", "processing_time": 1.2},
            expected_status=404)
        
        self.test_post("/api/v1/miner/document-translation/upload-result",
            data={"task_id": str(uuid.uuid4()), "miner_uid": self.test_miner_uid, "translated_text": "Test document translation result", "source_language": "en", "target_language": "es", "processing_time": 2.0},
            expected_status=404)
        
        self.test_post("/api/v1/miner/response",
            data={"task_id": str(uuid.uuid4()), "miner_uid": self.test_miner_uid, "response_data": json.dumps({"output": "Test response"}), "processing_time": 1.0},
            expected_status=404)
        
        self.test_post("/api/v1/miner/tts/upload",
            files={"audio_file": ("test.wav", self.create_test_audio_file(), "audio/wav")},
            form_data={"task_id": str(uuid.uuid4()), "miner_uid": str(self.test_miner_uid)},
            expected_status=503)  # 503 if Firebase not configured
        print()
        
        # Test 5: Validator endpoints
        print(f"{Colors.YELLOW}=== Validator Endpoints ==={Colors.RESET}")
        self.test_get("/api/v1/validator/tasks")
        # Validator evaluation will fail with non-existent task - expect 404
        self.test_post("/api/v1/validator/evaluation",
            data={"task_id": str(uuid.uuid4()), "validator_uid": 7, "evaluation_data": json.dumps({"miner_uid": self.test_miner_uid, "score": 0.8})},
            expected_status=404)
        print()
        
        # Test 6: Task status endpoints
        print(f"{Colors.YELLOW}=== Task Status Endpoints ==={Colors.RESET}")
        if self.test_task_id:
            self.test_get(f"/api/v1/task/{self.test_task_id}/status")
            self.test_get(f"/api/v1/task/{self.test_task_id}/responses")
        else:
            test_id = str(uuid.uuid4())
            self.test_get(f"/api/v1/task/{test_id}/status")
            self.test_get(f"/api/v1/task/{test_id}/responses")
        
        self.test_get("/api/v1/tasks/completed")
        self.test_get("/api/v1/tasks")
        # Test with non-existent task ID - expect 404
        test_id = str(uuid.uuid4())
        self.test_get(f"/api/v1/tasks/{test_id}", expected_status=404)
        print()
        
        # Test 7: Result endpoints
        print(f"{Colors.YELLOW}=== Result Endpoints ==={Colors.RESET}")
        if self.test_task_id:
            self.test_get(f"/api/v1/transcription/{self.test_task_id}/result")
            self.test_get(f"/api/v1/tts/{self.test_task_id}/result")
        else:
            test_id = str(uuid.uuid4())
            self.test_get(f"/api/v1/transcription/{test_id}/result")
            self.test_get(f"/api/v1/tts/{test_id}/result")
        print()
        
        # Test 8: File endpoints
        print(f"{Colors.YELLOW}=== File Endpoints ==={Colors.RESET}")
        self.test_get("/api/v1/files/stats", timeout=60)  # Increase timeout for stats endpoint
        self.test_get("/api/v1/files/list/audio")
        self.test_get("/api/v1/files/list/video")
        self.test_get("/api/v1/files/list/document")
        
        # Test with a file_id (will likely fail if no files exist)
        test_file_id = str(uuid.uuid4())
        self.test_get(f"/api/v1/files/{test_file_id}")
        self.test_get(f"/api/v1/files/{test_file_id}/download")
        
        # Test TTS audio endpoint
        test_file_id = str(uuid.uuid4())
        self.test_get(f"/api/v1/tts/audio/{test_file_id}")
        print()
        
        # Test 9: Miner management endpoints
        print(f"{Colors.YELLOW}=== Miner Management Endpoints ==={Colors.RESET}")
        self.test_post("/api/v1/miners/register",
            form_data={
                "uid": str(self.test_miner_uid),
                "hotkey": "test_hotkey",
                "stake": "0.0",
                "is_serving": "true",
                "task_type_specialization": "",
                "max_capacity": "5"
            },
            expected_status=200)
        
        self.test_get("/api/v1/miners")
        self.test_get("/api/v1/miners/performance")
        self.test_get(f"/api/v1/miners/{self.test_miner_uid}/tasks")
        self.test_get(f"/api/v1/miners/{self.test_miner_uid}/consensus")
        self.test_get("/api/v1/miners/network-status")
        print()
        
        # Test 10: Validator status endpoints
        print(f"{Colors.YELLOW}=== Validator Status Endpoints ==={Colors.RESET}")
        self.test_post("/api/v1/validators/miner-status",
            form_data={
                "validator_uid": "7",
                "miner_statuses": json.dumps([{
                    "uid": self.test_miner_uid,
                    "hotkey": "test_hotkey",
                    "ip": "127.0.0.1",
                    "port": 8091,
                    "is_serving": True,
                    "stake": 0.0
                }]),
                "epoch": "0"
            },
            expected_status=200)
        
        self.test_get("/api/v1/validators/consensus-stats")
        print()
        
        # Test 11: Metrics endpoints
        print(f"{Colors.YELLOW}=== Metrics Endpoints ==={Colors.RESET}")
        self.test_get("/api/v1/metrics")
        self.test_get("/api/v1/metrics/json")
        self.test_get("/api/v1/duplicate-protection/stats")
        print()
        
        # Print summary
        self.print_summary()
    
    def print_summary(self):
        """Print test summary"""
        print(f"\n{Colors.BLUE}{'='*80}{Colors.RESET}")
        print(f"{Colors.BLUE}Test Summary{Colors.RESET}")
        print(f"{Colors.BLUE}{'='*80}{Colors.RESET}\n")
        
        total = len(self.results)
        passed = len([r for r in self.results if r['status'] == 'PASS'])
        failed = len([r for r in self.results if r['status'] == 'FAIL'])
        skipped = len([r for r in self.results if r['status'] == 'SKIP'])
        
        print(f"Total Endpoints Tested: {total}")
        print(f"{Colors.GREEN}Passed: {passed}{Colors.RESET}")
        print(f"{Colors.RED}Failed: {failed}{Colors.RESET}")
        print(f"{Colors.YELLOW}Skipped: {skipped}{Colors.RESET}")
        print()
        
        if failed > 0:
            print(f"{Colors.RED}Failed Endpoints:{Colors.RESET}")
            for result in self.results:
                if result['status'] == 'FAIL':
                    print(f"  - {result['method']} {result['endpoint']}: {result['details']}")
            print()
        
        if skipped > 0:
            print(f"{Colors.YELLOW}Skipped Endpoints (Server not reachable):{Colors.RESET}")
            for result in self.results:
                if result['status'] == 'SKIP':
                    print(f"  - {result['method']} {result['endpoint']}")
            print()

if __name__ == "__main__":
    import sys
    
    # Allow custom base URL
    base_url = sys.argv[1] if len(sys.argv) > 1 else BASE_URL
    
    tester = EndpointTester(base_url)
    tester.run_all_tests()

