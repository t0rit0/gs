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
        # Define the workflow
        workflow = StateGraph(MainAgentState)

        # Define nodes
        async def agent_node(state: MainAgentState) -> Dict[str, Any]:
            """Agent node that uses LLM to decide what to do"""
            messages = [SystemMessage(content=self.system_prompt)] + state["messages"]
            response = await self.llm.ainvoke(messages)
            return {"messages": [response]}

        async def get_question_node(state: MainAgentState) -> Dict[str, Any]:
            """Get next diagnostic question from EntityGraph"""
            result = await tools.get_next_diagnostic_question_node(state)
            # Create a message with the hint for the LLM to formulate
            hint = result.get("last_hint", "Could you tell me more about your condition?")
            return {"messages": [AIMessage(content=f"[HINT: {hint}]")]}

        # Add nodes to graph
        workflow.add_node("agent", agent_node)
        workflow.add_node("get_question", get_question_node)

        # Set entry point
        workflow.set_entry_point("agent")

        # Add conditional edges
        def should_route(state: MainAgentState) -> str:
            """Decide next step based on state"""
            # If accomplished, we're done
            if state.get("accomplish", False):
                return END

            # Otherwise, continue getting questions
            return "get_question"

        # Agent -> conditional routing
        workflow.add_conditional_edges(
            "agent",
            should_route,
            {
                END: END,
                "get_question": "get_question"
            }
        )

        # Get question -> back to agent
        workflow.add_edge("get_question", "agent")

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
        # This will be implemented to integrate with DrHyper
        # For now, return a mock
        logger.info(f"Creating EntityGraph for patient {patient_id}, target: {target}")

        # Import EntityGraph from DrHyper
        try:
            from drhyper.core.graph import EntityGraph
            import asyncio

            # EntityGraph initialization is synchronous, run in thread pool
            loop = asyncio.get_event_loop()
            entity_graph = await loop.run_in_executor(
                None,
                lambda: EntityGraph(target=target)
            )
            # Initialize the graph
            await loop.run_in_executor(
                None,
                lambda: entity_graph.init(save=False)
            )

            return entity_graph

        except ImportError:
            logger.error("EntityGraph not available")
            # Return mock for now
            mock_graph = Mock()
            mock_graph.get_hint_message = Mock(
                return_value=("Tell me about your blood pressure", False, [])
            )
            mock_graph.accept_message = Mock(return_value=[])
            mock_graph._serialize_nodes_with_value = Mock(return_value="No data yet")
            mock_graph.entity_graph = Mock()
            mock_graph.entity_graph.nodes = Mock(return_value=[])
            mock_graph.entity_graph.number_of_nodes = Mock(return_value=0)
            return mock_graph


# Mock for when EntityGraph is not available
class Mock:
    """Simple mock class"""
    def __init__(self):
        pass
    def __getattr__(self, name):
        return Mock()
    def __call__(self, *args, **kwargs):
        return Mock()