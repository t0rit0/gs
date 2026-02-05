"""
Tests for DataManagerCodeAgent integration with ConfigManager

Tests cover:
1. Agent initialization with ConfigManager
2. Agent uses OpenAIModel with config settings
3. Fallback to environment variables
4. Configuration loading from YAML file
"""

import pytest
import os
import tempfile
import yaml
from unittest.mock import patch, MagicMock

from backend.agents.data_manager import DataManagerCodeAgent
from backend.config.config_manager import reset_config


class TestDataManagerConfigIntegration:
    """Test suite for DataManagerCodeAgent and ConfigManager integration"""

    def test_agent_initializes_with_config_manager(self):
        """
        Test that agent initializes using ConfigManager

        Given: A valid configuration file
        When: Initializing DataManagerCodeAgent
        Then: Should load config and create OpenAIModel
        """
        # Arrange: Create config file
        config_data = {
            "llm": {
                "api_key": "test-api-key-123",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4o"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            # Reset singleton before test
            reset_config()

            # Act: Initialize agent
            with patch("backend.agents.data_manager.CodeAgent"):
                agent = DataManagerCodeAgent(config_path=config_path)

                # Assert: Config loaded correctly
                assert agent.config.get_api_key() == "test-api-key-123"
                assert agent.config.get_base_url() == "https://api.openai.com/v1"
                assert agent.config.get_model() == "gpt-4o"

                # Assert: OpenAIModel created with correct parameters
                assert agent.model is not None
        finally:
            os.unlink(config_path)
            reset_config()

    def test_agent_falls_back_to_environment_variables(self):
        """
        Test that agent falls back to environment variables for API key

        Given: No API key in config file
        When: OPENAI_API_KEY environment variable is set
        Then: Should use environment variable
        """
        # Arrange: Set environment variable
        os.environ["OPENAI_API_KEY"] = "env-api-key"
        os.environ["OPENAI_BASE_URL"] = "https://env-api.example.com/v1"

        try:
            # Create empty config
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump({}, f)
                config_path = f.name

            reset_config()

            # Act: Initialize agent
            with patch("backend.agents.data_manager.CodeAgent"):
                agent = DataManagerCodeAgent(config_path=config_path)

                # Assert: Uses environment variables
                assert agent.config.get_api_key() == "env-api-key"
                assert agent.config.get_base_url() == "https://env-api.example.com/v1"

            os.unlink(config_path)
        finally:
            # Cleanup
            del os.environ["OPENAI_API_KEY"]
            del os.environ["OPENAI_BASE_URL"]
            reset_config()

    @patch("backend.agents.data_manager.OpenAIModel")
    @patch("backend.agents.data_manager.CodeAgent")
    def test_opensai_model_initialized_with_config(self, mock_code_agent, mock_openai_model):
        """
        Test that OpenAIModel is initialized with correct config parameters

        Given: A config file with specific model settings
        When: Initializing agent
        Then: OpenAIModel should be created with those settings
        """
        # Arrange: Create config
        config_data = {
            "llm": {
                "api_key": "my-key",
                "base_url": "https://custom.api.com/v1",
                "model": "gpt-4-turbo"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()

            # Mock OpenAIModel instance
            mock_model_instance = MagicMock()
            mock_openai_model.return_value = mock_model_instance

            # Act: Initialize agent
            agent = DataManagerCodeAgent(config_path=config_path)

            # Assert: OpenAIModel called with correct parameters
            assert mock_openai_model.called
            call_kwargs = mock_openai_model.call_args[1]
            assert call_kwargs["model_id"] == "gpt-4-turbo"
            assert call_kwargs["api_key"] == "my-key"
            assert call_kwargs["api_base"] == "https://custom.api.com/v1"

        finally:
            os.unlink(config_path)
            reset_config()

    def test_agent_raises_error_without_api_key(self):
        """
        Test that agent raises error when no API key is configured

        Given: No API key in config or environment
        When: Initializing agent
        Then: Should raise ValueError
        """
        # Arrange: Create empty config
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({}, f)
            config_path = f.name

        try:
            reset_config()

            # Make sure no env var is set
            original_key = os.environ.pop("OPENAI_API_KEY", None)

            # Act & Assert: Should raise error
            with pytest.raises(ValueError, match="API key not found"):
                DataManagerCodeAgent(config_path=config_path)

            # Restore
            if original_key:
                os.environ["OPENAI_API_KEY"] = original_key

        finally:
            os.unlink(config_path)
            reset_config()

    @patch("backend.agents.data_manager.OpenAIModel")
    @patch("backend.agents.data_manager.CodeAgent")
    def test_agent_uses_default_values(self, mock_code_agent, mock_openai_model):
        """
        Test that agent uses default values when config is missing

        Given: Minimal config (only API key)
        When: Initializing agent
        Then: Should use default values for other settings
        """
        # Arrange: Config with only API key
        config_data = {
            "llm": {
                "api_key": "minimal-key"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            reset_config()

            # Act: Initialize agent
            agent = DataManagerCodeAgent(config_path=config_path)

            # Assert: Uses defaults
            assert agent.config.get_model() == "gpt-4o"  # Default model
            assert agent.config.get_base_url() == "https://api.openai.com/v1"  # Default URL

        finally:
            os.unlink(config_path)
            reset_config()
