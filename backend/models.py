"""
Database models module.
Defines the SQLAlchemy ORM models with normalized Role-Based Access architecture.
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from backend.database import Base

class Role(Base):
    """Defines system roles for granular Access Control."""
    __tablename__ = "roles"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    description = Column(String(255))
    
    # Relationship: A role can have multiple users
    users = relationship("User", back_populates="role")

class User(Base):
    """Core user model with security and audit fields."""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    
    # Foreign Key strictly binding the user to a specific Role
    role_id = Column(Integer, ForeignKey("roles.id"), nullable=False)
    
    # Audit & Security fields (Enterprise standards)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_login_date = Column(DateTime(timezone=True), nullable=True)

    # Relationship: Access role properties directly via user.role.name
    role = relationship("Role", back_populates="users")