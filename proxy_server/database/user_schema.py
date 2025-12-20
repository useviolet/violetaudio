"""
User Authentication Schema
Handles user registration, login, and API key management with role-based access
"""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import uuid
import hashlib
import secrets
from database.postgresql_adapter import PostgreSQLAdapter

class UserRole(str, Enum):
    """User roles"""
    CLIENT = "client"
    MINER = "miner"
    VALIDATOR = "validator"
    ADMIN = "admin"

@dataclass
class User:
    """User model for authentication"""
    user_id: str
    email: str
    role: str  # "client", "miner", or "validator"
    hotkey: Optional[str] = None
    coldkey_address: Optional[str] = None
    uid: Optional[int] = None
    network: Optional[str] = None  # "test" or "finney"
    netuid: Optional[int] = None  # 292 for test, 49 for finney
    api_key: Optional[str] = None
    api_key_created_at: Optional[datetime] = None
    created_at: datetime = None
    updated_at: datetime = None
    is_active: bool = True
    last_login: Optional[datetime] = None

class UserOperations:
    """Database operations for user management"""
    
    @staticmethod
    def _is_postgresql(db) -> bool:
        """Check if db is PostgreSQL adapter"""
        return isinstance(db, PostgreSQLAdapter)
    
    @staticmethod
    def create_user(db, user_data: Dict[str, Any]) -> str:
        """Create a new user with role"""
        try:
            user_id = str(uuid.uuid4())
            now = datetime.utcnow()
            role = user_data.get('role', 'client')
            
            # Validate role against enum
            valid_roles = {r.value for r in UserRole}
            if role not in valid_roles:
                raise ValueError(f"Invalid role: {role}. Must be one of: {', '.join(valid_roles)}")
            
            # Sanitize email
            email = str(user_data.get('email', '')).lower().strip()
            if not email or '@' not in email:
                raise ValueError("Invalid email address")
            
            # Generate secure API key
            api_key = secrets.token_urlsafe(32)
            
            if UserOperations._is_postgresql(db):
                # PostgreSQL: Create user
                from database.postgresql_schema import User, UserRoleEnum
                session = db._get_session()
                try:
                    user = User(
                        user_id=user_id,
                        email=email,
                        role=UserRoleEnum(role),
                        api_key=api_key,
                        api_key_created_at=now,
                        created_at=now,
                        updated_at=now,
                        is_active=True,
                        hotkey=user_data.get('hotkey'),
                        coldkey_address=user_data.get('coldkey_address'),
                        uid=user_data.get('uid'),
                        network=user_data.get('network'),
                        netuid=user_data.get('netuid')
                    )
                    session.add(user)
                    session.commit()
                    return user_id
                finally:
                    session.close()
            else:
                # Firestore (legacy)
                # Firebase removed - PostgreSQL only
                user_doc = {
                    'user_id': user_id,
                    'email': email,
                    'role': role,
                    'api_key': api_key,
                    'api_key_created_at': now,
                    'created_at': now,
                    'updated_at': now,
                    'is_active': True,
                    'last_login': None
                }
                
                # Add miner/validator specific fields if applicable
                if role in ['miner', 'validator']:
                    user_doc.update({
                        'hotkey': user_data.get('hotkey'),
                        'coldkey_address': user_data.get('coldkey_address'),
                        'uid': user_data.get('uid'),
                        'network': user_data.get('network'),
                        'netuid': user_data.get('netuid')
                    })
                
                # Store in users collection
                db.collection('users').document(user_id).set(user_doc)
                
                # Also create index by email for quick lookup
                db.collection('user_emails').document(email).set({
                    'user_id': user_id,
                    'created_at': now
                })
                
                # Create API key index for quick lookup
                db.collection('api_keys').document(api_key).set({
                    'user_id': user_id,
                    'role': role,
                    'created_at': now
                })
                
                return user_id
            
        except Exception as e:
            raise Exception(f"Failed to create user: {str(e)}")
    
    @staticmethod
    def get_user_by_email(db, email: str) -> Optional[Dict[str, Any]]:
        """Get user by email"""
        try:
            if UserOperations._is_postgresql(db):
                # PostgreSQL: Query by email
                from database.postgresql_schema import User
                session = db._get_session()
                try:
                    user = session.query(User).filter(User.email == email.lower().strip()).first()
                    if user and user.is_active:
                        return {
                            'user_id': user.user_id,
                            'email': user.email,
                            'role': user.role.value if hasattr(user.role, 'value') else user.role,
                            'api_key': user.api_key,
                            'api_key_created_at': user.api_key_created_at,
                            'created_at': user.created_at,
                            'updated_at': user.updated_at,
                            'is_active': user.is_active,
                            'last_login': user.last_login,
                            'hotkey': user.hotkey,
                            'coldkey_address': user.coldkey_address,
                            'uid': user.uid,
                            'network': user.network,
                            'netuid': user.netuid
                        }
                    return None
                finally:
                    session.close()
            else:
                # Firestore (legacy)
                # Firebase removed - PostgreSQL only
                email_doc = db.collection('user_emails').document(email.lower().strip()).get()
                if not email_doc.exists:
                    return None
                
                user_id = email_doc.to_dict().get('user_id')
                user_doc = db.collection('users').document(user_id).get()
                
                if not user_doc.exists:
                    return None
                
                return user_doc.to_dict()
            
        except Exception as e:
            raise Exception(f"Failed to get user: {str(e)}")
    
    @staticmethod
    def get_user_by_api_key(db, api_key: str) -> Optional[Dict[str, Any]]:
        """Get user by API key"""
        try:
            if UserOperations._is_postgresql(db):
                # PostgreSQL: Query by API key
                from database.postgresql_schema import User
                session = db._get_session()
                try:
                    user = session.query(User).filter(User.api_key == api_key).first()
                    if user and user.is_active:
                        return {
                            'user_id': user.user_id,
                            'email': user.email,
                            'role': user.role.value if hasattr(user.role, 'value') else user.role,
                            'api_key': user.api_key,
                            'api_key_created_at': user.api_key_created_at,
                            'created_at': user.created_at,
                            'updated_at': user.updated_at,
                            'is_active': user.is_active,
                            'last_login': user.last_login,
                            'hotkey': user.hotkey,
                            'coldkey_address': user.coldkey_address,
                            'uid': user.uid,
                            'network': user.network,
                            'netuid': user.netuid
                        }
                    return None
                finally:
                    session.close()
            else:
                # Firestore (legacy)
                # Firebase removed - PostgreSQL only
                # First check API key index
                api_key_doc = db.collection('api_keys').document(api_key).get()
                if not api_key_doc.exists:
                    return None
                
                api_key_data = api_key_doc.to_dict()
                user_id = api_key_data.get('user_id')
                
                # Get user document
                user_doc = db.collection('users').document(user_id).get()
                if not user_doc.exists:
                    return None
                
                user_data = user_doc.to_dict()
                if not user_data.get('is_active', True):
                    return None
                
                return user_data
            
        except Exception as e:
            raise Exception(f"Failed to get user by API key: {str(e)}")
    
    @staticmethod
    def get_user_by_credentials(
        db, 
        hotkey: str, 
        coldkey_address: str, 
        uid: int, 
        network: str
    ) -> Optional[Dict[str, Any]]:
        """Get user by miner/validator credentials"""
        try:
            if UserOperations._is_postgresql(db):
                # PostgreSQL: Query by credentials
                from database.postgresql_schema import User
                from sqlalchemy import and_
                session = db._get_session()
                try:
                    user = session.query(User).filter(
                        and_(
                            User.hotkey == hotkey,
                            User.coldkey_address == coldkey_address,
                            User.uid == uid,
                            User.network == network,
                            User.is_active == True
                        )
                    ).first()
                    if user:
                        return {
                            'user_id': user.user_id,
                            'email': user.email,
                            'role': user.role.value if hasattr(user.role, 'value') else user.role,
                            'api_key': user.api_key,
                            'hotkey': user.hotkey,
                            'coldkey_address': user.coldkey_address,
                            'uid': user.uid,
                            'network': user.network,
                            'netuid': user.netuid
                        }
                    return None
                finally:
                    session.close()
            else:
                # Firestore (legacy)
                # Firebase removed - PostgreSQL only
                users_ref = db.collection('users')
                query = users_ref.where('hotkey', '==', hotkey)\
                               .where('coldkey_address', '==', coldkey_address)\
                               .where('uid', '==', uid)\
                               .where('network', '==', network)\
                               .where('is_active', '==', True)\
                               .limit(1)
                docs = query.stream()
                
                for doc in docs:
                    return doc.to_dict()
                
                return None
            
        except Exception as e:
            raise Exception(f"Failed to get user by credentials: {str(e)}")
    
    @staticmethod
    def update_last_login(db, user_id: str):
        """Update user's last login timestamp"""
        try:
            if UserOperations._is_postgresql(db):
                # PostgreSQL: Update last login
                from database.postgresql_schema import User
                session = db._get_session()
                try:
                    user = session.query(User).filter(User.user_id == user_id).first()
                    if user:
                        user.last_login = datetime.utcnow()
                        user.updated_at = datetime.utcnow()
                        session.commit()
                finally:
                    session.close()
            else:
                # Firestore (legacy)
                # Firebase removed - PostgreSQL only
                db.collection('users').document(user_id).update({
                    'last_login': datetime.utcnow(),
                    'updated_at': datetime.utcnow()
                })
        except Exception as e:
            raise Exception(f"Failed to update last login: {str(e)}")
    
    @staticmethod
    def generate_new_api_key(db, user_id: str) -> str:
        """Generate a new API key for user"""
        try:
            if UserOperations._is_postgresql(db):
                # PostgreSQL: Update API key
                from database.postgresql_schema import User
                session = db._get_session()
                try:
                    user = session.query(User).filter(User.user_id == user_id).first()
                    if not user:
                        raise Exception("User not found")
                    
                    # Generate new API key
                    api_key = secrets.token_urlsafe(32)
                    user.api_key = api_key
                    user.api_key_created_at = datetime.utcnow()
                    user.updated_at = datetime.utcnow()
                    session.commit()
                    return api_key
                finally:
                    session.close()
            else:
                # Firestore (legacy)
                # Firebase removed - PostgreSQL only
                # Get current user to preserve role
                user_doc = db.collection('users').document(user_id).get()
                if not user_doc.exists:
                    raise Exception("User not found")
                
                user_data = user_doc.to_dict()
                old_api_key = user_data.get('api_key')
                role = user_data.get('role', 'client')
                
                # Generate new API key
                api_key = secrets.token_urlsafe(32)
                now = datetime.utcnow()
                
                # Update user document
                db.collection('users').document(user_id).update({
                    'api_key': api_key,
                    'api_key_created_at': now,
                    'updated_at': now
                })
                
                # Update API key index
                db.collection('api_keys').document(api_key).set({
                    'user_id': user_id,
                    'role': role,
                    'created_at': now
                })
                
                # Remove old API key index if exists
                if old_api_key:
                    db.collection('api_keys').document(old_api_key).delete()
                
                return api_key
            
        except Exception as e:
            raise Exception(f"Failed to generate API key: {str(e)}")
    
    @staticmethod
    def verify_user_exists(db, email: str) -> bool:
        """Check if user exists"""
        try:
            if UserOperations._is_postgresql(db):
                # PostgreSQL: Check if user exists
                from database.postgresql_schema import User
                session = db._get_session()
                try:
                    user = session.query(User).filter(User.email == email.lower().strip()).first()
                    return user is not None
                finally:
                    session.close()
            else:
                # Firestore (legacy)
                # Firebase removed - PostgreSQL only
                email_doc = db.collection('user_emails').document(email.lower().strip()).get()
                return email_doc.exists
        except Exception as e:
            return False

