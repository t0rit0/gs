"""
CRUD Operations

Provides Create, Read, Update, Delete operations for all models.
Each CRUD class handles database operations for a specific model.
"""
from typing import List, Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy import desc
import json

from backend.database.models import Patient, Conversation, Message, MedicalReport
from backend.database.schemas import (
    PatientCreate, PatientUpdate,
    ConversationCreate, ConversationUpdate,
    MessageCreate,
    ReportCreate, ReportUpdate, ReportApproval
)
from datetime import datetime


# ============================================
# Patient CRUD
# ============================================

class PatientCRUD:
    """CRUD operations for Patient model"""

    @staticmethod
    def create(db: Session, patient_data: PatientCreate) -> Patient:
        """
        Create a new patient

        Args:
            db: Database session
            patient_data: Patient creation data

        Returns:
            Created Patient object
        """
        # Convert Pydantic model to dict
        patient_dict = patient_data.model_dump()

        # Handle medical_history_text: convert to medical_history record
        medical_history_text = patient_dict.pop("medical_history_text", None)
        if medical_history_text and medical_history_text.strip():
            medical_record = {
                "condition": medical_history_text.strip(),
                "diagnosis_date": datetime.now().isoformat(),
                "status": "active",
                "notes": None
            }
            # Prepend to existing medical_history if any
            existing_history = patient_dict.get("medical_history") or []
            patient_dict["medical_history"] = [medical_record] + existing_history

        # Create Patient instance
        db_patient = Patient(**patient_dict)

        # Add to database
        db.add(db_patient)
        db.commit()
        db.refresh(db_patient)

        return db_patient

    @staticmethod
    def get(db: Session, patient_id: str) -> Optional[Patient]:
        """
        Get a patient by ID

        Args:
            db: Database session
            patient_id: Patient UUID

        Returns:
            Patient object or None
        """
        return db.query(Patient).filter(Patient.patient_id == patient_id).first()

    @staticmethod
    def get_by_name(db: Session, name: str) -> List[Patient]:
        """
        Search patients by name (partial match)

        Args:
            db: Database session
            name: Name or partial name to search

        Returns:
            List of matching patients
        """
        return db.query(Patient).filter(Patient.name.contains(name)).all()

    @staticmethod
    def list_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        search: Optional[str] = None
    ) -> Tuple[List[Patient], int]:
        """
        Get list of patients with pagination and optional search

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Optional search term for patient name

        Returns:
            Tuple of (patient list, total count)
        """
        query = db.query(Patient)

        # Apply search filter if provided
        if search:
            query = query.filter(Patient.name.contains(search))

        # Get total count
        total = query.count()

        # Apply pagination
        patients = query.order_by(desc(Patient.created_at)).offset(skip).limit(limit).all()

        return patients, total

    @staticmethod
    def update(
        db: Session,
        patient_id: str,
        update_data: PatientUpdate
    ) -> Optional[Patient]:
        """
        Update patient information

        Args:
            db: Database session
            patient_id: Patient UUID
            update_data: Fields to update

        Returns:
            Updated Patient object or None
        """
        # Get existing patient
        db_patient = PatientCRUD.get(db, patient_id)
        if not db_patient:
            return None

        # Update only provided fields
        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(db_patient, field, value)

        # Update timestamp
        db_patient.updated_at = datetime.now()

        db.commit()
        db.refresh(db_patient)

        return db_patient

    @staticmethod
    def add_medical_history(
        db: Session,
        patient_id: str,
        condition: str,
        status: str,
        notes: Optional[str] = None
    ) -> Optional[Patient]:
        """
        Add a medical history record to patient

        Args:
            db: Database session
            patient_id: Patient UUID
            condition: Medical condition
            status: Status (active, resolved, chronic)
            notes: Optional notes

        Returns:
            Updated Patient object or None
        """
        patient = PatientCRUD.get(db, patient_id)
        if not patient:
            return None

        medical_record = {
            "condition": condition,
            "diagnosis_date": datetime.now().isoformat(),
            "status": status,
            "notes": notes
        }

        # Initialize list if None
        if patient.medical_history is None:
            patient.medical_history = []

        patient.medical_history.append(medical_record)
        patient.updated_at = datetime.now()

        # Flag the JSON field as modified for SQLAlchemy
        flag_modified(patient, "medical_history")

        db.commit()

        # Re-query to get fresh data
        db.refresh(patient)

        return patient

    @staticmethod
    def add_health_metric(
        db: Session,
        patient_id: str,
        metric_name: str,
        value: float,
        unit: str,
        notes: Optional[str] = None
    ) -> Optional[Patient]:
        """
        Add a health metric record to patient

        Args:
            db: Database session
            patient_id: Patient UUID
            metric_name: Name of the metric (e.g., "收缩压")
            value: Measured value
            unit: Unit of measurement
            notes: Optional notes

        Returns:
            Updated Patient object or None
        """
        patient = PatientCRUD.get(db, patient_id)
        if not patient:
            return None

        metric_record = {
            "metric_name": metric_name,
            "value": value,
            "unit": unit,
            "recorded_at": datetime.now().isoformat(),
            "notes": notes
        }

        # Initialize list if None
        if patient.health_metrics is None:
            patient.health_metrics = []

        patient.health_metrics.append(metric_record)
        patient.updated_at = datetime.now()

        # Flag the JSON field as modified for SQLAlchemy
        flag_modified(patient, "health_metrics")

        db.commit()
        db.refresh(patient)

        return patient

    @staticmethod
    def delete(db: Session, patient_id: str) -> bool:
        """
        Delete a patient (cascade deletes conversations and messages)

        Args:
            db: Database session
            patient_id: Patient UUID

        Returns:
            True if deleted, False otherwise
        """
        patient = PatientCRUD.get(db, patient_id)
        if not patient:
            return False

        db.delete(patient)
        db.commit()

        return True


