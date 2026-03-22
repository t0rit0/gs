"""
Integration Tests for Update Agent with Real LLM API

These tests make REAL LLM API calls to verify code generation works correctly.
Requires valid LLM API configuration in config.yaml.

Run with: uv run pytest tests/integration/test_update_agent_llm.py -v -s
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock

from backend.services.update_agent import UpdateAgent
from backend.services.node_type_matcher import NodeTypeMatcher
from backend.services.time_decay_executor import TimeDecayExecutor
from backend.services.metric_crud import MetricCRUD
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from drhyper.core.graph import EntityGraph
from drhyper.utils.llm_loader import load_chat_model
from drhyper.config.settings import ConfigManager as DrHyperConfig


@pytest.mark.integration
@pytest.mark.slow
class TestUpdateAgentWithRealLLM:
    """Integration tests with real LLM API calls"""
    
    @pytest.fixture
    def db_session(self, db_session):
        """Provide database session"""
        yield db_session
    
    @pytest.fixture
    def patient_with_metrics(self, db_session):
        """Create patient with health metrics for testing"""
        # Create patient
        patient = patient_crud.create(db_session, PatientCreate(
            name="测试患者 UpdateAgent",
            age=45,
            gender="male",
            phone="13900000000"
        ))
        
        # Create blood pressure record 145/92
        MetricCRUD.create_record(
            db=db_session,
            patient_id=patient.patient_id,
            metric_name="Blood Pressure",
            value="145/92",
            measured_at=datetime.now()
        )
        
        # Create blood glucose record 6.5 mmol/L
        MetricCRUD.create_record(
            db=db_session,
            patient_id=patient.patient_id,
            metric_name="Blood Glucose",
            value=6.5,
            unit="mmol/L",
            measured_at=datetime.now()
        )
        
        # Add symptom "头痛" with status "active"
        patient_crud.add_symptom(
            db=db_session,
            patient_id=patient.patient_id,
            symptom="头痛",
            description="持续 3 天，轻度疼痛",
            status="active"
        )
        
        db_session.commit()
        return patient
    
    @pytest.fixture
    def mock_entity_graph(self):
        """Create a mock EntityGraph for testing"""
        # Create real EntityGraph with mock models
        drhyper_config = DrHyperConfig()
        
        conv_model = load_chat_model(
            provider=drhyper_config.conversation_llm.provider,
            model_name=drhyper_config.conversation_llm.model,
            api_key=drhyper_config.conversation_llm.api_key,
            base_url=drhyper_config.conversation_llm.base_url,
            temperature=drhyper_config.conversation_llm.temperature
        )
        
        graph_model = load_chat_model(
            provider=drhyper_config.graph_llm.provider,
            model_name=drhyper_config.graph_llm.model,
            api_key=drhyper_config.graph_llm.api_key,
            base_url=drhyper_config.graph_llm.base_url,
            temperature=drhyper_config.graph_llm.temperature
        )
        
        entity_graph = EntityGraph(
            target="Hypertension diagnosis",
            graph_model=graph_model,
            conv_model=conv_model
        )
        
        # Initialize with empty graph
        entity_graph.entity_graph.clear()
        
        return entity_graph
    
    def test_update_metric_node_with_real_llm(self, db_session, patient_with_metrics, mock_entity_graph):
        """
        Test updating metric node with real LLM API
        
        Given: Patient has BP record 145/92
        When: UpdateAgent updates EntityGraph node
        Then: LLM-generated code should update node value to 145/92
        """
        # Setup: Add BP node with old value
        entity_graph = mock_entity_graph
        entity_graph.entity_graph.add_node(
            "metric_bp",
            name="Blood Pressure",
            value="120/80",  # Old value
            metric_name="Blood Pressure"
        )
        
        # Execute: Update with real LLM
        agent = UpdateAgent(db_session)
        success = agent._update_metric_node(
            entity_graph=entity_graph,
            node_id="metric_bp",
            metric_name="Blood Pressure",
            patient_id=patient_with_metrics.patient_id
        )
        
        # Assert
        assert success is True
        assert entity_graph.entity_graph.nodes["metric_bp"]["value"] == "145/92"
        assert entity_graph.entity_graph.nodes["metric_bp"]["last_updated"] is not None
    
    def test_update_symptom_node_with_real_llm(self, db_session, patient_with_metrics, mock_entity_graph):
        """
        Test updating symptom node with real LLM API
        
        Given: Patient has symptom "头痛" with status "active"
        When: UpdateAgent updates EntityGraph node
        Then: LLM-generated code should update node status to 2 (confirmed)
        """
        entity_graph = mock_entity_graph
        entity_graph.entity_graph.add_node(
            "symptom_headache",
            name="头痛",
            status=0,  # Unconfirmed
            value=""
        )
        
        agent = UpdateAgent(db_session)
        success = agent._update_symptom_node(
            entity_graph=entity_graph,
            node_id="symptom_headache",
            patient_id=patient_with_metrics.patient_id
        )
        
        # Assert
        assert success is True
        assert entity_graph.entity_graph.nodes["symptom_headache"]["status"] == 2
        assert entity_graph.entity_graph.nodes["symptom_headache"]["value"] != ""
    
    def test_retry_on_llm_syntax_error(self, db_session, patient_with_metrics, mock_entity_graph, mocker):
        """
        Test retry mechanism when LLM generates syntax error
        
        Given: Mock LLM returns syntax error first, then valid code
        When: UpdateAgent retries
        Then: Should succeed on second attempt
        """
        entity_graph = mock_entity_graph
        entity_graph.entity_graph.add_node(
            "metric_bp",
            name="Blood Pressure",
            value="120/80",
            metric_name="Blood Pressure"
        )
        
        # Mock LLM: first bad code, then good code
        bad_code = "record = MetricCRUD.get_latest_record(sandbox, patient_id"  # Missing args
        good_code = """record = MetricCRUD.get_latest_record(sandbox, patient_id, 'Blood Pressure')
