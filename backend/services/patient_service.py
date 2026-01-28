"""
Patient Service - Patient Management Service

Provides business logic layer for patient information
"""
from typing import List, Tuple
from sqlalchemy.orm import Session

from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate, PatientUpdate
from drhyper.utils.logging import get_logger

logger = get_logger("PatientService")


class PatientService:
    """Patient Service - Encapsulates patient-related business logic"""

    @staticmethod
    def create_patient(db: Session, patient_data: PatientCreate):
        """
        Create a new patient

        Args:
            db: Database session
            patient_data: Patient creation data

        Returns:
            Created patient object
        """
        logger.info(f"Creating patient: {patient_data.name}")
        return patient_crud.create(db, patient_data)

    @staticmethod
    def get_patient(db: Session, patient_id: str):
        """
        Get patient information

        Args:
            db: Database session
            patient_id: Patient ID

        Returns:
            Patient object or None
        """
        return patient_crud.get(db, patient_id)

    @staticmethod
    def list_patients(
        db: Session,
        skip: int = 0,
        limit: int = 100,
        search: str = None
    ) -> Tuple[List, int]:
        """
        Get patient list (supports pagination and search)

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            search: Search keyword (patient name)

        Returns:
            (patient list, total count)
        """
        return patient_crud.list_all(db, skip=skip, limit=limit, search=search)

    @staticmethod
    def update_patient(
        db: Session,
        patient_id: str,
        update_data: PatientUpdate
    ):
        """
        Update patient information

        Args:
            db: Database session
            patient_id: Patient ID
            update_data: Update data

        Returns:
            Updated patient object or None
        """
        logger.info(f"Updating patient {patient_id}")
        return patient_crud.update(db, patient_id, update_data)

    @staticmethod
    def add_medical_history(
        db: Session,
        patient_id: str,
        condition: str,
        status: str,
        notes: str = None
    ):
        """
        Add patient medical history record

        Args:
            db: Database session
            patient_id: Patient ID
            condition: Disease/condition
            status: Status
            notes: Notes

        Returns:
            Updated patient object or None
        """
        logger.info(f"Adding medical history for patient {patient_id}: {condition}")
        return patient_crud.add_medical_history(
            db, patient_id, condition, status, notes
        )

    @staticmethod
    def add_health_metric(
        db: Session,
        patient_id: str,
        metric_name: str,
        value: float,
        unit: str,
        notes: str = None
    ):
        """
        Add health metric record

        Args:
            db: Database session
            patient_id: Patient ID
            metric_name: Metric name (e.g., "Systolic Blood Pressure")
            value: Measured value
            unit: Unit (e.g., "mmHg")
            notes: Notes

        Returns:
            Updated patient object or None
        """
        logger.info(f"Adding health metric for patient {patient_id}: {metric_name}={value}{unit}")
        return patient_crud.add_health_metric(
            db, patient_id, metric_name, value, unit, notes
        )

    @staticmethod
    def delete_patient(db: Session, patient_id: str) -> bool:
        """
        Delete patient (cascades to conversations and messages)

        Args:
            db: Database session
            patient_id: Patient ID

        Returns:
            Whether deletion was successful
        """
        logger.warning(f"Deleting patient {patient_id}")
        return patient_crud.delete(db, patient_id)


# Export singleton
patient_service = PatientService()
