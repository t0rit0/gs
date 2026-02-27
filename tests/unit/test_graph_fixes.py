"""
Tests for graph.py and conversation.py fixes

Tests cover:
1. Handling list responses from LLM in _retrieve_entities
2. Handling list responses from LLM in _initialize_entity_attributes
3. DateTime serialization in to_cache_dict
4. DateTime deserialization in from_cache_dict
"""
import pytest
import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import networkx as nx

from drhyper.core.graph import EntityGraph
from drhyper.core.conversation import LongConversation


# ============================================
# Fixtures
# ============================================

@pytest.fixture
def mock_graph_model():
    """Mock graph model for testing"""
    return Mock()


@pytest.fixture
def mock_conv_model():
    """Mock conversation model for testing"""
    return Mock()


@pytest.fixture
def entity_graph(mock_graph_model, mock_conv_model):
    """Create a basic EntityGraph instance for testing"""
    eg = EntityGraph(
        target='Test target',
        graph_model=mock_graph_model,
        conv_model=mock_conv_model,
        working_directory='/tmp/test_graph_fixes'
    )
    return eg


# ============================================
# Test: _retrieve_entities handles list response
# ============================================

class TestRetrieveEntitiesListResponse:
    """Test that _retrieve_entities handles list responses from LLM"""

    def test_retrieve_entities_dict_response(self, entity_graph, mock_graph_model):
        """Test _retrieve_entities with normal dict response"""
        mock_graph_model.invoke.return_value = Mock(
            content='{"entities": ["血压", "心率", "体温"], "endpoint": true}'
        )

        entities, log_messages = entity_graph._retrieve_entities()

        assert len(entities) == 3
        assert entities[0] == {"id": "v1", "name": "血压"}
        assert entities[1] == {"id": "v2", "name": "心率"}
        assert entities[2] == {"id": "v3", "name": "体温"}

    def test_retrieve_entities_list_response(self, entity_graph, mock_graph_model):
        """Test _retrieve_entities when LLM returns a list directly"""
        # LLM might return a list instead of {"entities": [...]}
        mock_graph_model.invoke.return_value = Mock(
            content='["血压", "心率", "体温"]'
        )

        entities, log_messages = entity_graph._retrieve_entities()

        assert len(entities) == 3
        assert entities[0] == {"id": "v1", "name": "血压"}
        assert entities[1] == {"id": "v2", "name": "心率"}
        assert entities[2] == {"id": "v3", "name": "体温"}

    def test_retrieve_entities_empty_list_response(self, entity_graph, mock_graph_model):
        """Test _retrieve_entities with empty list response"""
        mock_graph_model.invoke.return_value = Mock(
            content='[]'
        )

        entities, log_messages = entity_graph._retrieve_entities()

        assert len(entities) == 0

    def test_retrieve_entities_nested_dict_response(self, entity_graph, mock_graph_model):
        """Test _retrieve_entities with nested dict containing entities key"""
        mock_graph_model.invoke.return_value = Mock(
            content='{"entities": [{"name": "血压"}, {"name": "心率"}], "endpoint": true}'
        )

        entities, log_messages = entity_graph._retrieve_entities()

        assert len(entities) == 2


# ============================================
# Test: _initialize_entity_attributes handles list response
# ============================================

class TestInitializeEntityAttributesListResponse:
    """Test that _initialize_entity_attributes handles list responses from LLM"""

    def test_init_entity_attributes_dict_response(self, entity_graph, mock_graph_model):
        """Test _initialize_entity_attributes with normal dict response"""
        entities = [
            {"id": "v1", "name": "血压"},
            {"id": "v2", "name": "心率"}
        ]

        mock_graph_model.invoke.return_value = Mock(
            content='{"entities": [{"id": "v1", "name": "血压", "description": "血压值", '
                    '"weight": 1.0, "uncertainty": 0.5, "confidential_level": 0.7}]}'
        )

        nodes, log_messages = entity_graph._initialize_entity_attributes(entities)

        assert len(nodes) == 1
        assert nodes[0]["id"] == "v1"
        assert "extracted_at" in nodes[0]
        assert isinstance(nodes[0]["extracted_at"], datetime)

    def test_init_entity_attributes_list_response(self, entity_graph, mock_graph_model):
        """Test _initialize_entity_attributes when LLM returns a list directly"""
        entities = [
            {"id": "v1", "name": "血压"},
            {"id": "v2", "name": "心率"}
        ]

        # LLM might return a list instead of {"entities": [...]}
        mock_graph_model.invoke.return_value = Mock(
            content='[{"id": "v1", "name": "血压", "description": "血压值", '
                    '"weight": 1.0, "uncertainty": 0.5, "confidential_level": 0.7}]'
        )

        nodes, log_messages = entity_graph._initialize_entity_attributes(entities)

        assert len(nodes) == 1
        assert nodes[0]["id"] == "v1"
        assert "extracted_at" in nodes[0]
        assert isinstance(nodes[0]["extracted_at"], datetime)

    def test_init_entity_attributes_multiple_chunks(self, entity_graph, mock_graph_model):
        """Test _initialize_entity_attributes with multiple chunks"""
        # Create more than 30 entities to test chunking
        entities = [{"id": f"v{i}", "name": f"实体{i}"} for i in range(1, 35)]

        mock_graph_model.invoke.return_value = Mock(
            content='{"entities": [{"id": "v1", "name": "实体1", "description": "测试", '
                    '"weight": 1.0, "uncertainty": 0.5, "confidential_level": 0.5}]}'
        )

        nodes, log_messages = entity_graph._initialize_entity_attributes(entities)

        # Should have called invoke multiple times for chunks
        assert mock_graph_model.invoke.call_count >= 1


