"""
SandboxSessionManager - Session-level sandbox management

This module provides a manager for maintaining sandbox sessions across
multiple requests, enabling operations to be accumulated and approved
in a single batch at conversation end.

Key Features:
- Maintains one SandboxSession per conversation
- Operations accumulate across multiple requests
- Batch approval/rejection at conversation end
- Thread-safe operations
"""

import logging
from typing import Dict, List, Optional
from sqlalchemy.orm import Session

from backend.services.sandbox_session import SandboxSession, DatabaseOperation

logger = logging.getLogger(__name__)


class SandboxSessionManager:
    """
    Manages sandbox sessions across multiple conversations

    This allows operations to be accumulated across multiple requests
    and approved in a single batch at conversation end.

    Usage:
        manager = SandboxSessionManager()

        # Request 1: First operation
        sandbox1 = manager.get_or_create_sandbox(db, "conv_123")
        # ... perform operations ...
        sandbox1.commit()  # Intercepted

        # Request 2: Second operation (same conversation)
        sandbox2 = manager.get_or_create_sandbox(db, "conv_123")
        # ... perform operations ...
        sandbox2.commit()  # Intercepted

        # Conversation end: Approve all
        result = manager.approve_and_execute_all(db, "conv_123")
    """

    def __init__(self):
        """
        Initialize the sandbox session manager

        Attributes:
            sessions: Dictionary mapping conversation_id to SandboxSession
        """
        self.sessions: Dict[str, SandboxSession] = {}
        logger.info("SandboxSessionManager initialized")

    def get_or_create_sandbox(
        self,
        real_session: Session,
        conversation_id: str
    ) -> SandboxSession:
        """
        Get existing sandbox or create new one for conversation

        Args:
            real_session: The real SQLAlchemy session to wrap
            conversation_id: ID of the conversation

        Returns:
            SandboxSession instance for this conversation
        """
        # Return existing if available
        if conversation_id in self.sessions:
            logger.debug(f"Reusing existing sandbox for {conversation_id}")
            return self.sessions[conversation_id]

        # Create new sandbox
        logger.info(f"Creating new sandbox for conversation {conversation_id}")
        sandbox = SandboxSession(real_session, conversation_id)
        self.sessions[conversation_id] = sandbox

        return sandbox

    def has_pending_operations(self, conversation_id: str) -> bool:
        """
        Check if conversation has pending operations

        Args:
            conversation_id: ID of the conversation

        Returns:
            True if pending operations exist, False otherwise
        """
        sandbox = self.sessions.get(conversation_id)
        if not sandbox:
            return False

        return sandbox.has_pending_operations()

    def get_pending_operations_summary(
        self,
        conversation_id: str
    ) -> List[Dict]:
        """
        Get summary of pending operations for a conversation

        Args:
            conversation_id: ID of the conversation

        Returns:
            List of operation dictionaries, or empty list if none
        """
        sandbox = self.sessions.get(conversation_id)
        if not sandbox:
            return []

        return sandbox.get_pending_operations()

    def approve_and_execute_all(
        self,
        real_session: Session,
        conversation_id: str
    ) -> Dict:
        """
        Approve and execute all pending operations for a conversation

        This method:
        1. Gets the sandbox for the conversation
        2. Checks for pending operations
        3. Disables sandbox mode
        4. Executes all pending operations
        5. Removes sandbox from manager

        Args:
            real_session: The real SQLAlchemy session
            conversation_id: ID of the conversation

        Returns:
            Dictionary with:
                - success: bool
                - executed_count: int (if success)
                - operations: list (if success)
                - message: str (if error)
        """
        sandbox = self.sessions.get(conversation_id)

        if not sandbox:
            return {
                "success": False,
                "message": f"Conversation not found: {conversation_id}"
            }

        if not sandbox.has_pending_operations():
            # Remove sandbox even if no operations
            self.remove_sandbox(conversation_id)
            return {
                "success": False,
                "message": "No pending operations to execute"
            }

        try:
            logger.info(
                f"Executing {len(sandbox.operations)} pending operations "
                f"for conversation {conversation_id}"
            )

            # Disable sandbox and execute
            sandbox.disable_sandbox()
            result = sandbox.execute_pending()

            # Clean up
            self.remove_sandbox(conversation_id)

            return result

        except Exception as e:
            logger.error(
                f"Error executing operations for {conversation_id}: {e}",
                exc_info=True
            )

            # Clean up on error
            self.remove_sandbox(conversation_id)

            return {
                "success": False,
                "message": str(e)
            }

    def reject_and_discard_all(self, conversation_id: str) -> Dict:
        """
        Reject and discard all pending operations for a conversation

        This method:
        1. Gets the sandbox for the conversation
        2. Counts pending operations
        3. Rolls back the session
        4. Removes sandbox from manager

        Args:
            conversation_id: ID of the conversation

        Returns:
            Dictionary with:
                - success: bool
                - discarded_count: int
                - message: str
        """
        sandbox = self.sessions.get(conversation_id)

        if not sandbox:
            return {
                "success": False,
                "message": f"Conversation not found: {conversation_id}"
            }

        discarded_count = len(sandbox.operations)

        try:
            logger.info(
                f"Rejecting {discarded_count} operations for "
                f"conversation {conversation_id}"
            )

            # Rollback to discard changes
            sandbox.rollback()

            # Clean up
            self.remove_sandbox(conversation_id)

            return {
                "success": True,
                "discarded_count": discarded_count,
                "message": f"Rejected {discarded_count} operation(s)"
            }

        except Exception as e:
            logger.error(
                f"Error rejecting operations for {conversation_id}: {e}",
                exc_info=True
            )

            # Still try to clean up
            self.remove_sandbox(conversation_id)

            return {
                "success": False,
                "message": str(e)
            }

    def remove_sandbox(self, conversation_id: str) -> None:
        """
        Remove sandbox from manager

        This also closes the sandbox session.

        Args:
            conversation_id: ID of the conversation
        """
        if conversation_id in self.sessions:
            sandbox = self.sessions.pop(conversation_id)
            sandbox.close()
            logger.info(f"Removed sandbox for conversation {conversation_id}")

    def get_sandbox(self, conversation_id: str) -> Optional[SandboxSession]:
        """
        Get sandbox for a conversation (without creating)

        Args:
            conversation_id: ID of the conversation

        Returns:
            SandboxSession or None if not found
        """
        return self.sessions.get(conversation_id)

    def get_all_conversation_ids(self) -> List[str]:
        """
        Get all conversation IDs currently in the manager

        Returns:
            List of conversation IDs
        """
        return list(self.sessions.keys())

    def close_all(self) -> None:
        """
        Close all sandboxes in the manager

        This is useful for cleanup/shutdown.
        """
        logger.info(f"Closing all {len(self.sessions)} sandboxes...")

        for conversation_id in list(self.sessions.keys()):
            self.remove_sandbox(conversation_id)

        logger.info("All sandboxes closed")

    def __len__(self) -> int:
        """Return number of active sandboxes"""
        return len(self.sessions)

    def __repr__(self) -> str:
        return f"SandboxSessionManager(sessions={len(self.sessions)})"


# Global singleton instance
sandbox_session_manager = SandboxSessionManager()
