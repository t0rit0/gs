"""
Intent Router

Analyzes user messages to determine intent and routes to appropriate agent.
Uses OpenAI API with structured output for reliable intent classification.

Intent Types:
- DIAGNOSTIC_CHAT: Medical diagnostic conversations (routed to DrHyper)
- DATA_QUERY: Querying patient data (routed to DataManager)
- DATA_UPDATE: Updating patient data (routed to DataManager)
- SYSTEM_CMD: System operations (routed to System handler)
- UNKNOWN: Unrecognized intent (routed to default handler)
"""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Optional
import openai
from pydantic import BaseModel

from backend.config.config_manager import get_config
from backend.prompts import load_prompt

logger = logging.getLogger(__name__)


class IntentType(str, Enum):
    """Intent types for routing"""

    DIAGNOSTIC_CHAT = "diagnostic_chat"
    DATA_QUERY = "data_query"
    DATA_UPDATE = "data_update"
    SYSTEM_CMD = "system_cmd"
    UNKNOWN = "unknown"


class IntentSchema(BaseModel):
    """Pydantic schema for structured intent output"""

    type: IntentType
    analysis: str


@dataclass
class Intent:
    """
    Recognized intent from user message

    Attributes:
        type: The intent type for routing
        analysis: Brief analysis of user requirements
                 (used to construct initial message for the target agent)
    """

    type: IntentType
    analysis: str


class IntentRouter:
    """
    Analyzes user messages and determines intent

    Uses OpenAI API with structured output to:
    1. Classify user intent
    2. Generate brief requirements analysis

    The analysis is used to construct the initial message when routing
    to the target agent.

    Usage:
        router = IntentRouter()

        # Recognize intent
        intent = router.recognize_intent("I have high blood pressure")

        # Route to appropriate agent
        agent_name = router.route(intent)  # Returns "drhyper"

        # Use analysis for initial message
        initial_message = f"{user_message}\\n\\nContext: {intent.analysis}"
    """

    # Default model for intent recognition
    DEFAULT_MODEL = "gpt-4o-mini"

    # Mapping from intent to agent names
    ROUTING_MAP = {
        IntentType.DIAGNOSTIC_CHAT: "drhyper",
        IntentType.DATA_QUERY: "data_manager",
        IntentType.DATA_UPDATE: "data_manager",
        IntentType.SYSTEM_CMD: "system",
        IntentType.UNKNOWN: "default",
    }

    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize IntentRouter

        Args:
            config_path: Optional path to configuration file
        """
        # Load configuration
        self.config = get_config(config_path)

        # Initialize OpenAI client
        self.client = openai.OpenAI(
            api_key=self.config.get_api_key(),
            base_url=self.config.get_base_url()
        )

        # Model to use for intent recognition
        self.model_name = self.config.get("llm.intent_model", self.DEFAULT_MODEL)

        # Load system prompt
        try:
            self.system_prompt = load_prompt("intent_router_system")
        except FileNotFoundError:
            logger.warning("intent_router_system.txt not found, using default prompt")
            self.system_prompt = self._get_default_prompt()

        logger.info(f"IntentRouter initialized with model={self.model_name}")

    def recognize_intent(self, user_message: str) -> Intent:
        """
        Analyze user message and recognize intent

        Args:
            user_message: User's input message

        Returns:
            Intent object with type and analysis

        Raises:
            No - errors are caught and returned as UNKNOWN intent
        """
        try:
            # Call OpenAI API with structured output
            response = self.client.chat.completions.create(
                model=self.model_name,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": user_message}
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "intent_schema",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["diagnostic_chat", "data_query", "data_update", "unknown"]
                                },
                                "analysis": {
                                    "type": "string",
                                    "description": "Brief analysis of user requirements"
                                }
                            },
                            "required": ["type", "analysis"],
                            "additionalProperties": False
                        }
                    }
                },
                temperature=0,  # Low temperature for consistent classification
                max_tokens=1024
            )

            # Parse structured output
            import json
            intent_data = json.loads(response.choices[0].message.content)
            intent = Intent(
                type=IntentType(intent_data["type"]),
                analysis=intent_data["analysis"]
            )

            logger.info(f"Recognized intent: {intent.type} for message: {user_message[:50]}...")
            return intent

        except Exception as e:
            logger.error(f"Error recognizing intent: {e}", exc_info=True)

            # Return UNKNOWN intent on error
            return Intent(
                type=IntentType.UNKNOWN,
                analysis=f"Error: Unable to recognize intent - {str(e)}"
            )

    def route(self, intent: Intent) -> str:
        """
        Route intent to appropriate agent

        Args:
            intent: Recognized intent object

        Returns:
            Agent name as string (e.g., "drhyper", "data_manager")
        """
        agent_name = self.ROUTING_MAP.get(intent.type, "default")

        logger.info(f"Routing {intent.type} -> {agent_name}")
        return agent_name

    def process_and_route(self, user_message: str) -> tuple[str, str, str]:
        """
        Convenience method: recognize intent and route in one call

        Args:
            user_message: User's input message

        Returns:
            Tuple of (agent_name, initial_message, analysis)
            - agent_name: Name of agent to route to
            - initial_message: Enhanced initial message with analysis
            - analysis: Brief requirements analysis
        """
        intent = self.recognize_intent(user_message)
        agent_name = self.route(intent)

        # Construct initial message with analysis
        initial_message = f"{user_message}\n\n(Context: {intent.analysis})"

        return agent_name, initial_message, intent.analysis

    def _get_default_prompt(self) -> str:
        """Get default system prompt if file not found"""
        return """You are an intent classifier for a medical assistant system.

Analyze the user's message and classify into one of these intent types:

1. diagnostic_chat: User is describing symptoms, asking for medical advice, or discussing health concerns
2. data_query: User is asking to view, search, or retrieve patient information
3. data_update: User is asking to add, modify, or update patient data or records
4. system_cmd: User is requesting system operations (export, import, etc.)
5. unknown: Cannot determine the intent

Also provide a brief analysis (1-2 sentences) of what the user is trying to accomplish.
"""


# Convenience function for quick routing
def route_message(user_message: str, config_path: Optional[str] = None) -> tuple[str, str]:
    """
    Quick routing function for simple use cases

    Args:
        user_message: User's input message
        config_path: Optional config path

    Returns:
        Tuple of (agent_name, initial_message)

    Example:
        agent_name, initial_msg = route_message("I have high blood pressure")
        print(f"Route to: {agent_name}")
    """
    router = IntentRouter(config_path)
    agent_name, initial_message, _ = router.process_and_route(user_message)
    return agent_name, initial_message
