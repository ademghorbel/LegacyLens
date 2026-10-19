#!/usr/bin/env python3
"""
Database Configuration and Models
Central database setup for the e-commerce application
"""
from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator
import os
from contextlib import contextmanager

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password@localhost/ecommerce_db")

# SQLAlchemy Setup
engine = create_engine(DATABASE_URL, echo=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for all models
Base = declarative_base()

# Metadata for schema management
metadata = MetaData()

class DatabaseManager:
    """Database connection and session management"""
    
    def __init__(self, database_url: str = DATABASE_URL):
        self.database_url = database_url
        self.engine = create_engine(database_url, echo=False)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
    
    def get_db(self) -> Generator[Session, None, None]:
        """Dependency to get database session"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    @contextmanager
    def get_db_context(self):
        """Context manager for database sessions"""
        db = self.SessionLocal()
        try:
            yield db
        finally:
            db.close()
    
    def create_tables(self):
        """Create all tables in the database"""
        Base.metadata.create_all(bind=self.engine)
    
    def drop_tables(self):
        """Drop all tables from the database"""
        Base.metadata.drop_all(bind=self.engine)
    
    def reset_database(self):
        """Reset the database by dropping and recreating all tables"""
        self.drop_tables()
        self.create_tables()

# Global database manager instance
db_manager = DatabaseManager()

# Dependency function for FastAPI
def get_database_session() -> Generator[Session, None, None]:
    """FastAPI dependency to get database session"""
    return db_manager.get_db()

# Configuration settings
class DatabaseConfig:
    """Database configuration settings"""
    
    # Connection settings
    DATABASE_URL = DATABASE_URL
    ECHO_SQL = os.getenv("ECHO_SQL", "false").lower() == "true"
    
    # Connection pool settings
    POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "5"))
    MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "10"))
    POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
    POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "3600"))
    
    # Application settings
    APP_NAME = "E-Commerce API"
    VERSION = "1.0.0"
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    
    # Security settings
    SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key-change-in-production")
    JWT_ALGORITHM = "HS256"
    JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "30"))
    
    # Email settings (for notifications)
    SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.gmail.com")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
    
    # External API settings
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN", "")
    FIREBASE_SERVER_KEY = os.getenv("FIREBASE_SERVER_KEY", "")

# Initialize database tables if needed
def init_database():
    """Initialize the database with all tables"""
    try:
        db_manager.create_tables()
        print("✅ Database tables created successfully")
    except Exception as e:
        print(f"❌ Failed to create database tables: {e}")

if __name__ == "__main__":
    # Initialize database when run directly
    print("🗄️  Initializing database...")
    init_database()
    print("🚀 Database setup complete!")
