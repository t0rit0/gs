"""
Configuration Manager

Handles loading and accessing configuration from:
1. YAML configuration files
2. Environment variables (fallback)
3. Default values

Supports nested configuration access and singleton pattern.
"""

import os
import logging
from pathlib import Path
from typing import Any, Optional
import yaml

logger = logging.getLogger(__name__)

# Singleton instance
_config_instance: Optional["ConfigManager"] = None


class ConfigManager:
    """
    Configuration manager for application settings

    Loads configuration from YAML files with environment variable fallback.
    Supports nested key access and provides default values.

    Usage:
        # Direct initialization
        config = ConfigManager(config_path="config.yaml")

        # Or use singleton
        config = get_config()
        api_key = config.get_api_key()
    """

    # Default configuration values
    DEFAULTS = {
        "llm.provider": "openai",
        "llm.model": "gpt-4o",
        "llm.base_url": "https://api.openai.com/v1",
        "llm.temperature": 0.7,
        "llm.max_tokens": 2000,
        "llm.timeout": 60,
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize ConfigManager

        Args:
            config_path: Path to YAML configuration file.
                        If None, looks for CONFIG_PATH environment variable,
                        then defaults to config.yaml in current directory.
        """
        # Determine config file path
        if config_path is None:
            config_path = os.getenv("CONFIG_PATH", "config.yaml")

        self.config_path = Path(config_path)
        self._config_data: dict[str, Any] = {}

        # Load configuration
        self._load_config()

        logger.info(f"ConfigManager initialized with {self.config_path}")

    def _load_config(self) -> None:
        """
        Load configuration from YAML file

        Loads from file if it exists, otherwise starts with empty config.
        """
        if self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    self._config_data = yaml.safe_load(f) or {}
                logger.info(f"Loaded configuration from {self.config_path}")
            except Exception as e:
                logger.error(f"Error loading config from {self.config_path}: {e}")
                self._config_data = {}
        else:
            logger.warning(f"Config file not found: {self.config_path}, using defaults and env vars")
            self._config_data = {}

    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value by key

        Supports nested keys using dot notation (e.g., "llm.model").
        Falls back to defaults if key not found.

        Args:
            key: Configuration key (supports dot notation for nested keys)
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        # Check default values first
        if key in self.DEFAULTS:
            default = self.DEFAULTS[key]

        # Navigate nested keys
        keys = key.split(".")
        value = self._config_data

        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default

    def get_api_key(self) -> str:
        """
        Get API key for LLM provider

        Priority:
        1. Config file (llm.api_key)
        2. Environment variable (OPENAI_API_KEY)
        3. Error (no API key available)

        Returns:
            API key string

        Raises:
            ValueError: If no API key is configured
        """
        # Try config file first
        api_key = self.get("llm.api_key")

        # Fallback to environment variable
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ValueError(
                "API key not found. Set llm.api_key in config file "
                "or OPENAI_API_KEY environment variable."
            )

        return api_key

    def get_base_url(self) -> str:
        """
        Get base URL for LLM API

        Priority:
        1. Config file (llm.base_url)
        2. Environment variable (OPENAI_BASE_URL)
        3. Default value

        Returns:
            Base URL string
        """
        # Try config file first
        base_url = self.get("llm.base_url")

        # Fallback to environment variable
        if not base_url or base_url == self.DEFAULTS["llm.base_url"]:
            env_url = os.getenv("OPENAI_BASE_URL")
            if env_url:
                base_url = env_url

        return base_url or self.DEFAULTS["llm.base_url"]

    def get_model(self) -> str:
        """
        Get model name for LLM

        Returns:
            Model name string
        """
        return self.get("llm.model", self.DEFAULTS["llm.model"])

    def get_temperature(self) -> float:
        """
        Get temperature setting for LLM

        Returns:
            Temperature value (0.0 to 2.0)
        """
        return self.get("llm.temperature", self.DEFAULTS["llm.temperature"])

    def get_max_tokens(self) -> int:
        """
        Get max tokens setting for LLM

        Returns:
            Max tokens value
        """
        return self.get("llm.max_tokens", self.DEFAULTS["llm.max_tokens"])

    def get_provider(self) -> str:
        """
        Get LLM provider name

        Returns:
            Provider name (e.g., "openai")
        """
        return self.get("llm.provider", self.DEFAULTS["llm.provider"])

    def reload(self) -> None:
        """
        Reload configuration from file

        Useful when config file changes after initialization.
        """
        self._load_config()
        logger.info("Configuration reloaded")

    def __repr__(self) -> str:
        return f"ConfigManager(path={self.config_path}, provider={self.get_provider()})"


def get_config(config_path: Optional[str] = None) -> ConfigManager:
    """
    Get singleton ConfigManager instance

    Creates instance on first call, returns same instance on subsequent calls.

    Args:
        config_path: Optional config path (only used on first call)

    Returns:
        ConfigManager singleton instance
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = ConfigManager(config_path=config_path)

    return _config_instance


def reset_config() -> None:
    """
    Reset the singleton ConfigManager instance

    Useful for testing or when you need to reload configuration.
    """
    global _config_instance
    _config_instance = None
    logger.debug("ConfigManager singleton reset")
