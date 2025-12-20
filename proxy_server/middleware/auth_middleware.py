"""
Authentication Middleware
Handles API key validation and role-based access control with security hardening
"""

from fastapi import HTTPException, Security, Depends
from fastapi.security import APIKeyHeader, APIKeyQuery
from typing import Optional, Dict, Any, Union
from database.user_schema import UserOperations, UserRole
import os
import hmac
import hashlib
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# API Key header and query parameter
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)

# Valid roles from enum
VALID_ROLES = {role.value for role in UserRole}

def constant_time_compare(a: str, b: str) -> bool:
    """Constant-time string comparison to prevent timing attacks"""
    if not a or not b:
        return False
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a.encode('utf-8'), b.encode('utf-8'))

def sanitize_api_key(api_key: Optional[str]) -> Optional[str]:
    """Sanitize and validate API key format"""
    if not api_key:
        return None
    
    # Convert to string and strip whitespace
    api_key = str(api_key).strip()
    
    # Reject empty strings
    if not api_key:
        return None
    
    # Reject keys that are too short (minimum 16 characters for security)
    if len(api_key) < 16:
        return None
    
    # Reject keys that are too long (prevent DoS)
    if len(api_key) > 256:
        return None
    
    # Only allow alphanumeric, hyphens, underscores, and URL-safe characters
    # This prevents injection attacks
    allowed_chars = set('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_')
    if not all(c in allowed_chars for c in api_key):
        return None
    
    return api_key

def validate_role(role: Optional[str]) -> str:
    """Validate and normalize role value"""
    if not role:
        raise HTTPException(status_code=401, detail="Invalid user role")
    
    role = str(role).lower().strip()
    
    # Only allow valid roles from enum
    if role not in VALID_ROLES:
        raise HTTPException(status_code=401, detail=f"Invalid role: {role}")
    
    return role

class AuthMiddleware:
    """Authentication and authorization middleware with security hardening"""
    
    def __init__(self, db: Union[Any, None]):
        """Initialize with database adapter (PostgreSQL or legacy Firestore)"""
        self.db = db
        # Load API keys from .env for miners, validators, and admin
        self.env_miner_api_key = os.getenv('MINER_API_KEY')
        self.env_validator_api_key = os.getenv('VALIDATOR_API_KEY')
        self.env_admin_api_key = os.getenv('ADMIN_API_KEY')
    
    def get_api_key(
        self,
        api_key_header: Optional[str] = Security(api_key_header),
        api_key_query: Optional[str] = Security(api_key_query)
    ) -> Optional[str]:
        """Extract API key from header or query parameter"""
        return api_key_header or api_key_query
    
    def verify_api_key(self, api_key: Optional[str]) -> Dict[str, Any]:
        """Verify API key and return user info with security validation"""
        # Sanitize API key first
        api_key = sanitize_api_key(api_key)
        if not api_key:
            raise HTTPException(
                status_code=401,
                detail="API key is required. Provide it via X-API-Key header or api_key query parameter"
            )
        
        # Check .env API keys first (for miners/validators/admin) using constant-time comparison
        if self.env_admin_api_key and constant_time_compare(api_key, self.env_admin_api_key):
            return {
                'role': 'admin',
                'api_key': api_key,
                'source': 'env'
            }
        
        if self.env_miner_api_key and constant_time_compare(api_key, self.env_miner_api_key):
            return {
                'role': 'miner',
                'api_key': api_key,
                'source': 'env'
            }
        
        if self.env_validator_api_key and constant_time_compare(api_key, self.env_validator_api_key):
            return {
                'role': 'validator',
                'api_key': api_key,
                'source': 'env'
            }
        
        # Check database API keys
        user = UserOperations.get_user_by_api_key(self.db, api_key)
        if not user:
            # Use constant-time comparison even for failed lookups to prevent timing attacks
            # Compare against a dummy value to maintain constant time
            constant_time_compare(api_key, "dummy_key_for_timing_protection")
            raise HTTPException(
                status_code=401,
                detail="Invalid API key"
            )
        
        # Validate role from database
        user_role = user.get('role', 'client')
        validated_role = validate_role(user_role)
        
        # Ensure user is active
        if not user.get('is_active', True):
            raise HTTPException(
                status_code=403,
                detail="User account is inactive"
            )
        
        return {
            'user_id': user.get('user_id'),
            'email': user.get('email'),
            'role': validated_role,  # Use validated role
            'api_key': api_key,
            'source': 'database',
            'hotkey': user.get('hotkey'),
            'coldkey_address': user.get('coldkey_address'),
            'uid': user.get('uid'),
            'network': user.get('network')
        }
    
    def require_role(self, allowed_roles: list):
        """Dependency to require specific role(s) with validation"""
        def role_checker(user_info: Dict[str, Any] = Depends(lambda: None)):
            if user_info is None:
                raise HTTPException(status_code=401, detail="Authentication required")
            
            user_role = user_info.get('role')
            
            # Validate role is in allowed list
            if not user_role or user_role not in allowed_roles:
                raise HTTPException(
                    status_code=403,
                    detail=f"Access denied. Required role: {', '.join(allowed_roles)}"
                )
            
            return user_info
        
        return role_checker
    
    def verify_miner_credentials(
        self,
        user_info: Dict[str, Any],
        hotkey: str,
        coldkey_address: str,
        uid: int,
        network: str
    ) -> bool:
        """Verify miner credentials match the API key"""
        role = user_info.get('role')
        
        # Admin can bypass credential verification
        if role == 'admin':
            return True
        
        # Validate role
        if role != 'miner':
            return False
        
        # For .env API keys, we trust them (they're configured by admin)
        if user_info.get('source') == 'env':
            return True
        
        # Sanitize and validate input credentials
        if not hotkey or not coldkey_address or not network:
            return False
        
        # For database API keys, verify credentials match using constant-time comparison
        user_hotkey = user_info.get('hotkey')
        user_coldkey = user_info.get('coldkey_address')
        user_uid = user_info.get('uid')
        user_network = user_info.get('network')
        
        return (
            user_hotkey and constant_time_compare(str(user_hotkey), str(hotkey)) and
            user_coldkey and constant_time_compare(str(user_coldkey), str(coldkey_address)) and
            user_uid == uid and
            user_network and constant_time_compare(str(user_network), str(network))
        )
    
    def verify_validator_credentials(
        self,
        user_info: Dict[str, Any],
        hotkey: str,
        coldkey_address: str,
        uid: int,
        network: str
    ) -> bool:
        """Verify validator credentials match the API key"""
        role = user_info.get('role')
        
        # Admin can bypass credential verification
        if role == 'admin':
            return True
        
        # Validate role
        if role != 'validator':
            return False
        
        # For .env API keys, we trust them (they're configured by admin)
        if user_info.get('source') == 'env':
            return True
        
        # Sanitize and validate input credentials
        if not hotkey or not coldkey_address or not network:
            return False
        
        # For database API keys, verify credentials match using constant-time comparison
        user_hotkey = user_info.get('hotkey')
        user_coldkey = user_info.get('coldkey_address')
        user_uid = user_info.get('uid')
        user_network = user_info.get('network')
        
        return (
            user_hotkey and constant_time_compare(str(user_hotkey), str(hotkey)) and
            user_coldkey and constant_time_compare(str(user_coldkey), str(coldkey_address)) and
            user_uid == uid and
            user_network and constant_time_compare(str(user_network), str(network))
        )
