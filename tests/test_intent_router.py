"""
Tests for IntentRouter

Tests cover:
1. Intent recognition from user messages (real API calls)
2. Structured output parsing
3. Routing to correct agent
4. User requirements analysis generation
5. Error handling
6. Configuration loading and validation

NOTE: These tests make real API calls to the configured LLM endpoint.
Make sure your config.yaml has valid API credentials.
"""

import pytest
import yaml
import os

from backend.agents.intent_router import (
    IntentRouter,
    IntentType,
    Intent
)
from backend.config.config_manager import reset_config, get_config


class TestIntentType:
    """Test suite for IntentType enum"""

    def test_intent_type_values(self):
        """Test that IntentType has expected values"""
        assert IntentType.DIAGNOSTIC_CHAT == "diagnostic_chat"
        assert IntentType.DATA_QUERY == "data_query"
        assert IntentType.DATA_UPDATE == "data_update"
        assert IntentType.SYSTEM_CMD == "system_cmd"
        assert IntentType.UNKNOWN == "unknown"


class TestIntent:
    """Test suite for Intent data class"""

    def test_intent_creation(self):
        """Test creating an Intent object"""
        intent = Intent(
            type=IntentType.DIAGNOSTIC_CHAT,
            analysis="Patient reports high blood pressure symptoms"
        )

        assert intent.type == IntentType.DIAGNOSTIC_CHAT
        assert intent.analysis == "Patient reports high blood pressure symptoms"
        assert "high blood pressure" in intent.analysis.lower()

    def test_intent_from_dict(self):
        """Test creating Intent from dictionary"""
        data = {
            "type": "data_query",
            "analysis": "User wants to see patient history"
        }

        intent = Intent(**data)

        assert intent.type == "data_query"
        assert intent.analysis == "User wants to see patient history"


