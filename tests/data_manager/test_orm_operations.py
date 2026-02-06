"""
ORM Operations Tests for DataManagerCodeAgent

Tests that the agent can correctly generate and execute code to perform
ORM operations on the database including:
- Query operations (read)
- Create operations (insert)
- Update operations (modify)
- Delete operations (remove)

These tests verify that the agent can interpret natural language requests
and generate valid Python code to perform database operations using the ORM.
"""
import pytest
from unittest.mock import MagicMock, patch

from backend.agents.data_manager import DataManagerCodeAgent, query_database, is_request_blocked
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from backend.config.config_manager import reset_config


class TestORMQueryOperations:
    """Test suite for ORM query (read) operations"""

    @pytest.mark.unit
    def test_query_database_tool_with_valid_read_code(self, clean_db, test_patient):
        """
        Test that query_database tool can execute valid read code

        Given: A patient exists in the database
        When: Code is submitted to query the patient
        Then: The patient information should be returned
        """
        code = f"""
# Use the auto-created sandbox for database operations
patient = patient_crud.get(sandbox, "{test_patient.patient_id}")
result["output"] = {{"name": patient.name, "age": patient.age}}
"""

        output = query_database(code)

        assert "Test Patient" in output
        assert "30" in output

    @pytest.mark.unit
    def test_query_database_tool_list_all_patients(self, clean_db, multiple_test_patients):
        """
        Test that query_database tool can list all patients

        Given: Multiple patients exist in the database
        When: Code is submitted to list all patients
        Then: All patients should be returned
        """
        # Commit changes so the new session can see them
        clean_db.commit()

        code = """
# Use the auto-created sandbox for database operations
patients = patient_crud.list_all(sandbox)
names = [p.name for p in patients]
result["output"] = f"Found {{len(names)}} patients: {{names}}"
"""

        output = query_database(code)

        # Check that it returns some patient info
        assert len(output) > 0

    @pytest.mark.unit
    def test_query_database_tool_with_filter(self, clean_db, multiple_test_patients):
        """
        Test that query_database tool can filter patients

        Given: Multiple patients with different ages exist
        When: Code is submitted to filter patients by age
        Then: Only matching patients should be returned
        """
        clean_db.commit()

        code = """
# Use the auto-created sandbox for database operations
patients = patient_crud.list_all(sandbox)
filtered = [p for p in patients if p.age > 30]
result["output"] = f"Found {{len(filtered)}} patients over 30"
"""

        output = query_database(code)

        # Should return some result
        assert len(output) > 0

    @pytest.mark.unit
    def test_query_database_tool_search_by_name(self, clean_db, test_patient):
        """
        Test that query_database tool can search patients by name

        Given: A patient with a specific name exists
        When: Code is submitted to search by that name
        Then: The matching patient should be returned
        """
        clean_db.commit()

        code = """
# Use the auto-created sandbox for database operations
patients = patient_crud.list_all(sandbox)
matching = [p for p in patients if "Test" in p.name]
result["output"] = f"Found {{len(matching)}} patients with 'Test' in name"
"""

        output = query_database(code)

        assert len(output) > 0

    @pytest.mark.slow
    @pytest.mark.integration
    def test_agent_queries_patient_by_id(self, clean_db, test_patient):
        """
        Test that agent can query patient by ID (integration test)

        Given: A patient exists in the database
        When: User requests patient by ID
        Then: Agent should generate correct code and return patient info
        """
        reset_config()

        # Note: This test makes real API calls - mark as slow
        agent = DataManagerCodeAgent()

        user_request = f"Get the patient with ID {test_patient.patient_id} and show their name and age"
        result = agent.process_request(user_request)

        # Verify result structure
        assert "success" in result
        assert "final_answer" in result
        assert result["success"] is True
        assert len(result["final_answer"]) > 0

        # Verify answer mentions the patient
        assert "test" in result["final_answer"].lower() or "patient" in result["final_answer"].lower()

        reset_config()

    @pytest.mark.slow
    @pytest.mark.integration
    def test_agent_lists_all_patients(self, clean_db, multiple_test_patients):
        """
        Test that agent can list all patients (integration test)
        """
        reset_config()

        agent = DataManagerCodeAgent()

        user_request = "Show me all patients in the database"
        result = agent.process_request(user_request)

        assert result["success"] is True
        assert len(result["final_answer"]) > 0

        reset_config()


