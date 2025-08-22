from datetime import datetime
from typing import Optional, Literal, Dict, Any, List
from pydantic import BaseModel, Field, validator, root_validator
from .base import BaseModelWithID

# Notification types as a constant for reuse
NOTIFICATION_TYPES = Literal["message", "opportunity", "application", "verification", "moderation"]

# Notification templates for consistent messaging
NOTIFICATION_TEMPLATES = {
    "message": {
        "title": "New Message",
        "message_template": "You received a new message from {sender_name}"
    },
    "opportunity": {
        "title": "New Opportunity",
        "message_template": "New opportunity available: {opportunity_title}"
    },
    "application": {
        "title": "Application Update",
        "message_template": "Your application for '{opportunity_title}' has been {application_status}"
    },
    "verification": {
        "title": "Verification Update",
        "message_template": "Your verification status has been updated to: {verification_status}"
    },
    "moderation": {
        "title": "Content Moderation",
        "message_template": "Your {content_type} has been {moderation_status}"
    }
}

# Template validation constants
VALID_NOTIFICATION_TYPES = list(NOTIFICATION_TEMPLATES.keys())
TEMPLATE_VARIABLES = {
    "message": ["sender_name"],
    "opportunity": ["opportunity_title"],
    "application": ["application_status", "opportunity_title"],
    "verification": ["verification_status"],
    "moderation": ["content_type", "moderation_status"]
}


class NotificationTemplate(BaseModel):
    """Model for notification templates"""
    title: str
    message_template: str
    
    @validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    @validator('message_template')
    def validate_message_template(cls, v):
        if not v or not v.strip():
            raise ValueError('Message template cannot be empty')
        return v.strip()


class NotificationTemplates(BaseModel):
    """Model for managing notification templates"""
    templates: Dict[str, NotificationTemplate]
    
    @classmethod
    def get_default_templates(cls) -> 'NotificationTemplates':
        """Get default notification templates"""
        return cls(templates=NOTIFICATION_TEMPLATES)
    
    def get_template(self, notification_type: str) -> Optional[NotificationTemplate]:
        """Get template for a specific notification type"""
        return self.templates.get(notification_type)
    
    def get_valid_types(self) -> List[str]:
        """Get list of valid notification types"""
        return list(self.templates.keys())
    
    def is_valid_type(self, notification_type: str) -> bool:
        """Check if notification type is valid"""
        return notification_type in self.templates
    
    def get_required_variables(self, notification_type: str) -> List[str]:
        """Get required variables for a notification type"""
        return TEMPLATE_VARIABLES.get(notification_type, [])
    
    def validate_template_variables(self, notification_type: str, provided_vars: Dict[str, Any]) -> bool:
        """Validate that all required template variables are provided"""
        required_vars = self.get_required_variables(notification_type)
        missing_vars = [var for var in required_vars if var not in provided_vars]
        if missing_vars:
            raise ValueError(f"Missing required template variables: {missing_vars}")
        return True


class Notification(BaseModelWithID):
    """Notification model for user notifications"""
    user_id: str
    type: NOTIFICATION_TYPES
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    is_read: bool = False
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v.strip()
    
    @validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip()
    
    @validator('type')
    def validate_type(cls, v):
        if v not in VALID_NOTIFICATION_TYPES:
            raise ValueError(f'Invalid notification type. Must be one of: {VALID_NOTIFICATION_TYPES}')
        return v


class NotificationCreate(BaseModel):
    """Model for creating notification"""
    user_id: str
    type: NOTIFICATION_TYPES
    title: str
    message: str
    data: Optional[Dict[str, Any]] = None
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v.strip()
    
    @validator('title')
    def validate_title(cls, v):
        if not v or not v.strip():
            raise ValueError('Title cannot be empty')
        return v.strip()
    
    @validator('message')
    def validate_message(cls, v):
        if not v or not v.strip():
            raise ValueError('Message cannot be empty')
        return v.strip()
    
    @validator('type')
    def validate_type(cls, v):
        if v not in VALID_NOTIFICATION_TYPES:
            raise ValueError(f'Invalid notification type. Must be one of: {VALID_NOTIFICATION_TYPES}')
        return v


class NotificationUpdate(BaseModel):
    """Model for updating notification"""
    is_read: bool


class NotificationSearchFilters(BaseModel):
    """Model for notification search filters"""
    type: Optional[NOTIFICATION_TYPES] = None
    unread_only: bool = False
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)
    
    @validator('type')
    def validate_type(cls, v):
        if v is not None and v not in VALID_NOTIFICATION_TYPES:
            raise ValueError(f'Invalid notification type. Must be one of: {VALID_NOTIFICATION_TYPES}')
        return v


class NotificationBulkRead(BaseModel):
    """Model for bulk marking notifications as read"""
    notification_ids: List[str]
    
    @validator('notification_ids')
    def validate_notification_ids(cls, v):
        if not v:
            raise ValueError('Notification IDs cannot be empty')
        if not all(isinstance(id, str) and id.strip() for id in v):
            raise ValueError('All notification IDs must be non-empty strings')
        return [id.strip() for id in v]