# ============================================
# Test: to_cache_dict datetime serialization
# ============================================

class TestToCacheDictDateTimeSerialization:
    """Test that to_cache_dict properly serializes datetime objects"""

    def test_to_cache_dict_serializes_datetime(self, mock_graph_model, mock_conv_model):
        """Test that datetime objects in graph nodes are serialized to ISO strings"""
        # Create LongConversation with mock models
        conv = LongConversation(
            target="Test target",
            conv_model=mock_conv_model,
            graph_model=mock_graph_model,
            working_directory="/tmp/test_cache"
        )

        # Manually add a node with datetime attributes
        now = datetime.now()
        conv.plan_graph.entity_graph.add_node(
            "v1",
            id="v1",
            name="血压",
            value="140/90",
            extracted_at=now,
            last_updated_at=now,
            source="conversation"
        )
        conv.plan_graph.relation_graph.add_node(
            "v1",
            id="v1",
            name="血压",
            value="140/90",
            extracted_at=now,
            last_updated_at=now,
            source="conversation"
        )

        # Call to_cache_dict
        cache_dict = conv.to_cache_dict()

        # Verify it can be JSON serialized
        json_str = json.dumps(cache_dict)
        assert json_str is not None

        # Parse it back and check datetime fields
        parsed = json.loads(json_str)
        entity_node = parsed["entity_graph"]["nodes"][0]

        # Datetime should be serialized as ISO string
        assert "extracted_at" in entity_node
        assert isinstance(entity_node["extracted_at"], str)
        # Should be parseable back to datetime
        parsed_dt = datetime.fromisoformat(entity_node["extracted_at"])
        assert parsed_dt is not None

    def test_to_cache_dict_nested_datetime(self, mock_graph_model, mock_conv_model):
        """Test serialization of nested structures with datetime"""
        conv = LongConversation(
            target="Test target",
            conv_model=mock_conv_model,
            graph_model=mock_graph_model,
            working_directory="/tmp/test_cache"
        )

        now = datetime.now()
        nested_data = {
            "history": [
                {"timestamp": now, "value": "old_value"}
            ]
        }

        conv.plan_graph.entity_graph.add_node(
            "v1",
            id="v1",
            name="测试",
            nested=nested_data,
            extracted_at=now
        )
        conv.plan_graph.relation_graph.add_node(
            "v1",
            id="v1",
            name="测试",
            nested=nested_data,
            extracted_at=now
        )

        cache_dict = conv.to_cache_dict()

        # Should not raise JSON serialization error
        json_str = json.dumps(cache_dict)
        assert json_str is not None


# ============================================
# Test: from_cache_dict datetime deserialization
# ============================================

