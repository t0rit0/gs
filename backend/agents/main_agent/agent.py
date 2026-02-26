"""
MainAgent - LangGraph-based diagnostic agent

Replaces IntentRouter + DrHyper's ConversationLLM.
Uses LangGraph StateGraph with checkpointer for multi-user state management.
"""

import logging
from typing import Optional, Dict, Any, Tuple
import uuid

from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage

from backend.agents.main_agent.graph import MainAgentState
from backend.agents.main_agent import tools
from backend.config.config_manager import get_config
from backend.services.checkpointer_factory import get_checkpointer

logger = logging.getLogger(__name__)


class MainAgent:
    """
    Main Diagnostic Agent using LangGraph

    Orchestrates diagnostic conversations through:
    - EntityGraph for diagnostic reasoning
    - Tools for data collection and report generation
    - Checkpointer for automatic state persistence
    """

    # Intent analysis prompt for LLM-based classification
    INTENT_ANALYSIS_PROMPT = """Analyze the user's latest message and determine the intent.

Choose one of the following intents:
- "database_query": User is asking about their medical data (history, medications, allergies, etc.)
  Examples: "What medications am I taking?", "Show me my blood pressure records"
- "diagnostic_question": User is providing health information (symptoms, body sensations, responses to questions)
  IMPORTANT: ANY message containing symptoms, body sensations, or health-related information MUST be classified as "diagnostic_question"
  This includes both direct answers AND new volunteered information
  Examples: "My head hurts", "130/85", "Yes, I have headaches", "By the way, I also feel dizzy sometimes"
- "continue_conversation": Greetings, goodbyes, thank you, or other non-medical conversational messages
  Examples: "Hello", "Thank you", "Goodbye"

Return ONLY the intent name."""

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize MainAgent

        Args:
            config_path: Optional path to config file
        """
        # Load configuration
        self.config = get_config(config_path)

        # Initialize LLM
        model_name = self.config.get("main_agent.model", self.config.get_model())
        temperature = self.config.get("main_agent.temperature", 0.7)

        self.llm = ChatOpenAI(
            model=model_name,
            api_key=self.config.get_api_key(),
            base_url=self.config.get_base_url(),
            temperature=temperature
        )

        logger.info(f"MainAgent initialized with model: {model_name}")

        # Create checkpointer for state persistence
        self.checkpointer = get_checkpointer(self.config)

        # Reference EntityGraphManager singleton for EntityGraph management
        from backend.services.entity_graph_manager import entity_graph_manager
        self.entity_graph_manager = entity_graph_manager

        # Load system prompt
        self.system_prompt = self._load_system_prompt()

        # Build the LangGraph
        self.graph = self._build_graph()

        logger.info("MainAgent graph compiled successfully")

    def _load_system_prompt(self) -> str:
        """Load system prompt from file"""
        try:
            from pathlib import Path
            prompt_path = Path(__file__).parent.parent.parent / "prompts" / "main_agent_system.txt"

            if prompt_path.exists():
                with open(prompt_path, "r", encoding="utf-8") as f:
                    return f.read()
            else:
                logger.warning(f"System prompt file not found: {prompt_path}, using default")
                return self._default_system_prompt()

        except Exception as e:
            logger.error(f"Error loading system prompt: {e}, using default")
            return self._default_system_prompt()

    def _default_system_prompt(self) -> str:
        """Default system prompt if file not found"""
        return """You are a hypertension specialist doctor assistant helping collect patient information for diagnosis.

## Your Role

You are conducting a structured diagnostic conversation to collect the necessary information for hypertension assessment. Your goal is to be thorough yet efficient, gathering all required data while maintaining a warm, professional bedside manner.

## Communication Principles

1. **One question at a time**: Never ask multiple questions simultaneously
2. **Conversational tone**: Use natural, empathetic language (not robotic)
3. **Context awareness**: Reference what the patient just shared
4. **Gentle guidance**: If the patient doesn't understand, rephrase kindly

## Workflow

Use the available tools to:
1. Get the next diagnostic question to ask
2. Update the diagnosis graph with patient responses
3. Query patient history when needed
4. Generate a diagnostic report when data collection is complete

## Important Notes

