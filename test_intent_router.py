#!/usr/bin/env python3
"""Test Intent Router with fallback mechanism"""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backend.agents.intent_router import IntentRouter, IntentType


def test_router():
    """Test intent router with various queries"""
    print("=" * 60)
    print("Testing Intent Router (Rule-based fallback)")
    print("=" * 60)
    print()

    test_queries = [
        "How many patients do we have?",
        "I have high blood pressure",
        "Add a new patient",
        "Export the data",
        "Show me patient list",
        "I feel dizzy",
    ]

    try:
        router = IntentRouter()
        print("Intent Router initialized\n")
    except Exception as e:
        print(f"Warning: Could not initialize router with API: {e}")
        print("Testing rule-based fallback directly...\n")

        # Create a minimal router for testing
        router = IntentRouter.__new__(IntentRouter)
        router.model_name = "test"

    for query in test_queries:
        print(f"Query: {query}")
        intent = router._rule_based_intent(query)
        print(f"  Intent: {intent.type.value}")
        print(f"  Analysis: {intent.analysis}")
        agent_name = router.route(intent)
        print(f"  Route to: {agent_name}")
        print()


if __name__ == "__main__":
    test_router()
