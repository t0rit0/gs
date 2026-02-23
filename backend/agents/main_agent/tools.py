"""
MainAgent Tools - Tools for diagnostic conversations

These tools are designed to work with LangGraph.
The state (entity_graph, patient_id, etc.) will be passed from the node function
that calls these tools.

Note: In LangGraph, tools typically receive individual parameters.
The full state is accessible in the node function that invokes these tools.
"""

import logging
from typing import Dict, Any

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

from backend.config.config_manager import get_config

logger = logging.getLogger(__name__)


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
def query_patient_history(question: str) -> str:
    """
    Query the patient's medical history from the database.

    Args:
        question: Natural language query about patient history

    Returns:
        Query results as formatted text
    """
    # This is a simplified tool version
    # In the actual node function, we'll access state["patient_id"]
    return f"PATIENT_HISTORY_QUERY_PLACEHOLDER: {question}"


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

    Has access to full state including entity_graph.
    Updates state with hint and accomplish status.
    """
    entity_graph = state.get("entity_graph")
    if not entity_graph:
        logger.warning("entity_graph not found in state")
        return {"messages": ["I apologize, but I'm having trouble accessing the diagnostic system."]}

    try:
        # Call EntityGraph.get_hint_message()
        hint_message, accomplish, log_messages = entity_graph.get_hint_message()

        logger.info(f"Got hint message: {hint_message[:100]}... accomplish={accomplish}")

        return {
            "last_hint": hint_message,
            "accomplish": accomplish
        }

    except Exception as e:
        logger.error(f"Error getting next diagnostic question: {e}")
        return {"messages": [f"I'm experiencing technical difficulties: {str(e)}"]}


async def update_diagnosis_graph_node(state: Dict[str, Any], user_response: str, query_message: str) -> Dict[str, Any]:
    """
    Node function that updates the diagnosis graph.

    Has access to full state including entity_graph and last_hint.
    """
    entity_graph = state.get("entity_graph")
    if not entity_graph:
        logger.error("entity_graph not found in state")
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
            f"Updated graph: {updated_nodes} nodes with values, "
            f"{new_nodes} total nodes, accomplish={accomplish}"
        )

        return {
            "accomplish": accomplish,
            "updated_nodes": updated_nodes,
            "new_nodes": new_nodes
        }

    except Exception as e:
        logger.error(f"Error updating diagnosis graph: {e}")
        return {"error": str(e)}


async def query_patient_history_node(state: Dict[str, Any], question: str) -> str:
    """
    Node function that queries patient history.

    Has access to full state including patient_id.
    """
    patient_id = state.get("patient_id")
    if not patient_id:
        logger.warning("patient_id not found in state")
        return "I'm unable to access patient records."

    try:
        # Import SQLAgent
        from backend.agents.sql_agent import SQLAgent

        # Create SQLAgent instance
        sql_agent = SQLAgent(config_path=None)

        # Formulate request with patient context
        full_request = f"For patient_id={patient_id}: {question}"

        # Process request via SQLAgent
        result = await sql_agent.process_request(
            conversation_id=state["conversation_id"],
            user_request=full_request
        )

        if result.get("success"):
            return result.get("final_answer", "No data found")
        else:
            return f"Error querying patient history: {result.get('error', 'Unknown error')}"

    except Exception as e:
        logger.error(f"Error querying patient history: {e}")
        return f"Error: {str(e)}"


async def generate_diagnostic_report_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Node function that generates the diagnostic report.

    Has access to full state including entity_graph.
    """
    entity_graph = state.get("entity_graph")
    if not entity_graph:
        logger.error("entity_graph not found in state")
        return {"error": "Entity graph not available", "summary": "Unable to generate report"}

    try:
        # Serialize collected data from EntityGraph
        collected_data = entity_graph._serialize_nodes_with_value(entity_graph.entity_graph)

        logger.info(f"Generating report with {len(collected_data)} characters of collected data")

        # Get LLM configuration
        config = get_config()
        llm = ChatOpenAI(
            model=config.get("main_agent.model", config.get_model()),
            api_key=config.get_api_key(),
            base_url=config.get_base_url(),
            temperature=0.7
        )

        # Generate report using LLM
        prompt = f"""You are a medical assistant generating a diagnostic report for hypertension assessment.

Based on the following collected patient information, generate a structured diagnostic report:

{collected_data}

Please provide a report with the following sections:
1. Summary: Brief overview of the patient's condition
2. Key Findings: Important clinical observations
3. Recommendations: Lifestyle and treatment recommendations
4. Follow-up: Recommended follow-up schedule

Format the report in a clear, professional manner suitable for medical documentation."""

        response = await llm.ainvoke([HumanMessage(content=prompt)])
        report_text = response.content

        # Parse report into sections
        report = {
            "summary": _extract_section(report_text, "Summary"),
            "key_findings": _extract_section(report_text, "Key Findings"),
            "recommendations": _extract_section(report_text, "Recommendations"),
            "follow_up": _extract_section(report_text, "Follow-up"),
            "full_report": report_text
        }

        logger.info("Diagnostic report generated successfully")
        return {"report": report}

    except Exception as e:
        logger.error(f"Error generating diagnostic report: {e}")
        return {"error": str(e), "summary": f"Error generating report: {str(e)}"}


def _extract_section(text: str, section_name: str) -> str:
    """Extract a section from the generated report text"""
    lines = text.split("\n")
    section_lines = []
    in_section = False

    for line in lines:
        if section_name in line:
            in_section = True
            continue
        if in_section:
            if line.strip() and not line.startswith("#"):
                section_lines.append(line)
            elif line.startswith("#") and section_lines:
                break

    return "\n".join(section_lines).strip() if section_lines else "Not specified"
