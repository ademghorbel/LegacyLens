#!/usr/bin/env python3
"""
Notification Service
Multi-channel notification system for email, SMS, and push notifications
"""
from fastapi import FastAPI, HTTPException, Depends, status, BackgroundTasks
from pydantic import BaseModel, EmailStr
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import enum
import smtplib
import requests
from email.mime.text import MimeText
from email.mime.multipart import MimeMultipart

Base = declarative_base()

# Enums
class NotificationType(str, enum.Enum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"
    IN_APP = "in_app"

class NotificationStatus(str, enum.Enum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    DELIVERED = "delivered"
    READ = "read"

class NotificationPriority(str, enum.Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"

class NotificationCategory(str, enum.Enum):
    ORDER_UPDATE = "order_update"
    PAYMENT_CONFIRMATION = "payment_confirmation"
    SHIPPING_UPDATE = "shipping_update"
    ACCOUNT_SECURITY = "account_security"
    MARKETING = "marketing"
    SYSTEM_ALERT = "system_alert"

# Database Models
class NotificationTemplate(Base):
    __tablename__ = "notification_templates"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), unique=True, nullable=False)
    category = Column(String, nullable=False)
    type = Column(String, nullable=False)
    subject_template = Column(String(500))  # For email notifications
    body_template = Column(Text, nullable=False)
    variables = Column(JSON)  # List of variables used in template
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)
    type = Column(String, nullable=False)
    category = Column(String, nullable=False)
    priority = Column(String, default=NotificationPriority.NORMAL.value)
    status = Column(String, default=NotificationStatus.PENDING.value)
    
    # Content
    subject = Column(String(500))
    message = Column(Text, nullable=False)
    data = Column(JSON)  # Additional data for the notification
    
    # Delivery details
    recipient_email = Column(String(255))
    recipient_phone = Column(String(20))
    recipient_device_token = Column(String(500))
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    scheduled_at = Column(DateTime, default=datetime.utcnow)
    sent_at = Column(DateTime)
    delivered_at = Column(DateTime)
    read_at = Column(DateTime)
    
    # Retry information
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    last_error = Column(Text)

class NotificationPreference(Base):
    __tablename__ = "notification_preferences"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, unique=True, nullable=False)
    
    # Email preferences
    email_enabled = Column(Boolean, default=True)
    email_orders = Column(Boolean, default=True)
    email_marketing = Column(Boolean, default=False)
    email_security = Column(Boolean, default=True)
    
    # SMS preferences
    sms_enabled = Column(Boolean, default=False)
    sms_orders = Column(Boolean, default=False)
    sms_security = Column(Boolean, default=True)
    
    # Push preferences
    push_enabled = Column(Boolean, default=True)
    push_orders = Column(Boolean, default=True)
    push_marketing = Column(Boolean, default=False)
    
    # In-app preferences
    in_app_enabled = Column(Boolean, default=True)
    
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# Pydantic Models
class NotificationTemplateCreate(BaseModel):
    name: str
    category: NotificationCategory
    type: NotificationType
    subject_template: Optional[str] = None
    body_template: str
    variables: Optional[List[str]] = []

class NotificationCreate(BaseModel):
    user_id: int
    type: NotificationType
    category: NotificationCategory
    priority: NotificationPriority = NotificationPriority.NORMAL
    template_name: Optional[str] = None
    subject: Optional[str] = None
    message: str
    data: Optional[Dict[str, Any]] = {}
    recipient_email: Optional[EmailStr] = None
    recipient_phone: Optional[str] = None
    scheduled_at: Optional[datetime] = None

class NotificationResponse(BaseModel):
    id: int
    user_id: int
    type: str
    category: str
    priority: str
    status: str
    subject: Optional[str]
    message: str
    created_at: datetime
    sent_at: Optional[datetime]
    read_at: Optional[datetime]

class NotificationPreferencesUpdate(BaseModel):
    email_enabled: Optional[bool] = None
    email_orders: Optional[bool] = None
    email_marketing: Optional[bool] = None
    email_security: Optional[bool] = None
    sms_enabled: Optional[bool] = None
    sms_orders: Optional[bool] = None
    sms_security: Optional[bool] = None
    push_enabled: Optional[bool] = None
    push_orders: Optional[bool] = None
    push_marketing: Optional[bool] = None
    in_app_enabled: Optional[bool] = None

