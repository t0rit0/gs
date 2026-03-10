"""
Database module for data persistence

Models are imported here to ensure they are registered with Base.metadata
when the database module is imported.
"""

# Import models to register them with Base.metadata
# This ensures tables are created when init_database() is called
from backend.database.models import Patient, Conversation, Message, MedicalReport

__all__ = ["Patient", "Conversation", "Message", "MedicalReport"]
