"""
MainAgent State Schema

Defines the state structure for MainAgent's LangGraph.
"""

from typing import TypedDict, Annotated, Optional, Dict, Any
from langgraph.graph import add_messages


class MainAgentState(TypedDict, total=False):
    """
    State for MainAgent's LangGraph.

    This state is automatically persisted by LangGraph's checkpointer
    based on thread_id (conversation_id).

    Note: total=False makes all fields optional, but we mark required fields below.
    """
    # Message history (automatically managed by LangGraph)
    messages: Annotated[list, add_messages]

    # Conversation identifiers
    conversation_id: str                      # Unique conversation identifier (used as thread_id)
    patient_id: str                           # Patient identifier for this conversation

    # EntityGraph is now managed by EntityGraphManager, NOT stored in state
    # Use conversation_id to retrieve EntityGraph instances via EntityGraphManager

    # Diagnostic state
    accomplish: bool                          # Whether diagnosis data collection is complete
    last_hint: str                            # Last hint message from get_hint_message

    # Workflow routing fields (eliminate redundant intent analysis)
    hint_message: Optional[str]               # Hint from EntityGraph (for routing check)
    query_message: Optional[str]              # Conversational question shown to user
    human_message: Optional[str]              # User's response (for routing check)

    # Report
    report: Optional[Dict[str, Any]]          # Generated diagnostic report (when accomplish=True)

    # Report Approval State
    report_status: Optional[str]              # Report status: "none", "generated", "pending_approval", "approved", "rejected"
    report_id: Optional[str]                 # Report ID after creation
    approval_notes: Optional[str]             # Doctor's notes during approval/rejection

    # Internal routing field (not persisted)
    _route: Optional[str]                     # Next node to route to (set by agent_node)
