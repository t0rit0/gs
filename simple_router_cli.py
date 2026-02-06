#!/usr/bin/env python3
"""
Simple CLI for testing Intent Router integration with DrHyper and DataManager

Flow:
1. User enters initial query
2. Intent Router analyzes and routes to appropriate agent
3. That agent takes over the conversation (multi-turn)
4. Exit when user says 'exit' or conversation completes

Usage:
    python simple_router_cli.py
"""

import argparse
import sys
import os
import logging

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.agents.intent_router import IntentRouter, IntentType
from backend.agents.data_manager import DataManagerCodeAgent
from drhyper.core.conversation import LongConversation
from drhyper.prompts.templates import ConversationPrompts
from drhyper.config.settings import ConfigManager
from drhyper.utils.logging import get_logger
from drhyper.utils.aux import (
    load_models,
    format_doctor_response,
    format_patient_input,
    format_system_message,
    format_error,
    format_debug,
    Colors
)


class DataManagerConversation:
    """Wrapper for DataManager to support conversation-like interface"""

    def __init__(self, agent: DataManagerCodeAgent, verbose: bool = False):
        self.agent = agent
        self.verbose = verbose
        self.logger = get_logger("DataManagerConversation")

    def chat(self, user_message: str) -> str:
        """
        Process user message through DataManager

        Args:
            user_message: User's request

        Returns:
            Agent's response as string
        """
        result = self.agent.process_request(user_message)

        if result.get("success"):
            response = result.get("final_answer", "No answer returned")

            # Show logs in verbose mode
            if self.verbose and result.get("logs"):
                logs = result.get("logs", "")
                if logs.strip():
                    print(format_debug(f"Logs: {logs[:200]}..."))

            return response
        else:
            error = result.get("error", "Unknown error")
            return f"Error: {error}"


