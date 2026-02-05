"""
Tests for ConfigManager

Tests cover:
1. Loading configuration from YAML file
2. Reading API keys and base URLs
3. Fallback to environment variables
4. Configuration validation
5. Singleton pattern
"""

import pytest
import os
import tempfile
from pathlib import Path
import yaml

from backend.config.config_manager import ConfigManager, get_config


class TestConfigManager:
    """Test suite for ConfigManager functionality"""

    def test_load_config_from_yaml_file(self):
        """
        Test that ConfigManager loads configuration from YAML file

        Given: A valid YAML configuration file
        When: Loading configuration
        Then: Should load all settings correctly
        """
        # Arrange: Create a temporary config file
        config_data = {
            "llm": {
                "provider": "openai",
                "api_key": "test-api-key-123",
                "base_url": "https://api.openai.com/v1",
                "model": "gpt-4",
                "temperature": 0.7,
                "max_tokens": 2000
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            # Act: Load configuration
            config = ConfigManager(config_path=config_path)

            # Assert: Configuration loaded correctly
            assert config.get("llm.provider") == "openai"
            assert config.get("llm.api_key") == "test-api-key-123"
            assert config.get("llm.base_url") == "https://api.openai.com/v1"
            assert config.get("llm.model") == "gpt-4"
            assert config.get("llm.temperature") == 0.7
            assert config.get("llm.max_tokens") == 2000
        finally:
            os.unlink(config_path)

    def test_fallback_to_environment_variables(self):
        """
        Test that ConfigManager falls back to environment variables

        Given: Missing YAML file or missing config values
        When: Environment variables are set
        Then: Should use environment variables
        """
        # Arrange: Set environment variables
        os.environ["OPENAI_API_KEY"] = "env-api-key"
        os.environ["OPENAI_BASE_URL"] = "https://env-api.example.com/v1"

        try:
            # Act: Create config with empty file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
                yaml.dump({}, f)
                config_path = f.name

            config = ConfigManager(config_path=config_path)

            # Assert: Uses environment variables
            assert config.get_api_key() == "env-api-key"
            assert config.get_base_url() == "https://env-api.example.com/v1"

            os.unlink(config_path)
        finally:
            # Cleanup
            del os.environ["OPENAI_API_KEY"]
            del os.environ["OPENAI_BASE_URL"]

    def test_get_api_key_returns_correct_value(self):
        """Test that get_api_key returns the API key from config"""
        config_data = {
            "llm": {
                "api_key": "my-secret-key"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = ConfigManager(config_path=config_path)
            assert config.get_api_key() == "my-secret-key"
        finally:
            os.unlink(config_path)

    def test_get_base_url_returns_correct_value(self):
        """Test that get_base_url returns the base URL from config"""
        config_data = {
            "llm": {
                "base_url": "https://custom-api.example.com/v1"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = ConfigManager(config_path=config_path)
            assert config.get_base_url() == "https://custom-api.example.com/v1"
        finally:
            os.unlink(config_path)

    def test_get_model_returns_correct_value(self):
        """Test that get_model returns the model name from config"""
        config_data = {
            "llm": {
                "model": "gpt-4o"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = ConfigManager(config_path=config_path)
            assert config.get_model() == "gpt-4o"
        finally:
            os.unlink(config_path)

    def test_default_values_when_not_specified(self):
        """
        Test that default values are used when config values are missing

        Given: Configuration file with missing optional values
        When: Accessing configuration
        Then: Should return appropriate defaults
        """
        config_data = {
            "llm": {
                "api_key": "test-key"
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = ConfigManager(config_path=config_path)

            # Should have defaults
            assert config.get_model() == "gpt-4o"  # Default model
            assert config.get_base_url() == "https://api.openai.com/v1"  # Default base URL
            assert config.get_temperature() == 0.7  # Default temperature
        finally:
            os.unlink(config_path)

    def test_singleton_pattern(self):
        """
        Test that get_config returns the same instance

        Given: Multiple calls to get_config
        When: Calling get_config multiple times
        Then: Should return the same ConfigManager instance
        """
        # Arrange: Create config file
        config_data = {"llm": {"api_key": "singleton-test"}}
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            # Set environment for singleton
            os.environ["CONFIG_PATH"] = config_path

            # Reset singleton
            from backend.config.config_manager import reset_config
            reset_config()

            # Act: Get config multiple times
            config1 = get_config()
            config2 = get_config()

            # Assert: Same instance
            assert config1 is config2
            assert config1.get_api_key() == config2.get_api_key()
        finally:
            os.unlink(config_path)
            if "CONFIG_PATH" in os.environ:
                del os.environ["CONFIG_PATH"]
            # Reset singleton
            from backend.config.config_manager import reset_config
            reset_config()

    def test_get_with_nested_keys(self):
        """Test that get method works with nested key paths"""
        config_data = {
            "llm": {
                "provider": "openai",
                "settings": {
                    "timeout": 30,
                    "retries": 3
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config_data, f)
            config_path = f.name

        try:
            config = ConfigManager(config_path=config_path)

            # Test nested access
            assert config.get("llm.provider") == "openai"
            assert config.get("llm.settings.timeout") == 30
            assert config.get("llm.settings.retries") == 3
        finally:
            os.unlink(config_path)

    def test_get_returns_default_for_missing_keys(self):
        """Test that get returns default value for missing keys"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump({}, f)
            config_path = f.name

        try:
            config = ConfigManager(config_path=config_path)

            # Test with default value
            assert config.get("missing.key", "default_value") == "default_value"
            assert config.get("another.missing.key", 42) == 42
        finally:
            os.unlink(config_path)
