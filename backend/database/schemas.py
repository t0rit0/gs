"""
Pydantic Schemas for API Validation

Defines request/response models for type safety and validation.
Compatible with FastAPI.
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any
from datetime import datetime


# ============================================
# Patient Schemas
# ============================================

class PatientBase(BaseModel):
    """Base patient model with common fields"""
    name: str = Field(..., min_length=1, max_length=100, description="Patient name")
    age: int = Field(..., gt=0, lt=150, description="Patient age")
    gender: str = Field(..., pattern="^(male|female|other)$", description="Patient gender")
    phone: Optional[str] = Field(None, max_length=20, description="Contact phone number")
    address: Optional[str] = Field(None, description="Home address")


class PatientCreate(PatientBase):
    """Schema for creating a new patient"""
    medical_history_text: Optional[str] = Field(None, description="Free text medical history input")
    medical_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    allergies: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    medications: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    family_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    health_metrics: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class PatientUpdate(BaseModel):
    """Schema for updating patient information (all fields optional)"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    age: Optional[int] = Field(None, gt=0, lt=150)
    gender: Optional[str] = Field(None, pattern="^(male|female|other)$")
    phone: Optional[str] = Field(None, max_length=20)
    address: Optional[str] = None

    medical_history: Optional[List[Dict[str, Any]]] = None
    allergies: Optional[List[Dict[str, Any]]] = None
    medications: Optional[List[Dict[str, Any]]] = None
    family_history: Optional[List[Dict[str, Any]]] = None
    health_metrics: Optional[List[Dict[str, Any]]] = None


class PatientResponse(PatientBase):
    """Schema for patient response (includes system fields)"""
    patient_id: str
    medical_history: List[Dict[str, Any]] = Field(default_factory=list)
    allergies: List[Dict[str, Any]] = Field(default_factory=list)
    medications: List[Dict[str, Any]] = Field(default_factory=list)
    family_history: List[Dict[str, Any]] = Field(default_factory=list)
    health_metrics: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    class Config:
        """Enable ORM mode for SQLAlchemy model conversion"""
        from_attributes = True


# ============================================
# Conversation Schemas
# ============================================

class ConversationBase(BaseModel):
    """Base conversation model"""
    patient_id: str = Field(..., description="Associated patient ID")
    target: str = Field(..., min_length=1, max_length=200, description="Conversation goal")
    model_type: str = Field(default="DrHyper", pattern="^(DrHyper|General|MainAgent)$", description="AI model type")


class ConversationCreate(ConversationBase):
    """Schema for creating a new conversation"""
    pass


class ConversationUpdate(BaseModel):
    """Schema for updating conversation (all fields optional)"""
    target: Optional[str] = Field(None, min_length=1, max_length=200)
    status: Optional[str] = Field(None, pattern="^(active|completed|abandoned)$")
    drhyper_state: Optional[Dict[str, Any]] = None


class ConversationResponse(ConversationBase):
    """Schema for conversation response"""
    conversation_id: str
    status: str
    drhyper_state: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


# ============================================
# Message Schemas
# ============================================

class MessageBase(BaseModel):
    """Base message model"""
    conversation_id: str = Field(..., description="Associated conversation ID")
    role: str = Field(..., pattern="^(human|ai|system)$", description="Message sender role")
    content: str = Field(..., min_length=1, description="Message content")


class MessageCreate(MessageBase):
    """Schema for creating a new message"""
    think_content: Optional[str] = Field(None, description="AI thinking process (for AI messages)")
    message_metadata: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Additional metadata")
    image_paths: Optional[List[str]] = Field(default_factory=list, description="Attached image file paths")


class MessageResponse(MessageBase):
    """Schema for message response"""
    id: int
    turn_number: int
    think_content: Optional[str] = None
    message_metadata: Dict[str, Any] = Field(default_factory=dict)
    image_paths: List[str] = Field(default_factory=list)
    timestamp: datetime

    class Config:
        from_attributes = True


# ============================================
# Medical Report Schemas
# ============================================

class ReportBase(BaseModel):
    """Base medical report model"""
    patient_id: str = Field(..., description="Associated patient ID")
    conversation_id: str = Field(..., description="Associated conversation ID")
    report_type: str = Field(default="hypertension_diagnosis", description="Type of diagnosis")


class ReportCreate(ReportBase):
    """Schema for creating a new medical report"""
    summary: Optional[str] = Field(None, description="Brief overview of patient's condition")
    key_findings: Optional[str] = Field(None, description="Important clinical observations")
    recommendations: Optional[str] = Field(None, description="Treatment recommendations")
    follow_up: Optional[str] = Field(None, description="Follow-up schedule")
    full_report: Optional[str] = Field(None, description="Complete report text")


