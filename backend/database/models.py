"""
SQLAlchemy ORM Models

Defines the database schema for the medical assistant system.

Compatible with:
- SQLite (development)
- PostgreSQL (production)
- MySQL (if needed)
"""
from sqlalchemy import Column, String, Integer, ForeignKey, Text, DateTime, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from backend.database.base import Base


# ============================================
# Utility Functions
# ============================================

def generate_uuid():
    """Generate a random UUID string"""
    return str(uuid.uuid4())


# ============================================
# Models
# ============================================

class Patient(Base):
    """
    Patient information table

    Stores basic patient demographics.
    Medical history, allergies, medications are stored
    as JSON fields for flexibility.
    """
    __tablename__ = "patients"

    # Primary Key
    patient_id = Column(String(36), primary_key=True, default=generate_uuid)

    # Basic Information
    name = Column(String(100), nullable=False)
    age = Column(Integer, nullable=False)
    gender = Column(String(10), nullable=False)  # male, female, other
    phone = Column(String(20))
    address = Column(Text)

    # Extended Medical Information (JSON)
    # Storing as JSON allows flexible schema without migrations
    medical_history = Column(JSON, default=list)  # List of medical conditions
    allergies = Column(JSON, default=list)  # List of allergies
    medications = Column(JSON, default=list)  # Current medications
    family_history = Column(JSON, default=list)  # Family medical history
    health_metrics = Column(JSON, default=list)  # Health metric records

    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    conversations = relationship(
        "Conversation",
        back_populates="patient",
        cascade="all, delete-orphan"  # Delete conversations when patient is deleted
    )

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "patient_id": self.patient_id,
            "name": self.name,
            "age": self.age,
            "gender": self.gender,
            "phone": self.phone,
            "address": self.address,
            "medical_history": self.medical_history or [],
            "allergies": self.allergies or [],
            "medications": self.medications or [],
            "family_history": self.family_history or [],
            "health_metrics": self.health_metrics or [],
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<Patient(id={self.patient_id}, name={self.name}, age={self.age})>"


class Conversation(Base):
    """
    Conversation session table

    Tracks dialog sessions between patients and the AI assistant.
    Stores both metadata and DrHyper state.
    """
    __tablename__ = "conversations"

    # Primary Key
    conversation_id = Column(String(36), primary_key=True, default=generate_uuid)

    # Foreign Keys
    patient_id = Column(String(36), ForeignKey("patients.patient_id"), nullable=False)

    # Conversation Metadata
    target = Column(String(200), nullable=False)  # e.g., "高血压诊断"
    model_type = Column(String(50), default="DrHyper")  # Model used
    status = Column(String(20), default="active")  # active, completed, abandoned

    # DrHyper State (JSON)
    # Stores the graph structure and conversation state
    drhyper_state = Column(JSON, default=dict)

    # EntityGraph State (JSON)
    # Stores EntityGraph serialization for MainAgent conversations
    entity_graph_state = Column(JSON, nullable=True)

    # Report Status
    # Tracks the status of the diagnostic report for this conversation
    report_status = Column(String(20), default="none")  # none, generated, pending_approval, approved, rejected

    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    patient = relationship("Patient", back_populates="conversations")
    messages = relationship(
        "Message",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="Message.turn_number"
    )

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "conversation_id": self.conversation_id,
            "patient_id": self.patient_id,
            "target": self.target,
            "model_type": self.model_type,
            "status": self.status,
            "drhyper_state": self.drhyper_state or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "message_count": len(self.messages) if self.messages else 0
        }

    def __repr__(self):
        return f"<Conversation(id={self.conversation_id}, target={self.target}, status={self.status})>"


class Message(Base):
    """
    Message table

    Stores individual messages in a conversation.
    Supports both text and image content.
    """
    __tablename__ = "messages"

    # Primary Key
    id = Column(Integer, primary_key=True, autoincrement=True)

    # Foreign Keys
    conversation_id = Column(String(36), ForeignKey("conversations.conversation_id"), nullable=False)

    # Message Content
    turn_number = Column(Integer, nullable=False)  # Position in conversation
    role = Column(String(20), nullable=False)  # human, ai, system
    content = Column(Text, nullable=False)  # Message text
    think_content = Column(Text)  # AI thinking process (optional)

    # Message Metadata (JSON)
    # Stores additional information like:
    # - Extracted entities
    # - Hints
    # - Image analysis results
    message_metadata = Column(JSON, default=dict)

    # Image Storage
    # Stores list of image file paths (not the actual images)
    # Images are stored in the file system
    image_paths = Column(JSON, default=list)

    # Timestamp
    timestamp = Column(DateTime, default=datetime.now, nullable=False)

    # Relationships
    conversation = relationship("Conversation", back_populates="messages")

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "turn_number": self.turn_number,
            "role": self.role,
            "content": self.content,
            "think_content": self.think_content,
            "metadata": self.message_metadata or {},
            "image_paths": self.image_paths or [],
            "timestamp": self.timestamp.isoformat() if self.timestamp else None
        }

    def __repr__(self):
        return f"<Message(id={self.id}, role={self.role}, turn={self.turn_number})>"