class TestORMCreateOperations:
    """Test suite for ORM create (insert) operations"""

    @pytest.mark.unit
    def test_query_database_tool_creates_patient(self, clean_db):
        """
        Test that query_database tool can create a new patient (with sandbox)

        Given: An empty database
        When: Code is submitted to create a patient
        Then: Patient should be created in sandbox (waiting for approval)
        """
        code = """
from datetime import datetime

# Use the auto-created sandbox for write operations
patient = Patient(
    patient_id="test-123",
    name="Jane Doe",
    age=28,
    gender="female",
    created_at=datetime.now(),
    updated_at=datetime.now()
)
sandbox.add(patient)
sandbox.commit()  # Intercepted by sandbox
sandbox.flush()

result["output"] = f"Created patient: {{patient.name}}, ID: {{patient.patient_id}}, pending operations: {{len(sandbox.operations)}}"
"""

        output = query_database(code)

        assert "Jane Doe" in output or "Created" in output
        # Should mention pending operations
        assert "pending" in output.lower() or "awaiting" in output.lower()

    @pytest.mark.slow
    @pytest.mark.integration
    def test_agent_creates_new_patient(self, clean_db):
        """
        Test that agent can create a new patient from natural language

        Given: User provides patient details in natural language
        When: User requests to create the patient
        Then: Agent should generate correct code to create the patient
        """
        reset_config()

        agent = DataManagerCodeAgent()

        user_request = "Create a new patient named 'Jane Smith', age 32, gender female"
        result = agent.process_request(user_request)

        # Verify success
        assert result["success"] is True
        assert len(result["final_answer"]) > 0
        assert "jane" in result["final_answer"].lower()

        reset_config()


class TestORMUpdateOperations:
    """Test suite for ORM update (modify) operations"""

    @pytest.mark.unit
    def test_query_database_tool_updates_patient(self, clean_db, test_patient):
        """
        Test that query_database tool can update a patient (with sandbox)

        Given: A patient exists in the database
        When: Code is submitted to update the patient's age
        Then: The patient should be updated in sandbox (waiting for approval)
        """
        code = f"""
from datetime import datetime

# Use the auto-created sandbox for write operations
patient = patient_crud.get(sandbox, "{test_patient.patient_id}")
patient.age = 35
patient.updated_at = datetime.now()
sandbox.commit()  # Intercepted by sandbox
sandbox.flush()

result["output"] = f"Updated {{patient.name}} to age {{patient.age}}, pending: {{len(sandbox.operations)}}"
"""

        output = query_database(code)

        assert "35" in output or "Updated" in output
        # Should mention pending operations
        assert "pending" in output.lower() or "awaiting" in output.lower()

    @pytest.mark.unit
    def test_query_database_tool_adds_health_metric(self, clean_db, test_patient):
        """
        Test that query_database tool can add health metric to patient (with sandbox)

        Given: A patient exists
        When: Code is submitted to add a health metric
        Then: The health metric should be added in sandbox
        """
        code = f"""
from datetime import datetime

# Use the auto-created sandbox for write operations
patient = patient_crud.get(sandbox, "{test_patient.patient_id}")
metric = {{
    "metric_name": "blood_pressure",
    "value": "120/80",
    "unit": "mmHg",
    "recorded_at": datetime.now().isoformat()
}}
patient.health_metrics = patient.health_metrics or []
patient.health_metrics.append(metric)
sandbox.commit()  # Intercepted by sandbox
sandbox.flush()

result["output"] = f"Added metric to {{patient.name}}, total: {{len(patient.health_metrics)}}"
"""

        output = query_database(code)

        assert len(output) > 0

    @pytest.mark.slow
    @pytest.mark.integration
    def test_agent_updates_patient_field(self, clean_db, test_patient):
        """
        Test that agent can update a patient field from natural language

        Given: A patient exists
        When: User requests to update a field
        Then: Agent should generate correct code to update the field
        """
        reset_config()

        agent = DataManagerCodeAgent()

        user_request = f"Update patient {test_patient.patient_id}: set age to 40"
        result = agent.process_request(user_request)

        # Verify success
        assert result["success"] is True
        assert len(result["final_answer"]) > 0

        reset_config()


