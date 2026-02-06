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

from smolagents import CodeAgent, OpenAIModel, tool

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
def query_database(code: str) -> str:
    """
    Execute database query code in sandbox mode

    This tool executes Python code for database operations in a sandboxed environment.
    The code will have access to:
    - SessionLocal: Database session factory
    - patient_crud: Patient CRUD operations
    - SandboxSession: Sandbox wrapper for sessions
    - Patient, Conversation, Message: ORM models

    IMPORTANT:
    - Code MUST use SandboxSession for any write operations
    - Conversations and messages tables are BLOCKED for security
    - Queries should return readable results

    Args:
        code: Python code to execute

    Returns:
        String representation of execution result
    """
    # Security check
    block_error = is_request_blocked(code)
    if block_error:
        return f"ERROR: {block_error}"

    # Create execution environment
    exec_globals = {
        "SessionLocal": SessionLocal,
        "SandboxSession": SandboxSession,
        # Models
        "Patient": Patient,
        "Conversation": Conversation,
        "Message": Message,
        # CRUD operations
        "patient_crud": patient_crud,
        "conversation_crud": conversation_crud,
        "message_crud": message_crud,
        # Schemas
        "PatientCreate": PatientCreate,
        "PatientUpdate": PatientUpdate,
        "ConversationCreate": ConversationCreate,
        "ConversationUpdate": ConversationUpdate,
        "MessageCreate": MessageCreate,
    }

    try:
        # Execute code
        exec_result = {}
        exec_globals["result"] = exec_result

        exec(code, exec_globals)

        # Return result
        if "output" in exec_result:
            return str(exec_result["output"])
        elif "data" in exec_result:
            return str(exec_result["data"])
        else:
            return "Code executed successfully (no explicit output)"

    except Exception as e:
        logger.error(f"Error executing database code: {e}", exc_info=True)
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
            api_base=self.config.get_base_url()
        )

        # Get custom instructions (ORM documentation)
        custom_instructions = get_custom_instructions()
        self.agent = CodeAgent(
            tools=[query_database],
            model=self.model,
            max_steps=5,
            instructions=custom_instructions
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

    def execute_pending(
        self,
        operations_data: List[Dict[str, Any]],
        conversation_id: str
    ) -> Dict[str, Any]:
        """
        Execute approved pending operations

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
        return "DataManagerCodeAgent(model=CodeAgent, tools=[query_database])"
