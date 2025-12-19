"""
Tests for Leaderboard API endpoints
"""

import pytest
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi.testclient import TestClient
from database.postgresql_adapter import PostgreSQLAdapter
from database.postgresql_schema import MinerMetrics, Task, MinerStatus, TaskStatusEnum
from api.leaderboard_api import LeaderboardAPI


class TestLeaderboardAPI:
    """Test suite for Leaderboard API"""
    
    @pytest.fixture
    def db(self):
        """Create test database adapter"""
        import os
        database_url = os.getenv(
            'DATABASE_URL',
            'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
        )
        return PostgreSQLAdapter(database_url)
    
    @pytest.fixture
    def leaderboard_api(self, db):
        """Create LeaderboardAPI instance"""
        return LeaderboardAPI(db)
    
    @pytest.mark.asyncio
    async def test_get_leaderboard_basic(self, leaderboard_api):
        """Test basic leaderboard retrieval"""
        leaderboard = await leaderboard_api.get_leaderboard(limit=10)
        
        assert isinstance(leaderboard, list)
        # Should return list even if empty
        print(f"✅ Basic leaderboard test passed: {len(leaderboard)} miners found")
    
    @pytest.mark.asyncio
    async def test_get_leaderboard_sorting(self, leaderboard_api):
        """Test leaderboard with different sorting options"""
        # Test sorting by overall_score
        leaderboard = await leaderboard_api.get_leaderboard(
            limit=10,
            sort_by="overall_score",
            order="desc"
        )
        assert isinstance(leaderboard, list)
        print(f"✅ Sorting by overall_score: {len(leaderboard)} miners")
        
        # Test sorting by invocation_count
        leaderboard = await leaderboard_api.get_leaderboard(
            limit=10,
            sort_by="invocation_count",
            order="desc"
        )
        assert isinstance(leaderboard, list)
        print(f"✅ Sorting by invocation_count: {len(leaderboard)} miners")
        
        # Test sorting by total_tasks_completed
        leaderboard = await leaderboard_api.get_leaderboard(
            limit=10,
            sort_by="total_tasks_completed",
            order="desc"
        )
        assert isinstance(leaderboard, list)
        print(f"✅ Sorting by total_tasks_completed: {len(leaderboard)} miners")
    
    @pytest.mark.asyncio
    async def test_leaderboard_entry_structure(self, leaderboard_api):
        """Test that leaderboard entries have all required fields"""
        leaderboard = await leaderboard_api.get_leaderboard(limit=5)
        
        if leaderboard:
            entry = leaderboard[0]
            required_fields = [
                'rank', 'uid', 'hotkey', 'miner_identity',
                'overall_score', 'uptime_score', 'invocation_count',
                'diversity_count', 'bounty_count',
                'total_tasks_assigned', 'total_tasks_completed',
                'completion_rate', 'is_serving'
            ]
            
            for field in required_fields:
                assert field in entry, f"Missing field: {field}"
            
            print(f"✅ Leaderboard entry structure test passed")
            print(f"   Sample entry keys: {list(entry.keys())[:10]}")
        else:
            print("⚠️ No miners in leaderboard to test structure")
    
    @pytest.mark.asyncio
    async def test_task_counts_calculation(self, leaderboard_api):
        """Test task counting logic"""
        session = leaderboard_api.db._get_session()
        try:
            task_counts = await leaderboard_api._get_task_counts_per_miner(session)
            assert isinstance(task_counts, dict)
            print(f"✅ Task counts calculation test passed: {len(task_counts)} miners with tasks")
        finally:
            session.close()
    
    @pytest.mark.asyncio
    async def test_miner_status_info(self, leaderboard_api):
        """Test miner status info retrieval"""
        session = leaderboard_api.db._get_session()
        try:
            status_info = await leaderboard_api._get_miner_status_info(session)
            assert isinstance(status_info, dict)
            print(f"✅ Miner status info test passed: {len(status_info)} miners")
        finally:
            session.close()
    
    @pytest.mark.asyncio
    async def test_overall_score_calculation(self, leaderboard_api):
        """Test overall score calculation"""
        leaderboard = await leaderboard_api.get_leaderboard(limit=10)
        
        for entry in leaderboard:
            # Verify overall_score is calculated correctly
            expected_score = (
                entry['uptime_score'] * 0.55 +
                entry['invocation_score'] * 0.25 +
                entry['diversity_score'] * 0.15 +
                entry['bounty_score'] * 0.05
            )
            
            # Allow small floating point differences
            assert abs(entry['overall_score'] - expected_score) < 0.0001, \
                f"Overall score mismatch for miner {entry['uid']}"
        
        print(f"✅ Overall score calculation test passed")


def run_tests():
    """Run leaderboard API tests"""
    print("🧪 Running Leaderboard API Tests...")
    print("=" * 60)
    
    # Create test instance
    import os
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    db = PostgreSQLAdapter(database_url)
    leaderboard_api = LeaderboardAPI(db)
    
    # Run async tests
    async def run_all_tests():
        test_suite = TestLeaderboardAPI()
        
        # Test 1: Basic retrieval
        try:
            await test_suite.test_get_leaderboard_basic(leaderboard_api)
        except Exception as e:
            print(f"❌ Basic leaderboard test failed: {e}")
        
        # Test 2: Sorting
        try:
            await test_suite.test_get_leaderboard_sorting(leaderboard_api)
        except Exception as e:
            print(f"❌ Sorting test failed: {e}")
        
        # Test 3: Entry structure
        try:
            await test_suite.test_leaderboard_entry_structure(leaderboard_api)
        except Exception as e:
            print(f"❌ Entry structure test failed: {e}")
        
        # Test 4: Task counts
        try:
            await test_suite.test_task_counts_calculation(leaderboard_api)
        except Exception as e:
            print(f"❌ Task counts test failed: {e}")
        
        # Test 5: Status info
        try:
            await test_suite.test_miner_status_info(leaderboard_api)
        except Exception as e:
            print(f"❌ Status info test failed: {e}")
        
        # Test 6: Overall score
        try:
            await test_suite.test_overall_score_calculation(leaderboard_api)
        except Exception as e:
            print(f"❌ Overall score test failed: {e}")
    
    asyncio.run(run_all_tests())
    print("=" * 60)
    print("✅ Leaderboard API tests completed")


if __name__ == "__main__":
    run_tests()