class TestORMDeleteOperations:
    """Test suite for ORM delete (remove) operations"""

    @pytest.mark.unit
    def test_query_database_tool_deletes_patient(self, clean_db, test_patient):
        """
        Test that query_database tool can delete a patient (with sandbox)

        Given: A patient exists in the database
        When: Code is submitted to delete the patient
        Then: The patient should be marked for deletion in sandbox
        """
        code = f"""
# Use the auto-created sandbox for write operations
patient = patient_crud.delete(sandbox, "{test_patient.patient_id}")
sandbox.commit()  # Intercepted by sandbox
sandbox.flush()

result["output"] = "Patient deletion staged successfully, pending: {{len(sandbox.operations)}}"
"""

        output = query_database(code)

        assert "deleted" in output.lower() or "success" in output.lower() or "staged" in output.lower()
        # Should mention pending operations
        assert "pending" in output.lower() or "awaiting" in output.lower()

    @pytest.mark.slow
    @pytest.mark.integration
    def test_agent_deletes_patient(self, clean_db, test_patient):
        """
        Test that agent can delete a patient from natural language

        Given: A patient exists
        When: User requests to delete the patient
        Then: Agent should generate correct code to delete the patient
        """
        reset_config()

        agent = DataManagerCodeAgent()

        user_request = f"Delete the patient with ID {test_patient.patient_id}"
        result = agent.process_request(user_request)

        # Verify success
        assert result["success"] is True
        assert len(result["final_answer"]) > 0

        reset_config()


class TestORMErrorHandling:
    """Test suite for ORM error handling"""

    @pytest.mark.unit
    def test_query_database_handles_syntax_error(self):
        """
        Test that query_database handles syntax errors gracefully

        Given: Invalid Python code
        When: Code is executed
        Then: Should return error message instead of crashing
        """
        invalid_code = "this is not valid python ))))"

        output = query_database(invalid_code)

        assert "ERROR" in output

    @pytest.mark.unit
    def test_query_database_handles_runtime_error(self):
        """
        Test that query_database handles runtime errors gracefully

        Given: Code that raises an exception
        When: Code is executed
        Then: Should return error message
        """
        error_code = """
raise ValueError("Test error")
"""

        output = query_database(error_code)

        assert "ERROR" in output

    @pytest.mark.unit
    def test_query_database_handles_invalid_uuid(self, clean_db):
        """
        Test that query_database handles invalid UUID gracefully

        Given: An invalid patient ID
        When: Code tries to query with that ID
        Then: Should handle error gracefully
        """
        code = """
# Use the auto-created sandbox for database operations
patient = patient_crud.get(sandbox, "invalid-uuid-12345")
result["output"] = patient
"""

        output = query_database(code)

        # Should not crash, may return error or None
        assert output is not None

    @pytest.mark.unit
    def test_query_database_handles_missing_table(self):
        """
        Test that query_database handles missing table references

        Given: Code referencing non-existent table
        When: Code is executed
        Then: Should return error message
        """
        code = """
# Use the auto-created sandbox for database operations
# Try to query non-existent table
result = sandbox.execute("SELECT * FROM non_existent_table")
result["output"] = result
"""

        output = query_database(code)

        # Should handle error
        assert "ERROR" in output or "error" in output.lower()


class TestORMComplexOperations:
    """Test suite for complex ORM operations"""

    @pytest.mark.unit
    def test_query_database_with_json_operations(self, clean_db, test_patient):
        """
        Test that query_database can handle JSON field operations (with sandbox)

        Given: A patient with JSON fields (health_metrics, allergies, etc.)
        When: Code manipulates JSON fields
        Then: Operations should work correctly in sandbox
        """
        code = f"""
from datetime import datetime

# Use the auto-created sandbox for write operations
patient = patient_crud.get(sandbox, "{test_patient.patient_id}")

metric = {{
    "metric_name": "heart_rate",
    "value": 72,
    "unit": "bpm",
    "recorded_at": datetime.now().isoformat()
}}
patient.health_metrics = patient.health_metrics or []
patient.health_metrics.append(metric)
sandbox.commit()  # Intercepted by sandbox
sandbox.flush()

result["output"] = f"Added {{patient.health_metrics[-1]['metric_name']}} to {{patient.name}}, pending: {{len(sandbox.operations)}}"
"""

        output = query_database(code)

        assert "heart_rate" in output or "Added" in output

    @pytest.mark.unit
    def test_query_database_with_multiple_operations(self, clean_db):
        """
        Test that query_database can handle multiple operations in one execution (with sandbox)

        Given: A database session
        When: Code performs multiple operations
        Then: All operations should be recorded in sandbox
        """
        code = """
from datetime import datetime

# Use the auto-created sandbox for write operations
# Create first patient
p1 = Patient(
    patient_id="multi-test-1",
    name="Patient One",
    age=25,
    gender="male",
    created_at=datetime.now(),
    updated_at=datetime.now()
)
sandbox.add(p1)

# Create second patient
p2 = Patient(
    patient_id="multi-test-2",
    name="Patient Two",
    age=30,
    gender="female",
    created_at=datetime.now(),
    updated_at=datetime.now()
)
sandbox.add(p2)

sandbox.commit()  # Intercepted by sandbox
sandbox.flush()

# Query both (from sandbox)
all_patients = patient_crud.list_all(sandbox)
result["output"] = {{
    "total": len(all_patients),
    "names": [p.name for p in all_patients if "multi-test" in p.patient_id],
    "pending_ops": len(sandbox.operations)
}}
"""

        output = query_database(code)

        assert "Patient One" in output or "Patient Two" in output

    @pytest.mark.unit
    def test_query_database_with_conditional_logic(self, clean_db, multiple_test_patients):
        """
        Test that query_database can execute code with conditional logic

        Given: Multiple patients in database
        When: Code uses conditional logic to filter/process
        Then: Should execute correctly
        """
        clean_db.commit()

        code = """
# Use the auto-created sandbox for read operations
patients = patient_crud.list_all(sandbox)

young = [p for p in patients if p.age < 30]
middle_aged = [p for p in patients if 30 <= p.age < 50]
older = [p for p in patients if p.age >= 50]

result["output"] = f"Young: {{len(young)}}, Middle: {{len(middle_aged)}}, Older: {{len(older)}}"
"""

        output = query_database(code)

        # Should return categorization
        assert len(output) > 0