# Service Classes
class EmailService:
    """Email delivery service"""
    
    def __init__(self):
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.smtp_username = "your-email@gmail.com"
        self.smtp_password = "your-app-password"
    
    def send_email(self, to_email: str, subject: str, body: str, is_html: bool = True) -> bool:
        """Send email notification"""
        try:
            # Create message
            msg = MimeMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = self.smtp_username
            msg['To'] = to_email
            
            # Add body
            if is_html:
                body_part = MimeText(body, 'html')
            else:
                body_part = MimeText(body, 'plain')
            
            msg.attach(body_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            return True
        except Exception as e:
            print(f"Email sending failed: {e}")
            return False

class SMSService:
    """SMS delivery service using Twilio API"""
    
    def __init__(self):
        self.api_url = "https://api.twilio.com/2010-04-01/Accounts"
        self.account_sid = "your-twilio-account-sid"
        self.auth_token = "your-twilio-auth-token"
        self.from_number = "+1234567890"
    
    def send_sms(self, to_phone: str, message: str) -> bool:
        """Send SMS notification"""
        try:
            # Mock SMS sending - in real implementation, use Twilio API
            print(f"Sending SMS to {to_phone}: {message}")
            return True
        except Exception as e:
            print(f"SMS sending failed: {e}")
            return False

class PushNotificationService:
    """Push notification service using Firebase FCM"""
    
    def __init__(self):
        self.fcm_url = "https://fcm.googleapis.com/fcm/send"
        self.server_key = "your-firebase-server-key"
    
    def send_push(self, device_token: str, title: str, body: str, data: Dict[str, Any] = None) -> bool:
        """Send push notification"""
        try:
            headers = {
                'Authorization': f'key={self.server_key}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                'to': device_token,
                'notification': {
                    'title': title,
                    'body': body
                },
                'data': data or {}
            }
            
            # Mock push notification - in real implementation, use FCM API
            print(f"Sending push notification: {title} - {body}")
            return True
        except Exception as e:
            print(f"Push notification failed: {e}")
            return False

class TemplateService:
    """Notification template management"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def render_template(self, template_name: str, variables: Dict[str, Any]) -> Dict[str, str]:
        """Render notification template with variables"""
        template = self.db.query(NotificationTemplate).filter(
            NotificationTemplate.name == template_name,
            NotificationTemplate.is_active == True
        ).first()
        
        if not template:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Template not found"
            )
        
        # Simple template rendering (in production, use Jinja2)
        subject = template.subject_template or ""
        body = template.body_template
        
        for key, value in variables.items():
            placeholder = f"{{{{{key}}}}}"
            subject = subject.replace(placeholder, str(value))
            body = body.replace(placeholder, str(value))
        
        return {
            "subject": subject,
            "body": body,
            "type": template.type
        }

class NotificationService:
    """Main notification service"""
    
    def __init__(self, db: Session):
        self.db = db
        self.email_service = EmailService()
        self.sms_service = SMSService()
        self.push_service = PushNotificationService()
        self.template_service = TemplateService(db)
    
    def create_notification(self, notification_data: NotificationCreate) -> NotificationResponse:
        """Create a new notification"""
        # Render template if provided
        if notification_data.template_name:
            rendered = self.template_service.render_template(
                notification_data.template_name,
                notification_data.data or {}
            )
            subject = rendered["subject"]
            message = rendered["body"]
        else:
            subject = notification_data.subject
            message = notification_data.message
        
        # Create notification record
        notification = Notification(
            user_id=notification_data.user_id,
            type=notification_data.type.value,
            category=notification_data.category.value,
            priority=notification_data.priority.value,
            subject=subject,
            message=message,
            data=notification_data.data,
            recipient_email=notification_data.recipient_email,
            recipient_phone=notification_data.recipient_phone,
            scheduled_at=notification_data.scheduled_at or datetime.utcnow()
        )
        
        self.db.add(notification)
        self.db.commit()
        self.db.refresh(notification)
        
        return NotificationResponse(
            id=notification.id,
            user_id=notification.user_id,
            type=notification.type,
            category=notification.category,
            priority=notification.priority,
            status=notification.status,
            subject=notification.subject,
            message=notification.message,
            created_at=notification.created_at,
            sent_at=notification.sent_at,
            read_at=notification.read_at
        )
    
    def send_notification(self, notification_id: int) -> bool:
        """Send a notification"""
        notification = self.db.query(Notification).filter(Notification.id == notification_id).first()
        if not notification:
            return False
        
        # Check user preferences
        if not self._check_user_preferences(notification):
            notification.status = NotificationStatus.FAILED.value
            notification.last_error = "User preferences disabled this notification type"
            self.db.commit()
            return False
        
        success = False
        
        try:
            if notification.type == NotificationType.EMAIL.value:
                success = self.email_service.send_email(
                    notification.recipient_email,
                    notification.subject,
                    notification.message
                )
            elif notification.type == NotificationType.SMS.value:
                success = self.sms_service.send_sms(
                    notification.recipient_phone,
                    notification.message
                )
            elif notification.type == NotificationType.PUSH.value:
                success = self.push_service.send_push(
                    notification.recipient_device_token,
                    notification.subject,
                    notification.message,
                    notification.data
                )
            elif notification.type == NotificationType.IN_APP.value:
                # In-app notifications are just stored in database
                success = True
            
            if success:
                notification.status = NotificationStatus.SENT.value
                notification.sent_at = datetime.utcnow()
            else:
                notification.status = NotificationStatus.FAILED.value
                notification.retry_count += 1
                
        except Exception as e:
            notification.status = NotificationStatus.FAILED.value
            notification.last_error = str(e)
            notification.retry_count += 1
        
        self.db.commit()
        return success
    
    def get_user_notifications(self, user_id: int, unread_only: bool = False) -> List[NotificationResponse]:
        """Get notifications for a user"""
        query = self.db.query(Notification).filter(Notification.user_id == user_id)
        
        if unread_only:
            query = query.filter(Notification.read_at.is_(None))
        
        notifications = query.order_by(Notification.created_at.desc()).all()
        
        return [NotificationResponse(
            id=n.id,
            user_id=n.user_id,
            type=n.type,
            category=n.category,
            priority=n.priority,
            status=n.status,
            subject=n.subject,
            message=n.message,
            created_at=n.created_at,
            sent_at=n.sent_at,
            read_at=n.read_at
        ) for n in notifications]
    
    def mark_as_read(self, notification_id: int, user_id: int) -> bool:
        """Mark notification as read"""
        notification = self.db.query(Notification).filter(
            Notification.id == notification_id,
            Notification.user_id == user_id
        ).first()
        
        if not notification:
            return False
        
        notification.read_at = datetime.utcnow()
        self.db.commit()
        return True
    
    def _check_user_preferences(self, notification: Notification) -> bool:
        """Check if user preferences allow this notification"""
        prefs = self.db.query(NotificationPreference).filter(
            NotificationPreference.user_id == notification.user_id
        ).first()
        
        if not prefs:
            return True  # Default to allowing notifications
        
        # Check type-specific preferences
        if notification.type == NotificationType.EMAIL.value and not prefs.email_enabled:
            return False
        elif notification.type == NotificationType.SMS.value and not prefs.sms_enabled:
            return False
        elif notification.type == NotificationType.PUSH.value and not prefs.push_enabled:
            return False
        elif notification.type == NotificationType.IN_APP.value and not prefs.in_app_enabled:
            return False
        
        # Check category-specific preferences
        if notification.category == NotificationCategory.ORDER_UPDATE.value:
            if notification.type == NotificationType.EMAIL.value and not prefs.email_orders:
                return False
            elif notification.type == NotificationType.SMS.value and not prefs.sms_orders:
                return False
        
        return True

# FastAPI Routes
app = FastAPI(title="Notification Service", version="1.0.0")

@app.post("/notifications", response_model=NotificationResponse)
async def create_notification(
    notification_data: NotificationCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """Create and optionally send a notification"""
    service = NotificationService(db)
    notification = service.create_notification(notification_data)
    
    # Schedule notification sending in background
    background_tasks.add_task(service.send_notification, notification.id)
    
    return notification

@app.get("/notifications/user/{user_id}", response_model=List[NotificationResponse])
async def get_user_notifications(
    user_id: int,
    unread_only: bool = False,
    db: Session = Depends(get_db)
):
    """Get notifications for a user"""
    service = NotificationService(db)
    return service.get_user_notifications(user_id, unread_only)

@app.put("/notifications/{notification_id}/read")
async def mark_notification_read(
    notification_id: int,
    user_id: int,
    db: Session = Depends(get_db)
):
    """Mark a notification as read"""
    service = NotificationService(db)
    success = service.mark_as_read(notification_id, user_id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Notification not found"
        )
    
    return {"message": "Notification marked as read"}

@app.post("/templates", response_model=dict)
async def create_template(template_data: NotificationTemplateCreate, db: Session = Depends(get_db)):
    """Create a notification template"""
    template = NotificationTemplate(
        name=template_data.name,
        category=template_data.category.value,
        type=template_data.type.value,
        subject_template=template_data.subject_template,
        body_template=template_data.body_template,
        variables=template_data.variables
    )
    
    db.add(template)
    db.commit()
    db.refresh(template)
    
    return {"id": template.id, "name": template.name, "message": "Template created successfully"}

@app.get("/preferences/user/{user_id}")
async def get_user_preferences(user_id: int, db: Session = Depends(get_db)):
    """Get user notification preferences"""
    prefs = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == user_id
    ).first()
    
    if not prefs:
        # Create default preferences
        prefs = NotificationPreference(user_id=user_id)
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    
    return {
        "user_id": prefs.user_id,
        "email_enabled": prefs.email_enabled,
        "email_orders": prefs.email_orders,
        "email_marketing": prefs.email_marketing,
        "email_security": prefs.email_security,
        "sms_enabled": prefs.sms_enabled,
        "sms_orders": prefs.sms_orders,
        "sms_security": prefs.sms_security,
        "push_enabled": prefs.push_enabled,
        "push_orders": prefs.push_orders,
        "push_marketing": prefs.push_marketing,
        "in_app_enabled": prefs.in_app_enabled
    }

@app.put("/preferences/user/{user_id}")
async def update_user_preferences(
    user_id: int,
    preferences: NotificationPreferencesUpdate,
    db: Session = Depends(get_db)
):
    """Update user notification preferences"""
    prefs = db.query(NotificationPreference).filter(
        NotificationPreference.user_id == user_id
    ).first()
    
    if not prefs:
        prefs = NotificationPreference(user_id=user_id)
        db.add(prefs)
    
    # Update fields
    for field, value in preferences.dict(exclude_unset=True).items():
        setattr(prefs, field, value)
    
    prefs.updated_at = datetime.utcnow()
    db.commit()
    
    return {"message": "Preferences updated successfully"}

def get_db():
    """Database dependency - placeholder"""
    pass
