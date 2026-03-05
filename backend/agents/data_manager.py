"""
DataManagerCodeAgent - Database Operations Agent using Code Generation

This agent uses smolagents CodeAgent to generate and execute Python code
for database operations. Key features:

1. Uses Code Agent for maximum flexibility in generating database queries
2. Integrates with SandboxSession for approval workflow
3. Blocks access to conversations table (security)
4. Auto-loads ORM information as context
5. Executes generated code in controlled environment

Usage:
    agent = DataManagerCodeAgent()
    result = agent.process_request("Get patient with ID 123")
    # If result has pending_operations, get approval
    approved_result = agent.execute_pending(result["operation_id"])
"""

import os
import re
import logging
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session

from smolagents import ToolCallingAgent, OpenAIModel, tool

from backend.database.base import SessionLocal
from backend.database.models import Patient, Conversation, Message
from backend.database.crud import patient_crud, conversation_crud, message_crud
from backend.database.schemas import (
    PatientCreate, PatientUpdate,
    ConversationCreate, ConversationUpdate,
    MessageCreate
)
from backend.services.sandbox_session import SandboxSession
from backend.config.config_manager import get_config
from backend.prompts import load_prompt
from backend.agents.orm_helpers import get_custom_instructions

logger = logging.getLogger(__name__)


# ============================================
# Security: Blocked tables
# ============================================

BLOCKED_TABLES = ["conversations", "messages"]


def is_request_blocked(user_request: str) -> Optional[str]:
    """
    Check if request attempts to access blocked tables

    Args:
        user_request: User's natural language request

    Returns:
        Error message if blocked, None if allowed
    """
    request_lower = user_request.lower()

    # Check for blocked table names (both singular and plural)
    # Also check for variations like "conversation" vs "conversations"
    blocked_patterns = {
        "conversations": ["conversation", "conversations"],
        "messages": ["message", "messages"]
    }

    operation_keywords = [
        "get", "show", "find", "query", "search",
        "update", "modify", "change", "edit",
        "delete", "remove", "drop",
        "create", "insert", "add"
    ]

    # Check for operation keyword first
    has_operation = any(keyword in request_lower for keyword in operation_keywords)

    if not has_operation:
        return None

    # Now check for blocked table patterns
    for table, patterns in blocked_patterns.items():
        for pattern in patterns:
            if pattern in request_lower:
                return (
                    f"Security: Access to '{table}' table is not allowed. "
                    f"This table contains conversation data and cannot be accessed "
                    f"through the DataManager agent."
                )

    return None


# ============================================
# Tools for Code Agent
# ============================================