# ============================================
# Conversation CRUD
# ============================================

class ConversationCRUD:
    """CRUD operations for Conversation model"""

    @staticmethod
    def create(db: Session, conv_data: ConversationCreate) -> Conversation:
        """
        Create a new conversation

        Args:
            db: Database session
            conv_data: Conversation creation data

        Returns:
            Created Conversation object
        """
        # Convert Pydantic model to dict if needed
        if isinstance(conv_data, dict):
            conv_dict = conv_data
        else:
            conv_dict = conv_data.model_dump()

        # Create Conversation instance with default DrHyper state
        db_conv = Conversation(**conv_dict)
        db_conv.drhyper_state = {
            "entity_graph": {"nodes": [], "edges": []},
            "relation_graph": {"nodes": [], "edges": []},
            "current_hint": None,
            "step": 0,
            "accomplish": False
        }

        # Add to database
        db.add(db_conv)
        db.commit()
        db.refresh(db_conv)

        return db_conv

    @staticmethod
    def get(db: Session, conversation_id: str) -> Optional[Conversation]:
        """
        Get a conversation by ID

        Args:
            db: Database session
            conversation_id: Conversation UUID

        Returns:
            Conversation object or None
        """
        return db.query(Conversation).filter(
            Conversation.conversation_id == conversation_id
        ).first()

    @staticmethod
    def list_by_patient(
        db: Session,
        patient_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[Conversation], int]:
        """
        Get all conversations for a patient

        Args:
            db: Database session
            patient_id: Patient UUID
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            Tuple of (conversation list, total count)
        """
        query = db.query(Conversation).filter(
            Conversation.patient_id == patient_id
        )

        total = query.count()
        conversations = query.order_by(
            desc(Conversation.created_at)
        ).offset(skip).limit(limit).all()

        return conversations, total

    @staticmethod
    def list_all(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None
    ) -> Tuple[List[Conversation], int]:
        """
        Get list of conversations with optional status filter

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records
            status: Optional status filter

        Returns:
            Tuple of (conversation list, total count)
        """
        query = db.query(Conversation)

        if status:
            query = query.filter(Conversation.status == status)

        total = query.count()
        conversations = query.order_by(
            desc(Conversation.created_at)
        ).offset(skip).limit(limit).all()

        return conversations, total

    @staticmethod
    def update(
        db: Session,
        conversation_id: str,
        update_data: ConversationUpdate
    ) -> Optional[Conversation]:
        """
        Update conversation information

        Args:
            db: Database session
            conversation_id: Conversation UUID
            update_data: Fields to update

        Returns:
            Updated Conversation object or None
        """
        db_conv = ConversationCRUD.get(db, conversation_id)
        if not db_conv:
            return None

        # Handle both dict and Pydantic model inputs
        if isinstance(update_data, dict):
            update_dict = update_data
        else:
            update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(db_conv, field, value)

        db_conv.updated_at = datetime.now()

        db.commit()
        db.refresh(db_conv)

        return db_conv

    @staticmethod
    def update_drhyper_state(
        db: Session,
        conversation_id: str,
        drhyper_state: Dict[str, Any]
    ) -> Optional[Conversation]:
        """
        Update DrHyper state for a conversation

        Args:
            db: Database session
            conversation_id: Conversation UUID
            drhyper_state: DrHyper state dictionary

        Returns:
            Updated Conversation object or None
        """
        db_conv = ConversationCRUD.get(db, conversation_id)
        if not db_conv:
            return None

        db_conv.drhyper_state = drhyper_state
        db_conv.updated_at = datetime.now()

        db.commit()
        db.refresh(db_conv)

        return db_conv

    @staticmethod
    def update_entity_graph_state(
        db: Session,
        conversation_id: str,
        entity_graph_state: Dict[str, Any]
    ) -> Optional[Conversation]:
        """
        Update EntityGraph state for a conversation

        Args:
            db: Database session
            conversation_id: Conversation UUID
            entity_graph_state: EntityGraph state dictionary

        Returns:
            Updated Conversation object or None
        """
        db_conv = ConversationCRUD.get(db, conversation_id)
        if not db_conv:
            return None

        db_conv.entity_graph_state = entity_graph_state
        db_conv.updated_at = datetime.now()

        # Flag the JSON field as modified for SQLAlchemy
        flag_modified(db_conv, "entity_graph_state")

        db.commit()
        db.refresh(db_conv)

        return db_conv

    @staticmethod
    def close(db: Session, conversation_id: str) -> Optional[Conversation]:
        """
        Close a conversation (mark as completed)

        Args:
            db: Database session
            conversation_id: Conversation UUID

        Returns:
            Updated Conversation object or None
        """
        return ConversationCRUD.update(
            db,
            conversation_id,
            ConversationUpdate(status="completed")
        )

    @staticmethod
    def delete(db: Session, conversation_id: str) -> bool:
        """
        Delete a conversation (cascade deletes messages)

        Args:
            db: Database session
            conversation_id: Conversation UUID

        Returns:
            True if deleted, False otherwise
        """
        conv = ConversationCRUD.get(db, conversation_id)
        if not conv:
            return False

        db.delete(conv)
        db.commit()

        return True