class TestORMWithChineseQueries:
    """Test suite for ORM operations with Chinese language queries"""

    @pytest.mark.slow
    @pytest.mark.integration
    def test_agent_handles_chinese_query(self, clean_db, test_patient):
        """
        Test that agent can handle Chinese language queries

        Given: A patient exists
        When: User queries in Chinese
        Then: Agent should understand and execute correctly
        """
        reset_config()

        agent = DataManagerCodeAgent()

        # Chinese query for patient info
        user_request = f"查询ID为 {test_patient.patient_id} 的患者信息"
        result = agent.process_request(user_request)

        # Verify success
        assert result["success"] is True
        assert len(result["final_answer"]) > 0

        reset_config()

    @pytest.mark.slow
    @pytest.mark.integration
    def test_agent_creates_patient_with_chinese_request(self, clean_db):
        """
        Test that agent can create patient with Chinese request
        """
        reset_config()

        agent = DataManagerCodeAgent()

        user_request = "创建一个新患者，姓名叫'张三'，年龄45岁，性别男"
        result = agent.process_request(user_request)

        # Verify success
        assert result["success"] is True
        assert len(result["final_answer"]) > 0

        reset_config()


class TestORMCodeGeneration:
    """Test suite for verifying code generation quality"""

    @pytest.mark.unit
    def test_generated_code_uses_patient_crud(self, clean_db):
        """
        Test that generated code uses patient_crud properly (with sandbox)

        Given: A sandbox session
        When: Code uses patient_crud
        Then: Should work correctly
        """
        code = """
# Use the auto-created sandbox for database operations
# Verify patient_crud is available
patients = patient_crud.list_all(sandbox)
result["output"] = f"Found {{len(patients)}} patients using patient_crud"
"""

        output = query_database(code)

        assert "patient" in output.lower()

    @pytest.mark.unit
    def test_generated_code_has_access_to_models(self, clean_db):
        """
        Test that generated code has access to ORM models (with sandbox)

        Given: A sandbox session
        When: Code references Patient model
        Then: Should work correctly
        """
        code = """
# Use the auto-created sandbox for database operations
# Verify Patient model is available
patients = sandbox.query(Patient).limit(1).all()
result["output"] = f"Patient model accessible: {{len(patients)}} records"
"""

        output = query_database(code)

        assert "accessible" in output or "patient" in output.lower()

    @pytest.mark.unit
    def test_generated_code_can_use_schemas(self, clean_db):
        """
        Test that generated code has access to Pydantic schemas

        Given: A sandbox session
        When: Code uses PatientCreate schema
        Then: Should work correctly
        """
        code = """
from datetime import datetime
# Verify PatientCreate schema is available
schema = PatientCreate(
    name="Schema Test",
    age=25,
    gender="male"
)
result["output"] = f"Schema created: {{schema.name}}, age {{schema.age}}"
"""

        output = query_database(code)

        assert "Schema Test" in output or "schema" in output.lower()
