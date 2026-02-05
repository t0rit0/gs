"""
Sandbox Session for Intercepting Database Commits

This module provides a sandbox mechanism that intercepts database commit operations
to enable approval workflows for data modifications.
"""

from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from contextlib import contextmanager
import logging

logger = logging.getLogger(__name__)


class DatabaseOperation:
    """
    Represents a single database operation (insert/update/delete)

    Attributes:
        operation_type: Type of operation ("insert", "update", "delete")
        table_name: Name of the database table
        details: Operation details (data, changes, etc.)
        timestamp: When the operation was created
    """

    def __init__(
        self,
        operation_type: str,
        table_name: str,
        details: Dict[str, Any]
    ):
        self.operation_type = operation_type
        self.table_name = table_name
        self.details = details
        from datetime import datetime
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization"""
        return {
            "operation_type": self.operation_type,
            "table_name": self.table_name,
            "details": self.details,
            "timestamp": self.timestamp
        }

    def __repr__(self):
        return f"DatabaseOperation({self.operation_type} on {self.table_name})"


class SandboxSession:
    """
    Wrapper around SQLAlchemy Session that intercepts commit operations

    Key Features:
    - Wraps real SQLAlchemy session
    - Intercepts all commit() calls
    - Records operations without executing them
    - Enables approval workflow
    - Can execute approved operations

    Usage:
        with sandbox_session(real_db, conversation_id) as sandbox:
            # Normal ORM operations
            patient = patient_crud.get(sandbox, patient_id)
            patient.name = "New Name"
            sandbox.commit()  # Intercepted, not actually committed

        # After approval
        sandbox.execute_pending()  # Actually commits
    """

    def __init__(self, real_session: Session, conversation_id: str):
        """
        Initialize sandbox session

        Args:
            real_session: The real SQLAlchemy session to wrap
            conversation_id: ID of the current conversation
        """
        self.real_session = real_session
        self.conversation_id = conversation_id

        # Operation tracking
        self.operations: List[DatabaseOperation] = []
        self.is_sandboxed = True  # Default: sandbox mode enabled

        # Execution state
        self._committed = False
        self._rolled_back = False

        logger.info(f"Created SandboxSession for conversation {conversation_id}")

    def __getattr__(self, name: str):
        """
        Proxy all other attributes to the real session

        This allows SandboxSession to behave exactly like a real Session
        """
        return getattr(self.real_session, name)

    def commit(self) -> None:
        """
        Intercept commit calls

        - If sandboxed: Record operation and flush only (no actual commit)
        - If not sandboxed: Actually commit to database
        """
        if self.is_sandboxed:
            # Sandbox mode: Record operation but don't commit
            self._record_pending_commit()
            logger.info(f"Commit intercepted in sandbox mode. Operations: {len(self.operations)}")
        else:
            # Non-sandbox mode: Actually commit
            self.real_session.commit()
            self._committed = True
            logger.info(f"Actually committed to database. Conversation: {self.conversation_id}")

    def _record_pending_commit(self) -> None:
        """
        Record all pending changes as operations

        Scans the session for:
        - New objects (insert)
        - Dirty objects (update)
        - Deleted objects (delete)
        """
        # Scan session for pending changes
        pending_changes = self._scan_pending_changes()

        if not pending_changes:
            logger.debug("No pending changes to record")
            return

        # Create operation record
        operation = DatabaseOperation(
            operation_type="batch_commit",
            table_name="patients",  # Simplified; in real use, detect from changes
            details={
                "pending_changes": pending_changes,
                "conversation_id": self.conversation_id,
                "change_count": len(pending_changes)
            }
        )

        self.operations.append(operation)

        # Flush to make changes visible in transaction, but don't commit
        self.real_session.flush()
        logger.info(f"Recorded {len(pending_changes)} pending changes")

    def _scan_pending_changes(self) -> List[Dict[str, Any]]:
        """
        Scan session for pending database changes

        Returns:
            List of pending changes (insert/update/delete)
        """
        pending = []

        # New objects (insert)
        for obj in self.real_session.new:
            pending.append({
                "type": "insert",
                "table": self._get_table_name(obj),
                "data": self._serialize_object(obj)
            })
            logger.debug(f"Detected INSERT on {self._get_table_name(obj)}")

        # Dirty objects (update)
        for obj in self.real_session.dirty:
            pending.append({
                "type": "update",
                "table": self._get_table_name(obj),
                "object_id": self._get_object_id(obj),
                "changes": self._get_object_changes(obj)
            })
            logger.debug(f"Detected UPDATE on {self._get_table_name(obj)}")

        # Deleted objects (delete)
        for obj in self.real_session.deleted:
            pending.append({
                "type": "delete",
                "table": self._get_table_name(obj),
                "object_id": self._get_object_id(obj)
            })
            logger.debug(f"Detected DELETE on {self._get_table_name(obj)}")

        return pending

    def _get_table_name(self, obj) -> str:
        """Get table name from ORM object"""
        if hasattr(obj, '__tablename__'):
            return obj.__tablename__
        if hasattr(obj, '__table__'):
            return obj.__table__.name
        return "unknown"

    def _get_object_id(self, obj) -> Optional[str]:
        """Get primary key value from object"""
        try:
            if hasattr(obj, 'patient_id'):
                return obj.patient_id
            if hasattr(obj, 'id'):
                return str(obj.id)
        except Exception:
            pass
        return None

    def _serialize_object(self, obj) -> Dict[str, Any]:
        """
        Serialize ORM object to dictionary

        Args:
            obj: SQLAlchemy model object

        Returns:
            Dictionary representation of the object
        """
        # Use to_dict() if available
        if hasattr(obj, 'to_dict'):
            return obj.to_dict()

        # Generic serialization
        result = {}
        for column in obj.__table__.columns:
            value = getattr(obj, column.name, None)
            if value is not None:
                # Handle complex types
                if isinstance(value, (list, dict)):
                    result[column.name] = value
                elif hasattr(value, 'isoformat'):  # datetime
                    result[column.name] = value.isoformat()
                else:
                    result[column.name] = value
        return result

    def _get_object_changes(self, obj) -> Dict[str, Dict[str, Any]]:
        """
        Get changes made to a dirty object

        Returns:
            Dictionary mapping field names to {old, new} values
        """
        from sqlalchemy import inspect

        state = inspect(obj)
        changes = {}

        for attr in state.attrs:
            history = attr.load_history()
            if history.has_changes():
                old_value = history.deleted[0] if history.deleted else None
                new_value = history.added[0] if history.added else None

                # Serialize values
                if hasattr(old_value, 'isoformat'):
                    old_value = old_value.isoformat()
                if hasattr(new_value, 'isoformat'):
                    new_value = new_value.isoformat()

                changes[attr.key] = {
                    "old": old_value,
                    "new": new_value
                }

        return changes

    def rollback(self) -> None:
        """
        Rollback the database transaction

        Note: Operations are preserved for review even after rollback.
        This allows inspection of what was attempted.
        """
        self.real_session.rollback()
        self._rolled_back = True
        logger.info("Rolled back session (operations preserved for review)")

    def disable_sandbox(self) -> None:
        """
        Disable sandbox mode to allow actual commits
        """
        self.is_sandboxed = False
        logger.info("Sandbox mode DISABLED - commits will be executed")

    def enable_sandbox(self) -> None:
        """
        Enable sandbox mode to intercept commits
        """
        self.is_sandboxed = True
        logger.info("Sandbox mode ENABLED - commits will be intercepted")

    def get_pending_operations(self) -> List[Dict[str, Any]]:
        """
        Get all recorded operations as dictionaries

        Returns:
            List of operation dictionaries
        """
        return [op.to_dict() for op in self.operations]

    def has_pending_operations(self) -> bool:
        """Check if there are pending operations"""
        return len(self.operations) > 0

    def execute_pending(self) -> Dict[str, Any]:
        """
        Actually execute all pending operations

        This method:
        1. Disables sandbox mode
        2. Actually commits to database
        3. Returns execution result

        Returns:
            Dictionary with execution status and details
        """
        if not self.operations:
            return {
                "success": False,
                "error": "No pending operations to execute"
            }

        try:
            logger.info(f"Executing {len(self.operations)} pending operations...")

            # Disable sandbox to allow real commit
            self.disable_sandbox()

            # Actually commit
            self.real_session.commit()
            self._committed = True

            result = {
                "success": True,
                "executed_count": len(self.operations),
                "operations": self.get_pending_operations(),
                "conversation_id": self.conversation_id
            }

            logger.info(f"Successfully executed {len(self.operations)} operations")
            return result

        except Exception as e:
            # Rollback on error
            self.real_session.rollback()
            logger.error(f"Failed to execute operations: {e}", exc_info=True)

            return {
                "success": False,
                "error": str(e),
                "operations": self.get_pending_operations()
            }

    def close(self) -> None:
        """
        Close the sandbox session

        This closes the underlying real session but preserves operations for review.
        """
        self.real_session.close()
        logger.info("Closed sandbox session (operations preserved)")

    def __repr__(self):
        return f"SandboxSession(conversation={self.conversation_id}, sandboxed={self.is_sandboxed}, operations={len(self.operations)})"

    # Context manager protocol
    def __enter__(self):
        """Enter context manager"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """
        Exit context manager

        Automatically rollback if not committed
        """
        # Cleanup: Rollback if not committed
        if not self._committed and not self._rolled_back:
            logger.debug("Auto-rolling back uncommitted changes")
            self.rollback()
        return False  # Don't suppress exceptions


@contextmanager
def sandbox_session(real_session: Session, conversation_id: str):
    """
    Context manager for creating sandbox sessions

    Automatically handles cleanup and rollback on exit.

    Args:
        real_session: Real SQLAlchemy session to wrap
        conversation_id: ID of current conversation

    Yields:
        SandboxSession instance

    Example:
        with sandbox_session(db, "conv_123") as sandbox:
            patient = patient_crud.get(sandbox, patient_id)
            patient.name = "New Name"
            sandbox.commit()  # Intercepted

        # After approval
        sandbox.execute_pending()
    """
    sandbox = SandboxSession(real_session, conversation_id)

    try:
        logger.debug(f"Entering sandbox context for conversation {conversation_id}")
        yield sandbox

    finally:
        # Cleanup: Rollback if not committed
        if not sandbox._committed and not sandbox._rolled_back:
            logger.debug("Auto-rolling back uncommitted changes")
            sandbox.rollback()

        logger.debug(f"Exiting sandbox context for conversation {conversation_id}")
