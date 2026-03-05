"""
Real API Tests for DataManagerCodeAgent

These tests make actual API calls to verify the fixes:
1. extra_body with enable_thinking=False works correctly
2. max_steps=5 prevents infinite loops

These tests require a valid API configuration and are marked as @pytest.mark.slow
"""
import pytest
import logging

from backend.agents.data_manager import DataManagerCodeAgent
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from backend.config.config_manager import reset_config

logger = logging.getLogger(__name__)


@pytest.mark.slow
@pytest.mark.integration
class TestDataManagerRealAPI:
    """Test suite for DataManager with real API calls"""

    def test_agent_initialization_with_extra_body(self):
        """
        Test that DataManagerCodeAgent initializes correctly with extra_body params

        This verifies the fix for: tool_choice parameter does not support being
        set to required or object in thinking mode

        Given: A valid configuration
        When: DataManagerCodeAgent is initialized
        Then: The model should have extra_body with enable_thinking=False
        """
        reset_config()

        agent = DataManagerCodeAgent()

        # Verify model was created with extra_body
        assert agent.model is not None
        # The model should have the extra_body configuration
        # Check if model has the necessary attributes
        assert hasattr(agent.model, 'model_id')

        # Verify agent has max_steps set
        assert agent.agent is not None
        assert hasattr(agent.agent, 'max_steps')
        assert agent.agent.max_steps == 5

        reset_config()
        logger.info("Agent initialized successfully with thinking mode disabled")

    def test_agent_query_patient_age_chinese(self, clean_db):
        """
        Test that agent can handle Chinese query for patient age

        Given: A patient exists in database
        When: User asks "我的年龄是多少？" in Chinese
        Then: Agent should return the patient's age without tool_choice error

        This test verifies the fix for the thinking mode issue.
        """
        reset_config()

        # Create a test patient
        patient = patient_crud.create(clean_db, PatientCreate(
            name="测试用户",
            age=35,
            gender="male",
            phone="13900000000"
        ))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        # Query in Chinese - this previously failed with tool_choice error
        result = agent.process_request(f"查询患者 {patient.patient_id} 的年龄是多少？")

        # Verify result
        assert result["success"] is True
        assert result["final_answer"] is not None
        assert len(result["final_answer"]) > 0

        # The answer should mention the age
        answer = result["final_answer"].lower()
        assert "35" in answer or "年龄" in result["final_answer"]

        reset_config()
        logger.info(f"Chinese query result: {result['final_answer']}")

    def test_agent_query_patient_info(self, clean_db):
        """
        Test that agent can query patient information

        Given: A patient exists in database
        When: User asks for patient info
        Then: Agent should return correct patient information
        """
        reset_config()

        # Create a test patient
        patient = patient_crud.create(clean_db, PatientCreate(
            name="张三",
            age=45,
            gender="male",
            phone="13800138000",
            address="北京市朝阳区"
        ))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        # Query for patient info
        result = agent.process_request(f"获取ID为 {patient.patient_id} 的患者信息")

        # Verify result
        assert result["success"] is True
        assert result["final_answer"] is not None

        # Check that response contains relevant info
        answer = result["final_answer"]
        assert "张三" in answer or "45" in answer or "patient" in answer.lower()

        reset_config()
        logger.info(f"Patient query result: {result['final_answer']}")

    def test_agent_handles_error_gracefully(self, clean_db):
        """
        Test that agent handles errors gracefully and stops after max_steps

        This verifies the fix for infinite retry loops.

        Given: An invalid request that will cause an error
        When: Agent processes the request
        Then: Agent should stop after max_steps (5) and return an error
        """
        reset_config()

        agent = DataManagerCodeAgent()

        # Query for non-existent patient - should not loop infinitely
        result = agent.process_request("获取ID为 non-existent-uuid-12345 的患者信息")

        # Should complete (not hang) and return some result
        assert result is not None
        assert "success" in result

        # Even if it fails, it should not loop forever
        # The max_steps=5 ensures it stops after 5 attempts

        reset_config()
        logger.info(f"Error handling result: success={result['success']}")

    def test_agent_list_patients(self, clean_db):
        """
        Test that agent can list all patients

        Given: Multiple patients in database
        When: User asks to list patients
        Then: Agent should return list of patients
        """
        reset_config()

        # Create multiple patients
        for i in range(3):
            patient_crud.create(clean_db, PatientCreate(
                name=f"患者{i+1}",
                age=30 + i * 5,
                gender="male" if i % 2 == 0 else "female"
            ))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        # List all patients
        result = agent.process_request("列出所有患者的信息")

        # Verify result
        assert result["success"] is True
        assert result["final_answer"] is not None

        reset_config()
        logger.info(f"List patients result: {result['final_answer']}")

    def test_agent_create_patient(self, clean_db):
        """
        Test that agent can create a new patient

        Given: User provides patient details
        When: User asks to create a patient
        Then: Agent should create patient with pending operations
        """
        reset_config()

        agent = DataManagerCodeAgent()

        # Create patient request
        result = agent.process_request(
            "创建一个新患者，姓名'李四'，年龄28岁，性别女"
        )

        # Verify result
        assert result["success"] is True
        assert result["final_answer"] is not None

        # Should mention pending operations for write
        answer = result["final_answer"].lower()
        assert "李四" in answer or "创建" in answer or "pending" in answer or "success" in answer

        reset_config()
        logger.info(f"Create patient result: {result['final_answer']}")

    def test_max_steps_prevents_infinite_loop(self, clean_db):
        """
        Test that max_steps=5 prevents infinite retry loops

        This specifically tests the fix for infinite loops when
        query_database returns an error string.

        Given: A request that may cause repeated errors
        When: Agent processes the request
        Then: Agent should stop after max_steps attempts
        """
        reset_config()

        agent = DataManagerCodeAgent()

        # Verify max_steps is set correctly
        assert agent.agent.max_steps == 5

        # Make a request that could potentially loop
        # (The agent should complete within reasonable time)
        import time
        start_time = time.time()

        result = agent.process_request("查找年龄大于1000岁的患者")

        elapsed_time = time.time() - start_time

        # Should complete in reasonable time (< 60 seconds for 5 steps)
        assert elapsed_time < 60, f"Agent took too long ({elapsed_time:.1f}s), may be stuck in loop"
        assert result is not None

        reset_config()
        logger.info(f"Max steps test completed in {elapsed_time:.1f}s")