class MedicalReport(Base):
    """
    Medical report table - stores diagnostic reports generated from each consultation.

    A patient can have multiple reports from different consultations over time.
    This allows tracking of patient history and provides context for future consultations.
    """
    __tablename__ = "medical_reports"

    # Primary Key
    report_id = Column(String(36), primary_key=True, default=generate_uuid)

    # Foreign Keys
    patient_id = Column(String(36), ForeignKey("patients.patient_id"), nullable=False)
    conversation_id = Column(String(36), ForeignKey("conversations.conversation_id"), nullable=False)

    # Report Content
    report_type = Column(String(50), default="hypertension_diagnosis")  # Type of diagnosis
    status = Column(String(20), default="pending")  # pending, approved, rejected

    # Structured Report Data
    summary = Column(Text)  # Brief overview of the patient's condition
    key_findings = Column(Text)  # Important clinical observations
    recommendations = Column(Text)  # Treatment and lifestyle recommendations
    follow_up = Column(Text)  # Follow-up schedule
    full_report = Column(Text)  # Complete report text

    # Timestamps
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    approved_at = Column(DateTime, nullable=True)  # When approved by doctor
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

    # Relationships
    patient = relationship("Patient", backref="medical_reports")
    conversation = relationship("Conversation", backref="medical_report", uselist=False)

    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "report_id": self.report_id,
            "patient_id": self.patient_id,
            "conversation_id": self.conversation_id,
            "report_type": self.report_type,
            "status": self.status,
            "summary": self.summary,
            "key_findings": self.key_findings,
            "recommendations": self.recommendations,
            "follow_up": self.follow_up,
            "full_report": self.full_report,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "approved_at": self.approved_at.isoformat() if self.approved_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f"<MedicalReport(id={self.report_id}, status={self.status})>"


# ============================================
# Utility Functions for Models
# ============================================

def get_all_models():
    """Get all model classes"""
    return [Patient, Conversation, Message, MedicalReport]


def get_model_by_tablename(tablename: str):
    """Get model class by table name"""
    models_map = {
        "patients": Patient,
        "conversations": Conversation,
        "messages": Message,
        "medical_reports": MedicalReport
    }
    return models_map.get(tablename)


# ============================================
# Examples of JSON field structures
# ============================================

"""
Patient.medical_history example:
[
    {
        "condition": "高血压",
        "diagnosis_date": "2023-01-15T00:00:00",
        "status": "chronic",  # active, resolved, chronic
        "notes": "确诊为原发性高血压"
    }
]

Patient.allergies example:
[
    {
        "allergen": "青霉素",
        "severity": "severe",  # mild, moderate, severe
        "reaction": "皮疹、呼吸困难",
        "diagnosed_date": "2020-05-10T00:00:00"
    }
]

Patient.medications example:
[
    {
        "medication_name": "氨氯地平",
        "dosage": "5mg",
        "frequency": "每日一次",
        "start_date": "2023-01-15T00:00:00",
        "end_date": null,
        "prescribing_doctor": "李医生",
        "notes": "降压药"
    }
]

Patient.health_metrics example:
[
    {
        "metric_name": "收缩压",
        "value": 145,
        "unit": "mmHg",
        "recorded_at": "2026-01-27T09:00:00",
        "notes": "早晨测量"
    }
]

Conversation.drhyper_state example:
{
    "entity_graph": {
        "nodes": [
            {
                "id": "symptom_1",
                "type": "symptom",
                "properties": {"name": "血压高"},
                "confidence": 0.9
            }
        ],
        "edges": []
    },
    "relation_graph": {
        "nodes": [],
        "edges": []
    },
    "current_hint": "请提供血压数值",
    "step": 1,
    "accomplish": false
}

Message.metadata example:
{
    "hint": "询问血压值",
    "extracted_entities": {
        "symptoms": ["血压高"],
        "numbers": []
    },
    "updated_nodes": ["symptom_1"],
    "new_nodes": [],
    "image_analysis": {
        "detected_text": "血压: 140/90 mmHg",
        "confidence": 0.95
    }
}
"""
