#!/usr/bin/env python3
"""
Authentication Service Module
JWT-based authentication system with role-based access control
"""
from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Enum
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
import bcrypt
import jwt
from datetime import datetime, timedelta
from typing import Optional
import enum

Base = declarative_base()

# Enums
class UserRole(str, enum.Enum):
    ADMIN = "admin"
    USER = "user"
    MODERATOR = "moderator"

class TokenType(str, enum.Enum):
    ACCESS = "access"
    REFRESH = "refresh"

# Database Models
class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    password_hash = Column(String, nullable=False)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    role = Column(Enum(UserRole), default=UserRole.USER)
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    token_hash = Column(String, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    is_revoked = Column(Boolean, default=False)

# Pydantic Models
class UserSignup(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: int
    email: str
    first_name: str
    last_name: str
    role: UserRole
    is_active: bool
    is_verified: bool
    created_at: datetime

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int

class TokenRefresh(BaseModel):
    refresh_token: str

# Service Classes
class PasswordService:
    """Password hashing and verification service"""
    
    @staticmethod
    def hash_password(password: str) -> str:
        """Hash a password using bcrypt"""
        salt = bcrypt.gensalt()
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    @staticmethod
    def verify_password(password: str, hashed: str) -> bool:
        """Verify a password against its hash"""
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))

class JWTService:
    """JWT token creation and validation service"""
    
    SECRET_KEY = "your-secret-key-here"
    ALGORITHM = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES = 30
    REFRESH_TOKEN_EXPIRE_DAYS = 7
    
    @classmethod
    def create_access_token(cls, user_id: int, email: str, role: str) -> str:
        """Create an access token"""
        expire = datetime.utcnow() + timedelta(minutes=cls.ACCESS_TOKEN_EXPIRE_MINUTES)
        payload = {
            "sub": str(user_id),
            "email": email,
            "role": role,
            "type": TokenType.ACCESS.value,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
    
    @classmethod
    def create_refresh_token(cls, user_id: int) -> str:
        """Create a refresh token"""
        expire = datetime.utcnow() + timedelta(days=cls.REFRESH_TOKEN_EXPIRE_DAYS)
        payload = {
            "sub": str(user_id),
            "type": TokenType.REFRESH.value,
            "exp": expire,
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, cls.SECRET_KEY, algorithm=cls.ALGORITHM)
    
    @classmethod
    def verify_token(cls, token: str) -> dict:
        """Verify and decode a token"""
        try:
            payload = jwt.decode(token, cls.SECRET_KEY, algorithms=[cls.ALGORITHM])
            return payload
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token has expired"
            )
        except jwt.JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )

class AuthService:
    """Main authentication service"""
    
    def __init__(self, db_session: Session):
        self.db = db_session
        self.password_service = PasswordService()
        self.jwt_service = JWTService()
    
    def signup_user(self, user_data: UserSignup) -> UserResponse:
        """Register a new user"""
        # Check if user already exists
        existing_user = self.db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )
        
        # Create new user
        hashed_password = self.password_service.hash_password(user_data.password)
        new_user = User(
            email=user_data.email,
            password_hash=hashed_password,
            first_name=user_data.first_name,
            last_name=user_data.last_name
        )
        
        self.db.add(new_user)
        self.db.commit()
        self.db.refresh(new_user)
        
        return UserResponse(
            id=new_user.id,
            email=new_user.email,
            first_name=new_user.first_name,
            last_name=new_user.last_name,
            role=new_user.role,
            is_active=new_user.is_active,
            is_verified=new_user.is_verified,
            created_at=new_user.created_at
        )
    
    def login_user(self, login_data: UserLogin) -> TokenResponse:
        """Authenticate user and return tokens"""
        # Find user
        user = self.db.query(User).filter(User.email == login_data.email).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Verify password
        if not self.password_service.verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid credentials"
            )
        
        # Update last login
        user.last_login = datetime.utcnow()
        self.db.commit()
        
        # Create tokens
        access_token = self.jwt_service.create_access_token(user.id, user.email, user.role.value)
        refresh_token = self.jwt_service.create_refresh_token(user.id)
        
        # Store refresh token
        token_hash = self.password_service.hash_password(refresh_token)
        refresh_token_record = RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.utcnow() + timedelta(days=self.jwt_service.REFRESH_TOKEN_EXPIRE_DAYS)
        )
        self.db.add(refresh_token_record)
        self.db.commit()
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.jwt_service.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )
    
    def verify_token(self, token: str) -> dict:
        """Verify an access token"""
        payload = self.jwt_service.verify_token(token)
        if payload.get("type") != TokenType.ACCESS.value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        return payload
    
    def refresh_access_token(self, refresh_data: TokenRefresh) -> TokenResponse:
        """Refresh access token using refresh token"""
        payload = self.jwt_service.verify_token(refresh_data.refresh_token)
        if payload.get("type") != TokenType.REFRESH.value:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type"
            )
        
        user_id = int(payload.get("sub"))
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found or inactive"
            )
        
        # Create new access token
        access_token = self.jwt_service.create_access_token(user.id, user.email, user.role.value)
        
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_data.refresh_token,
            expires_in=self.jwt_service.ACCESS_TOKEN_EXPIRE_MINUTES * 60
        )

# FastAPI Routes
app = FastAPI(title="Authentication Service", version="1.0.0")
security = HTTPBearer()

@app.post("/signup", response_model=UserResponse)
async def signup(user_data: UserSignup, db: Session = Depends(get_db)):
    """Register a new user account"""
    auth_service = AuthService(db)
    return auth_service.signup_user(user_data)

@app.post("/login", response_model=TokenResponse)
async def login(login_data: UserLogin, db: Session = Depends(get_db)):
    """Authenticate user and return JWT tokens"""
    auth_service = AuthService(db)
    return auth_service.login_user(login_data)

@app.post("/refresh", response_model=TokenResponse)
async def refresh_token(refresh_data: TokenRefresh, db: Session = Depends(get_db)):
    """Refresh access token using refresh token"""
    auth_service = AuthService(db)
    return auth_service.refresh_access_token(refresh_data)

@app.get("/verify")
async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Verify JWT token and return user info"""
    auth_service = AuthService(db)
    payload = auth_service.verify_token(credentials.credentials)
    return {"valid": True, "user_id": payload.get("sub"), "role": payload.get("role")}

@app.post("/logout")
async def logout(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Logout user and revoke refresh tokens"""
    auth_service = AuthService(db)
    payload = auth_service.verify_token(credentials.credentials)
    user_id = int(payload.get("sub"))
    
    # Revoke all refresh tokens for this user
    refresh_tokens = db.query(RefreshToken).filter(RefreshToken.user_id == user_id, RefreshToken.is_revoked == False).all()
    for token in refresh_tokens:
        token.is_revoked = True
    db.commit()
    
    return {"message": "Successfully logged out"}

def get_db():
    """Database dependency - placeholder"""
    pass
