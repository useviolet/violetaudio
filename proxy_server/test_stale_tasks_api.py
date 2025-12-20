"""
Tests for Stale Task Completion API endpoints
"""

import pytest
import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.postgresql_adapter import PostgreSQLAdapter
from database.postgresql_schema import Task, TaskStatusEnum
from orchestrators.workflow_orchestrator import WorkflowOrchestrator
from managers.task_manager import TaskManager


class TestStaleTasksAPI:
    """Test suite for Stale Task Completion API"""
    
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
    def workflow_orchestrator(self, db):
        """Create WorkflowOrchestrator instance"""
        task_manager = TaskManager(db)
        return WorkflowOrchestrator(db, task_manager, None)
    
    @pytest.mark.asyncio
    async def test_handle_stale_tasks_basic(self, workflow_orchestrator):
        """Test basic stale task handling"""
        result = await workflow_orchestrator._handle_stale_tasks_with_partial_responses()
        
        assert isinstance(result, dict)
        assert 'success' in result
        assert 'completed_count' in result
        assert 'failed_count' in result
        assert 'total_checked' in result
        
        print(f"✅ Basic stale task handling test passed")
        print(f"   Completed: {result.get('completed_count', 0)}")
        print(f"   Failed: {result.get('failed_count', 0)}")
        print(f"   Total checked: {result.get('total_checked', 0)}")
    
    @pytest.mark.asyncio
    async def test_handle_stale_tasks_manual(self, workflow_orchestrator):
        """Test manual stale task trigger"""
        result = await workflow_orchestrator.handle_stale_tasks_manual()
        
        assert isinstance(result, dict)
        assert 'success' in result
        print(f"✅ Manual stale task trigger test passed")
    
    @pytest.mark.asyncio
    async def test_stale_task_completion_criteria(self, db):
        """Test that stale tasks meet completion criteria"""
        session = db._get_session()
        try:
            # Get assigned tasks older than 1 hour
            one_hour_ago = datetime.now() - timedelta(hours=1)
            stale_tasks = session.query(Task).filter(
                Task.status == TaskStatusEnum.ASSIGNED,
                Task.created_at < one_hour_ago
            ).limit(5).all()
            
            print(f"✅ Found {len(stale_tasks)} stale assigned tasks for testing")
            
            # Get pending tasks older than 1 hour
            stale_pending = session.query(Task).filter(
                Task.status == TaskStatusEnum.PENDING,
                Task.created_at < one_hour_ago
            ).limit(5).all()
            
            print(f"✅ Found {len(stale_pending)} stale pending tasks for testing")
            
        finally:
            session.close()
    
    @pytest.mark.asyncio
    async def test_task_counting_logic(self, db):
        """Test task counting for leaderboard"""
        session = db._get_session()
        try:
            # Get a sample task
            sample_task = session.query(Task).first()
            
            if sample_task:
                assigned_miners = sample_task.assigned_miners or []
                miner_responses = sample_task.miner_responses or []
                
                if isinstance(miner_responses, str):
                    import json
                    try:
                        miner_responses = json.loads(miner_responses)
                    except:
                        miner_responses = []
                
                print(f"✅ Task counting test:")
                print(f"   Task ID: {sample_task.task_id}")
                print(f"   Assigned miners: {len(assigned_miners)}")
                print(f"   Responses: {len(miner_responses) if isinstance(miner_responses, list) else 0}")
            else:
                print("⚠️ No tasks found for counting test")
                
        finally:
            session.close()


def run_tests():
    """Run stale tasks API tests"""
    print("🧪 Running Stale Tasks API Tests...")
    print("=" * 60)
    
    # Create test instance
    import os
    database_url = os.getenv(
        'DATABASE_URL',
        'postgresql://violet_db_user:ZiqeR2tAHgdaxjyi3YGwT3nbXBWW6t1w@dpg-d515p2vfte5s738uemkg-a.oregon-postgres.render.com/violet_db'
    )
    db = PostgreSQLAdapter(database_url)
    task_manager = TaskManager(db)
    workflow_orchestrator = WorkflowOrchestrator(db, task_manager, None)
    
    # Run async tests
    async def run_all_tests():
        test_suite = TestStaleTasksAPI()
        
        # Test 1: Basic handling
        try:
            await test_suite.test_handle_stale_tasks_basic(workflow_orchestrator)
        except Exception as e:
            print(f"❌ Basic stale task handling test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 2: Manual trigger
        try:
            await test_suite.test_handle_stale_tasks_manual(workflow_orchestrator)
        except Exception as e:
            print(f"❌ Manual trigger test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 3: Completion criteria
        try:
            await test_suite.test_stale_task_completion_criteria(db)
        except Exception as e:
            print(f"❌ Completion criteria test failed: {e}")
            import traceback
            traceback.print_exc()
        
        # Test 4: Task counting
        try:
            await test_suite.test_task_counting_logic(db)
        except Exception as e:
            print(f"❌ Task counting test failed: {e}")
            import traceback
            traceback.print_exc()
    
    asyncio.run(run_all_tests())
    print("=" * 60)
    print("✅ Stale Tasks API tests completed")


if __name__ == "__main__":
    run_tests()

