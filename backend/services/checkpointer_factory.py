"""
Checkpointer Factory for LangGraph

Creates LangGraph checkpointers based on configuration.
Supports PostgreSQL for production and Memory for testing.
"""

import logging
from typing import Optional

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

# Try to import PostgresSaver, fall back gracefully if not available
try:
    from langgraph.checkpoint.postgres import PostgresSaver
    POSTGRES_AVAILABLE = True
except ImportError:
    POSTGRES_AVAILABLE = False
    PostgresSaver = None

from backend.config.config_manager import get_config, ConfigManager

logger = logging.getLogger(__name__)


def get_checkpointer(config: Optional[ConfigManager] = None) -> BaseCheckpointSaver:
    """
    Create checkpointer based on configuration.

    Args:
        config: Optional ConfigManager instance. If None, uses singleton.

    Returns:
        PostgresSaver or MemorySaver instance

    Raises:
        ValueError: If PostgreSQL checkpointer requested but not available
    """
    config = config or get_config()
    checkpoint_type = config.get("langgraph.checkpoint.type", "memory")

    if checkpoint_type == "postgres":
        if not POSTGRES_AVAILABLE:
            logger.warning(
                "PostgreSQL checkpointer requested but psycopg not available. "
                "Falling back to Memory checkpointer. "
                "Install with: uv add 'psycopg[binary]'"
            )
            return MemorySaver()

        connection_string = config.get("langgraph.checkpoint.connection_string")

        # Also try DATABASE_URL environment variable as fallback
        if not connection_string:
            import os
            connection_string = os.getenv("DATABASE_URL")

        if not connection_string:
            logger.warning(
                "PostgreSQL connection string not found. "
                "Falling back to Memory checkpointer. "
                "Set langgraph.checkpoint.connection_string in config.yaml "
                "or DATABASE_URL environment variable."
            )
            return MemorySaver()

        logger.info(f"Creating PostgreSQL checkpointer")
        # Create PostgresSaver (automatically creates tables if needed on first use)
        checkpointer = PostgresSaver.from_conn_string(connection_string)
        return checkpointer
    else:
        # Memory checkpointer for testing and development
        logger.info("Creating Memory checkpointer (for testing/dev)")
        return MemorySaver()


async def initialize_checkpoint_tables(config: Optional[ConfigManager] = None) -> None:
    """
    Initialize PostgreSQL checkpoint tables.

    Creates checkpoint tables in PostgreSQL if they don't exist.
    Call this once during application startup.

    Args:
        config: Optional ConfigManager instance. If None, uses singleton.
    """
    config = config or get_config()
    checkpoint_type = config.get("langgraph.checkpoint.type", "memory")

    if checkpoint_type == "postgres" and POSTGRES_AVAILABLE:
        checkpointer = get_checkpointer(config)
        # PostgresSaver.setup() creates the necessary tables
        if isinstance(checkpointer, PostgresSaver):
            await checkpointer.setup()
            logger.info("PostgreSQL checkpoint tables initialized")
    else:
        logger.info("Skipping checkpoint table initialization (using memory checkpointer)")


def get_checkpointer_sync(config: Optional[ConfigManager] = None) -> BaseCheckpointSaver:
    """
    Synchronous wrapper for get_checkpointer.

    This is provided for compatibility with code that doesn't use async.
    The checkpointer itself works the same way.

    Args:
        config: Optional ConfigManager instance. If None, uses singleton.

    Returns:
        PostgresSaver or MemorySaver instance
    """
    return get_checkpointer(config)
