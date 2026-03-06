"""
MainAgent Tools - Tools for diagnostic conversations

These tools are designed to work with LangGraph.
The state (entity_graph, patient_id, etc.) will be passed from the node function
that calls these tools.

Note: In LangGraph, tools typically receive individual parameters.
The full state is accessible in the node function that invokes these tools.
"""

import logging
import time
from typing import Dict, Any

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from backend.config.config_manager import get_config
from drhyper.utils.logging import get_logger, log_event

logger = get_logger("MainAgentTools")


@tool
def get_next_diagnostic_question() -> str:
    """
    Get the next diagnostic question to ask the patient.

    This tool is called by the agent node which has access to the full state.
    The node function will update the state based on the result.

    Returns:
        Placeholder hint message (actual implementation will use entity_graph from state)
    """
    # This is a simplified tool version
    # In the actual node function, we'll access state["entity_graph"].get_hint_message()
    return "DIAGNOSTIC_QUESTION_PLACEHOLDER"


@tool
def update_diagnosis_graph(user_response: str, query_message: str) -> Dict[str, Any]:
    """
    Update the diagnosis graph with information from the patient's response.

    Args:
        user_response: The patient's response
        query_message: The question that was asked to the user

    Returns:
        Dict with updated_nodes, new_nodes, accomplish status
    """
    # This is a simplified tool version
    # In the actual node function, we'll access state["entity_graph"] and state["last_hint"]
    return {
        "updated_nodes": 0,
        "new_nodes": 0,
        "accomplish": False,
        "success": True
    }


@tool
def data_manager(question: str) -> str:
    """
    Query or modify patient data in the database.

    This tool handles ALL database-related requests from the user, including:
    - Reading patient history, medications, allergies, etc.
    - Updating patient information
    - Adding new health records

    IMPORTANT: Write operations are recorded in a sandbox and require user approval
    at the end of the conversation.

    Args:
        question: Natural language request about patient data

    Returns:
        Query result or confirmation of pending changes
    """
    # This is a simplified tool version
    # In the actual node function, we'll access state["patient_id"]
    return f"DATABASE_QUERY_PLACEHOLDER: {question}"


@tool
def generate_diagnostic_report() -> Dict[str, Any]:
    """
    Generate the final diagnostic report when data collection is complete.

    Returns:
        Dict with summary, findings, recommendations, follow_up
    """
    # This is a simplified tool version
    # In the actual node function, we'll access state["entity_graph"]
    return {
        "summary": "Placeholder report",
        "key_findings": "No findings",
        "recommendations": "No recommendations",
        "follow_up": "No follow-up",
        "full_report": "Placeholder full report"
    }


