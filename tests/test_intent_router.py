"""
Tests for IntentRouter

Tests cover:
1. Intent recognition from user messages
2. Structured output parsing
3. Routing to correct agent
4. User requirements analysis generation
5. Error handling
"""

import pytest
from unittest.mock import patch, MagicMock
import tempfile
import yaml

from backend.agents.intent_router import (
    IntentRouter,
    IntentType,
    Intent
)
from backend.config.config_manager import reset_config


class TestIntentType:
    """Test suite for IntentType enum"""

    def test_intent_type_values(self):
        """Test that IntentType has expected values"""
        assert IntentType.DIAGNOSTIC_CHAT == "diagnostic_chat"
        assert IntentType.DATA_QUERY == "data_query"
        assert IntentType.DATA_UPDATE == "data_update"
        assert IntentType.SYSTEM_CMD == "system_cmd"
        assert IntentType.UNKNOWN == "unknown"


class TestIntent:
    """Test suite for Intent data class"""

    def test_intent_creation(self):
        """Test creating an Intent object"""
        intent = Intent(
            type=IntentType.DIAGNOSTIC_CHAT,
            analysis="Patient reports high blood pressure symptoms"
        )

        assert intent.type == IntentType.DIAGNOSTIC_CHAT
        assert intent.analysis == "Patient reports high blood pressure symptoms"
        assert "high blood pressure" in intent.analysis.lower()

    def test_intent_from_dict(self):
        """Test creating Intent from dictionary"""
        data = {
            "type": "data_query",
            "analysis": "User wants to see patient history"
        }

        intent = Intent(**data)

        assert intent.type == "data_query"
        assert intent.analysis == "User wants to see patient history"


class TestIntentRouter:
    """Test suite for IntentRouter"""

    @pytest.fixture
    def mock_openai_response(self):
        """Mock OpenAI API response for intent recognition"""
        return {
            "type": IntentType.DIAGNOSTIC_CHAT,
            "analysis": "Patient reports symptoms consistent with hypertension"
        }

    def test_router_initialization(self):
        """Test that IntentRouter initializes correctly"""
        # Create test config
        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()

            with patch("openai.OpenAI"):
                router = IntentRouter(config_path=config_path)

                assert router is not None
                assert router.model_name == "gpt-4o-mini"  # Default model
        finally:
            import os
            os.unlink(config_path)
            reset_config()

    @patch("backend.agents.intent_router.openai")
    def test_recognize_diagnostic_intent(self, mock_openai, mock_openai_response):
        """Test recognizing diagnostic chat intent"""
        # Mock OpenAI response
        mock_client = MagicMock()
        mock_response = MagicMock()
        # Return JSON string for content
        import json
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = json.dumps(mock_openai_response)
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        # Create router
        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            router = IntentRouter(config_path=config_path)

            # Test diagnostic message
            user_message = "I've been having headaches and my blood pressure is high"
            intent = router.recognize_intent(user_message)

            assert intent.type == IntentType.DIAGNOSTIC_CHAT
            assert "hypertension" in intent.analysis.lower() or "symptoms" in intent.analysis.lower()

            # Verify OpenAI was called with structured output
            assert mock_client.chat.completions.create.called
            call_args = mock_client.chat.completions.create.call_args
            assert "response_format" in call_args.kwargs
        finally:
            import os
            os.unlink(config_path)
            reset_config()

    @patch("backend.agents.intent_router.openai")
    def test_recognize_data_query_intent(self, mock_openai):
        """Test recognizing data query intent"""
        # Mock response
        mock_response_data = {
            "type": IntentType.DATA_QUERY,
            "analysis": "User requests patient information retrieval"
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        import json
        mock_response.choices[0].message.content = json.dumps(mock_response_data)
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            router = IntentRouter(config_path=config_path)

            user_message = "Show me all patient records from last month"
            intent = router.recognize_intent(user_message)

            assert intent.type == IntentType.DATA_QUERY
        finally:
            import os
            os.unlink(config_path)
            reset_config()

    @patch("backend.agents.intent_router.openai")
    def test_recognize_data_update_intent(self, mock_openai):
        """Test recognizing data update intent"""
        mock_response_data = {
            "type": IntentType.DATA_UPDATE,
            "analysis": "User wants to update patient health metrics"
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        import json
        mock_response.choices[0].message.content = json.dumps(mock_response_data)
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            router = IntentRouter(config_path=config_path)

            user_message = "Add a new blood pressure reading of 140/90 for patient John"
            intent = router.recognize_intent(user_message)

            assert intent.type == IntentType.DATA_UPDATE
            assert "health metrics" in intent.analysis.lower() or "blood pressure" in intent.analysis.lower()
        finally:
            import os
            os.unlink(config_path)
            reset_config()

    @patch("backend.agents.intent_router.openai")
    def test_recognize_system_command_intent(self, mock_openai):
        """Test recognizing system command intent"""
        mock_response_data = {
            "type": IntentType.SYSTEM_CMD,
            "analysis": "User requests system operation"
        }

        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        import json
        mock_response.choices[0].message.content = json.dumps(mock_response_data)
        mock_client.chat.completions.create.return_value = mock_response
        mock_openai.OpenAI.return_value = mock_client

        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            router = IntentRouter(config_path=config_path)

            user_message = "Export all conversation data to CSV"
            intent = router.recognize_intent(user_message)

            assert intent.type == IntentType.SYSTEM_CMD
        finally:
            import os
            os.unlink(config_path)
            reset_config()

    def test_route_returns_correct_agent_type(self):
        """Test that routing returns correct agent type"""
        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()

            with patch("openai.OpenAI"):
                router = IntentRouter(config_path=config_path)

                # Test routing
                assert router.route(Intent(type=IntentType.DIAGNOSTIC_CHAT, analysis="")) == "drhyper"
                assert router.route(Intent(type=IntentType.DATA_QUERY, analysis="")) == "data_manager"
                assert router.route(Intent(type=IntentType.DATA_UPDATE, analysis="")) == "data_manager"
                assert router.route(Intent(type=IntentType.SYSTEM_CMD, analysis="")) == "system"
                assert router.route(Intent(type=IntentType.UNKNOWN, analysis="")) == "default"

        finally:
            import os
            os.unlink(config_path)
            reset_config()

    @patch("backend.agents.intent_router.openai")
    def test_handle_openai_error_gracefully(self, mock_openai):
        """Test that OpenAI API errors are handled gracefully"""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        mock_openai.OpenAI.return_value = mock_client

        config_data = {"llm": {"api_key": "test-key"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()
            router = IntentRouter(config_path=config_path)

            # Should return UNKNOWN intent on error
            intent = router.recognize_intent("Test message")

            assert intent.type == IntentType.UNKNOWN
            assert "error" in intent.analysis.lower()
        finally:
            import os
            os.unlink(config_path)
            reset_config()