class ReportUpdate(BaseModel):
    """Schema for updating a medical report (all fields optional)"""
    report_type: Optional[str] = None
    summary: Optional[str] = None
    key_findings: Optional[str] = None
    recommendations: Optional[str] = None
    follow_up: Optional[str] = None
    full_report: Optional[str] = None


class ReportApproval(BaseModel):
    """Schema for approving/rejecting a medical report"""
    approved: bool = Field(..., description="Whether the report is approved")
    notes: Optional[str] = Field(None, description="Approval notes or rejection reason")


class ReportResponse(ReportBase):
    """Schema for medical report response"""
    report_id: str
    status: str = Field(description="Report status: pending, approved, rejected")
    summary: Optional[str] = None
    key_findings: Optional[str] = None
    recommendations: Optional[str] = None
    follow_up: Optional[str] = None
    full_report: Optional[str] = None
    created_at: datetime
    approved_at: Optional[datetime] = None
    updated_at: datetime

    class Config:
        from_attributes = True


class ReportListResponse(BaseModel):
    """Schema for list of reports"""
    reports: List[ReportResponse]
    total: int


# ============================================
# Extended Schemas with Relationships
# ============================================

class ConversationWithMessages(ConversationResponse):
    """Conversation schema including all messages"""
    messages: List[MessageResponse] = Field(default_factory=list)


class PatientWithConversations(PatientResponse):
    """Patient schema including conversation summary"""
    conversations: List[ConversationResponse] = Field(default_factory=list)


# ============================================
# Query Parameters
# ============================================

class PatientQueryParams(BaseModel):
    """Query parameters for patient list"""
    search: Optional[str] = Field(None, description="Search by name")
    skip: int = Field(0, ge=0, description="Number of records to skip")
    limit: int = Field(100, ge=1, le=1000, description="Maximum number of records to return")


class ConversationQueryParams(BaseModel):
    """Query parameters for conversation list"""
    patient_id: Optional[str] = Field(None, description="Filter by patient ID")
    status: Optional[str] = Field(None, pattern="^(active|completed|abandoned)$", description="Filter by status")
    skip: int = Field(0, ge=0)
    limit: int = Field(100, ge=1, le=1000)


# ============================================
# Utility Schemas
# ============================================

class HealthMetricRecord(BaseModel):
    """Schema for health metric records"""
    metric_name: str = Field(..., description="Metric name (e.g., '收缩压')")
    value: float = Field(..., description="Measured value")
    unit: str = Field(..., description="Unit of measurement (e.g., 'mmHg')")
    recorded_at: datetime = Field(default_factory=datetime.now, description="Recording time")
    notes: Optional[str] = Field(None, description="Additional notes")


class MedicalHistoryRecord(BaseModel):
    """Schema for medical history records"""
    condition: str = Field(..., description="Medical condition name")
    diagnosis_date: datetime = Field(default_factory=datetime.now)
    status: str = Field(..., pattern="^(active|resolved|chronic)$")
    notes: Optional[str] = None


class AllergyRecord(BaseModel):
    """Schema for allergy records"""
    allergen: str = Field(..., description="Allergen name")
    severity: str = Field(..., pattern="^(mild|moderate|severe)$")
    reaction: str = Field(..., description="Reaction description")
    diagnosed_date: datetime = Field(default_factory=datetime.now)


class MedicationRecord(BaseModel):
    """Schema for medication records"""
    medication_name: str = Field(..., description="Medication name")
    dosage: str = Field(..., description="Dosage amount")
    frequency: str = Field(..., description="Dosage frequency")
    start_date: datetime = Field(default_factory=datetime.now)
    end_date: Optional[datetime] = None
    prescribing_doctor: str = Field(..., description="Doctor who prescribed")
    notes: Optional[str] = None


# ============================================
# Response Wrappers
# ============================================

class PaginatedResponse(BaseModel):
    """Generic paginated response wrapper"""
    total: int = Field(..., description="Total number of records")
    skip: int = Field(..., description="Number of records skipped")
    limit: int = Field(..., description="Maximum records per page")
    data: List[Any] = Field(..., description="Paginated data")


class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str = Field(..., description="Error type")
    message: str = Field(..., description="Error message")
    details: Optional[Dict[str, Any]] = Field(None, description="Additional error details")


class SuccessResponse(BaseModel):
    """Success response schema"""
    message: str = Field(..., description="Success message")
    data: Optional[Any] = Field(None, description="Response data")