# ============================================
# Message CRUD
# ============================================

class MessageCRUD:
    """CRUD operations for Message model"""

    @staticmethod
    def create(db: Session, msg_data: MessageCreate) -> Message:
        """
        Create a new message

        Args:
            db: Database session
            msg_data: Message creation data

        Returns:
            Created Message object
        """
        # Get current max turn number for this conversation
        max_turn = db.query(Message).filter(
            Message.conversation_id == msg_data.conversation_id
        ).count()

        # Convert Pydantic model to dict
        msg_dict = msg_data.model_dump()

        # Add turn number
        msg_dict['turn_number'] = max_turn + 1

        # Ensure lists are not None
        if 'message_metadata' not in msg_dict or msg_dict['message_metadata'] is None:
            msg_dict['message_metadata'] = {}
        if 'image_paths' not in msg_dict or msg_dict['image_paths'] is None:
            msg_dict['image_paths'] = []

        # Create Message instance
        db_msg = Message(**msg_dict)

        # Add to database
        db.add(db_msg)

        # Update conversation's updated_at timestamp
        conv = db.query(Conversation).filter(
            Conversation.conversation_id == msg_data.conversation_id
        ).first()
        if conv:
            conv.updated_at = datetime.now()

        db.commit()
        db.refresh(db_msg)

        return db_msg

    @staticmethod
    def get(db: Session, message_id: int) -> Optional[Message]:
        """
        Get a message by ID

        Args:
            db: Database session
            message_id: Message ID

        Returns:
            Message object or None
        """
        return db.query(Message).filter(Message.id == message_id).first()

    @staticmethod
    def list_by_conversation(
        db: Session,
        conversation_id: str
    ) -> List[Message]:
        """
        Get all messages for a conversation (ordered by turn number)

        Args:
            db: Database session
            conversation_id: Conversation UUID

        Returns:
            List of messages ordered by turn_number
        """
        return db.query(Message).filter(
            Message.conversation_id == conversation_id
        ).order_by(Message.turn_number).all()

    @staticmethod
    def delete(db: Session, message_id: int) -> bool:
        """
        Delete a message

        Args:
            db: Database session
            message_id: Message ID

        Returns:
            True if deleted, False otherwise
        """
        msg = MessageCRUD.get(db, message_id)
        if not msg:
            return False

        db.delete(msg)
        db.commit()

        return True


