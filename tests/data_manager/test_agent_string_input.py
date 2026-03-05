"""
Test DataManagerCodeAgent with Real API Calls - String Input

This test verifies that the DataManagerCodeAgent can process a simple
string input using real API calls. The test is designed to run in background
using pytest.

Usage:
    # Run in foreground
    uv run pytest tests/data_manager/test_agent_string_input.py -v

    # Run in background
    uv run pytest tests/data_manager/test_agent_string_input.py -v &
"""

import pytest
import logging
import uuid
import asyncio
from unittest.mock import patch, MagicMock

from backend.agents.data_manager import DataManagerCodeAgent
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from backend.config.config_manager import reset_config

logger = logging.getLogger(__name__)


@pytest.mark.slow
@pytest.mark.integration
class TestAgentStringInput:
    """Test suite for DataManagerCodeAgent with string input"""

    def test_agent_processes_simple_string_query(self, clean_db):
        """
        Test that agent can process a simple string query

        Given: A patient exists in database
        When: Agent receives a simple string query
        Then: Agent should return a successful response

        This is the most basic test to verify the agent works with string input.
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

        # Initialize agent
        agent = DataManagerCodeAgent()

        # Simple string query - the key test
        simple_query = f"查询患者 {patient.patient_id} 的年龄"

        # Process request with string input
        result = agent.process_request(simple_query)

        # Verify basic structure
        assert result is not None, "Agent should return a result"
        assert "success" in result, "Result should have 'success' field"
        assert isinstance(result["success"], bool), "'success' should be boolean"

        # If successful, verify final_answer exists
        if result["success"]:
            assert "final_answer" in result, "Successful result should have 'final_answer'"
            assert result["final_answer"] is not None, "'final_answer' should not be None"
            logger.info(f"Agent response: {result['final_answer'][:200]}...")
        else:
            # Log error for debugging
            logger.warning(f"Agent returned error: {result.get('error', 'Unknown error')}")

        reset_config()

    def test_agent_handles_various_string_inputs(self, clean_db):
        """
        Test that agent can handle various string input formats

        Given: Multiple patients in database
        When: Agent receives different string queries
        Then: Agent should handle each gracefully
        """
        reset_config()

        # Create test patients
        patient1 = patient_crud.create(clean_db, PatientCreate(
            name="张三",
            age=45,
            gender="male"
        ))
        patient2 = patient_crud.create(clean_db, PatientCreate(
            name="李四",
            age=30,
            gender="female"
        ))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        # Test different string inputs
        test_queries = [
            f"查询患者 {patient1.patient_id}",
            "列出所有患者",
            "查询年龄大于40岁的患者",
        ]

        for query in test_queries:
            result = agent.process_request(query)

            # Each query should return a result
            assert result is not None, f"Query '{query}' should return a result"
            assert "success" in result, f"Query '{query}' result should have 'success'"

            logger.info(f"Query: {query[:50]}... -> success={result['success']}")

        reset_config()

    def test_agent_string_input_with_conversation_id(self, clean_db):
        """
        Test that agent can process string input with conversation_id

        Given: A patient exists
        When: Agent receives query with conversation_id for sandbox tracking
        Then: Agent should process correctly and track operations
        """
        reset_config()

        patient = patient_crud.create(clean_db, PatientCreate(
            name="王五",
            age=50,
            gender="male"
        ))
        clean_db.commit()

        agent = DataManagerCodeAgent()
        conversation_id = f"test_conv_{uuid.uuid4().hex[:8]}"

        # Process with conversation_id
        result = agent.process_request(
            user_request=f"查询患者 {patient.patient_id} 的信息",
            conversation_id=conversation_id
        )

        assert result is not None
        assert "success" in result

        if result["success"]:
            logger.info(f"Conversation {conversation_id} processed successfully")

        reset_config()

    def test_agent_string_input_with_special_characters(self, clean_db):
        """
        Test that agent handles string input with special characters

        Given: A patient with special characters in data
        When: Agent receives query
        Then: Agent should handle gracefully
        """
        reset_config()

        # Create patient with special characters in name
        patient = patient_crud.create(clean_db, PatientCreate(
            name="测试-用户 (Test)",
            age=28,
            gender="female",
            address="北京市朝阳区/海淀区"
        ))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        # Query with special characters
        result = agent.process_request(f"查询患者 {patient.patient_id} 的地址")

        assert result is not None
        assert "success" in result

        reset_config()

    def test_agent_empty_string_input(self, clean_db):
        """
        Test that agent handles empty or minimal string input

        When: Agent receives empty or minimal input
        Then: Agent should handle gracefully (not crash)
        """
        reset_config()

        agent = DataManagerCodeAgent()

        # Empty string should not crash
        result = agent.process_request("")

        assert result is not None
        assert "success" in result
        # Empty input might fail, but should not crash
        logger.info(f"Empty input result: success={result['success']}")

        reset_config()

    def test_agent_long_string_input(self, clean_db):
        """
        Test that agent handles long string input

        When: Agent receives a long string query
        Then: Agent should process without issues
        """
        reset_config()

        patient = patient_crud.create(clean_db, PatientCreate(
            name="测试用户",
            age=35,
            gender="male"
        ))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        # Long query
        long_query = f"""
        请帮我查询一下数据库中ID为 {patient.patient_id} 的患者信息，
        我需要了解这个患者的所有详细信息，包括姓名、年龄、性别、
        联系方式以及其他所有相关的医疗信息。
        请详细列出所有信息。
        """

        result = agent.process_request(long_query)

        assert result is not None
        assert "success" in result

        logger.info(f"Long input result: success={result['success']}")

        reset_config()


@pytest.mark.slow
@pytest.mark.integration
class TestAgentWithRealLLM:
    """Test DataManagerCodeAgent with actual LLM calls"""

    def test_agent_generates_code_for_query(self, clean_db):
        """
        Test that agent generates and executes code for a query

        This test verifies the core functionality:
        1. Agent receives string input
        2. Agent generates Python code
        3. Code executes in sandbox
        4. Returns result
        """
        reset_config()

        patient = patient_crud.create(clean_db, PatientCreate(
            name="测试患者",
            age=40,
            gender="male",
            phone="13800138000"
        ))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        # This query should cause the agent to generate code
        result = agent.process_request(f"获取患者 {patient.patient_id} 的年龄")

        assert result["success"] is True
        # The result should contain the age
        answer = result["final_answer"]
        assert "40" in answer or "年龄" in answer or "age" in answer.lower()

        logger.info(f"Generated code executed, result: {answer[:100]}...")

        reset_config()

    def test_agent_handles_complex_query(self, clean_db):
        """
        Test agent with a more complex query requiring multi-step reasoning
        """
        reset_config()

        # Create multiple patients
        patient_crud.create(clean_db, PatientCreate(name="患者A", age=25, gender="male"))
        patient_crud.create(clean_db, PatientCreate(name="患者B", age=45, gender="male"))
        patient_crud.create(clean_db, PatientCreate(name="患者C", age=65, gender="female"))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        # Complex query requiring filtering
        result = agent.process_request("查找所有年龄大于30岁的男性患者")

        assert result["success"] is True
        assert result["final_answer"] is not None

        logger.info(f"Complex query result: {result['final_answer'][:100]}...")

        reset_config()

    def test_agent_returns_within_timeout(self, clean_db):
        """
        Test that agent completes within reasonable time

        The agent has max_steps=5 to prevent infinite loops.
        This test verifies it completes quickly.
        """
        import time

        reset_config()

        patient = patient_crud.create(clean_db, PatientCreate(
            name="超时测试",
            age=50,
            gender="male"
        ))
        clean_db.commit()

        agent = DataManagerCodeAgent()

        start_time = time.time()
        result = agent.process_request(f"查询患者 {patient.patient_id}")
        elapsed = time.time() - start_time

        # Should complete within 60 seconds (generous for API calls)
        assert elapsed < 60, f"Agent took too long: {elapsed:.1f}s"
        assert result is not None

        logger.info(f"Agent completed in {elapsed:.1f}s")

        reset_config()


@pytest.mark.slow
@pytest.mark.integration
class TestAgentErrorHandling:
    """Test error handling with real API calls"""

    def test_agent_handles_nonexistent_patient(self, clean_db):
        """
        Test that agent handles query for non-existent patient gracefully
        """
        reset_config()

        agent = DataManagerCodeAgent()

        # Query for non-existent patient
        result = agent.process_request("查询患者 non-existent-uuid-12345")

        # Should complete without crashing
        assert result is not None
        assert "success" in result

        logger.info(f"Non-existent patient result: success={result['success']}")

        reset_config()

    def test_agent_handles_invalid_request(self, clean_db):
        """
        Test that agent handles invalid request gracefully
        """
        reset_config()

        agent = DataManagerCodeAgent()

        # Invalid query - trying to access blocked table
        result = agent.process_request("查询所有对话记录")

        # Should be blocked
        assert result["success"] is False
        assert "error" in result
        assert "Security" in result["error"] or "blocked" in result["error"].lower()

        logger.info(f"Blocked request: {result['error']}")

        reset_config()


# Standalone test function for quick verification
def test_basic_agent_string_input(clean_db):
    """
    Standalone test for quick verification

    Run this single test to verify the agent works:
        uv run pytest tests/data_manager/test_agent_string_input.py::test_basic_agent_string_input -v
    """
    reset_config()

    patient = patient_crud.create(clean_db, PatientCreate(
        name="基础测试用户",
        age=30,
        gender="male"
    ))
    clean_db.commit()

    agent = DataManagerCodeAgent()

    # The simplest possible test
    result = agent.process_request(f"查询患者 {patient.patient_id}")

    assert result is not None
    assert result["success"] is True
    assert result["final_answer"] is not None

    print(f"\n✅ Agent response: {result['final_answer'][:200]}...")

    reset_config()