# Node functions that have access to full state and call the tools
async def get_next_diagnostic_question_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node function that gets the next diagnostic question.

    Gets EntityGraph from EntityGraphManager using conversation_id.
    Updates state with hint and accomplish status.
    """
    from langchain_core.messages import AIMessage
    from backend.services.entity_graph_manager import entity_graph_manager

    conversation_id = state.get("conversation_id", "unknown")
    logger.debug(f"[conv:{conversation_id[:8]}] get_next_diagnostic_question_node started")
    start_time = time.time()

    # Get EntityGraph from manager
    entity_graph = entity_graph_manager.get_or_create(
        conversation_id=state.get("conversation_id", ""),
        patient_id=state.get("patient_id", "")
    )

    if not entity_graph:
        logger.warning(f"[conv:{conversation_id[:8]}] EntityGraph not available from manager")
        # Set accomplish=True to stop the loop
        return {
            "messages": [AIMessage(content="I apologize, but I'm having trouble accessing the diagnostic system.")],
            "accomplish": True
        }

    try:
        # Call EntityGraph.get_hint_message()
        hint_message, accomplish, log_messages = entity_graph.get_hint_message()

        logger.info(f"[conv:{conversation_id[:8]}] Got hint: {hint_message[:100]}... accomplish={accomplish}")
        log_event(logger, "HINT_GENERATED", f"Hint: {hint_message[:50]}...",
                 extra_data={
                     "conversation_id": conversation_id,
                     "accomplish": accomplish,
                     "hint_length": len(hint_message) if hint_message else 0
                 })

        # Save EntityGraph state to database
        entity_graph_manager.save_state(state["conversation_id"])
        logger.debug(f"[conv:{conversation_id[:8]}] EntityGraph state saved")
        
        elapsed = time.time() - start_time
        logger.debug(f"[conv:{conversation_id[:8]}] get_next_diagnostic_question_node completed in {elapsed:.2f}s")

        return {
            "last_hint": hint_message,
            "accomplish": accomplish
        }

    except Exception as e:
        logger.error(f"[conv:{conversation_id[:8]}] Error getting next diagnostic question: {e}", exc_info=True)
        log_event(logger, "HINT_ERROR", f"Error: {str(e)}",
                 extra_data={"conversation_id": conversation_id}, level=logging.ERROR)
        # Set accomplish=True to stop the loop on error
        return {
            "messages": [AIMessage(content=f"I'm experiencing technical difficulties: {str(e)}")],
            "accomplish": True
        }


async def update_diagnosis_graph_node(state: Dict[str, Any], user_response: str, query_message: str) -> Dict[str, Any]:
    """
    Node function that updates the diagnosis graph.

    Has access to full state including entity_graph and last_hint.
    """
    conversation_id = state.get("conversation_id", "unknown")
    logger.debug(f"[conv:{conversation_id[:8]}] update_diagnosis_graph_node started")
    
    entity_graph = state.get("entity_graph")
    if not entity_graph:
        logger.error(f"[conv:{conversation_id[:8]}] entity_graph not found in state")
        return {"error": "Entity graph not available"}

    try:
        # Get hint from state
        hint = state.get("last_hint", "")

        # Call EntityGraph.accept_message()
        log_messages = entity_graph.accept_message(
            hint_message=hint,
            query_message=query_message,
            user_message=user_response
        )

        # Check if data collection is complete
        hint_message, accomplish, _ = entity_graph.get_hint_message()

        # Count nodes in graph
        updated_nodes = len([n for n, d in entity_graph.entity_graph.nodes(data=True) if d.get("value")])
        new_nodes = entity_graph.entity_graph.number_of_nodes()

        logger.info(
            f"[conv:{conversation_id[:8]}] Updated graph: {updated_nodes} nodes with values, "
            f"{new_nodes} total nodes, accomplish={accomplish}"
        )
        log_event(logger, "GRAPH_UPDATED", "Diagnosis graph updated",
                 extra_data={
                     "conversation_id": conversation_id,
                     "updated_nodes": updated_nodes,
                     "total_nodes": new_nodes,
                     "accomplish": accomplish
                 })

        return {
            "accomplish": accomplish,
            "updated_nodes": updated_nodes,
            "new_nodes": new_nodes
        }

    except Exception as e:
        logger.error(f"[conv:{conversation_id[:8]}] Error updating diagnosis graph: {e}", exc_info=True)
        log_event(logger, "GRAPH_UPDATE_ERROR", f"Error: {str(e)}",
                 extra_data={"conversation_id": conversation_id}, level=logging.ERROR)
        return {"error": str(e)}


async def data_manager_node(state: Dict[str, Any], question: str) -> str:
    """
    Node function that handles database requests.

    Has access to full state including patient_id.
    Uses DataManagerCodeAgent with sandbox functionality for database operations.

    Note: Write operations are recorded in the sandbox and require approval.

    Args:
        state: MainAgentState containing patient_id and conversation_id
        question: Natural language database query from user

    Returns:
        Query result or confirmation of pending changes
    """
    patient_id = state.get("patient_id")
    conversation_id = state.get("conversation_id")
    
    logger.debug(f"[conv:{conversation_id[:8]}] data_manager_node started: {question[:50]}...")
    start_time = time.time()

    if not patient_id:
        logger.warning(f"[conv:{conversation_id[:8]}] patient_id not found in state")
        return "I'm unable to access patient records."

    try:
        # Import DataManagerCodeAgent (smolagents-based with sandbox)
        from backend.agents.data_manager import DataManagerCodeAgent

        # Create DataManagerCodeAgent instance
        data_manager = DataManagerCodeAgent(config_path=None)

        # Formulate request with patient context
        full_request = f"For patient_id={patient_id}: {question}"

        # Process request via DataManager
        logger.info(f"[conv:{conversation_id[:8]}] Processing data_manager query: {question[:80]}...")
        result = data_manager.process_request(
            user_request=full_request,
            conversation_id=conversation_id
        )
        
        elapsed = time.time() - start_time

        if result.get("success"):
            answer = result.get("final_answer", "No data found")

            # Check if there are pending operations (writes awaiting approval)
            has_pending = data_manager.has_pending_operations(conversation_id)
            if has_pending:
                pending_ops = data_manager.get_pending_operations(conversation_id)
                pending_count = len(pending_ops)
                logger.info(f"[conv:{conversation_id[:8]}] Query resulted in {pending_count} pending write operations")
                log_event(logger, "PENDING_OPERATIONS", f"{pending_count} operations pending approval",
                         extra_data={
                             "conversation_id": conversation_id,
                             "pending_count": pending_count,
                             "latency_ms": elapsed * 1000
                         })

                # Append a note about pending operations
                answer += f"\n\n[Note: {pending_count} database change(s) are pending approval. "
                answer += f"These will be saved after you approve them at the end of the conversation.]"
            else:
                logger.debug(f"[conv:{conversation_id[:8]}] data_manager_node completed successfully")
                log_event(logger, "DATA_MANAGER_QUERY", "Query completed",
                         extra_data={
                             "conversation_id": conversation_id,
                             "success": True,
                             "latency_ms": elapsed * 1000
                         })

            return answer
        else:
            error = result.get("error", "Unknown error")
            logger.error(f"[conv:{conversation_id[:8]}] data_manager error: {error}")
            log_event(logger, "DATA_MANAGER_ERROR", f"Error: {str(error)}",
                     extra_data={"conversation_id": conversation_id}, level=logging.ERROR)
            return f"Error querying database: {error}"

    except Exception as e:
        logger.error(f"[conv:{conversation_id[:8]}] Error in data_manager_node: {e}", exc_info=True)
        log_event(logger, "DATA_MANAGER_EXCEPTION", f"Exception: {str(e)}",
                 extra_data={"conversation_id": conversation_id}, level=logging.ERROR)
        return f"Error: {str(e)}"


async def generate_diagnostic_report_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node function that generates the diagnostic report.

    Gets EntityGraph from EntityGraphManager using conversation_id.
    Returns the report as a markdown string directly.
    """
    from pathlib import Path
    from backend.services.entity_graph_manager import entity_graph_manager

    conversation_id = state.get("conversation_id", "unknown")
    logger.info(f"[conv:{conversation_id[:8]}] generate_diagnostic_report_node started")
    start_time = time.time()

    # Get EntityGraph from manager
    entity_graph = entity_graph_manager.get_or_create(
        conversation_id=state.get("conversation_id", ""),
        patient_id=state.get("patient_id", "")
    )

    if not entity_graph:
        logger.error(f"[conv:{conversation_id[:8]}] EntityGraph not available from manager")
        return {"error": "Entity graph not available", "report": "Unable to generate report: Entity graph not available"}

    try:
        # Serialize collected data from EntityGraph
        collected_data = entity_graph._serialize_nodes_with_value(entity_graph.entity_graph)

        logger.info(f"[conv:{conversation_id[:8]}] Generating report with {len(collected_data)} characters of collected data")
        log_event(logger, "REPORT_GENERATION_START", "Starting report generation",
                 extra_data={
                     "conversation_id": conversation_id,
                     "collected_data_length": len(collected_data)
                 })

        # Load report template
        template_path = Path(__file__).parent.parent.parent / "prompts" / "report_template.txt"
        if template_path.exists():
            template = template_path.read_text()
            prompt = template.format(collected_data=collected_data)
            logger.debug(f"[conv:{conversation_id[:8]}] Using report template from {template_path}")
        else:
            # Fallback to inline prompt
            prompt = f"""You are a medical assistant generating a diagnostic report for hypertension assessment.

Generate a comprehensive diagnostic report in Markdown format based on the following collected patient information:

{collected_data}

Include sections for Summary, Key Findings, Recommendations, Follow-up Plan, and Risk Assessment.
Be professional, clear, and actionable in your recommendations."""
            logger.debug(f"[conv:{conversation_id[:8]}] Using fallback inline report prompt")

        # Get LLM configuration
        config = get_config()
        llm = ChatOpenAI(
            model=config.get("main_agent.model", config.get_model()),
            api_key=config.get_api_key(),
            base_url=config.get_base_url(),
            temperature=0.7
        )

        # Generate report using LLM
        logger.debug(f"[conv:{conversation_id[:8]}] Invoking LLM for report generation")
        response = await llm.ainvoke([HumanMessage(content=prompt)])
        report_text = response.content
        
        elapsed = time.time() - start_time

        logger.info(f"[conv:{conversation_id[:8]}] Diagnostic report generated successfully ({len(report_text)} chars, {elapsed:.2f}s)")
        log_event(logger, "REPORT_GENERATED", "Report generation completed",
                 extra_data={
                     "conversation_id": conversation_id,
                     "report_length": len(report_text),
                     "latency_ms": elapsed * 1000
                 })
        return {
            "report": report_text,
            "report_status": "generated"
        }

    except Exception as e:
        logger.error(f"[conv:{conversation_id[:8]}] Error generating diagnostic report: {e}", exc_info=True)
        log_event(logger, "REPORT_GENERATION_ERROR", f"Error: {str(e)}",
                 extra_data={"conversation_id": conversation_id}, level=logging.ERROR)
        return {
            "error": str(e),
            "report": f"Error generating report: {str(e)}",
            "report_status": "error"
        }
