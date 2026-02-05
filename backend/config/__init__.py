"""
Configuration Module

Manages application configuration from YAML files and environment variables.
"""
from backend.config.config_manager import ConfigManager, get_config

__all__ = ["ConfigManager", "get_config"]
