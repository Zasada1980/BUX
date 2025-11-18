"""JWT token utilities and dependencies."""
import os
import jwt
import bcrypt
from datetime import datetime, timedelta, timezone
from typing import Optional
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from db import SessionLocal
from models import Employee, AuthCredential, RefreshToken
import hashlib
import hmac

# Configuration
JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "CHANGE_THIS_IN_PRODUCTION_12345678901234567890")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 15
REFRESH_TOKEN_EXPIRE_DAYS = 7
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# HTTP Bearer security
security = HTTPBearer()


def get_db():
    """Database session dependency."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def hash_password(password: str) -> str:
    """Hash password using bcrypt (cost 12)."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def verify_password(password: str, password_hash: str) -> bool:
    """Verify password against bcrypt hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


def verify_telegram_auth(auth_data: dict) -> bool:
    """
    Verify Telegram OAuth widget data using HMAC-SHA256.
    https://core.telegram.org/widgets/login#checking-authorization
    """
    if not TELEGRAM_BOT_TOKEN:
        raise ValueError("TELEGRAM_BOT_TOKEN not configured")
    
    received_hash = auth_data.pop('hash', '')
    
    # Create data-check-string
    data_check_arr = [f"{k}={v}" for k, v in sorted(auth_data.items())]
    data_check_string = '\n'.join(data_check_arr)
    
    # Compute secret key (SHA256 of bot token)
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode()).digest()
    
    # Compute HMAC-SHA256
    computed_hash = hmac.new(
        secret_key,
        data_check_string.encode(),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(computed_hash, received_hash)


def create_access_token(employee_id: int, role: str, username: str, expires_delta: Optional[timedelta] = None) -> str:
    """Create JWT access token."""
    if expires_delta is None:
        expires_delta = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    
    expire = datetime.now(timezone.utc) + expires_delta
    
    payload = {
        "sub": username,
        "user_id": employee_id,
        "role": role,
        "type": "access",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def create_refresh_token(employee_id: int, db: Session) -> str:
    """Create and store refresh token in database."""
    # Delete all existing tokens for this employee (cleaner than update)
    db.query(RefreshToken).filter(
        RefreshToken.employee_id == employee_id
    ).delete()
    db.flush()  # Ensure deletion is applied before insert
    
    expires_delta = timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)
    expire = datetime.now(timezone.utc) + expires_delta
    
    payload = {
        "sub": str(employee_id),
        "type": "refresh",
        "exp": expire,
        "iat": datetime.now(timezone.utc)
    }
    
    token = jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)
    
    # Store in database
    refresh_token_obj = RefreshToken(
        employee_id=employee_id,
        token=token,
        expires_at=expire,
        revoked=False
    )
    db.add(refresh_token_obj)
    db.commit()
    
    return token


def verify_token(token: str, token_type: str = "access") -> dict:
    """Verify JWT token and return payload."""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        
        if payload.get("type") != token_type:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=f"Invalid token type (expected {token_type})"
            )
        
        return payload
    
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired"
        )
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )


async def get_current_employee(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Employee:
    """Get current authenticated employee from JWT token."""
    token = credentials.credentials
    payload = verify_token(token, token_type="access")
    
    employee_id = int(payload["user_id"])  # Use user_id instead of sub
    employee = db.query(Employee).filter(Employee.id == employee_id).first()
    
    if not employee:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Employee not found"
        )
    
    if not employee.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account disabled"
        )
    
    return employee


def require_role(*allowed_roles: str):
    """Dependency factory for role-based access control."""
    async def role_checker(employee: Employee = Depends(get_current_employee)):
        if employee.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Insufficient permissions (required: {', '.join(allowed_roles)})"
            )
        return employee
    
    return role_checker


# Convenience dependencies
require_admin = require_role("admin")
require_foreman = require_role("admin", "foreman")
require_any_role = require_role("admin", "foreman", "worker")