if record:
    entity_graph.nodes[node_id]['value'] = record.value_string
    result['updated'] = True"""
        
        agent = UpdateAgent(db_session)
        agent.model.invoke = Mock(side_effect=[
            Mock(content=bad_code),  # First attempt fails
            Mock(content=good_code),  # Second attempt succeeds
        ])
        
        success = agent._update_metric_node(
            entity_graph=entity_graph,
            node_id="metric_bp",
            metric_name="Blood Pressure",
            patient_id=patient_with_metrics.patient_id
        )
        
        # Assert
        assert success is True
        assert agent.model.invoke.call_count == 2  # Retried once
    
    def test_max_retries_exceeded(self, db_session, patient_with_metrics, mock_entity_graph, mocker):
        """
        Test max retries exceeded
        
        Given: Mock LLM always returns invalid code
        When: UpdateAgent retries 3 times
        Then: Should return False after max retries
        """
        entity_graph = mock_entity_graph
        entity_graph.entity_graph.add_node(
            "metric_bp",
            name="Blood Pressure",
            value="120/80",
            metric_name="Blood Pressure"
        )
        
        bad_code = "invalid python code {{{{"
        
        agent = UpdateAgent(db_session)
        agent.model.invoke = Mock(return_value=Mock(content=bad_code))
        
        success = agent._update_metric_node(
            entity_graph=entity_graph,
            node_id="metric_bp",
            metric_name="Blood Pressure",
            patient_id=patient_with_metrics.patient_id
        )
        
        # Assert
        assert success is False
        assert agent.model.invoke.call_count == 3  # Max 3 retries
    
    def test_update_all_nodes_mixed_types(self, db_session, patient_with_metrics, mock_entity_graph):
        """
        Test updating all node types
        
        Given: EntityGraph has metric, symptom, and other nodes
        When: update_all_nodes is called
        Then: Each type should be updated correctly
        """
        entity_graph = mock_entity_graph
        
        # Add metric node
        entity_graph.entity_graph.add_node(
            "metric_bp",
            name="Blood Pressure",
            value="120/80",
            metric_name="Blood Pressure",
            confidence=1.0
        )
        
        # Add symptom node
        entity_graph.entity_graph.add_node(
            "symptom_headache",
            name="头痛",
            status=0,
            value="",
            confidence=1.0
        )
        
        # Add demographic node (time decay only)
        entity_graph.entity_graph.add_node(
            "demo_age",
            name="年龄",
            value=55,
            confidence=1.0
        )
        
        # Execute
        agent = UpdateAgent(db_session)
        stats = agent.update_all_nodes(entity_graph, patient_with_metrics.patient_id)
        
        # Assert stats
        assert stats["metric_updated"] >= 1
        assert stats["symptom_updated"] >= 1
        assert stats["time_decay_applied"] >= 3
        
        # Assert values updated
        assert entity_graph.entity_graph.nodes["metric_bp"]["value"] == "145/92"
        assert entity_graph.entity_graph.nodes["symptom_headache"]["status"] == 2


@pytest.mark.integration
@pytest.mark.slow
class TestNodeTypeMatcherIntegration:
    """Integration tests for NodeTypeMatcher with real data"""
    
    def test_classify_node_from_real_entity_graph(self, db_session):
        """Test node classification with real EntityGraph node structure"""
        # Simulate real node data structures
        metric_node = {
            "name": "Blood Pressure",
            "value": "145/92",
            "status": 2,
            "confidence": 0.9,
            "metric_name": "Blood Pressure",
            "last_updated": datetime.now()
        }
        
        symptom_node = {
            "name": "头痛",
            "value": "持续 3 天",
            "status": 1,
            "confidence": 0.7,
            "last_updated": datetime.now()
        }
        
        demo_node = {
            "name": "年龄",
            "value": "55",
            "status": 2,
            "confidence": 1.0
        }
        
        # Test classification
        assert NodeTypeMatcher.classify_node(metric_node) == ("metric", "Blood Pressure")
        assert NodeTypeMatcher.classify_node(symptom_node) == ("symptom", None)
        assert NodeTypeMatcher.classify_node(demo_node) == ("time_decay", None)


@pytest.mark.integration
@pytest.mark.slow
class TestTimeDecayExecutorIntegration:
    """Integration tests for TimeDecayExecutor with real EntityGraph"""
    
    def test_apply_decay_to_real_entity_graph(self):
        """Test applying decay to real EntityGraph structure"""
        drhyper_config = DrHyperConfig()
        
        conv_model = load_chat_model(
            provider=drhyper_config.conversation_llm.provider,
            model_name=drhyper_config.conversation_llm.model,
            api_key=drhyper_config.conversation_llm.api_key,
            base_url=drhyper_config.conversation_llm.base_url,
            temperature=drhyper_config.conversation_llm.temperature
        )
        
        graph_model = load_chat_model(
            provider=drhyper_config.graph_llm.provider,
            model_name=drhyper_config.graph_llm.model,
            api_key=drhyper_config.graph_llm.api_key,
            base_url=drhyper_config.graph_llm.base_url,
            temperature=drhyper_config.graph_llm.temperature
        )
        
        entity_graph = EntityGraph(
            target="Hypertension diagnosis",
            graph_model=graph_model,
            conv_model=conv_model
        )
        
        # Add nodes with old timestamps
        old_date = datetime.now() - timedelta(days=7)
        entity_graph.entity_graph.add_node(
            "bp",
            name="Blood Pressure",
            confidence=1.0,
            last_updated=old_date
        )
        
        # Apply decay
        decay = TimeDecayExecutor()
        new_conf = decay.apply_decay(entity_graph, "bp", "metric")
        
        # 7 days / 3-day half-life ≈ 0.5^(7/3) ≈ 0.20
        assert abs(new_conf - 0.20) < 0.05
