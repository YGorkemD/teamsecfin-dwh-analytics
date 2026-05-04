"""
Security utility module.
Handles password hashing (Bcrypt) and JSON Web Token (JWT) generation.
"""

from datetime import datetime, timedelta
from jose import jwt
from passlib.context import CryptContext
from config import settings

# Initialize bcrypt context for secure password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verifies a plain-text password against its stored hash."""
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password: str) -> str:
    """Generates and returns the bcrypt hash for a given password."""
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    """
    Generates a JWT access token with an expiration claim (exp).
    """
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)