"""Patient Context Builder (Simplified)

Reads text information from patient records to provide context during EntityGraph initialization.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.database.models import Patient, MedicalReport


@dataclass
class PatientContext:
    """Patient context (simplified)"""
    patient_id: str
    basic_info: Dict[str, Any]
    # Raw text records for LLM context during initialization
    patient_text_records: Dict[str, str] = field(default_factory=dict)


class PatientContextBuilder:
    """Patient context builder (simplified)

    Only reads patient basic information and text records, does not parse structured data.
    """

    def __init__(
        self,
        max_text_records: int = 50,
        max_historical_reports: int = 10
    ):
        """
        Args:
            max_text_records: Maximum number of text records to include
            max_historical_reports: Maximum number of historical reports to load
        """
        self.max_text_records = max_text_records
        self.max_historical_reports = max_historical_reports

    def build(self, db: Session, patient_id: str) -> PatientContext:
        """
        Build context from patient records

        Args:
            db: Database session
            patient_id: Patient ID

        Returns:
            PatientContext containing patient basic info and text records
        """
        # Load patient data
        patient = db.query(Patient).filter(
            Patient.patient_id == patient_id
        ).first()

        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        # Build basic info
        basic_info = {
            "name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "phone": patient.phone,
            "address": patient.address
        }

        # Collect text records
        patient_text_records = {}

        # Add various text records (up to max_text_records entries)
        self._add_text_record(patient_text_records, "medical_history", patient.medical_history)
        self._add_text_record(patient_text_records, "allergies", patient.allergies)
        self._add_text_record(patient_text_records, "medications", patient.medications)
        self._add_text_record(patient_text_records, "family_history", patient.family_history)
        self._add_text_record(patient_text_records, "health_metrics", patient.health_metrics)

        # Load approved historical reports
        self._add_historical_reports(db, patient_id, patient_text_records)

        return PatientContext(
            patient_id=patient_id,
            basic_info=basic_info,
            patient_text_records=patient_text_records
        )

    def _add_text_record(
        self,
        records: Dict[str, str],
        field_name: str,
        value: Any
    ) -> None:
        """
        Add text record to dictionary

        Args:
            records: Records dictionary
            field_name: Field name
            value: Field value (can be list or single value)
        """
        if not value:
            return

        # Convert value to string
        if isinstance(value, list):
            # If it's a list (like medical_history), merge into text
            text_value = "\n".join([
                f"- {item}" if isinstance(item, dict) else str(item)
                for item in value
            ])
        elif isinstance(value, dict):
            # If it's a dict, format as text
            parts = [f"{k}: {v}" for k, v in value.items()]
            text_value = "; ".join(parts)
        else:
            # Convert directly to string
            text_value = str(value)

        # Only add non-empty records
        if text_value.strip():
            records[field_name] = text_value

    def _add_historical_reports(
        self,
        db: Session,
        patient_id: str,
        records: Dict[str, str]
    ) -> None:
        """
        Load approved historical reports and add them to patient text records

        Args:
            db: Database session
            patient_id: Patient ID
            records: Records dictionary to update
        """
        try:
            # Query approved reports for this patient, ordered by date (newest first)
            reports = db.query(MedicalReport).filter(
                MedicalReport.patient_id == patient_id,
                MedicalReport.status == "approved"
            ).order_by(MedicalReport.created_at.desc()).limit(self.max_historical_reports).all()

            # Add each report as a text record
            for i, report in enumerate(reports):
                report_key = f"historical_report_{i+1}"
                records[report_key] = self._format_report_as_text(report)

        except Exception as e:
            # Log error but don't fail the context building
            import logging
            logging.getLogger(__name__).warning(f"Failed to load historical reports: {e}")

    def _format_report_as_text(self, report: MedicalReport) -> str:
        """
        Format a medical report as text for LLM context

        Args:
            report: MedicalReport instance

        Returns:
            Formatted text string
        """
        date_str = report.created_at.strftime("%Y-%m-%d") if report.created_at else "Unknown date"

        # Prefer full_report if available (new format)
        if report.full_report:
            return f"[Historical Consultation Record - {date_str}]\n\n{report.full_report}"

        # Fall back to structured fields (old format)
#         text = f"""[Historical Consultation Record - {date_str}]
# Summary: {report.summary or 'Not specified'}
# Key Findings: {report.key_findings or 'Not specified'}
# Recommendations: {report.recommendations or 'Not specified'}
# Follow-up: {report.follow_up or 'Not specified'}"""
#         return text