class RouterCLI:
    """CLI for router-based conversation system with multi-turn dialogs"""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose
        self.config = ConfigManager()
        self.logger = get_logger("RouterCLI")

        if self.verbose:
            self.logger.logger.setLevel(logging.DEBUG)

        # Components
        self.intent_router = None
        self.conv_model = None
        self.graph_model = None

    def initialize(self):
        """Initialize router and models (agents are created when needed)"""
        print(format_system_message("Initializing Router System..."))

        # 1. Initialize Intent Router
        print(format_system_message("Loading Intent Router..."))
        self.intent_router = IntentRouter()

        # 2. Load models for DrHyper (when needed)
        print(format_system_message("Loading DrHyper models..."))
        self.conv_model, self.graph_model = load_models(self.verbose)

        print(format_system_message("System initialized!\n"))

    def route_initial_query(self, user_query: str) -> tuple[str, IntentType]:
        """
        Route initial query to appropriate agent

        Returns:
            Tuple of (agent_name, intent_type)
        """
        print(format_system_message("Analyzing intent..."))
        intent = self.intent_router.recognize_intent(user_query)

        if self.verbose:
            print(format_debug(f"Intent Type: {intent.type.value}"))
            print(format_debug(f"Analysis: {intent.analysis}"))

        agent_name = self.intent_router.route(intent)

        return agent_name, intent

    def run_drhyper_conversation(self, initial_query: str):
        """
        Run DrHyper conversation loop

        Similar to drhyper/cli.py cmd_start_conversation
        """
        print(format_system_message("Routing to DrHyper..."))
        print(format_system_message("Initializing DrHyper conversation..."))

        # Initialize conversation
        prompts = ConversationPrompts()
        target = prompts.get("HYPERTENSION_CONSULTATION_TARGET",
                            language=self.config.system.language)
        routine = prompts.get("HYPERTENSION_ASSESSMENT_ROUTINE", "")

        conv = LongConversation(
            target=target,
            conv_model=self.conv_model,
            graph_model=self.graph_model,
            routine=routine,
            visualize=False,
            working_directory=self.config.system.working_directory,
        )

        # Initialize graph
        if self.verbose:
            print(format_debug("Initializing knowledge graph..."))
        conv.init_graph(save=False)

        # Get initial greeting
        response, _ = conv.init()
        print()
        print(format_doctor_response(response))
        print()

        # Process initial query
        if initial_query:
            if self.verbose:
                print(format_debug("Processing initial query..."))
            ai_response, is_accomplished, _, _ = conv.conversation(initial_query)
            print(format_doctor_response(ai_response))

            if is_accomplished:
                print(format_system_message("\nThe consultation goals have been accomplished!"))
                return

        # Main conversation loop
        while True:
            try:
                user_input = input("\n" + format_patient_input(""))

                if user_input.lower() in ["exit", "quit", "bye"]:
                    print(format_system_message("Ending conversation."))
                    break

                if self.verbose:
                    print(format_debug("Processing response..."))
                    if conv.current_hint:
                        print(format_debug(f"Hint: {conv.current_hint[:100]}..."))

                ai_response, is_accomplished, _, _ = conv.conversation(user_input)
                print(format_doctor_response(ai_response))

                if is_accomplished:
                    print(format_system_message("\nThe consultation goals have been accomplished!"))
                    print(format_system_message("Type 'exit' to end or continue chatting."))
                    # Don't break immediately, let user decide when to exit

            except KeyboardInterrupt:
                print(format_system_message("\nEnding conversation."))
                break
            except Exception as e:
                print(format_error(f"Error: {e}"))
                if self.verbose:
                    import traceback
                    print(format_debug(traceback.format_exc()))

    def run_data_manager_conversation(self, initial_query: str):
        """
        Run DataManager conversation loop

        DataManager is query-based, so each request is independent
        """
        print(format_system_message("Routing to DataManager..."))
        print(format_system_message("DataManager initialized. You can query/modify patient data."))

        # Initialize DataManager
        agent = DataManagerCodeAgent()
        conv = DataManagerConversation(agent, verbose=self.verbose)

        # Process initial query
        if initial_query:
            response = conv.chat(initial_query)
            print()
            print(format_doctor_response(response))

        # Main conversation loop
        while True:
            try:
                user_input = input("\n" + format_patient_input(""))

                if user_input.lower() in ["exit", "quit", "bye"]:
                    print(format_system_message("Ending session."))
                    break

                response = conv.chat(user_input)
                print()
                print(format_doctor_response(response))

            except KeyboardInterrupt:
                print(format_system_message("\nEnding session."))
                break
            except Exception as e:
                print(format_error(f"Error: {e}"))
                if self.verbose:
                    import traceback
                    print(format_debug(traceback.format_exc()))

    def run(self):
        """Run the main CLI flow"""
        print(format_system_message("=" * 60))
        print(format_system_message("Router System CLI"))
        print(format_system_message("=" * 60))
        print()
        print(format_system_message("Please enter your initial query to start:"))
        print(format_system_message("(e.g., 'I have high blood pressure' or 'Show patient list')"))
        print()

        # Get initial query
        try:
            initial_query = input(format_patient_input("")).strip()

            if not initial_query:
                print(format_error("Empty input. Please try again."))
                return

            if initial_query.lower() in ["exit", "quit", "bye"]:
                print(format_system_message("Goodbye!"))
                return

        except KeyboardInterrupt:
            print(format_system_message("\nGoodbye!"))
            return

        print()

        # Route to appropriate agent
        try:
            agent_name, intent = self.route_initial_query(initial_query)
            print()

            # Route to agent and start conversation
            if agent_name == "drhyper":
                self.run_drhyper_conversation(initial_query)

            elif agent_name == "data_manager":
                self.run_data_manager_conversation(initial_query)

            else:
                print(format_error(f"Unknown routing target: {agent_name}"))
                print(format_system_message(f"Intent: {intent.type.value}"))
                print(format_system_message("Please try a different query."))

        except Exception as e:
            print(format_error(f"Error: {e}"))
            if self.verbose:
                import traceback
                print(format_debug(traceback.format_exc()))


def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Simple CLI for Router System with Multi-turn Conversations"
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose debug output"
    )
    parser.add_argument(
        "--no-color",
        action="store_true",
        help="Disable colored output"
    )

    args = parser.parse_args()

    # Disable colors if requested
    if args.no_color:
        for attr in dir(Colors):
            if not attr.startswith("__"):
                setattr(Colors, attr, "")

    # Create and run CLI
    try:
        cli = RouterCLI(verbose=args.verbose)
        cli.initialize()
        cli.run()
    except Exception as e:
        print(format_error(f"Failed: {e}"))
        if args.verbose:
            import traceback
            print(format_debug(traceback.format_exc()))
        sys.exit(1)


if __name__ == "__main__":
    main()
