"""
Database module for Enhanced Proxy Server
PostgreSQL-only - no Firestore dependencies
"""

# Import from postgresql_schema instead of schema (which has Firebase)
from .postgresql_schema import (
    TaskStatusEnum as TaskStatus,
    TaskPriorityEnum as TaskPriority,
    TaskTypeEnum as TaskType
)

# DatabaseManager is now PostgreSQLAdapter
from .postgresql_adapter import PostgreSQLAdapter as DatabaseManager

__all__ = ['DatabaseManager', 'TaskStatus', 'TaskPriority', 'TaskType']