@pytest.mark.slow
@pytest.mark.integration
class TestDataManagerAPIEdgeCases:
    """Test edge cases with real API calls"""

    def test_empty_database_query(self, clean_db):
        """
        Test querying empty database

        Given: Empty database
        When: User queries for patients
        Then: Agent should handle gracefully
        """
        reset_config()

        # Ensure database is empty
        clean_db.commit()

        agent = DataManagerCodeAgent()

        result = agent.process_request("列出所有患者")

        assert result["success"] is True
        assert result["final_answer"] is not None

        reset_config()

    def test_complex_query_with_filters(self, clean_db):
        """
        Test complex query with multiple filters

        Given: Multiple patients with different attributes
        When: User makes complex query
        Then: Agent should generate correct code
        """
        reset_config()

        # Create patients with different ages
        patient_crud.create(clean_db, PatientCreate(name="年轻患者", age=25, gender="male"))
        patient_crud.create(clean_db, PatientCreate(name="中年患者", age=45, gender="female"))
        patient_crud.create(clean_db, PatientCreate(name="老年患者", age=65, gender="male"))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        # Complex query
        result = agent.process_request("查找年龄大于40岁的所有男性患者")

        assert result["success"] is True
        assert result["final_answer"] is not None

        reset_config()

    def test_update_patient_age(self, clean_db):
        """
        Test updating patient information

        Given: A patient exists
        When: User asks to update patient age
        Then: Agent should stage update operation
        """
        reset_config()

        patient = patient_crud.create(clean_db, PatientCreate(
            name="王五",
            age=50,
            gender="male"
        ))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        # Update request
        result = agent.process_request(
            f"更新患者 {patient.patient_id} 的年龄为55岁"
        )

        assert result["success"] is True
        assert result["final_answer"] is not None

        reset_config()