@tool
def query_database(code: str, conversation_id: str = "auto") -> str:
    """
    Execute database query code in SANDBOX MODE (ENFORCED)

    CRITICAL SECURITY: ALL write operations AUTOMATICALLY go through sandbox.
    User approval is REQUIRED before any changes are committed to database.

    IMPORTANT - Session-level sandbox:
    - Operations from the same conversation_id ACCUMULATE across multiple requests
    - All operations can be approved together at conversation end
    - Use SandboxSessionManager.approve_and_execute_all() to commit

    The code will have access to:
    - sandbox: SandboxSession for all operations (managed by SandboxSessionManager)
    - Patient, Conversation, Message: ORM models
    - patient_crud: Patient CRUD operations (uses sandbox automatically)

    SECURITY RESTRICTIONS:
    - Direct SessionLocal() usage is BLOCKED
    - Conversations and messages tables are BLOCKED
    - All write operations require user approval

    Args:
        code: Python code to execute
        conversation_id: ID for tracking sandbox operations (default: "auto")
                        IMPORTANT: Use consistent conversation_id to accumulate operations

    Returns:
        Execution result with pending operations info (if any writes attempted)
    """
    import uuid
    from backend.services.session_sandbox_manager import sandbox_session_manager

    # Security check for blocked tables
    block_error = is_request_blocked(code)
    if block_error:
        return f"ERROR: {block_error}"

    # Generate conversation_id if not provided
    if conversation_id == "auto":
        conversation_id = f"conv_{uuid.uuid4().hex[:8]}"

    # CRITICAL: Check if code tries to use SessionLocal directly
    forbidden_patterns = [
        "SessionLocal()",
        "SessionLocal (",
    ]
    for pattern in forbidden_patterns:
        if pattern in code:
            return (
                f"ERROR: Security violation - Direct session usage is not allowed. "
                f"Use the 'sandbox' object (managed by SandboxSessionManager) for all database operations. "
                f"All write operations will be recorded and require user approval."
            )

    # Create or get existing sandbox from manager
    # This enables operation accumulation across multiple requests
    _real_session = SessionLocal()
    sandbox = sandbox_session_manager.get_or_create_sandbox(_real_session, conversation_id)

    try:
        # Create execution environment with sandbox (NOT SessionLocal)
        exec_globals = {
            # EXPOSE: Sandbox session (this is the ONLY way to access DB)
            "sandbox": sandbox,
            "SandboxSession": SandboxSession,  # For reference, but sandbox is pre-created
            # Models (read-only access)
            "Patient": Patient,
            "Conversation": Conversation,
            "Message": Message,
            # NOTE: SessionLocal is NOT exposed - prevents direct access
            # CRUD operations (they will use the sandbox)
            "patient_crud": patient_crud,
            # Schemas
            "PatientCreate": PatientCreate,
            "PatientUpdate": PatientUpdate,
            # Result container
            "result": {},
        }

        # Execute code with sandbox environment
        exec_result = exec_globals["result"]
        exec(code, exec_globals)

        # Check if there are pending operations
        pending_ops = sandbox.get_pending_operations()

        # Build response
        if "output" in exec_result:
            output = str(exec_result["output"])
        elif "data" in exec_result:
            output = str(exec_result["data"])
        else:
            output = "Code executed successfully"

        # If there are pending operations, include that info
        if pending_ops:
            total_ops = len(pending_ops)
            output += f"\n\n[INFO] {total_ops} pending operation(s) recorded for conversation '{conversation_id}'."
            output += f" Use approve_and_execute_all('{conversation_id}') to commit when ready."

        # NOTE: We DON'T rollback or close here
        # The SandboxSessionManager manages the lifecycle
        # Operations accumulate across requests until approved/rejected

        return output

    except Exception as e:
        logger.error(f"Error executing database code: {e}", exc_info=True)
        # Rollback on error - but keep sandbox for potential retry
        if not sandbox._committed:
            sandbox.rollback()
        return f"ERROR: {str(e)}"


# ============================================
# DataManagerCodeAgent
# ============================================

