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

    def _build_graph(self) -> StateGraph:
        """
        Build LangGraph StateGraph with nodes and edges

        Returns:
            Compiled StateGraph with checkpointer
        """
        from langchain_core.messages import AIMessage, HumanMessage
        import uuid

        # Define the workflow
        workflow = StateGraph(MainAgentState)

        # Intent analysis prompt (internal, not exposed to tools)
        INTENT_ANALYSIS_PROMPT = """Analyze the user's latest message and determine the intent.

Choose one of the following intents:
- "database_query": User is asking about their medical data (history, medications, allergies, etc.)
- "diagnostic_question": User is responding to a diagnostic question
- "generate_report": All data collected, ready to generate report (accomplish=True)
- "continue_conversation": General conversational message, need to get next diagnostic question

Return ONLY the intent name."""

        # Agent node with explicit routing
        async def agent_node(state: MainAgentState) -> Dict[str, Any]:
            """
            Agent node that:
            1. Analyzes user intent
            2. Routes to appropriate tool node
            3. Generates conversational responses
            """
            # Check if conversation is accomplished - if so, return END signal
            if state.get("accomplish", False):
                # Conversation complete, set route to END
                return {"_route": END}

            messages = [SystemMessage(content=self.system_prompt)] + state["messages"]

            # Get last user message
            user_message = None
            for msg in reversed(state["messages"]):
                if msg.type == "human":
                    user_message = msg.content
                    break

            if not user_message:
                # No user message, start conversation
                return {"messages": [AIMessage(content="Hello, I'm your medical assistant. Let's start by gathering some information about your health.")], "_route": "get_question_tool"}

            # Analyze intent using LLM (reuse self.llm for consistency)
            intent_response = await self.llm.ainvoke([
                SystemMessage(content=INTENT_ANALYSIS_PROMPT),
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
            elif intent == "diagnostic_question":
                # User is responding to a question, update graph
                query_message = state.get("last_hint", "")
                return {
                    "messages": [AIMessage(content="", tool_calls=[{
                        "name": "update_diagnosis_graph",
                        "args": {
                            "user_response": user_message,
                            "query_message": query_message
                        },
                        "id": f"update_graph_{uuid.uuid4().hex}"
                    }])],
                    "_route": "update_graph_tool"
                }
            elif intent == "generate_report" or state.get("accomplish", False):
                # Generate report
                return {
                    "messages": [AIMessage(content="", tool_calls=[{
                        "name": "generate_diagnostic_report",
                        "args": {},
                        "id": f"generate_report_{uuid.uuid4().hex}"
                    }])],
                    "_route": "generate_report_tool"
                }
            else:
                # Continue conversation, get next question
                return {
                    "messages": [AIMessage(content="", tool_calls=[{
                        "name": "get_next_diagnostic_question",
                        "args": {},
                        "id": f"get_question_{uuid.uuid4().hex}"
                    }])],
                    "_route": "get_question_tool"
                }

        # Tool execution nodes
        async def get_question_tool_node(state: MainAgentState) -> Dict[str, Any]:
            """Execute get_next_diagnostic_question tool"""
            result = await tools.get_next_diagnostic_question_node(state)

            # Generate conversational question from hint
            hint = result.get("last_hint", "Could you tell me more about your condition?")

            # Use LLM to translate hint into conversational language
            conversational_prompt = f"""You are a medical assistant. The system suggests asking about: {hint}

Translate this into a warm, natural, conversational question for the patient.
Be empathetic and professional."""

            response = await self.llm.ainvoke([
                SystemMessage(content="You are a warm, professional medical assistant."),
                HumanMessage(content=conversational_prompt)
            ])

            result["messages"] = [AIMessage(content=response.content)]
            return result

        async def update_graph_tool_node(state: MainAgentState) -> Dict[str, Any]:
            """Execute update_diagnosis_graph tool"""
            # Extract parameters from state's tool call
            last_message = state["messages"][-1]
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                tool_call = last_message.tool_calls[0]
                user_response = tool_call["args"]["user_response"]
                query_message = tool_call["args"]["query_message"]
            else:
                return {"messages": [AIMessage(content="I apologize, but I couldn't process your response.")], "accomplish": True}

            result = await tools.update_diagnosis_graph_node(state, user_response, query_message)

            # Check for error
            if "error" in result:
                return {"messages": [AIMessage(content=f"I apologize, but I'm having trouble with the diagnostic system: {result['error']}")], "accomplish": True}

            # Generate acknowledgment
            if result.get("accomplish"):
                ack = "Thank you for that information. I've collected all the necessary data. Let me generate your diagnostic report now."
            else:
                ack = "Thank you. Let me ask you about another aspect of your health."

            result["messages"] = [AIMessage(content=ack)]
            return result

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
                summary = f"""
# Diagnostic Report Complete

## Summary
{report.get('summary', 'Not available')}

## Key Findings
{report.get('key_findings', 'Not available')}

## Recommendations
{report.get('recommendations', 'Not available')}

## Follow-up
{report.get('follow_up', 'Not available')}
"""
                result["messages"] = [AIMessage(content=summary)]
            else:
                result["messages"] = [AIMessage(content="I apologize, but I couldn't generate the report.")]

            result["accomplish"] = True
            return result

        # Routing function
        def route_from_agent(state: MainAgentState) -> str:
            """Route based on _route set by agent_node"""
            return state.get("_route", END)

        # Add nodes to graph
        workflow.add_node("agent", agent_node)
        workflow.add_node("get_question_tool", get_question_tool_node)
        workflow.add_node("update_graph_tool", update_graph_tool_node)
        workflow.add_node("data_manager_tool", data_manager_tool_node)
        workflow.add_node("generate_report_tool", generate_report_tool_node)

        # Set entry point
        workflow.set_entry_point("agent")

        # Add conditional edges from agent
        workflow.add_conditional_edges("agent", route_from_agent, {
            "get_question_tool": "get_question_tool",
            "update_graph_tool": "update_graph_tool",
            "data_manager_tool": "data_manager_tool",
            "generate_report_tool": "generate_report_tool",
            END: END
        })

        # All tool nodes return to agent (for next turn or to end)
        for tool_node in ["get_question_tool", "update_graph_tool", "data_manager_tool", "generate_report_tool"]:
            workflow.add_edge(tool_node, "agent")

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

        # Initialize EntityGraph
        entity_graph = await self._create_entity_graph(patient_id, target)

        # Create initial state
        config = {"configurable": {"thread_id": conversation_id}}
        initial_state: MainAgentState = {
            "messages": [],
            "conversation_id": conversation_id,
            "patient_id": patient_id,
            "entity_graph": entity_graph,
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

        # Add user message to state
        result = await self.graph.ainvoke(
            {"messages": [HumanMessage(content=user_message)]},
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

    async def _create_entity_graph(self, patient_id: str, target: str):
        """
        Create EntityGraph for the conversation

        Args:
            patient_id: Patient identifier
            target: Diagnostic target

        Returns:
            Initialized EntityGraph instance
        """
        logger.info(f"Creating EntityGraph for patient {patient_id}, target: {target}")

        try:
            from drhyper.core.graph import EntityGraph
            from drhyper.utils.llm_loader import load_chat_model
            from drhyper.config.settings import ConfigManager as DrHyperConfig
            from backend.services.patient_context_builder import PatientContextBuilder
            from backend.database.session import get_db
            import asyncio

            # Load patient context
            patient_context_builder = PatientContextBuilder()
            with get_db() as db:
                patient_context = patient_context_builder.build(db, patient_id)

            logger.info(f"Loaded patient context for {patient_id}: "
                       f"{len(patient_context.patient_text_records)} text records")

            # Convert PatientContext to dict for EntityGraph
            patient_context_dict = {
                "patient_id": patient_context.patient_id,
                "basic_info": patient_context.basic_info,
                "patient_text_records": patient_context.patient_text_records
            }

            # Use DrHyper configuration for EntityGraph models
            drhyper_config = DrHyperConfig()
            conv_model = load_chat_model(
                provider=drhyper_config.conversation_llm.provider,
                model_name=drhyper_config.conversation_llm.model,
                api_key=drhyper_config.conversation_llm.api_key,
                base_url=drhyper_config.conversation_llm.base_url,
                temperature=drhyper_config.conversation_llm.temperature,
                max_tokens=drhyper_config.conversation_llm.max_tokens
            )

            graph_model = load_chat_model(
                provider=drhyper_config.graph_llm.provider,
                model_name=drhyper_config.graph_llm.model,
                api_key=drhyper_config.graph_llm.api_key,
                base_url=drhyper_config.graph_llm.base_url,
                temperature=drhyper_config.graph_llm.temperature,
                max_tokens=drhyper_config.graph_llm.max_tokens
            )

            # EntityGraph initialization is synchronous, run in thread pool
            loop = asyncio.get_event_loop()

            # Create EntityGraph with required parameters
            entity_graph = await loop.run_in_executor(
                None,
                lambda: EntityGraph(
                    target=target,
                    graph_model=graph_model,
                    conv_model=conv_model
                )
            )

            # Initialize the graph with patient context
            await loop.run_in_executor(
                None,
                lambda: entity_graph.init(save=False, patient_context=patient_context_dict)
            )

            logger.info("EntityGraph created and initialized successfully with patient context")
            return entity_graph

        except Exception as e:
            logger.error(f"Error creating EntityGraph: {e}")
            # Return None for testing without full EntityGraph
            return None

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