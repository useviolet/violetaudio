"""
Database Adapter for graceful migration from Firestore to PostgreSQL
Supports both databases during transition period
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime
import os
from enum import Enum

class DatabaseType(str, Enum):
    FIRESTORE = "firestore"
    POSTGRESQL = "postgresql"
    DUAL = "dual"  # Write to both during migration

class DatabaseAdapter(ABC):
    """Abstract base class for database adapters"""
    
    @abstractmethod
    def create_task(self, task_data: Dict[str, Any]) -> str:
        """Create a new task"""
        pass
    
    @abstractmethod
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID"""
        pass
    
    @abstractmethod
    def update_task(self, task_id: str, update_data: Dict[str, Any]) -> bool:
        """Update a task"""
        pass
    
    @abstractmethod
    def get_tasks_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get tasks by status"""
        pass
    
    @abstractmethod
    def assign_task_to_miners(self, task_id: str, miner_uids: List[int], 
                             min_count: int = 1, max_count: int = 5) -> bool:
        """Assign task to miners"""
        pass
    
    @abstractmethod
    def get_available_miners(self, task_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get available miners"""
        pass
    
    @abstractmethod
    def update_miner_task_load(self, miner_uid: int, increment: bool = True):
        """Update miner task load"""
        pass
    
    @abstractmethod
    def get_miner_task_count(self, miner_uid: int) -> int:
        """Get miner task count"""
        pass

class DualDatabaseAdapter:
    """
    Dual database adapter that writes to both Firestore and PostgreSQL
    Reads from PostgreSQL (primary) with Firestore fallback
    """
    
    def __init__(self, firestore_adapter, postgresql_adapter):
        self.firestore = firestore_adapter
        self.postgresql = postgresql_adapter
        self.read_primary = "postgresql"  # Start reading from PostgreSQL
        self.write_both = True  # Write to both during migration
    
    def create_task(self, task_data: Dict[str, Any]) -> str:
        """Create task in both databases"""
        task_id = None
        
        # Try PostgreSQL first
        try:
            task_id = self.postgresql.create_task(task_data)
        except Exception as e:
            print(f"⚠️ PostgreSQL create_task failed: {e}")
        
        # Also write to Firestore if enabled
        if self.write_both:
            try:
                if task_id:
                    # Use same task_id for consistency
                    task_data['task_id'] = task_id
                firestore_task_id = self.firestore.create_task(task_data)
                if not task_id:
                    task_id = firestore_task_id
            except Exception as e:
                print(f"⚠️ Firestore create_task failed: {e}")
        
        return task_id
    
    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get task from primary (PostgreSQL), fallback to Firestore"""
        # Try PostgreSQL first
        if self.read_primary == "postgresql":
            try:
                task = self.postgresql.get_task(task_id)
                if task:
                    return task
            except Exception as e:
                print(f"⚠️ PostgreSQL get_task failed: {e}, falling back to Firestore")
        
        # Fallback to Firestore
        try:
            return self.firestore.get_task(task_id)
        except Exception as e:
            print(f"❌ Both databases failed for get_task: {e}")
            return None
    
    def update_task(self, task_id: str, update_data: Dict[str, Any]) -> bool:
        """Update task in both databases"""
        success = False
        
        # Try PostgreSQL first
        try:
            success = self.postgresql.update_task(task_id, update_data)
        except Exception as e:
            print(f"⚠️ PostgreSQL update_task failed: {e}")
        
        # Also update Firestore if enabled
        if self.write_both:
            try:
                firestore_success = self.firestore.update_task(task_id, update_data)
                if not success:
                    success = firestore_success
            except Exception as e:
                print(f"⚠️ Firestore update_task failed: {e}")
        
        return success
    
    def get_tasks_by_status(self, status: str, limit: int = 100) -> List[Dict[str, Any]]:
        """Get tasks from primary (PostgreSQL), fallback to Firestore"""
        if self.read_primary == "postgresql":
            try:
                tasks = self.postgresql.get_tasks_by_status(status, limit)
                if tasks:
                    return tasks
            except Exception as e:
                print(f"⚠️ PostgreSQL get_tasks_by_status failed: {e}, falling back to Firestore")
        
        # Fallback to Firestore
        try:
            return self.firestore.get_tasks_by_status(status, limit)
        except Exception as e:
            print(f"❌ Both databases failed for get_tasks_by_status: {e}")
            return []
    
    def assign_task_to_miners(self, task_id: str, miner_uids: List[int], 
                             min_count: int = 1, max_count: int = 5) -> bool:
        """Assign task to miners in both databases"""
        success = False
        
        try:
            success = self.postgresql.assign_task_to_miners(task_id, miner_uids, min_count, max_count)
        except Exception as e:
            print(f"⚠️ PostgreSQL assign_task_to_miners failed: {e}")
        
        if self.write_both:
            try:
                firestore_success = self.firestore.assign_task_to_miners(task_id, miner_uids, min_count, max_count)
                if not success:
                    success = firestore_success
            except Exception as e:
                print(f"⚠️ Firestore assign_task_to_miners failed: {e}")
        
        return success
    
    def get_available_miners(self, task_type: str = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get available miners from primary (PostgreSQL), fallback to Firestore"""
        if self.read_primary == "postgresql":
            try:
                miners = self.postgresql.get_available_miners(task_type, limit)
                if miners:
                    return miners
            except Exception as e:
                print(f"⚠️ PostgreSQL get_available_miners failed: {e}, falling back to Firestore")
        
        try:
            return self.firestore.get_available_miners(task_type, limit)
        except Exception as e:
            print(f"❌ Both databases failed for get_available_miners: {e}")
            return []
    
    def update_miner_task_load(self, miner_uid: int, increment: bool = True):
        """Update miner task load in both databases"""
        try:
            self.postgresql.update_miner_task_load(miner_uid, increment)
        except Exception as e:
            print(f"⚠️ PostgreSQL update_miner_task_load failed: {e}")
        
        if self.write_both:
            try:
                self.firestore.update_miner_task_load(miner_uid, increment)
            except Exception as e:
                print(f"⚠️ Firestore update_miner_task_load failed: {e}")
    
    def get_miner_task_count(self, miner_uid: int) -> int:
        """Get miner task count from primary (PostgreSQL), fallback to Firestore"""
        if self.read_primary == "postgresql":
            try:
                count = self.postgresql.get_miner_task_count(miner_uid)
                return count
            except Exception as e:
                print(f"⚠️ PostgreSQL get_miner_task_count failed: {e}, falling back to Firestore")
        
        try:
            return self.firestore.get_miner_task_count(miner_uid)
        except Exception as e:
            print(f"❌ Both databases failed for get_miner_task_count: {e}")
            return 0
    
    def switch_read_primary(self, primary: str):
        """Switch read primary between 'postgresql' and 'firestore'"""
        if primary in ["postgresql", "firestore"]:
            self.read_primary = primary
            print(f"✅ Switched read primary to: {primary}")
        else:
            raise ValueError(f"Invalid primary: {primary}. Must be 'postgresql' or 'firestore'")
    
    def disable_dual_write(self):
        """Disable dual write (stop writing to Firestore)"""
        self.write_both = False
        print("✅ Dual write disabled - now writing only to PostgreSQL")
    
    def enable_dual_write(self):
        """Enable dual write (write to both databases)"""
        self.write_both = True
        print("✅ Dual write enabled - writing to both databases")


