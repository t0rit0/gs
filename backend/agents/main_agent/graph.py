"""
MainAgent State Schema

Defines the state structure for MainAgent's LangGraph.
"""

from typing import TypedDict, Annotated, Optional, Dict, Any
from langgraph.graph import add_messages


class MainAgentState(TypedDict):
    """
    State for MainAgent's LangGraph.

    This state is automatically persisted by LangGraph's checkpointer
    based on thread_id (conversation_id).
    """
    # Message history (automatically managed by LangGraph)
    messages: Annotated[list, add_messages]

    # Conversation identifiers
    conversation_id: str                      # Unique conversation identifier (used as thread_id)
    patient_id: str                           # Patient identifier for this conversation

    # EntityGraph state
    entity_graph: Any                         # DrHyper EntityGraph instance (will be properly typed)

    # Diagnostic state
    accomplish: bool                          # Whether diagnosis data collection is complete
    last_hint: str                            # Last hint message from get_hint_message

    # Report
    report: Optional[Dict[str, Any]]          # Generated diagnostic report (when accomplish=True)
