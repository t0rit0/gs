"""
LangGraph node functions for MainAgent

Pure node functions that don't require access to MainAgent instance state.
LLM-dependent nodes are kept as methods in the MainAgent class.
"""

import logging
from typing import Dict, Any
from langchain_core.messages import AIMessage

from backend.agents.main_agent.graph import MainAgentState
from backend.agents.main_agent import tools
from backend.services.entity_graph_manager import entity_graph_manager

logger = logging.getLogger(__name__)


def routing_node(state: MainAgentState) -> Dict[str, Any]:
    """
    Routing node that checks if we have complete workflow state.

    If all three fields exist (hint_message, query_message, human_message),
    route directly to update_graph_tool (skip agent intent analysis).

    Otherwise, route to agent for normal intent-based routing.
    """
    hint_msg = state.get("hint_message")
    query_msg = state.get("query_message")
    human_msg = state.get("human_message")

    if hint_msg and query_msg and human_msg:
        # All three fields present - skip agent, go directly to update_graph
        logger.info("Routing: workflow state complete → update_graph_tool (skip intent analysis)")
        return {"_route": "update_graph_tool"}
    else:
        # Missing workflow state - route to agent for intent analysis
        logger.info(f"Routing: workflow state incomplete → agent (hint={bool(hint_msg)}, query={bool(query_msg)}, human={bool(human_msg)})")
        return {"_route": "agent"}


async def get_question_tool_node(state: MainAgentState) -> Dict[str, Any]:
    """
    Execute get_next_diagnostic_question tool

    Gets the structured hint from EntityGraph and returns it for the agent
    to convert into a natural conversational question.
    """
    result = await tools.get_next_diagnostic_question_node(state)

    # Check if data collection is complete - short-circuit to generate_report
    if result.get("accomplish"):
        result["_route"] = "generate_report_tool"
        return result

    # Store hint in state, but don't generate message yet
    # Let agent convert hint to natural conversation
    hint = result.get("last_hint", "Could you tell me more about your condition?")
    result["hint_message"] = hint
    # Don't set query_message or messages here - agent will generate them
    result["_route"] = "agent"
    return result


async def update_graph_tool_node(state: MainAgentState) -> Dict[str, Any]:
    """
    Execute update_diagnosis_graph tool

    Uses workflow state fields (hint_message, query_message, human_message)
    if available (set by routing_node), otherwise falls back to extracting from messages.
    """
    # Get EntityGraph from manager using conversation_id
    entity_graph = entity_graph_manager.get_or_create(
        conversation_id=state["conversation_id"],
        patient_id=state["patient_id"]
    )

    if not entity_graph:
        return {"messages": [AIMessage(content="I apologize, but I'm having trouble accessing the diagnostic system.")], "accomplish": True}

    try:
        # PRIORITY: Use workflow state fields if available (set by routing_node)
        hint = state.get("hint_message", "")
        ai_query = state.get("query_message", "")
        user_response = state.get("human_message", "")

        # FALLBACK: Extract from messages if workflow state not available
        if not (hint and ai_query and user_response):
            messages = state.get("messages", [])
            for msg in reversed(messages):
                if not user_response and msg.type == "human":
                    user_response = msg.content if hasattr(msg, 'content') else str(msg)
                elif not ai_query and msg.type == "ai":
                    ai_query = msg.content if hasattr(msg, 'content') else str(msg)
                if user_response and ai_query:
                    break

        if not hint:
            hint = state.get("last_hint", "")

        # Call EntityGraph.accept_message()
        log_messages = entity_graph.accept_message(
            hint_message=hint,
            query_message=ai_query,
            user_message=user_response
        )

        # Check if data collection is complete
        hint_message, accomplish, _ = entity_graph.get_hint_message()

        logger.info(f"Updated graph: accomplish={accomplish}")

        # Save EntityGraph state to database after update
        entity_graph_manager.save_state(state["conversation_id"])

        # Clear workflow state after use
        clear_state = {
            "hint_message": None,
            "query_message": None,
            "human_message": None
        }

        # Short-circuit routing: if accomplished, go directly to generate_report
        if accomplish:
            ack = "Thank you for that information. I've collected all the necessary data."
            result = {
                "messages": [AIMessage(content=ack)],
                "accomplish": accomplish,
                "_route": "generate_report_tool",
                **clear_state
            }
        else:
            ack = "Thank you. Let me ask you about another aspect of your health."
            result = {
                "messages": [AIMessage(content=ack)],
                "accomplish": accomplish,
                "_route": "agent",
                **clear_state
            }

        return result

    except Exception as e:
        logger.error(f"Error updating diagnosis graph: {e}")
        # Clear workflow state on error
        return {
            "messages": [AIMessage(content=f"I apologize, but I encountered an error: {str(e)}")],
            "accomplish": True,
            "_route": "generate_report_tool",
            "hint_message": None,
            "query_message": None,
            "human_message": None
        }


async def data_manager_tool_node(state: MainAgentState) -> Dict[str, Any]:
    """Execute data_manager tool"""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        question = last_message.tool_calls[0]["args"]["question"]
    else:
        return {"messages": [AIMessage(content="I couldn't understand your request about the database.")]}

    result_text = await tools.data_manager_node(state, question)
    return {"messages": [AIMessage(content=result_text)]}


async def generate_report_tool_node(state: MainAgentState) -> Dict[str, Any]:
    """Execute generate_diagnostic_report tool"""
    result = await tools.generate_diagnostic_report_node(state)

    report = result.get("report")
    if report:
        # Report is now a markdown string, display directly
        result["messages"] = [AIMessage(content=report)]
    else:
        result["messages"] = [AIMessage(content="I apologize, but I couldn't generate the report.")]

    result["accomplish"] = True
    result["_route"] = "agent"  # Route to agent to show report to user
    return result


# Routing functions

def route_from_routing(state: MainAgentState) -> str:
    """Route from routing_node based on _route"""
    return state.get("_route", "agent")


def route_from_agent(state: MainAgentState) -> str:
    """Route based on _route set by agent_node"""
    from langgraph.graph import END
    return state.get("_route", END)


def route_from_get_question(state: MainAgentState) -> str:
    """Route from get_question_tool based on _route"""
    return state.get("_route", "agent")


def route_from_update_graph(state: MainAgentState) -> str:
    """Route from update_graph_tool based on _route"""
    return state.get("_route", "agent")