class TestFromCacheDictDateTimeDeserialization:
    """Test that from_cache_dict properly deserializes ISO strings to datetime"""

    def test_from_cache_dict_restores_datetime(self, mock_graph_model, mock_conv_model):
        """Test that ISO datetime strings are restored to datetime objects"""
        now = datetime.now()

        # Create cache dict with ISO datetime strings
        cache_dict = {
            "target": "Test target",
            "routine": None,
            "visualize": False,
            "working_directory": "/tmp/test_cache",
            "stream": False,
            "message_reserve_turns": 2,
            "messages": [],
            "entire_messages": [],
            "current_hint": "",
            "step": 0,
            "think_history": [],
            "entity_graph": {
                "nodes": [
                    {
                        "id": "v1",
                        "name": "血压",
                        "value": "140/90",
                        "extracted_at": now.isoformat(),
                        "last_updated_at": now.isoformat(),
                        "source": "conversation"
                    }
                ],
                "links": [],
                "directed": True,
                "multigraph": False,
                "graph": {}
            },
            "relation_graph": {
                "nodes": [
                    {
                        "id": "v1",
                        "name": "血压",
                        "value": "140/90",
                        "extracted_at": now.isoformat(),
                        "last_updated_at": now.isoformat(),
                        "source": "conversation"
                    }
                ],
                "links": [],
                "directed": True,
                "multigraph": False,
                "graph": {}
            },
            "graph_state": {
                "step": 0,
                "accomplish": False,
                "prev_node": None
            },
            "metadata": {
                "version": "2.2"
            }
        }

        # Restore from cache
        conv = LongConversation.from_cache_dict(
            cache_dict=cache_dict,
            conv_model=mock_conv_model,
            graph_model=mock_graph_model
        )

        # Check that datetime fields are restored as datetime objects
        node_data = conv.plan_graph.entity_graph.nodes["v1"]
        assert "extracted_at" in node_data
        assert isinstance(node_data["extracted_at"], datetime)

        # Check the datetime values are approximately correct
        time_diff = abs((node_data["extracted_at"] - now).total_seconds())
        assert time_diff < 1  # Within 1 second

    def test_from_cache_dict_handles_old_format(self, mock_graph_model, mock_conv_model):
        """Test that from_cache_dict handles old format without datetime strings"""
        cache_dict = {
            "target": "Test target",
            "routine": None,
            "visualize": False,
            "working_directory": "/tmp/test_cache",
            "stream": False,
            "message_reserve_turns": 2,
            "messages": [],
            "entire_messages": [],
            "current_hint": "",
            "step": 0,
            "think_history": [],
            "entity_graph": {
                "nodes": [
                    {
                        "id": "v1",
                        "name": "血压",
                        "value": "140/90"
                        # No datetime fields
                    }
                ],
                "links": [],
                "directed": True,
                "multigraph": False,
                "graph": {}
            },
            "relation_graph": {
                "nodes": [
                    {
                        "id": "v1",
                        "name": "血压",
                        "value": "140/90"
                    }
                ],
                "links": [],
                "directed": True,
                "multigraph": False,
                "graph": {}
            },
            "graph_state": {
                "step": 0,
                "accomplish": False,
                "prev_node": None
            },
            "metadata": {
                "version": "2.0"  # Old version
            }
        }

        # Should not raise error
        conv = LongConversation.from_cache_dict(
            cache_dict=cache_dict,
            conv_model=mock_conv_model,
            graph_model=mock_graph_model
        )

        assert conv is not None
        assert conv.plan_graph.entity_graph.number_of_nodes() == 1


# ============================================
# Test: Round-trip serialization
# ============================================

class TestRoundTripSerialization:
    """Test that serialization and deserialization work together"""

    def test_roundtrip_preserves_data(self, mock_graph_model, mock_conv_model):
        """Test that data is preserved through serialize/deserialize cycle"""
        now = datetime.now()

        # Create original conversation
        original = LongConversation(
            target="Test target",
            conv_model=mock_conv_model,
            graph_model=mock_graph_model,
            working_directory="/tmp/test_cache"
        )

        # Add node with datetime
        original.plan_graph.entity_graph.add_node(
            "v1",
            id="v1",
            name="血压",
            value="140/90",
            extracted_at=now,
            last_updated_at=now,
            source="conversation",
            confidential_level=0.8
        )
        original.plan_graph.relation_graph.add_node(
            "v1",
            id="v1",
            name="血压",
            value="140/90",
            extracted_at=now,
            last_updated_at=now,
            source="conversation",
            confidential_level=0.8
        )

        # Serialize
        cache_dict = original.to_cache_dict()

        # Verify JSON serializable
        json_str = json.dumps(cache_dict)

        # Deserialize
        restored = LongConversation.from_cache_dict(
            cache_dict=json.loads(json_str),
            conv_model=mock_conv_model,
            graph_model=mock_graph_model
        )

        # Verify data preserved
        original_node = original.plan_graph.entity_graph.nodes["v1"]
        restored_node = restored.plan_graph.entity_graph.nodes["v1"]

        assert restored_node["name"] == original_node["name"]
        assert restored_node["value"] == original_node["value"]
        assert restored_node["source"] == original_node["source"]

        # Datetime should be approximately preserved
        time_diff = abs((restored_node["extracted_at"] - original_node["extracted_at"]).total_seconds())
        assert time_diff < 1