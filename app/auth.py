from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, Cookie, Depends
import os
from dotenv import load_dotenv
from .github_utils import GitHubManager

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 1

# Initialize GitHub manager for auth
github_manager = GitHubManager()

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    """Create JWT access token"""
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(hours=ACCESS_TOKEN_EXPIRE_HOURS)
    
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def verify_token(token: str):
    """Verify JWT token"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return email
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(access_token: Optional[str] = Cookie(None)):
    """Get current user from JWT token with GitHub verification"""
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    email = verify_token(access_token)
    
    # Verify user exists in GitHub data
    try:
        users_data = github_manager.get_users()
        
        user_exists = False
        for user in users_data.get("users", []):
            if user["email"] == email:
                user_exists = True
                break
        
        if not user_exists:
            raise HTTPException(status_code=401, detail="User not found")
        
        return email
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")

def is_admin(email: str) -> bool:
    """Check if user is admin"""
    try:
        users_data = github_manager.get_users()
        
        for user in users_data.get("users", []):
            if user["email"] == email:
                return user.get("is_admin", False)
        
        return False
    except Exception:
        return False

def get_admin_user(access_token: Optional[str] = Cookie(None)):
    """Get current admin user"""
    email = get_current_user(access_token)
    
    if not is_admin(email):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return email