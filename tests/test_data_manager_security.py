"""
Comprehensive Security and Functionality Tests for DataManagerCodeAgent

Tests cover:
1. Security: Agent blocks conversations/messages table access
2. Security: Agent is_request_blocked function works correctly
3. Integration: Agent initialization and system prompt
4. Integration: query_database tool behavior
"""

import pytest
import os
import tempfile
import yaml
from unittest.mock import patch, MagicMock

from backend.agents.data_manager import (
    DataManagerCodeAgent,
    is_request_blocked,
    BLOCKED_TABLES,
    query_database
)
from backend.config.config_manager import reset_config


class TestSecurityBlocking:
    """Test suite for security blocking functionality"""

    def test_blocks_conversations_table_query(self):
        """Test that requests to query conversations table are blocked"""
        request = "Show me all conversations"
        error = is_request_blocked(request)
        assert error is not None
        assert "conversations" in error.lower()
        assert "not allowed" in error.lower()

    def test_blocks_messages_table_query(self):
        """Test that requests to query messages table are blocked"""
        request = "Get messages for conversation 123"
        error = is_request_blocked(request)
        assert error is not None
        assert "messages" in error.lower() or "not allowed" in error.lower()

    def test_blocks_conversations_update(self):
        """Test that requests to update conversations are blocked"""
        request = "Update conversation 123 status to completed"
        error = is_request_blocked(request)
        assert error is not None
        assert "conversations" in error.lower()

    def test_blocks_conversations_delete(self):
        """Test that requests to delete conversations are blocked"""
        request = "Delete conversation with ID 456"
        error = is_request_blocked(request)
        assert error is not None
        assert "conversations" in error.lower()

    def test_allows_patient_queries(self):
        """Test that patient table queries are allowed"""
        request = "Get patient with ID 123"
        error = is_request_blocked(request)
        assert error is None

    def test_allows_patient_updates(self):
        """Test that patient table updates are allowed"""
        request = "Update patient 123 age to 35"
        error = is_request_blocked(request)
        assert error is None

    def test_allows_health_metric_queries(self):
        """Test that health metric queries are allowed"""
        request = "Show health metrics for patient 123"
        error = is_request_blocked(request)
        assert error is None

    def test_allows_medical_history_operations(self):
        """Test that medical history operations are allowed"""
        request = "Add medical history for patient 123"
        error = is_request_blocked(request)
        assert error is None

    def test_blocked_tables_constant(self):
        """Test that BLOCKED_TABLES includes expected tables"""
        assert "conversations" in BLOCKED_TABLES
        assert "messages" in BLOCKED_TABLES

    def test_case_insensitive_blocking(self):
        """Test that blocking is case-insensitive"""
        variations = [
            "Show me Conversations",
            "Get all MESSAGES",
            "UPDATE conversations SET status='completed'",
            "Delete from Messages"
        ]
        for request in variations:
            error = is_request_blocked(request)
            # At least one should be blocked
            if "conversation" in request.lower() or "message" in request.lower():
                assert error is not None or "messages" in request.lower()


class TestQueryDatabaseTool:
    """Test suite for query_database tool"""

    def test_tool_blocks_conversations_in_code(self):
        """Test that query_database tool blocks code accessing conversations"""
        malicious_code = """
session = SessionLocal()
convs = session.query(Conversation).all()
result["output"] = convs
"""
        result = query_database(malicious_code)
        assert "ERROR" in result or "not allowed" in result.lower()

    def test_tool_blocks_messages_in_code(self):
        """Test that query_database tool blocks code accessing messages"""
        malicious_code = """
session = SessionLocal()
msgs = message_crud.list_by_conversation(session, "conv_123")
result["output"] = msgs
"""
        result = query_database(malicious_code)
        assert "ERROR" in result or "not allowed" in result.lower() or "blocked" in result.lower()

    def test_tool_handles_syntax_errors(self):
        """Test that query_database tool handles code syntax errors gracefully"""
        invalid_code = "this is not valid python ))))"
        result = query_database(invalid_code)
        assert "ERROR" in result

    def test_tool_handles_runtime_errors(self):
        """Test that query_database tool handles runtime errors gracefully"""
        error_code = """
raise ValueError("Test error")
"""
        result = query_database(error_code)
        assert "ERROR" in result or "Test error" in result