# Template-specific notification models
class MessageNotificationCreate(BaseModel):
    """Model for creating message notifications with template validation"""
    user_id: str
    conversation_id: str
    sender_name: str
    
    @validator('user_id', 'conversation_id', 'sender_name')
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()
    
    def to_notification_create(self) -> NotificationCreate:
        """Convert to NotificationCreate using template"""
        template = NOTIFICATION_TEMPLATES["message"]
        return NotificationCreate(
            user_id=self.user_id,
            type="message",
            title=template["title"],
            message=template["message_template"].format(sender_name=self.sender_name),
            data={"conversation_id": self.conversation_id}
        )


class OpportunityNotificationCreate(BaseModel):
    """Model for creating opportunity notifications with template validation"""
    user_id: str
    opportunity_id: str
    opportunity_title: str
    
    @validator('user_id', 'opportunity_id', 'opportunity_title')
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()
    
    def to_notification_create(self) -> NotificationCreate:
        """Convert to NotificationCreate using template"""
        template = NOTIFICATION_TEMPLATES["opportunity"]
        return NotificationCreate(
            user_id=self.user_id,
            type="opportunity",
            title=template["title"],
            message=template["message_template"].format(opportunity_title=self.opportunity_title),
            data={"opportunity_id": self.opportunity_id}
        )


class ApplicationNotificationCreate(BaseModel):
    """Model for creating application notifications with template validation"""
    user_id: str
    application_status: str
    opportunity_title: str
    
    @validator('user_id', 'opportunity_title')
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()
    
    @validator('application_status')
    def validate_application_status(cls, v):
        valid_statuses = ["pending", "accepted", "rejected", "withdrawn"]
        if v not in valid_statuses:
            raise ValueError(f'Invalid application status. Must be one of: {valid_statuses}')
        return v
    
    def to_notification_create(self) -> NotificationCreate:
        """Convert to NotificationCreate using template"""
        template = NOTIFICATION_TEMPLATES["application"]
        return NotificationCreate(
            user_id=self.user_id,
            type="application",
            title=template["title"],
            message=template["message_template"].format(
                application_status=self.application_status,
                opportunity_title=self.opportunity_title
            ),
            data={"status": self.application_status}
        )


class VerificationNotificationCreate(BaseModel):
    """Model for creating verification notifications with template validation"""
    user_id: str
    verification_status: str
    
    @validator('user_id')
    def validate_user_id(cls, v):
        if not v or not v.strip():
            raise ValueError('User ID cannot be empty')
        return v.strip()
    
    @validator('verification_status')
    def validate_verification_status(cls, v):
        valid_statuses = ["pending", "approved", "rejected"]
        if v not in valid_statuses:
            raise ValueError(f'Invalid verification status. Must be one of: {valid_statuses}')
        return v
    
    def to_notification_create(self) -> NotificationCreate:
        """Convert to NotificationCreate using template"""
        template = NOTIFICATION_TEMPLATES["verification"]
        return NotificationCreate(
            user_id=self.user_id,
            type="verification",
            title=template["title"],
            message=template["message_template"].format(verification_status=self.verification_status),
            data={"status": self.verification_status}
        )


class ModerationNotificationCreate(BaseModel):
    """Model for creating moderation notifications with template validation"""
    user_id: str
    content_type: str
    moderation_status: str
    
    @validator('user_id', 'content_type')
    def validate_required_fields(cls, v):
        if not v or not v.strip():
            raise ValueError('Field cannot be empty')
        return v.strip()
    
    @validator('moderation_status')
    def validate_moderation_status(cls, v):
        valid_statuses = ["pending", "approved", "rejected"]
        if v not in valid_statuses:
            raise ValueError(f'Invalid moderation status. Must be one of: {valid_statuses}')
        return v
    
    def to_notification_create(self) -> NotificationCreate:
        """Convert to NotificationCreate using template"""
        template = NOTIFICATION_TEMPLATES["moderation"]
        return NotificationCreate(
            user_id=self.user_id,
            type="moderation",
            title=template["title"],
            message=template["message_template"].format(
                content_type=self.content_type,
                moderation_status=self.moderation_status
            ),
            data={"content_type": self.content_type, "status": self.moderation_status}
        )


# Utility functions for template management
def get_notification_templates() -> NotificationTemplates:
    """Get default notification templates"""
    return NotificationTemplates.get_default_templates()


def is_valid_notification_type(notification_type: str) -> bool:
    """Check if notification type is valid"""
    return notification_type in VALID_NOTIFICATION_TYPES


def get_valid_notification_types() -> List[str]:
    """Get list of valid notification types"""
    return VALID_NOTIFICATION_TYPES.copy()


def get_template_variables(notification_type: str) -> List[str]:
    """Get required variables for a notification type"""
    return TEMPLATE_VARIABLES.get(notification_type, [])


def validate_template_variables(notification_type: str, provided_vars: Dict[str, Any]) -> bool:
    """Validate that all required template variables are provided"""
    required_vars = get_template_variables(notification_type)
    missing_vars = [var for var in required_vars if var not in provided_vars]
    if missing_vars:
        raise ValueError(f"Missing required template variables: {missing_vars}")
    return True 