class TestIntentRouter:
    """Test suite for IntentRouter with real API calls"""

    def test_router_initialization(self):
        """Test that IntentRouter initializes correctly with actual config.yaml"""
        # Load actual config.yaml
        config_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config.yaml")

        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)

        # Reset and load config
        reset_config()
        config = get_config()

        # Initialize IntentRouter (uses default config path)
        router = IntentRouter()

        # Verify router is created
        assert router is not None
        assert router.client is not None

        # Verify router's config matches config.yaml
        # Check model name - should use intent_model from config or default
        expected_model = config_data.get("llm", {}).get("intent_model", "gpt-4o-mini")
        assert router.model_name == expected_model

        reset_config()

    def test_recognize_diagnostic_intent(self):
        """Test recognizing diagnostic chat intent with real API call"""
        reset_config()
        router = IntentRouter()

        # Test diagnostic message
        user_message = "I've been having headaches and my blood pressure is high"
        intent = router.recognize_intent(user_message)

        assert intent.type == IntentType.DIAGNOSTIC_CHAT
        assert len(intent.analysis) > 0
        # Analysis should mention something relevant
        assert any(keyword in intent.analysis.lower() for keyword in
                   ["symptom", "blood pressure", "hypertension", "headache", "health"])

        reset_config()

    def test_recognize_data_query_intent(self):
        """Test recognizing data query intent with real API call"""
        reset_config()
        router = IntentRouter()

        user_message = "Show me all patient records from last month"
        intent = router.recognize_intent(user_message)

        assert intent.type == IntentType.DATA_QUERY
        assert len(intent.analysis) > 0

        reset_config()

    def test_recognize_data_update_intent(self):
        """Test recognizing data update intent with real API call"""
        reset_config()
        router = IntentRouter()

        user_message = "Add a new blood pressure reading of 140/90 for patient John"
        intent = router.recognize_intent(user_message)

        assert intent.type == IntentType.DATA_UPDATE
        assert len(intent.analysis) > 0
        # Analysis should mention something about updating/modifying
        assert any(keyword in intent.analysis.lower() for keyword in
                   ["update", "add", "modify", "change", "blood pressure"])

        reset_config()

    def test_recognize_system_command_intent(self):
        """Test recognizing system command intent with real API call"""
        reset_config()
        router = IntentRouter()

        user_message = "Export all conversation data to CSV"
        intent = router.recognize_intent(user_message)

        assert intent.type == IntentType.SYSTEM_CMD
        assert len(intent.analysis) > 0

        reset_config()

    def test_route_returns_correct_agent_type(self):
        """Test that routing returns correct agent type"""
        reset_config()
        router = IntentRouter()

        # Test routing for different intents
        assert router.route(Intent(type=IntentType.DIAGNOSTIC_CHAT, analysis="")) == "drhyper"
        assert router.route(Intent(type=IntentType.DATA_QUERY, analysis="")) == "data_manager"
        assert router.route(Intent(type=IntentType.DATA_UPDATE, analysis="")) == "data_manager"
        assert router.route(Intent(type=IntentType.SYSTEM_CMD, analysis="")) == "system"
        assert router.route(Intent(type=IntentType.UNKNOWN, analysis="")) == "default"

        reset_config()

    def test_process_and_route_convenience_method(self):
        """Test the convenience method that combines recognition and routing"""
        reset_config()
        router = IntentRouter()

        # Test with a diagnostic message
        user_message = "I have chest pain and shortness of breath"
        agent_name, initial_message, analysis = router.process_and_route(user_message)

        assert agent_name == "drhyper"
        assert user_message in initial_message
        assert len(analysis) > 0

        reset_config()

    def test_chinese_diagnostic_query(self):
        """Test recognizing Chinese diagnostic queries"""
        reset_config()
        router = IntentRouter()

        user_message = "我有高血压，经常感到头晕"
        intent = router.recognize_intent(user_message)

        assert intent.type == IntentType.DIAGNOSTIC_CHAT
        assert len(intent.analysis) > 0

        reset_config()

    def test_chinese_data_query(self):
        """Test recognizing Chinese data queries"""
        reset_config()
        router = IntentRouter()

        user_message = "显示所有患者的列表"
        intent = router.recognize_intent(user_message)

        assert intent.type == IntentType.DATA_QUERY
        assert len(intent.analysis) > 0

        reset_config()

    def test_chinese_data_update(self):
        """Test recognizing Chinese data update requests"""
        reset_config()
        router = IntentRouter()

        user_message = "给患者张三添加一个新的血压记录 140/90"
        intent = router.recognize_intent(user_message)

        assert intent.type == IntentType.DATA_UPDATE
        assert len(intent.analysis) > 0

        reset_config()

    def test_multiple_queries_in_sequence(self):
        """Test processing multiple queries sequentially with same router instance"""
        reset_config()
        router = IntentRouter()

        queries = [
            ("I have high blood pressure", IntentType.DIAGNOSTIC_CHAT),
            ("Show all patients", IntentType.DATA_QUERY),
            ("Add new patient", IntentType.DATA_UPDATE),
        ]

        for query, expected_type in queries:
            intent = router.recognize_intent(query)
            assert intent.type == expected_type, f"Query '{query}' expected {expected_type}, got {intent.type}"
            assert len(intent.analysis) > 0

        reset_config()

    @pytest.mark.slow
    def test_various_diagnostic_expressions(self):
        """Test various ways users might express diagnostic concerns"""
        reset_config()
        router = IntentRouter()

        diagnostic_queries = [
            "I'm not feeling well",
            "My head hurts",
            "I've been feeling dizzy lately",
            "Can you help me with my health?",
            "I think I have the flu",
            "What should I do about my cough?",
        ]

        for query in diagnostic_queries:
            intent = router.recognize_intent(query)
            # Most should be recognized as diagnostic or unknown (not data operations)
            assert intent.type in [IntentType.DIAGNOSTIC_CHAT, IntentType.UNKNOWN], \
                f"Query '{query}' was classified as {intent.type}"
            assert len(intent.analysis) > 0

        reset_config()
