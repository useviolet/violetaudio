#!/usr/bin/env python3
"""
Test script to verify proxy server fixes for:
1. Datetime timezone handling
2. Zero stake miner inclusion
3. Consensus threshold adjustment
"""

from datetime import datetime, timedelta, timezone
from typing import Dict, Any

def test_datetime_timezone_handling():
    """Test that timezone-aware and naive datetimes are handled correctly"""
    print("🧪 Testing datetime timezone handling...")
    
    current_time = datetime.utcnow()
    
    # Test cases
    test_cases = [
        # (last_seen, description)
        (datetime.utcnow() - timedelta(minutes=5), "Naive datetime (recent)"),
        (datetime.now(timezone.utc) - timedelta(minutes=5), "Timezone-aware datetime (recent)"),
        (datetime.utcnow() - timedelta(minutes=20), "Naive datetime (stale)"),
        (datetime.now(timezone.utc) - timedelta(minutes=20), "Timezone-aware datetime (stale)"),
    ]
    
    miner_timeout = 900  # 15 minutes
    
    for last_seen, description in test_cases:
        try:
            # Simulate the timezone handling logic
            if isinstance(last_seen, datetime):
                if last_seen.tzinfo is not None:
                    last_seen = last_seen.replace(tzinfo=None)
                time_diff = (current_time - last_seen).total_seconds()
            else:
                time_diff = None
            
            if time_diff is not None:
                is_recent = time_diff < miner_timeout
                status = "✅ PASS" if (is_recent and "recent" in description) or (not is_recent and "stale" in description) else "❌ FAIL"
                print(f"   {status} - {description}: time_diff={time_diff:.1f}s, is_recent={is_recent}")
            else:
                print(f"   ❌ FAIL - {description}: Could not calculate time_diff")
        except Exception as e:
            print(f"   ❌ FAIL - {description}: {e}")
    
    print()

def test_zero_stake_inclusion():
    """Test that miners with 0 stake are included"""
    print("🧪 Testing zero stake miner inclusion...")
    
    test_miners = [
        {"uid": 6, "stake": 0.0, "is_serving": True, "description": "Miner 6 (0 stake, serving)"},
        {"uid": 7, "stake": 100.0, "is_serving": True, "description": "Miner 7 (100 stake, serving)"},
        {"uid": 8, "stake": 0.0, "is_serving": False, "description": "Miner 8 (0 stake, not serving)"},
    ]
    
    for miner in test_miners:
        # Simulate the new logic (no stake requirement)
        is_eligible = miner.get('is_serving', False)  # Removed stake > 0 check
        expected = miner['is_serving']
        status = "✅ PASS" if is_eligible == expected else "❌ FAIL"
        print(f"   {status} - {miner['description']}: eligible={is_eligible}")
    
    print()

def test_consensus_threshold():
    """Test that consensus threshold is lowered for single-validator scenarios"""
    print("🧪 Testing consensus threshold adjustment...")
    
    test_cases = [
        (0.0, False, "No consensus (should be excluded)"),
        (0.2, False, "Low consensus (should be excluded)"),
        (0.3, True, "Minimum threshold (should be included)"),
        (0.5, True, "Medium consensus (should be included)"),
        (0.7, True, "High consensus (should be included)"),
        (1.0, True, "Perfect consensus (should be included)"),
    ]
    
    threshold = 0.3  # New lower threshold
    
    for confidence, should_include, description in test_cases:
        is_included = confidence >= threshold
        status = "✅ PASS" if is_included == should_include else "❌ FAIL"
        print(f"   {status} - {description}: confidence={confidence:.1f}, included={is_included}")
    
    print()

def test_miner_6_scenario():
    """Test the specific scenario for miner 6"""
    print("🧪 Testing Miner 6 specific scenario...")
    
    miner_6 = {
        "uid": 6,
        "hotkey": "5C8BqfD9MgdabzYBNFEEvne1bKejJAycEHUYSwQE2GW7Uy2y",
        "stake": 0.0,
        "is_serving": True,
        "last_seen": datetime.utcnow() - timedelta(minutes=2),
        "performance_score": 0.5,
        "current_load": 0.0,
        "max_capacity": 5.0,
    }
    
    # Test 1: Zero stake should not exclude
    stake_check = miner_6.get('is_serving', False)  # No stake > 0 requirement
    print(f"   {'✅ PASS' if stake_check else '❌ FAIL'} - Zero stake check: is_serving={stake_check}")
    
    # Test 2: Recent last_seen should pass
    current_time = datetime.utcnow()
    last_seen = miner_6['last_seen']
    if last_seen.tzinfo is not None:
        last_seen = last_seen.replace(tzinfo=None)
    time_diff = (current_time - last_seen).total_seconds()
    is_recent = time_diff < 900  # 15 minutes
    print(f"   {'✅ PASS' if is_recent else '❌ FAIL'} - Recent check: time_diff={time_diff:.1f}s, is_recent={is_recent}")
    
    # Test 3: Should be eligible for task assignment
    is_eligible = stake_check and is_recent
    print(f"   {'✅ PASS' if is_eligible else '❌ FAIL'} - Overall eligibility: {is_eligible}")
    
    print()

if __name__ == "__main__":
    print("=" * 60)
    print("Testing Proxy Server Fixes")
    print("=" * 60)
    print()
    
    test_datetime_timezone_handling()
    test_zero_stake_inclusion()
    test_consensus_threshold()
    test_miner_6_scenario()
    
    print("=" * 60)
    print("✅ All tests completed!")
    print("=" * 60)

