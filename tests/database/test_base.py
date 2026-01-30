"""
Test database connection and basic functionality
"""
import pytest
from backend.database.base import get_database_info, engine, Base


@pytest.mark.unit
def test_database_connection():
    """Test that database connection works"""
    info = get_database_info()

    assert info is not None
    assert "url" in info
    assert "driver" in info
    assert info["driver"] in ["sqlite", "postgresql"]


@pytest.mark.unit
def test_database_tables_exist():
    """Test that all required tables exist"""
    # Get table names from metadata
    tables = list(Base.metadata.tables.keys())

    # Check required tables exist
    assert "patients" in tables
    assert "conversations" in tables
    assert "messages" in tables


@pytest.mark.unit
def test_database_session(db_session):
    """Test that database session works"""
    # Simple query to test session
    from backend.database.models import Patient

    # Should not raise any errors
    patients = db_session.query(Patient).all()

    # Result should be a list
    assert isinstance(patients, list)


@pytest.mark.unit
def test_database_url_format():
    """Test that database URL is correctly formatted"""
    info = get_database_info()
    url = info["url"]

    # Check URL starts with expected scheme
    assert url.startswith("sqlite:///") or url.startswith("postgresql://")
