from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from fastapi import HTTPException, Cookie, Depends
import os
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-here")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_HOURS = 1

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

async def get_current_user(access_token: Optional[str] = Cookie(None)):
    """Get current user from JWT token with database verification"""
    if not access_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    
    try:
        email = verify_token(access_token)
    except HTTPException as e:
        # Token expired or invalid - redirect to login
        if e.status_code == 401:
            raise HTTPException(status_code=401, detail="Token expired")
        raise e
    
    # Import here to avoid circular imports
    from .database import db_manager
    
    # Verify user exists in database
    try:
        user = await db_manager.get_user_by_email(email)
        
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        
        return email
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Authentication error: {str(e)}")

async def is_admin(email: str) -> bool:
    """Check if user is admin"""
    try:
        from .database import db_manager
        user = await db_manager.get_user_by_email(email)
        return user.get("is_admin", False) if user else False
    except Exception:
        return False

async def get_admin_user(access_token: Optional[str] = Cookie(None)):
    """Get current admin user"""
    email = await get_current_user(access_token)
    
    if not await is_admin(email):
        raise HTTPException(status_code=403, detail="Admin access required")
    
    return email