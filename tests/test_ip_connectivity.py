#!/usr/bin/env python3
"""
Test script to verify connectivity to IP address 154.161.97.168
Tests TCP connections on common ports and HTTP/HTTPS if applicable
"""

import sys
import os
import asyncio
import socket
import httpx
from typing import List, Tuple

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

TARGET_IP = "154.161.97.168"
COMMON_PORTS = [80, 443, 22, 8080, 8000, 8443, 3000, 5000, 8092]
CONNECTION_TIMEOUT = 5.0


def test_tcp_connection(ip: str, port: int, timeout: float = CONNECTION_TIMEOUT) -> Tuple[bool, str]:
    """
    Test TCP connection to a specific IP and port
    
    Returns:
        (success: bool, message: str)
    """
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        
        if result == 0:
            return True, f"✅ Port {port} is OPEN"
        else:
            return False, f"❌ Port {port} is CLOSED or FILTERED"
    except socket.gaierror as e:
        return False, f"❌ DNS resolution failed: {e}"
    except socket.timeout:
        return False, f"⏱️  Port {port} connection TIMEOUT"
    except Exception as e:
        return False, f"❌ Error connecting to port {port}: {e}"


async def test_http_connection(ip: str, port: int, use_https: bool = False) -> Tuple[bool, str]:
    """
    Test HTTP/HTTPS connection to a specific IP and port
    
    Returns:
        (success: bool, message: str)
    """
    protocol = "https" if use_https else "http"
    url = f"{protocol}://{ip}:{port}"
    
    try:
        async with httpx.AsyncClient(timeout=CONNECTION_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(url)
            return True, f"✅ {protocol.upper()} connection successful - Status: {response.status_code}"
    except httpx.ConnectError:
        return False, f"❌ {protocol.upper()} connection failed - Cannot connect"
    except httpx.TimeoutException:
        return False, f"⏱️  {protocol.upper()} connection TIMEOUT"
    except httpx.HTTPError as e:
        return False, f"❌ {protocol.upper()} error: {e}"
    except Exception as e:
        return False, f"❌ Unexpected error with {protocol.upper()}: {e}"


async def test_ip_connectivity():
    """Main test function to check connectivity to the target IP"""
    print("=" * 80)
    print(f"Testing Connectivity to IP: {TARGET_IP}")
    print("=" * 80)
    
    # Test 1: Basic TCP connection tests on common ports
    print("\n📡 Test 1: TCP Connection Tests on Common Ports")
    print("-" * 80)
    
    open_ports = []
    for port in COMMON_PORTS:
        success, message = test_tcp_connection(TARGET_IP, port)
        print(f"   {message}")
        if success:
            open_ports.append(port)
    
    if not open_ports:
        print("\n   ⚠️  No open ports found on common ports")
    else:
        print(f"\n   ✅ Found {len(open_ports)} open port(s): {open_ports}")
    
    # Test 2: HTTP/HTTPS tests on common web ports
    print("\n🌐 Test 2: HTTP/HTTPS Connection Tests")
    print("-" * 80)
    
    web_ports = [80, 443, 8080, 8000, 8443, 3000, 5000, 8092]
    for port in web_ports:
        # Test HTTP
        if port != 443 and port != 8443:  # Skip HTTP for HTTPS-only ports
            success, message = await test_http_connection(TARGET_IP, port, use_https=False)
            print(f"   HTTP on port {port}: {message}")
        
        # Test HTTPS
        success, message = await test_http_connection(TARGET_IP, port, use_https=True)
        print(f"   HTTPS on port {port}: {message}")
    
    # Test 3: DNS resolution test
    print("\n🔍 Test 3: DNS Resolution Test")
    print("-" * 80)
    try:
        hostname = socket.gethostbyaddr(TARGET_IP)[0]
        print(f"   ✅ Reverse DNS lookup successful: {hostname}")
    except socket.herror:
        print(f"   ℹ️  No reverse DNS record found (this is normal)")
    except Exception as e:
        print(f"   ⚠️  DNS lookup error: {e}")
    
    # Test 4: Ping-like test (using socket)
    print("\n🏓 Test 4: Basic Reachability Test")
    print("-" * 80)
    try:
        # Try to resolve the IP (though it's already an IP)
        socket.inet_aton(TARGET_IP)
        print(f"   ✅ IP address format is valid: {TARGET_IP}")
        
        # Try a quick connection to a common port to test basic reachability
        test_port = 8092
        success, message = test_tcp_connection(TARGET_IP, test_port, timeout=2.0)
        if success:
            print(f"   ✅ IP is reachable (port {test_port} is open)")
        else:
            # Try another port
            test_port = 80
            success, message = test_tcp_connection(TARGET_IP, test_port, timeout=2.0)
            if success:
                print(f"   ✅ IP is reachable (port {test_port} is open)")
            else:
                # Try HTTPS port
                test_port = 443
                success, message = test_tcp_connection(TARGET_IP, test_port, timeout=2.0)
                if success:
                    print(f"   ✅ IP is reachable (port {test_port} is open)")
                else:
                    print(f"   ⚠️  IP may be reachable but no common ports are open")
                    print(f"   (This doesn't necessarily mean the IP is unreachable)")
    except socket.error as e:
        print(f"   ❌ Invalid IP address format: {e}")
    
    # Summary
    print("\n" + "=" * 80)
    print("📊 Summary")
    print("=" * 80)
    if open_ports:
        print(f"✅ IP {TARGET_IP} is reachable")
        print(f"   Open ports found: {open_ports}")
    else:
        print(f"⚠️  No open ports detected on common ports")
        print(f"   The IP may still be reachable but not listening on tested ports")
        print(f"   Or it may be behind a firewall")
    
    print("=" * 80)
    
    return len(open_ports) > 0


if __name__ == "__main__":
    result = asyncio.run(test_ip_connectivity())
    sys.exit(0 if result else 1)