- Always translate technical hints into natural, conversational language
- When the diagnosis is complete, provide a clear summary and next steps
- Be empathetic and professional in all interactions
"""

    async def _agent_node(self, state: MainAgentState) -> Dict[str, Any]:
        """
        Agent node that:
        1. Checks if conversation should end (report generated)
        2. Checks if returning from a tool (show response to user)
        3. Analyzes user intent
        4. Routes to appropriate tool node
        5. Generates conversational responses
        """
        from langchain_core.messages import AIMessage

        # Check if report was generated - if so, END the conversation
        # This happens after generate_report_tool routes back to agent
        if state.get("accomplish", False) and state.get("report"):
            # Report generated, show it to user and end conversation
            # The report message is already in the messages list from generate_report_tool
            logger.info("Report generated, ending conversation")
            return {"_route": END}

        messages_list = state.get("messages", [])

        # Check if we're returning from a tool node (last message is AI, not followed by new human message)
        if messages_list and messages_list[-1].type == "ai":
            # Last message is AI - check if there's a human message after it (new user input)
            has_new_human_input = False
            for i in range(len(messages_list) - 2, -1, -1):
                if messages_list[i].type == "human":
                    has_new_human_input = True
                    break
                elif messages_list[i].type == "ai":
                    # Found another AI message before a human one - no new input
                    break

            if not has_new_human_input:
                # Last message is AI from a tool, no new human input after it - show to user
                logger.info("Returning from tool, ending to show response to user")
                return {"_route": END}

        messages = [SystemMessage(content=self.system_prompt)] + state["messages"]

        # Get last user message
        user_message = None
        for msg in reversed(state["messages"]):
            if msg.type == "human":
                user_message = msg.content
                break

        if not user_message:
            # No user message yet - check if this is the initial start
            if len(state.get("messages", [])) == 0:
                # Initial start - route to get_question_tool to get first question
                # Don't generate a message, let get_question_tool handle it
                return {"_route": "get_question_tool"}
            else:
                # We have messages but no human message - should END to show AI message
                return {"_route": END}

        # Analyze intent using LLM (reuse self.llm for consistency)
        intent_response = await self.llm.ainvoke([
            SystemMessage(content=self.INTENT_ANALYSIS_PROMPT),
            HumanMessage(content=f"User message: {user_message}\nCurrent accomplish state: {state.get('accomplish', False)}")
        ])

        intent = intent_response.content.strip().lower()
        logger.info(f"Detected intent: {intent}")

        # Route based on intent
        if intent == "database_query":
            # Store intent for routing, call data_manager tool
            return {
                "messages": [AIMessage(content="", tool_calls=[{
                    "name": "data_manager",
                    "args": {"question": user_message},
                    "id": f"data_manager_{uuid.uuid4().hex}"
                }])],
                "_route": "data_manager_tool"
            }
        else:
            # For all other intents (diagnostic_question, continue_conversation):
            # Route to get_question_tool
            # Note: If user is responding to a diagnostic question, routing_node
            # will have already routed directly to update_graph_tool, bypassing agent.
            # We only reach here for:
            # 1. Greetings/conversational messages
            # 2. Volunteered health information (not responding to a question)
            # For volunteered info, get_question_tool will call EntityGraph which
            # can process it through its accept_message() or get_hint_message() methods
            return {
                "messages": [AIMessage(content="", tool_calls=[{
                    "name": "get_next_diagnostic_question",
                    "args": {},
                    "id": f"get_question_{uuid.uuid4().hex}"
                }])],
                "_route": "get_question_tool"
            }

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph StateGraph with nodes and edges

        Returns:
            Compiled StateGraph with checkpointer
        """
        # Import nodes module
        from backend.agents.main_agent import nodes

        # Define the workflow
        workflow = StateGraph(MainAgentState)

        # Add pure nodes from nodes module
        workflow.add_node("routing", nodes.routing_node)
        workflow.add_node("get_question_tool", nodes.get_question_tool_node)
        workflow.add_node("update_graph_tool", nodes.update_graph_tool_node)
        workflow.add_node("data_manager_tool", nodes.data_manager_tool_node)
        workflow.add_node("generate_report_tool", nodes.generate_report_tool_node)

        # Add LLM-dependent agent node as class method (bound to self)
        workflow.add_node("agent", self._agent_node)

        # Set entry point to routing_node
        workflow.set_entry_point("routing")

        # Add conditional edges from routing_node
        workflow.add_conditional_edges("routing", nodes.route_from_routing, {
            "update_graph_tool": "update_graph_tool",
            "agent": "agent"
        })

        # Add conditional edges from agent
        workflow.add_conditional_edges("agent", nodes.route_from_agent, {
            "get_question_tool": "get_question_tool",
            "data_manager_tool": "data_manager_tool",
            "generate_report_tool": "generate_report_tool",
            END: END
        })

        # Add conditional edges from get_question_tool
        workflow.add_conditional_edges("get_question_tool", nodes.route_from_get_question, {
            "generate_report_tool": "generate_report_tool",
            "agent": "agent"
        })

        # Add conditional edges from update_graph_tool
        workflow.add_conditional_edges("update_graph_tool", nodes.route_from_update_graph, {
            "generate_report_tool": "generate_report_tool",
            "agent": "agent"
        })

        # data_manager_tool always returns to agent
        workflow.add_edge("data_manager_tool", "agent")

        # generate_report_tool returns to agent (agent will decide to END)
        workflow.add_edge("generate_report_tool", "agent")

        # Compile with checkpointer
        return workflow.compile(checkpointer=self.checkpointer)

    async def astart_conversation(
        self,
        conversation_id: str,
        patient_id: str,
        target: str = "Hypertension diagnosis"
    ) -> str:
        """
        Start new diagnostic conversation

        Args:
            conversation_id: Unique conversation identifier (used as thread_id)
            patient_id: Patient identifier
            target: Diagnostic target (default: "Hypertension diagnosis")

        Returns:
            First AI message to the user
        """
        logger.info(f"Starting conversation: {conversation_id} for patient: {patient_id}")

        # Get or create EntityGraph via manager (pre-loads into cache)
        entity_graph = self.entity_graph_manager.get_or_create(
            conversation_id=conversation_id,
            patient_id=patient_id,
            target=target
        )

        if not entity_graph:
            logger.error("Failed to create EntityGraph")
            return "I apologize, but I'm having trouble starting the conversation."

        # Create initial state (NO entity_graph in state!)
        config = {"configurable": {"thread_id": conversation_id}}
        initial_state: MainAgentState = {
            "messages": [],
            "conversation_id": conversation_id,
            "patient_id": patient_id,
            "accomplish": False,
            "report": None,
            "last_hint": ""
        }

        # Invoke graph to get first message
        result = await self.graph.ainvoke(initial_state, config)

        # Extract first message
        if result.get("messages"):
            first_message = result["messages"][-1].content
            logger.info(f"First message generated: {first_message[:100]}...")
            return first_message
        else:
            logger.error("No messages returned from graph")
            return "I apologize, but I'm having trouble starting the conversation. Please try again."

    async def aprocess_message(
        self,
        conversation_id: str,
        user_message: str
    ) -> Tuple[str, bool, Optional[Dict[str, Any]]]:
        """
        Process user message

        Args:
            conversation_id: Unique conversation identifier (used as thread_id)
            user_message: User's input message

        Returns:
            Tuple of (ai_message, accomplish, report)
        """
        logger.info(f"Processing message for conversation: {conversation_id}")

        config = {"configurable": {"thread_id": conversation_id}}

        # Add user message to state AND set human_message for routing
        result = await self.graph.ainvoke(
            {
                "messages": [HumanMessage(content=user_message)],
                "human_message": user_message  # Set for routing_node to check
            },
            config
        )

        # Extract response
        if result.get("messages"):
            ai_message = result["messages"][-1].content
        else:
            ai_message = "I apologize, but I'm having trouble processing your message."

        accomplish = result.get("accomplish", False)
        report = result.get("report")

        logger.info(f"Response generated, accomplish={accomplish}")

        return ai_message, accomplish, report

    def get_pending_operations(self, conversation_id: str) -> list:
        """
        Get pending database operations for approval.

        When DataManagerCodeAgent performs write operations, they are recorded
        in a sandbox and require user approval before being committed to the database.

        Args:
            conversation_id: Conversation identifier

        Returns:
            List of pending operation dictionaries
        """
        try:
            from backend.agents.data_manager import DataManagerCodeAgent
            data_manager = DataManagerCodeAgent(config_path=None)
            return data_manager.get_pending_operations(conversation_id)
        except Exception as e:
            logger.error(f"Error getting pending operations: {e}")
            return []

    def has_pending_operations(self, conversation_id: str) -> bool:
        """
        Check if conversation has pending database operations.

        Args:
            conversation_id: Conversation identifier

        Returns:
            True if pending operations exist
        """
        try:
            from backend.agents.data_manager import DataManagerCodeAgent
            data_manager = DataManagerCodeAgent(config_path=None)
            return data_manager.has_pending_operations(conversation_id)
        except Exception as e:
            logger.error(f"Error checking pending operations: {e}")
            return False

    def approve_and_execute_pending_operations(self, conversation_id: str) -> Dict[str, Any]:
        """
        Approve and execute all pending database operations.

        This commits the sandbox operations to the actual database.
        Call this when the user approves the changes at conversation end.

        Args:
            conversation_id: Conversation identifier

        Returns:
            Dict with execution results
        """
        try:
            from backend.agents.data_manager import DataManagerCodeAgent
            data_manager = DataManagerCodeAgent(config_path=None)

            logger.info(f"Approving and executing pending operations for conversation: {conversation_id}")
            result = data_manager.approve_and_execute_all(conversation_id)

            return result
        except Exception as e:
            logger.error(f"Error approving pending operations: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }

    async def end_conversation(
        self,
        conversation_id: str
    ) -> Tuple[str, bool, Optional[list], Optional[dict]]:
        """
        End conversation and check for pending operations.

        This should be called when the conversation ends (either by user request
        or when diagnostic data collection is complete).

        Args:
            conversation_id: Conversation identifier

        Returns:
            Tuple of (final_message, has_pending_ops, pending_ops, report)
        """
        logger.info(f"Ending conversation: {conversation_id}")

        # Invalidate EntityGraph from cache to free memory
        self.entity_graph_manager.invalidate(conversation_id)

        # Check for pending database operations
        pending_ops = self.get_pending_operations(conversation_id)
        has_pending = len(pending_ops) > 0

        # Get final state to check for report
        config = {"configurable": {"thread_id": conversation_id}}
        try:
            state = self.graph.get_state(config)
            report = state.values.get("report")
        except Exception as e:
            logger.error(f"Error getting final state: {e}")
            report = None

        # Generate end message
        if has_pending:
            final_message = self._format_pending_operations(pending_ops)
        elif report:
            final_message = self._format_report_message(report)
        else:
            final_message = "Conversation ended. Thank you."

        return final_message, has_pending, pending_ops if has_pending else None, report

    def _format_pending_operations(self, pending_ops: list) -> str:
        """Format pending operations for user approval"""
        msg = "\n📋 **Pending Database Changes**\n\n"
        msg += f"There are {len(pending_ops)} operation(s) pending approval:\n\n"

        for i, op in enumerate(pending_ops, 1):
            msg += f"{i}. **{op.get('operation_type', 'UNKNOWN').upper()}** on `{op.get('table_name', 'unknown')}`\n"

            if op.get('operation_type') == 'insert':
                details = op.get('details', {})
                msg += f"   New data: {str(details)[:100]}...\n"
            elif op.get('operation_type') == 'update':
                details = op.get('details', {})
                msg += f"   Changes: {str(details)[:100]}...\n"
            elif op.get('operation_type') == 'delete':
                details = op.get('details', {})
                msg += f"   Deleted: {str(details)[:100]}...\n"
            msg += "\n"

        msg += "Please review these changes:\n"
        msg += "- Type **approve** to save all changes\n"
        msg += "- Type **discard** to cancel all changes\n"

        return msg

    def _format_report_message(self, report: dict) -> str:
        """Format report message for end of conversation"""
        return "Conversation ended. Diagnostic report has been generated."


# Mock for when EntityGraph is not available
class Mock:
    """Simple mock class"""
    def __init__(self):
        pass
    def __getattr__(self, name):
        return Mock()
    def __call__(self, *args, **kwargs):
        return Mock()