# ============================================
# Medical Report CRUD
# ============================================

class ReportCRUD:
    """CRUD operations for MedicalReport model"""

    @staticmethod
    def create(db: Session, report_data: ReportCreate) -> MedicalReport:
        """
        Create a new medical report

        Args:
            db: Database session
            report_data: Report creation data

        Returns:
            Created MedicalReport object
        """
        report_dict = report_data.model_dump()
        db_report = MedicalReport(**report_dict)

        db.add(db_report)
        db.commit()
        db.refresh(db_report)

        return db_report

    @staticmethod
    def get(db: Session, report_id: str) -> Optional[MedicalReport]:
        """
        Get a report by ID

        Args:
            db: Database session
            report_id: Report UUID

        Returns:
            MedicalReport object or None
        """
        return db.query(MedicalReport).filter(
            MedicalReport.report_id == report_id
        ).first()

    @staticmethod
    def get_by_conversation(db: Session, conversation_id: str) -> Optional[MedicalReport]:
        """
        Get report by conversation ID

        Args:
            db: Database session
            conversation_id: Conversation UUID

        Returns:
            MedicalReport object or None
        """
        return db.query(MedicalReport).filter(
            MedicalReport.conversation_id == conversation_id
        ).first()

    @staticmethod
    def list_by_patient(
        db: Session,
        patient_id: str,
        skip: int = 0,
        limit: int = 100
    ) -> Tuple[List[MedicalReport], int]:
        """
        Get all reports for a patient

        Args:
            db: Database session
            patient_id: Patient UUID
            skip: Number of records to skip
            limit: Maximum number of records

        Returns:
            Tuple of (report list, total count)
        """
        query = db.query(MedicalReport).filter(
            MedicalReport.patient_id == patient_id
        )

        total = query.count()
        reports = query.order_by(
            desc(MedicalReport.created_at)
        ).offset(skip).limit(limit).all()

        return reports, total

    @staticmethod
    def get_approved_by_patient(db: Session, patient_id: str, limit: int = 10) -> List[MedicalReport]:
        """
        Get approved reports for a patient

        Args:
            db: Database session
            patient_id: Patient UUID
            limit: Maximum number of records

        Returns:
            List of approved MedicalReport objects
        """
        return db.query(MedicalReport).filter(
            MedicalReport.patient_id == patient_id,
            MedicalReport.status == "approved"
        ).order_by(desc(MedicalReport.created_at)).limit(limit).all()

    @staticmethod
    def approve(
        db: Session,
        report_id: str,
        approval: ReportApproval
    ) -> Optional[MedicalReport]:
        """
        Approve or reject a report

        Args:
            db: Database session
            report_id: Report UUID
            approval: Approval data with approved flag and notes

        Returns:
            Updated MedicalReport object or None
        """
        report = ReportCRUD.get(db, report_id)
        if not report:
            return None

        if approval.approved:
            report.status = "approved"
            report.approved_at = datetime.now()
        else:
            report.status = "rejected"

        report.updated_at = datetime.now()
        db.commit()
        db.refresh(report)

        return report

    @staticmethod
    def update(
        db: Session,
        report_id: str,
        update_data: ReportUpdate
    ) -> Optional[MedicalReport]:
        """
        Update report content

        Args:
            db: Database session
            report_id: Report UUID
            update_data: Fields to update

        Returns:
            Updated MedicalReport object or None
        """
        report = ReportCRUD.get(db, report_id)
        if not report:
            return None

        update_dict = update_data.model_dump(exclude_unset=True)
        for field, value in update_dict.items():
            setattr(report, field, value)

        report.updated_at = datetime.now()
        db.commit()
        db.refresh(report)

        return report

    @staticmethod
    def delete(db: Session, report_id: str) -> bool:
        """
        Delete a report

        Args:
            db: Database session
            report_id: Report UUID

        Returns:
            True if deleted, False otherwise
        """
        report = ReportCRUD.get(db, report_id)
        if not report:
            return False

        db.delete(report)
        db.commit()

        return True


# ============================================
# Export CRUD instances
# ============================================

# Singleton instances for convenient access
patient_crud = PatientCRUD()
conversation_crud = ConversationCRUD()
message_crud = MessageCRUD()
report_crud = ReportCRUD()
