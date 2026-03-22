"""
Unit Tests for Update Agent

Tests for:
- NodeTypeMatcher: Node type classification
- TimeDecayExecutor: Time-based confidence decay
- UpdateAgent: LLM-based code generation (mocked LLM)

These tests do NOT make real LLM API calls.
Run with: uv run pytest tests/unit/test_update_agent.py -v
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, MagicMock, patch

from backend.services.node_type_matcher import NodeTypeMatcher
from backend.services.time_decay_executor import TimeDecayExecutor


# ============================================
# NodeTypeMatcher Tests
# ============================================

@pytest.mark.unit
class TestNodeTypeMatcher:
    """Test node type classification"""
    
    def test_classify_metric_by_type_field(self):
        """Test metric node detection via type field"""
        node_data = {"type": "health_metric", "metric_name": "Blood Pressure"}
        node_type, metric_name = NodeTypeMatcher.classify_node(node_data)
        assert node_type == "metric"
        assert metric_name == "Blood Pressure"
    
    def test_classify_metric_by_metric_name_field(self):
        """Test metric node detection via metric_name field"""
        node_data = {"name": "血压", "metric_name": "Blood Pressure"}
        node_type, metric_name = NodeTypeMatcher.classify_node(node_data)
        assert node_type == "metric"
        assert metric_name == "Blood Pressure"
    
    def test_classify_symptom_by_type_field(self):
        """Test symptom node detection via type field"""
        node_data = {"type": "symptom", "name": "头痛"}
        node_type, metric_name = NodeTypeMatcher.classify_node(node_data)
        assert node_type == "symptom"
        assert metric_name is None
    
    def test_classify_symptom_by_keyword(self):
        """Test symptom node detection via keyword matching"""
        node_data = {"name": "头痛", "value": "持续 3 天"}
        node_type, metric_name = NodeTypeMatcher.classify_node(node_data)
        assert node_type == "symptom"
        assert metric_name is None
    
    def test_classify_metric_by_name_keyword(self):
        """Test metric node detection via name keyword"""
        node_data = {"name": "Blood Pressure", "value": "145/92"}
        node_type, metric_name = NodeTypeMatcher.classify_node(node_data)
        assert node_type == "metric"
        assert metric_name == "Blood Pressure"
    
    def test_classify_time_decay_only(self):
        """Test nodes that only need time decay"""
        node_data = {"name": "年龄", "value": "55", "type": "demographic"}
        node_type, metric_name = NodeTypeMatcher.classify_node(node_data)
        assert node_type == "time_decay"
        assert metric_name is None
    
    def test_classify_english_symptom_keywords(self):
        """Test English symptom keyword matching"""
        node_data = {"name": "Headache", "value": "severe"}
        node_type, metric_name = NodeTypeMatcher.classify_node(node_data)
        assert node_type == "symptom"
    
    def test_classify_english_metric_keywords(self):
        """Test English metric keyword matching"""
        node_data = {"name": "Heart Rate", "value": "72"}
        node_type, metric_name = NodeTypeMatcher.classify_node(node_data)
        assert node_type == "metric"
        assert metric_name == "Heart Rate"
    
    def test_is_metric_node_helper(self):
        """Test is_metric_node helper method"""
        assert NodeTypeMatcher.is_metric_node({"type": "health_metric"}) is True
        assert NodeTypeMatcher.is_metric_node({"name": "血压"}) is True
        assert NodeTypeMatcher.is_metric_node({"name": "头痛"}) is False
    
    def test_is_symptom_node_helper(self):
        """Test is_symptom_node helper method"""
        assert NodeTypeMatcher.is_symptom_node({"type": "symptom"}) is True
        assert NodeTypeMatcher.is_symptom_node({"name": "头痛"}) is True
        assert NodeTypeMatcher.is_symptom_node({"name": "血压"}) is False


# ============================================
# TimeDecayExecutor Tests
# ============================================

@pytest.mark.unit
class TestTimeDecayExecutor:
    """Test time decay calculations"""
    
    def test_apply_exponential_decay_vital_signs(self):
        """Test exponential decay for vital signs (3-day half-life)"""
        # Create mock EntityGraph
        entity_graph = Mock()
        old_date = datetime.now() - timedelta(days=6)  # 6 days = 2 half-lives
        
        entity_graph.entity_graph.nodes = {
            "bp_node": {
                "confidence": 1.0,
                "last_updated": old_date,
                "name": "Blood Pressure"
            }
        }
        
        decay = TimeDecayExecutor()
        new_conf = decay.apply_decay(entity_graph, "bp_node", "metric")
        
        # 6 days / 3-day half-life = 2 half-lives = 0.5^2 = 0.25
        assert abs(new_conf - 0.25) < 0.01
    
    def test_apply_exponential_decay_lab_metabolism(self):
        """Test exponential decay for lab metabolism (30-day half-life)"""
        entity_graph = Mock()
        old_date = datetime.now() - timedelta(days=30)  # 30 days = 1 half-life
        
        entity_graph.entity_graph.nodes = {
            "glucose_node": {
                "confidence": 1.0,
                "last_updated": old_date,
                "name": "Blood Glucose"
            }
        }
        
        decay = TimeDecayExecutor()
        new_conf = decay.apply_decay(entity_graph, "glucose_node", "metric")
        
        # 30 days / 30-day half-life = 1 half-life = 0.5
        assert abs(new_conf - 0.5) < 0.01
    
    def test_apply_step_decay_symptom(self):
        """Test step decay for symptoms (0.8 per week)"""
        entity_graph = Mock()
        old_date = datetime.now() - timedelta(days=14)  # 2 weeks
        
        entity_graph.entity_graph.nodes = {
            "symptom_node": {
                "confidence": 1.0,
                "last_updated": old_date,
                "name": "头痛"
            }
        }
        
        decay = TimeDecayExecutor()
        new_conf = decay.apply_decay(entity_graph, "symptom_node", "symptom")
        
        # 2 weeks * 0.8^2 = 0.64
        assert abs(new_conf - 0.64) < 0.01
    
    def test_apply_default_decay(self):
        """Test default decay (14-day half-life)"""
        entity_graph = Mock()
        old_date = datetime.now() - timedelta(days=14)
        
        entity_graph.entity_graph.nodes = {
            "demo_node": {
                "confidence": 1.0,
                "last_updated": old_date,
                "name": "年龄"
            }
        }
        
        decay = TimeDecayExecutor()
        new_conf = decay.apply_decay(entity_graph, "demo_node", "time_decay")
        
        # 14 days / 14-day half-life = 0.5
        assert abs(new_conf - 0.5) < 0.01
    
    def test_apply_decay_floor(self):
        """Test confidence floor at 0.1"""
        entity_graph = Mock()
        very_old_date = datetime.now() - timedelta(days=365)  # 1 year
        
        entity_graph.entity_graph.nodes = {
            "old_node": {
                "confidence": 1.0,
                "last_updated": very_old_date,
                "name": "Old Symptom"
            }
        }
        
        decay = TimeDecayExecutor()
        new_conf = decay.apply_decay(entity_graph, "old_node", "symptom")
        
        # Should be floored at 0.1
        assert new_conf >= 0.1
        assert abs(new_conf - 0.1) < 0.01
    
    def test_apply_decay_no_timestamp(self):
        """Test node without timestamp keeps original confidence"""
        entity_graph = Mock()
        
        entity_graph.entity_graph.nodes = {
            "no_timestamp_node": {
                "confidence": 0.8,
                "name": "No Timestamp"
            }
        }
        
        decay = TimeDecayExecutor()
        new_conf = decay.apply_decay(entity_graph, "no_timestamp_node", "metric")
        
        # Should keep original confidence
        assert new_conf == 0.8
    
    def test_apply_decay_iso_string_timestamp(self):
        """Test handling of ISO string timestamps"""
        entity_graph = Mock()
        old_date = datetime.now() - timedelta(days=7)
        
        entity_graph.entity_graph.nodes = {
            "iso_node": {
                "confidence": 1.0,
                "last_updated": old_date.isoformat(),  # ISO string
                "name": "Blood Pressure"
            }
        }
        
        decay = TimeDecayExecutor()
        new_conf = decay.apply_decay(entity_graph, "iso_node", "metric")
        
        # 7 days / 3-day half-life ≈ 0.5^(7/3) ≈ 0.20
        assert abs(new_conf - 0.20) < 0.05
    
    def test_apply_decay_to_all_nodes(self):
        """Test applying decay to all nodes in graph"""
        # Create mock EntityGraph with proper structure
        from collections import UserDict
        
        old_date = datetime.now() - timedelta(days=7)
        
        # Create mock nodes that support both iteration and subscript access
        mock_nodes_data = {
            "bp_node": {
                "confidence": 1.0,
                "last_updated": old_date,
                "name": "Blood Pressure",
                "type": "health_metric"
            },
            "symptom_node": {
                "confidence": 1.0,
                "last_updated": old_date,
                "name": "头痛"
            },
            "demo_node": {
                "confidence": 1.0,
                "last_updated": old_date,
                "name": "年龄"
            }
        }
        
        # Create mock entity_graph
        entity_graph = Mock()
        entity_graph.entity_graph = Mock()
        
        # Mock nodes[data=True]() to return items
        entity_graph.entity_graph.nodes = Mock(return_value=mock_nodes_data.items())
        # Also support subscript access: nodes[node_id]
        entity_graph.entity_graph.nodes.__getitem__ = lambda self, key: mock_nodes_data[key]
        
        decay = TimeDecayExecutor()
        results = decay.apply_decay_to_all_nodes(entity_graph)
        
        # Should return results for all nodes
        assert len(results) == 3
        assert "bp_node" in results
        assert "symptom_node" in results
        assert "demo_node" in results