class TestAgentInitialization:
    """Test suite for agent initialization"""

    def test_agent_requires_api_key(self):
        """Test that agent initialization requires API key"""
        # Create empty config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({}, f)
            config_path = f.name

        try:
            reset_config()
            original_key = os.environ.pop("OPENAI_API_KEY", None)

            with pytest.raises(ValueError, match="API key not found"):
                DataManagerCodeAgent(config_path=config_path)

            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key
        finally:
            os.unlink(config_path)
            reset_config()

    @patch("backend.agents.data_manager.CodeAgent")
    def test_agent_initializes_with_code_agent(self, mock_code_agent):
        """Test that agent initializes CodeAgent with correct parameters"""
        # Create test config
        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            mock_instance = MagicMock()
            mock_code_agent.return_value = mock_instance

            agent = DataManagerCodeAgent(config_path=config_path)

            # Verify CodeAgent was called
            assert mock_code_agent.called
            call_kwargs = mock_code_agent.call_args[1]

            # Check that it was initialized with tools
            assert "tools" in call_kwargs
            assert len(call_kwargs["tools"]) > 0

            # Check that system prompt includes security rules
            assert "system_prompt" in call_kwargs
            prompt = call_kwargs["system_prompt"]
            assert "BLOCKED" in prompt or "Security" in prompt
        finally:
            os.unlink(config_path)
            reset_config()

    @patch("backend.agents.data_manager.CodeAgent")
    def test_system_prompt_includes_orm_info(self, mock_code_agent):
        """Test that system prompt includes ORM model information"""
        # Create test config
        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            mock_instance = MagicMock()
            mock_code_agent.return_value = mock_instance

            agent = DataManagerCodeAgent(config_path=config_path)

            call_kwargs = mock_code_agent.call_args[1]
            prompt = call_kwargs["system_prompt"]

            # Check for Patient model info
            assert "Patient" in prompt
            assert "patient_crud" in prompt

            # Check for SandboxSession
            assert "SandboxSession" in prompt

            # Check for security rules
            assert "Security" in prompt or "BLOCKED" in prompt
        finally:
            os.unlink(config_path)
            reset_config()


class TestAgentProcessRequest:
    """Test suite for agent process_request method"""

    @patch("backend.agents.data_manager.CodeAgent")
    def test_process_request_blocks_malicious_queries(self, mock_code_agent):
        """Test that process_request blocks malicious requests"""
        # Create test config
        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            mock_instance = MagicMock()
            mock_code_agent.return_value = mock_instance

            agent = DataManagerCodeAgent(config_path=config_path)

            # Test blocked request
            result = agent.process_request("Show me all conversations")

            assert result["success"] is False
            assert "error" in result
            assert "conversations" in result["error"].lower() or "not allowed" in result["error"].lower()

            # Agent should not have been called for blocked requests
            assert not mock_instance.run.called
        finally:
            os.unlink(config_path)
            reset_config()

    @patch("backend.agents.data_manager.CodeAgent")
    def test_process_request_handles_agent_errors(self, mock_code_agent):
        """Test that process_request handles agent errors gracefully"""
        # Create test config
        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            mock_instance = MagicMock()
            mock_instance.run.side_effect = Exception("Agent error")
            mock_code_agent.return_value = mock_instance

            agent = DataManagerCodeAgent(config_path=config_path)

            result = agent.process_request("Get patient 123")

            assert result["success"] is False
            assert "error" in result
            assert "Agent error" in result["error"]
        finally:
            os.unlink(config_path)
            reset_config()


class TestAgentExecutePending:
    """Test suite for agent execute_pending method"""

    @patch("backend.agents.data_manager.CodeAgent")
    @patch("backend.agents.data_manager.SandboxSession")
    def test_execute_pending_creates_sandbox(self, mock_sandbox, mock_code_agent):
        """Test that execute_pending creates sandbox with operations"""
        # Create test config
        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            mock_instance = MagicMock()
            mock_code_agent.return_value = mock_instance

            mock_sandbox_instance = MagicMock()
            mock_sandbox.return_value = mock_sandbox_instance
            mock_sandbox_instance.execute_pending.return_value = {
                "success": True,
                "executed_count": 1
            }

            agent = DataManagerCodeAgent(config_path=config_path)

            operations_data = [
                {
                    "operation_type": "update",
                    "table_name": "patients",
                    "details": {"changes": []}
                }
            ]

            result = agent.execute_pending(operations_data, "conv_123")

            # Verify sandbox was created and operations were restored
            assert mock_sandbox.called
            assert mock_sandbox_instance.disable_sandbox.called
            assert mock_sandbox_instance.execute_pending.called
            assert mock_sandbox_instance.close.called

            assert result["success"] is True
            assert result["executed_count"] == 1
        finally:
            os.unlink(config_path)
            reset_config()

    @patch("backend.agents.data_manager.CodeAgent")
    @patch("backend.agents.data_manager.SandboxSession")
    def test_execute_pending_handles_errors(self, mock_sandbox, mock_code_agent):
        """Test that execute_pending handles errors gracefully"""
        # Create test config
        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            mock_instance = MagicMock()
            mock_code_agent.return_value = mock_instance

            mock_sandbox_instance = MagicMock()
            mock_sandbox.return_value = mock_sandbox_instance
            mock_sandbox_instance.execute_pending.side_effect = Exception("Sandbox error")

            agent = DataManagerCodeAgent(config_path=config_path)

            operations_data = [
                {
                    "operation_type": "update",
                    "table_name": "patients",
                    "details": {"changes": []}
                }
            ]

            result = agent.execute_pending(operations_data, "conv_123")

            assert result["success"] is False
            assert "error" in result
            assert "Sandbox error" in result["error"]
        finally:
            os.unlink(config_path)
            reset_config()