class DataManagerCodeAgent:
    """
    Database operations agent using code generation

    This agent:
    1. Generates Python code for database operations
    2. Executes code in sandbox mode for safety
    3. Blocks access to sensitive tables
    4. Requires approval for write operations
    """

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the DataManagerCodeAgent

        Args:
            config_path: Optional path to configuration file.
                        If not provided, uses default config loading.
        """
        # Load model
        self.config = get_config(config_path)
        self.model = OpenAIModel(
            model_id=self.config.get_model(),
            api_key=self.config.get_api_key(),
            api_base=self.config.get_base_url(),
            extra_body={"enable_thinking": False}
        )

        # Get custom instructions (ORM documentation)
        custom_instructions = get_custom_instructions()

        from smolagents import LogLevel

        self.agent = ToolCallingAgent(
            tools=[query_database],
            model=self.model,
            verbosity_level=LogLevel.DEBUG,
            instructions=custom_instructions,
            max_steps=5 
        )

        logger.info(
            f"DataManagerCodeAgent initialized with "
            f"model={self.config.get_model()}, "
            f"base_url={self.config.get_base_url()}"
        )

    def process_request(
        self,
        user_request: str,
        conversation_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Process a natural language database request

        Args:
            user_request: Natural language request
            conversation_id: Optional conversation ID for sandbox

        Returns:
            Result dictionary with:
                - success: bool
                - final_answer: str (agent's final answer)
                - logs: str (execution logs)
                - error: str (if error occurred)
        """
        logger.info(f"Processing request: {user_request[:100]}...")

        # Security check
        block_error = is_request_blocked(user_request)
        if block_error:
            return {
                "success": False,
                "error": block_error
            }

        try:
            # Run agent to generate and execute code
            # Use return_full_result=True to get complete RunResult
            run_result = self.agent.run(user_request, return_full_result=True)

            # Build result dictionary with only final_answer and logs
            result = {
                "success": True,
                "final_answer": run_result.final_answer if hasattr(run_result, 'final_answer') else str(run_result),
                "logs": run_result.logs if hasattr(run_result, 'logs') else ""
            }

            # Check for errors
            if hasattr(run_result, 'error') and run_result.error:
                result["success"] = False
                result["error"] = run_result.error

            logger.info("Request processed successfully")
            return result

        except Exception as e:
            logger.error(f"Error processing request: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def get_pending_operations(self, conversation_id: str) -> List[Dict[str, Any]]:
        """
        Get pending operations for a conversation

        Args:
            conversation_id: Conversation ID

        Returns:
            List of pending operation dictionaries
        """
        from backend.services.session_sandbox_manager import sandbox_session_manager
        return sandbox_session_manager.get_pending_operations_summary(conversation_id)

    def has_pending_operations(self, conversation_id: str) -> bool:
        """
        Check if conversation has pending operations

        Args:
            conversation_id: Conversation ID

        Returns:
            True if pending operations exist
        """
        from backend.services.session_sandbox_manager import sandbox_session_manager
        return sandbox_session_manager.has_pending_operations(conversation_id)

    def approve_and_execute_all(self, conversation_id: str) -> Dict[str, Any]:
        """
        Approve and execute all pending operations for a conversation

        This is the NEW method that uses SandboxSessionManager for
        session-level sandbox management.

        Args:
            conversation_id: Conversation ID

        Returns:
            Result dictionary with execution status
        """
        from backend.services.session_sandbox_manager import sandbox_session_manager

        try:
            # Use the manager to approve and execute
            result = sandbox_session_manager.approve_and_execute_all(
                SessionLocal(),
                conversation_id
            )

            logger.info(f"Approval completed for {conversation_id}: {result}")
            return result

        except Exception as e:
            logger.error(f"Error approving operations for {conversation_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def reject_and_discard_all(self, conversation_id: str) -> Dict[str, Any]:
        """
        Reject and discard all pending operations for a conversation

        Args:
            conversation_id: Conversation ID

        Returns:
            Result dictionary with rejection status
        """
        from backend.services.session_sandbox_manager import sandbox_session_manager

        try:
            result = sandbox_session_manager.reject_and_discard_all(conversation_id)

            logger.info(f"Rejection completed for {conversation_id}: {result}")
            return result

        except Exception as e:
            logger.error(f"Error rejecting operations for {conversation_id}: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def execute_pending(
        self,
        operations_data: List[Dict[str, Any]],
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        Execute approved pending operations (LEGACY METHOD)

        Note: This method is kept for backward compatibility.
        New code should use approve_and_execute_all() instead.

        Args:
            operations_data: List of pending operations to execute
            conversation_id: Conversation ID for sandbox

        Returns:
            Result dictionary with execution status
        """
        try:
            # Create sandbox session
            sandbox = SandboxSession(SessionLocal(), conversation_id)

            # Restore operations
            from backend.services.sandbox_session import DatabaseOperation
            sandbox.operations = []
            for op_dict in operations_data:
                op = DatabaseOperation(
                    operation_type=op_dict["operation_type"],
                    table_name=op_dict["table_name"],
                    details=op_dict["details"]
                )
                sandbox.operations.append(op)

            # Disable sandbox and execute
            sandbox.disable_sandbox()
            result = sandbox.execute_pending()
            sandbox.close()

            return result

        except Exception as e:
            logger.error(f"Error executing pending operations: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    def __repr__(self):
        return "DataManagerCodeAgent(model=ToolCallingAgent, tools=[query_database])"
