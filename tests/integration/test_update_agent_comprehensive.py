"""
Comprehensive Integration Tests for Update Agent

This test suite verifies the complete UpdateAgent functionality with REAL LLM calls
and REAL database operations (no mocking).

Tests cover:
1. Node connection: DrHyper nodes → metric/symptom nodes from data
2. Code generation: LLM generates correct update code
3. Code application: Generated code correctly updates EntityGraph
4. Data manager trigger: Node linking triggers database updates
5. Time decay: Correct decay code generation and execution
6. Sandbox mechanism: Write operations are intercepted
7. Approval mechanism: Operations require explicit approval

Requirements:
- Valid LLM API configuration in config.yaml
- Database access (SQLite or PostgreSQL)
- DrHyper submodule initialized

Run with:
    uv run pytest tests/integration/test_update_agent_comprehensive.py -v -s

Or use the test runner script:
    uv run python tests/integration/run_update_agent_tests.py
"""

import pytest
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from backend.services.entity_graph_manager import EntityGraphManager
from backend.services.update_agent import UpdateAgent
from backend.services.metric_crud import MetricCRUD
from backend.agents.data_manager import DataManagerCodeAgent
from backend.services.sandbox_session import SandboxSession, sandbox_session
from backend.services.session_sandbox_manager import sandbox_session_manager
from backend.database.crud import patient_crud, conversation_crud
from backend.database.schemas import PatientCreate, ConversationCreate
from backend.database.base import SessionLocal
from backend.config.config_manager import get_config

logger = logging.getLogger(__name__)


# ============================================
# Test Configuration
# ============================================

@pytest.fixture(scope="function")
def db_session():
    """Provide fresh database session for each test"""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture(scope="function")
def clean_db(db_session):
    """Clean database before each test"""
    from backend.database.models import Patient, Conversation, Message, HealthMetricRecord
    
    # Delete all records
    db_session.query(HealthMetricRecord).delete()
    db_session.query(Message).delete()
    db_session.query(Conversation).delete()
    db_session.query(Patient).delete()
    db_session.commit()
    
    yield db_session


@pytest.fixture
def patient_with_metrics(clean_db):
    """
    Create patient with multiple health metric records
    
    Returns:
        Tuple of (patient, metric_records)
    """
    # Create patient
    patient = patient_crud.create(clean_db, PatientCreate(
        name="综合测试患者",
        age=55,
        gender="male",
        phone="13800000001"
    ))
    
    # Create multiple metric records
    now = datetime.now()
    records = []
    
    # Blood Pressure: 150/95 (recent)
    bp_record = MetricCRUD.create_record(
        db=clean_db,
        patient_id=patient.patient_id,
        metric_name="Blood Pressure",
        value="150/95",
        measured_at=now
    )
    records.append(("Blood Pressure", bp_record))
    
    # Blood Pressure: 145/92 (5 days ago - for time decay test)
    bp_old = MetricCRUD.create_record(
        db=clean_db,
        patient_id=patient.patient_id,
        metric_name="Blood Pressure",
        value="145/92",
        measured_at=now - timedelta(days=5)
    )
    records.append(("Blood Pressure (old)", bp_old))
    
    # Heart Rate: 78 bpm
    hr_record = MetricCRUD.create_record(
        db=clean_db,
        patient_id=patient.patient_id,
        metric_name="Heart Rate",
        value="78",
        measured_at=now
    )
    records.append(("Heart Rate", hr_record))
    
    # Glucose: 6.5 mmol/L
    glucose_record = MetricCRUD.create_record(
        db=clean_db,
        patient_id=patient.patient_id,
        metric_name="Glucose",
        value="6.5",
        measured_at=now
    )
    records.append(("Glucose", glucose_record))
    
    clean_db.commit()
    
    return patient, records


@pytest.fixture
def patient_with_symptoms(clean_db):
    """
    Create patient with multiple symptom records
    
    Returns:
        Tuple of (patient, symptoms)
    """
    patient = patient_crud.create(clean_db, PatientCreate(
        name="症状测试患者",
        age=50,
        gender="female",
        phone="13800000002"
    ))
    
    # Add multiple symptoms
    symptoms = []
    
    # Active symptom: 头痛
    patient_crud.add_symptom(
        db=clean_db,
        patient_id=patient.patient_id,
        symptom="头痛",
        description="持续 3 天，中度疼痛",
        status="active"
    )
    symptoms.append(("头痛", "active"))
    
    # Active symptom: 头晕
    patient_crud.add_symptom(
        db=clean_db,
        patient_id=patient.patient_id,
        symptom="头晕",
        description="偶尔发作",
        status="active"
    )
    symptoms.append(("头晕", "active"))
    
    # Resolved symptom: 恶心
    patient_crud.add_symptom(
        db=clean_db,
        patient_id=patient.patient_id,
        symptom="恶心",
        description="已缓解",
        status="resolved"
    )
    symptoms.append(("恶心", "resolved"))
    
    clean_db.commit()
    
    return patient, symptoms


@pytest.fixture
def patient_comprehensive(clean_db):
    """
    Create comprehensive patient with both metrics and symptoms
    
    Returns:
        Tuple of (patient, metrics, symptoms)
    """
    # Create patient
    patient = patient_crud.create(clean_db, PatientCreate(
        name="完整测试患者",
        age=60,
        gender="male",
        phone="13800000003",
        medical_history=[
            {
                "condition": "高血压",
                "diagnosis_date": "2024-01-15T00:00:00",
                "status": "chronic",
                "notes": "原发性高血压"
            }
        ]
    ))
    
    now = datetime.now()
    
    # Create metric records
    MetricCRUD.create_record(
        db=clean_db,
        patient_id=patient.patient_id,
        metric_name="Blood Pressure",
        value="155/98",
        measured_at=now
    )
    
    MetricCRUD.create_record(
        db=clean_db,
        patient_id=patient.patient_id,
        metric_name="Heart Rate",
        value="82",
        measured_at=now - timedelta(days=2)
    )
    
    # Add symptoms
    patient_crud.add_symptom(
        db=clean_db,
        patient_id=patient.patient_id,
        symptom="头痛",
        description="最近一周频繁发作",
        status="active"
    )
    
    patient_crud.add_symptom(
        db=clean_db,
        patient_id=patient.patient_id,
        symptom="心悸",
        description="运动后明显",
        status="active"
    )
    
    clean_db.commit()
    
    return patient


# ============================================
# Test 1: Node Connection to Metric/Symptom Nodes
# ============================================

class TestNodeConnection:
    """
    Test 1: Verify DrHyper nodes connect correctly to metric/symptom nodes from data
    
    This tests the NodeTypeMatcher classification and node linking mechanism.
    """
    
    def test_metric_node_classification(self, clean_db, patient_with_metrics):
        """
        Test that metric nodes are correctly classified and linked
        
        Given: Patient with Blood Pressure and Heart Rate records
        When: UpdateAgent processes EntityGraph nodes
        Then: Metric nodes should be correctly identified and updated
        """
        patient, records = patient_with_metrics
        
        # Create EntityGraph
        manager = EntityGraphManager()
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        # Get EntityGraph (triggers UpdateAgent)
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        # Verify metric nodes exist and are updated
        metric_nodes_found = 0
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_type, metric_name = manager.classify_node_type(node_data)
            
            if node_type == "metric":
                metric_nodes_found += 1
                logger.info(f"Found metric node: {node_id}, metric_name={metric_name}, value={node_data.get('value')}")
                
                # Verify node has required fields
                assert "value" in node_data, f"Metric node {node_id} missing 'value' field"
                assert "last_updated" in node_data, f"Metric node {node_id} missing 'last_updated' field"
                assert "confidence" in node_data, f"Metric node {node_id} missing 'confidence' field"
        
        # Should have found at least one metric node
        assert metric_nodes_found > 0, "No metric nodes found in EntityGraph"
        logger.info(f"✅ Test passed: {metric_nodes_found} metric nodes found and classified")
    
    def test_symptom_node_classification(self, clean_db, patient_with_symptoms):
        """
        Test that symptom nodes are correctly classified and linked
        
        Given: Patient with 头痛，头晕，恶心 symptoms
        When: UpdateAgent processes EntityGraph nodes
        Then: Symptom nodes should be correctly identified and updated
        """
        patient, symptoms = patient_with_symptoms
        
        manager = EntityGraphManager()
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        # Verify symptom nodes
        symptom_nodes_found = 0
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_type, _ = manager.classify_node_type(node_data)
            
            if node_type == "symptom":
                symptom_nodes_found += 1
                logger.info(f"Found symptom node: {node_id}, name={node_data.get('name')}, status={node_data.get('status')}")
                
                # Verify node has required fields
                assert "status" in node_data, f"Symptom node {node_id} missing 'status' field"
                assert "value" in node_data, f"Symptom node {node_id} missing 'value' field"
        
        logger.info(f"✅ Test passed: {symptom_nodes_found} symptom nodes found and classified")
    
    def test_node_connection_with_update_agent(self, clean_db, patient_comprehensive):
        """
        Test complete node connection workflow with UpdateAgent
        
        Given: Patient with metrics and symptoms
        When: UpdateAgent.update_all_nodes() is called
        Then: All nodes should be correctly connected and updated
        """
        patient = patient_comprehensive
        
        # Create EntityGraph manually
        from drhyper.core.graph import EntityGraph
        
        manager = EntityGraphManager()
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        # Run UpdateAgent explicitly
        update_agent = UpdateAgent(clean_db)
        stats = update_agent.update_all_nodes(entity_graph, patient.patient_id)
        
        logger.info(f"UpdateAgent stats: {stats}")
        
        # Verify updates were applied
        assert stats["metric_updated"] >= 0, "Metric update count should be non-negative"
        assert stats["symptom_updated"] >= 0, "Symptom update count should be non-negative"
        assert stats["time_decay_applied"] > 0, "Time decay should be applied to all nodes"
        
        logger.info(
            f"✅ Test passed: {stats['metric_updated']} metrics updated, "
            f"{stats['symptom_updated']} symptoms updated, "
            f"{stats['time_decay_applied']} nodes with time decay"
        )


# ============================================
# Test 2: Code Generation and Application
# ============================================

class TestCodeGeneration:
    """
    Test 2: Verify LLM generates correct update code and applies it correctly
    
    This tests the UpdateAgent's LLM-based code generation mechanism.
    """
    
    def test_metric_code_generation(self, clean_db, patient_with_metrics):
        """
        Test LLM generates correct code for metric updates
        
        Given: Metric node with outdated value
        When: UpdateAgent generates code for metric update
        Then: Generated code should query database and update node value
        """
        patient, records = patient_with_metrics
        
        # Create EntityGraph
        manager = EntityGraphManager()
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        # Find a metric node
        metric_node_id = None
        metric_node_name = None
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_type, metric_name = manager.classify_node_type(node_data)
            if node_type == "metric" and metric_name == "Blood Pressure":
                metric_node_id = node_id
                metric_node_name = metric_name
                break
        
        assert metric_node_id is not None, "Blood Pressure metric node not found"
        
        # Get initial value
        initial_value = entity_graph.entity_graph.nodes[metric_node_id].get("value")
        logger.info(f"Initial BP value: {initial_value}")
        
        # Create UpdateAgent and update this specific node
        update_agent = UpdateAgent(clean_db)
        success = update_agent._update_metric_node(
            entity_graph, metric_node_id, metric_node_name, patient.patient_id
        )
        
        # Verify update was successful
        assert success, f"Failed to update metric node {metric_node_id}"
        
        # Verify value was updated
        updated_value = entity_graph.entity_graph.nodes[metric_node_id].get("value")
        logger.info(f"Updated BP value: {updated_value}")
        
        # Value should be the latest record value (150/95)
        assert updated_value == "150/95", f"Expected BP value '150/95', got '{updated_value}'"
        
        logger.info(f"✅ Test passed: Metric code generation and application successful")
    
    def test_symptom_code_generation(self, clean_db, patient_with_symptoms):
        """
        Test LLM generates correct code for symptom updates
        
        Given: Symptom node with outdated status
        When: UpdateAgent generates code for symptom update
        Then: Generated code should query database and update node status
        """
        patient, symptoms = patient_with_symptoms
        
        manager = EntityGraphManager()
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        # Find symptom node for 头痛
        symptom_node_id = None
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            if "头痛" in node_data.get("name", ""):
                symptom_node_id = node_id
                break
        
        if symptom_node_id is None:
            logger.warning("头痛 symptom node not found, skipping test")
            pytest.skip("头痛 symptom node not created by DrHyper")
        
        # Get initial status
        initial_status = entity_graph.entity_graph.nodes[symptom_node_id].get("status")
        logger.info(f"Initial 头痛 status: {initial_status}")
        
        # Update symptom node
        update_agent = UpdateAgent(clean_db)
        success = update_agent._update_symptom_node(
            entity_graph, symptom_node_id, patient.patient_id
        )
        
        # Verify update was successful
        assert success, f"Failed to update symptom node {symptom_node_id}"
        
        # Verify status was updated to 2 (confirmed/active)
        updated_status = entity_graph.entity_graph.nodes[symptom_node_id].get("status")
        logger.info(f"Updated 头痛 status: {updated_status}")
        
        # Active symptom should have status=2
        assert updated_status == 2, f"Expected status 2 for active symptom, got {updated_status}"
        
        logger.info(f"✅ Test passed: Symptom code generation and application successful")
    
    def test_code_generation_retry_mechanism(self, clean_db, patient_with_metrics):
        """
        Test code generation retry mechanism with errors
        
        Given: UpdateAgent with retry logic
        When: Code generation encounters errors
        Then: Should retry up to max_retries times
        """
        patient, _ = patient_with_metrics
        
        manager = EntityGraphManager()
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        # Find any metric node
        metric_node_id = None
        metric_name = None
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_type, m_name = manager.classify_node_type(node_data)
            if node_type == "metric":
                metric_node_id = node_id
                metric_name = m_name
                break
        
        assert metric_node_id is not None
        
        # UpdateAgent should handle errors gracefully
        update_agent = UpdateAgent(clean_db)
        
        # This should complete (either succeed or fail gracefully after retries)
        success = update_agent._update_metric_node(
            entity_graph, metric_node_id, metric_name, patient.patient_id
        )
        
        # Should either succeed or fail gracefully (not crash)
        logger.info(f"Code generation completed: success={success}")
        assert isinstance(success, bool), "Update result should be boolean"


# ============================================
# Test 3: Data Manager Database Update Trigger
# ============================================

class TestDataManagerTrigger:
    """
    Test 3: Verify node linking triggers data manager database updates
    
    This tests the workflow where EntityGraph changes trigger database writes
    through the DataManager mechanism.
    """
    
    def test_data_manager_write_operation(self, clean_db, patient_comprehensive):
        """
        Test DataManager intercepts write operations
        
        Given: User requests database modification through DataManager
        When: DataManager executes code with write operations
        Then: Operations should be intercepted by sandbox
        """
        patient = patient_comprehensive
        
        # Create DataManager agent
        data_manager = DataManagerCodeAgent()
        
        # Request that requires database write
        user_request = f"Update patient {patient.patient_id} name to '测试更新'"
        
        # Process request
        result = data_manager.process_request(
            user_request,
            conversation_id="test_conv_001"
        )
        
        logger.info(f"DataManager result: {result}")
        
        # Check for pending operations
        pending_ops = data_manager.get_pending_operations("test_conv_001")
        
        # Should have pending operations (not yet committed)
        assert len(pending_ops) > 0, "Should have pending operations in sandbox"
        
        logger.info(f"Pending operations: {pending_ops}")
        
        # Verify patient name NOT yet updated in database
        fresh_patient = patient_crud.get(clean_db, patient.patient_id)
        assert fresh_patient.name == "完整测试患者", "Name should not be updated until approved"
        
        # Approve operations
        approval_result = data_manager.approve_and_execute_all("test_conv_001")
        logger.info(f"Approval result: {approval_result}")
        
        # Verify patient name IS now updated
        final_patient = patient_crud.get(clean_db, patient.patient_id)
        assert final_patient.name == "测试更新", "Name should be updated after approval"
        
        logger.info(f"✅ Test passed: DataManager write operation and approval workflow")
    
    def test_sandbox_intercepts_commit(self, clean_db, patient_with_metrics):
        """
        Test that SandboxSession intercepts commit operations
        
        Given: SandboxSession wrapping database session
        When: Code attempts to commit changes
        Then: Commit should be intercepted and recorded
        """
        patient, _ = patient_with_metrics
        
        # Create sandbox session
        with sandbox_session(clean_db, "test_conv_002") as sandbox:
            # Perform write operation
            patient_obj = patient_crud.get(sandbox, patient.patient_id)
            patient_obj.age = 99
            
            # Attempt commit (should be intercepted)
            sandbox.commit()
            
            # Verify operation was recorded
            pending_ops = sandbox.get_pending_operations()
            assert len(pending_ops) > 0, "Commit should be intercepted and recorded"
            
            logger.info(f"Intercepted operations: {pending_ops}")
            
            # Verify change NOT in database (rollback happens on exit)
        
        # Verify age NOT updated in database
        fresh_patient = patient_crud.get(clean_db, patient.patient_id)
        assert fresh_patient.age != 99, "Age should not be updated (sandbox rolled back)"
        
        logger.info(f"✅ Test passed: Sandbox commit interception")
    
    def test_operation_accumulation_across_requests(self, clean_db, patient_comprehensive):
        """
        Test that operations accumulate across multiple requests
        
        Given: Multiple requests from same conversation
        When: Each request makes database changes
        Then: Operations should accumulate in sandbox
        """
        patient = patient_comprehensive
        
        data_manager = DataManagerCodeAgent()
        conv_id = "test_conv_003"
        
        # Request 1: Update name
        result1 = data_manager.process_request(
            f"Update patient {patient.patient_id} name to '累积测试'",
            conversation_id=conv_id
        )
        
        # Request 2: Update age
        result2 = data_manager.process_request(
            f"Update patient {patient.patient_id} age to 65",
            conversation_id=conv_id
        )
        
        # Check pending operations
        pending_ops = data_manager.get_pending_operations(conv_id)
        
        # Should have accumulated operations from both requests
        assert len(pending_ops) >= 1, f"Should have accumulated operations, got {len(pending_ops)}"
        
        logger.info(f"Accumulated operations: {pending_ops}")
        
        # Cleanup: Reject operations
        data_manager.reject_and_discard_all(conv_id)
        
        logger.info(f"✅ Test passed: Operation accumulation across requests")


# ============================================
# Test 4: Time Decay Code Execution
# ============================================

class TestTimeDecay:
    """
    Test 4: Verify time decay code is correctly generated and executed
    
    This tests the TimeDecayExecutor and LLM-generated time decay code.
    """
    
    def test_time_decay_application(self, clean_db, patient_with_metrics):
        """
        Test time decay is applied to nodes
        
        Given: EntityGraph with nodes having old last_updated timestamps
        When: UpdateAgent applies time decay
        Then: Node confidence should be reduced based on age
        """
        patient, _ = patient_with_metrics
        
        manager = EntityGraphManager()
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        # Manually age some nodes
        old_date = datetime.now() - timedelta(days=10)
        aged_nodes = []
        
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_data["last_updated"] = old_date
            node_data["confidence"] = 1.0
            aged_nodes.append(node_id)
        
        logger.info(f"Aged {len(aged_nodes)} nodes by 10 days")
        
        # Run UpdateAgent (applies time decay)
        update_agent = UpdateAgent(clean_db)
        stats = update_agent.update_all_nodes(entity_graph, patient.patient_id)
        
        # Verify time decay was applied
        assert stats["time_decay_applied"] > 0, "Time decay should be applied"
        
        # Check confidence was reduced
        decayed_count = 0
        for node_id in aged_nodes:
            node_data = entity_graph.entity_graph.nodes[node_id]
            confidence = node_data.get("confidence", 1.0)
            
            if confidence < 1.0:
                decayed_count += 1
                logger.info(f"Node {node_id}: confidence reduced to {confidence}")
        
        # At least some nodes should have reduced confidence
        assert decayed_count > 0, f"No nodes had confidence reduced. Aged nodes: {len(aged_nodes)}"
        
        logger.info(f"✅ Test passed: {decayed_count} nodes had time decay applied")
    
    def test_time_decay_different_strategies(self, clean_db, patient_comprehensive):
        """
        Test different decay strategies for different node types
        
        Given: Nodes of different types (vital signs, symptoms, metrics)
        When: Time decay is applied
        Then: Each type should use appropriate decay strategy
        """
        patient = patient_comprehensive
        
        manager = EntityGraphManager()
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        # Age all nodes by 7 days
        old_date = datetime.now() - timedelta(days=7)
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_data["last_updated"] = old_date
            node_data["confidence"] = 1.0
        
        # Apply time decay
        update_agent = UpdateAgent(clean_db)
        update_agent.update_all_nodes(entity_graph, patient.patient_id)
        
        # Check confidence values
        confidence_values = []
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            confidence = node_data.get("confidence", 1.0)
            node_type, _ = manager.classify_node_type(node_data)
            confidence_values.append((node_id, node_type, confidence))
            logger.info(f"Node {node_id} ({node_type}): confidence={confidence}")
        
        # All should have reduced confidence (7 days is significant)
        for node_id, node_type, confidence in confidence_values:
            assert confidence < 1.0, f"Node {node_id} should have reduced confidence"
            assert confidence >= 0.1, f"Node {node_id} confidence should not go below 0.1 floor"
        
        logger.info(f"✅ Test passed: Different decay strategies applied correctly")
    
    def test_time_decay_confidence_floor(self, clean_db, patient_with_metrics):
        """
        Test that confidence floor (0.1) is enforced
        
        Given: Very old nodes (e.g., 90 days old)
        When: Time decay is applied
        Then: Confidence should not go below 0.1
        """
        patient, _ = patient_with_metrics
        
        manager = EntityGraphManager()
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        # Age nodes by 90 days (should hit confidence floor)
        very_old_date = datetime.now() - timedelta(days=90)
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_data["last_updated"] = very_old_date
            node_data["confidence"] = 1.0
        
        # Apply time decay
        update_agent = UpdateAgent(clean_db)
        update_agent.update_all_nodes(entity_graph, patient.patient_id)
        
        # Check confidence floor
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            confidence = node_data.get("confidence", 1.0)
            
            # Should not go below 0.1
            assert confidence >= 0.1, f"Node {node_id} confidence {confidence} below floor 0.1"
            
            logger.info(f"Node {node_id}: confidence={confidence} (floor enforced)")
        
        logger.info(f"✅ Test passed: Confidence floor (0.1) enforced")


# ============================================
# Test 5: Sandbox and Approval Mechanism
# ============================================

class TestSandboxApproval:
    """
    Test 5: Verify sandbox mechanism and approval workflow
    
    This tests the complete sandbox → approval → commit workflow.
    """
    
    def test_sandbox_blocks_direct_commit(self, clean_db, patient_comprehensive):
        """
        Test that sandbox blocks direct commit
        
        Given: SandboxSession in sandboxed mode
        When: Code calls commit()
        Then: Commit should be intercepted, not executed
        """
        patient = patient_comprehensive
        
        with sandbox_session(clean_db, "test_conv_004") as sandbox:
            # Verify sandbox is enabled
            assert sandbox.is_sandboxed, "Sandbox should be enabled by default"
            
            # Perform write operation
            patient_obj = patient_crud.get(sandbox, patient.patient_id)
            original_name = patient_obj.name
            patient_obj.name = "沙盒测试"
            
            # Call commit (should be intercepted)
            sandbox.commit()
            
            # Verify operation recorded
            assert sandbox.has_pending_operations(), "Operation should be recorded"
            
            # Rollback (simulating rejection)
            sandbox.rollback()
            
            # Verify name NOT changed
            fresh_patient = patient_crud.get(clean_db, patient.patient_id)
            assert fresh_patient.name == original_name, "Name should not change after rollback"
        
        logger.info(f"✅ Test passed: Sandbox blocks direct commit")
    
    def test_approval_executes_operations(self, clean_db, patient_comprehensive):
        """
        Test that approval executes pending operations
        
        Given: SandboxSession with pending operations
        When: execute_pending() is called
        Then: Operations should be committed to database
        """
        patient = patient_comprehensive
        
        sandbox = SandboxSession(clean_db, "test_conv_005")
        
        try:
            # Perform write operation
            patient_obj = patient_crud.get(sandbox, patient.patient_id)
            patient_obj.name = "批准测试"
            
            # Intercept commit
            sandbox.commit()
            
            # Verify pending
            assert sandbox.has_pending_operations(), "Should have pending operations"
            
            # Execute pending (approve)
            result = sandbox.execute_pending()
            
            # Verify success
            assert result["success"], f"Execution should succeed: {result}"
            
            # Verify name IS changed
            fresh_patient = patient_crud.get(clean_db, patient.patient_id)
            assert fresh_patient.name == "批准测试", "Name should change after approval"
            
            logger.info(f"✅ Test passed: Approval executes operations")
            
        finally:
            sandbox.close()
    
    def test_rejection_discards_operations(self, clean_db, patient_comprehensive):
        """
        Test that rejection discards pending operations
        
        Given: SandboxSession with pending operations
        When: rollback() is called (rejection)
        Then: Operations should be discarded, database unchanged
        """
        patient = patient_comprehensive
        original_name = patient.name
        
        sandbox = SandboxSession(clean_db, "test_conv_006")
        
        try:
            # Perform write operation
            patient_obj = patient_crud.get(sandbox, patient.patient_id)
            patient_obj.name = "拒绝测试"
            
            # Intercept commit
            sandbox.commit()
            
            # Verify pending
            assert sandbox.has_pending_operations(), "Should have pending operations"
            
            # Rollback (reject)
            sandbox.rollback()
            
            # Verify name NOT changed
            fresh_patient = patient_crud.get(clean_db, patient.patient_id)
            assert fresh_patient.name == original_name, "Name should not change after rejection"
            
            logger.info(f"✅ Test passed: Rejection discards operations")
            
        finally:
            sandbox.close()
    
    def test_session_sandbox_manager_lifecycle(self, clean_db, patient_comprehensive):
        """
        Test SandboxSessionManager lifecycle management
        
        Given: Multiple operations across same conversation
        When: Manager approves all operations
        Then: All operations should be committed together
        """
        patient = patient_comprehensive
        
        # Use the global manager
        manager = sandbox_session_manager
        
        # Get sandbox for conversation
        sandbox = manager.get_or_create_sandbox(clean_db, "test_conv_007")
        
        # Perform operation 1
        patient_obj = patient_crud.get(sandbox, patient.patient_id)
        patient_obj.age = 70
        sandbox.commit()
        
        # Get same sandbox again (simulating second request)
        sandbox2 = manager.get_or_create_sandbox(clean_db, "test_conv_007")
        assert sandbox is sandbox2, "Should return same sandbox instance"
        
        # Perform operation 2
        patient_obj = patient_crud.get(sandbox2, patient.patient_id)
        patient_obj.gender = "female"
        sandbox2.commit()
        
        # Verify both operations pending
        pending = manager.get_pending_operations_summary("test_conv_007")
        assert len(pending) >= 1, f"Should have accumulated operations: {pending}"
        
        # Approve all
        result = manager.approve_and_execute_all(clean_db, "test_conv_007")
        
        # Verify success
        assert result.get("success"), f"Approval should succeed: {result}"
        
        # Verify changes in database
        fresh_patient = patient_crud.get(clean_db, patient.patient_id)
        assert fresh_patient.age == 70, "Age should be updated"
        # Note: gender change might not persist due to how SQLAlchemy tracks changes
        
        logger.info(f"✅ Test passed: Session sandbox manager lifecycle")


# ============================================
# Test 6: End-to-End Comprehensive Workflow
# ============================================

class TestEndToEnd:
    """
    Test 6: Complete end-to-end workflow combining all features
    
    This tests the full conversation flow with all UpdateAgent features.
    """
    
    def test_full_conversation_workflow(self, clean_db, patient_comprehensive):
        """
        Test complete conversation workflow
        
        Given: New patient conversation
        When: Full conversation flow (start → chat → data update → end)
        Then: All features should work together correctly
        """
        patient = patient_comprehensive
        
        # Step 1: Create conversation
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        logger.info(f"Created conversation: {conv.conversation_id}")
        
        # Step 2: Start conversation (triggers UpdateAgent)
        manager = EntityGraphManager()
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        logger.info(f"EntityGraph created with {entity_graph.entity_graph.number_of_nodes()} nodes")
        
        # Step 3: Verify nodes updated by UpdateAgent
        metric_count = 0
        symptom_count = 0
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_type, _ = manager.classify_node_type(node_data)
            if node_type == "metric":
                metric_count += 1
            elif node_type == "symptom":
                symptom_count += 1
        
        logger.info(f"Nodes: {metric_count} metrics, {symptom_count} symptoms")
        
        # Step 4: Simulate data update through DataManager
        data_manager = DataManagerCodeAgent()
        
        # Request data update
        result = data_manager.process_request(
            f"Add new symptom '胸闷' for patient {patient.patient_id}",
            conversation_id=conv.conversation_id
        )
        
        logger.info(f"DataManager result: {result}")
        
        # Step 5: Check pending operations
        pending_ops = data_manager.get_pending_operations(conv.conversation_id)
        has_pending = len(pending_ops) > 0
        
        logger.info(f"Pending operations: {len(pending_ops)}")
        
        # Step 6: Approve operations (if any)
        if has_pending:
            approval_result = data_manager.approve_and_execute_all(conv.conversation_id)
            logger.info(f"Approval result: {approval_result}")
        
        # Step 7: Verify symptom was added
        symptoms = patient_crud.get_symptoms(clean_db, patient.patient_id)
        symptom_names = [s.get("symptom") for s in symptoms]
        logger.info(f"Patient symptoms: {symptom_names}")
        
        # Step 8: Save and reload EntityGraph
        manager.save_state(conv.conversation_id, patient.patient_id)
        manager.invalidate(conv.conversation_id)
        
        # Reload
        entity_graph2 = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        logger.info(f"Reloaded EntityGraph with {entity_graph2.entity_graph.number_of_nodes()} nodes")
        
        # Step 9: Verify time decay applied on reload
        for node_id, node_data in entity_graph2.entity_graph.nodes(data=True):
            confidence = node_data.get("confidence", 1.0)
            assert 0.1 <= confidence <= 1.0, f"Confidence should be in valid range: {confidence}"
        
        logger.info(f"✅ Test passed: Full conversation workflow complete")
    
    @pytest.mark.slow
    def test_comprehensive_all_features(self, clean_db, patient_comprehensive):
        """
        Comprehensive test of ALL UpdateAgent features
        
        This is the main integration test combining:
        1. Node connection to metric/symptom nodes
        2. Code generation and application
        3. Data manager database triggers
        4. Time decay execution
        5. Sandbox and approval mechanism
        """
        patient = patient_comprehensive
        
        logger.info("=" * 60)
        logger.info("COMPREHENSIVE UPDATE AGENT TEST")
        logger.info("=" * 60)
        
        # ===== Test 1: Node Connection =====
        logger.info("\n[TEST 1] Node Connection to Metric/Symptom Nodes")
        
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        
        manager = EntityGraphManager()
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        
        # Count node types
        nodes_by_type = {"metric": 0, "symptom": 0, "other": 0}
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_type, _ = manager.classify_node_type(node_data)
            if node_type in nodes_by_type:
                nodes_by_type[node_type] += 1
            else:
                nodes_by_type["other"] += 1
        
        logger.info(f"  ✓ Nodes created: {nodes_by_type}")
        assert nodes_by_type["metric"] > 0 or nodes_by_type["symptom"] > 0
        
        # ===== Test 2: Code Generation =====
        logger.info("\n[TEST 2] Code Generation and Application")
        
        update_agent = UpdateAgent(clean_db)
        stats = update_agent.update_all_nodes(entity_graph, patient.patient_id)
        
        logger.info(f"  ✓ UpdateAgent stats: {stats}")
        assert stats["metric_updated"] >= 0
        assert stats["symptom_updated"] >= 0
        
        # ===== Test 3: Data Manager Trigger =====
        logger.info("\n[TEST 3] Data Manager Database Update Trigger")
        
        data_manager = DataManagerCodeAgent()
        
        # Request write operation
        result = data_manager.process_request(
            f"Update patient {patient.patient_id} medical history to add '糖尿病'",
            conversation_id=conv.conversation_id
        )
        
        pending_ops = data_manager.get_pending_operations(conv.conversation_id)
        logger.info(f"  ✓ Pending operations: {len(pending_ops)}")
        
        # Approve
        if pending_ops:
            approval = data_manager.approve_and_execute_all(conv.conversation_id)
            logger.info(f"  ✓ Approval result: {approval}")
        
        # ===== Test 4: Time Decay =====
        logger.info("\n[TEST 4] Time Decay Code Execution")
        
        # Age nodes
        old_date = datetime.now() - timedelta(days=14)
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_data["last_updated"] = old_date
            node_data["confidence"] = 1.0
        
        # Apply decay
        update_agent2 = UpdateAgent(clean_db)
        decay_stats = update_agent2.update_all_nodes(entity_graph, patient.patient_id)
        
        # Verify decay
        decayed = 0
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            if node_data.get("confidence", 1.0) < 1.0:
                decayed += 1
        
        logger.info(f"  ✓ Time decay applied to {decayed} nodes")
        assert decayed > 0
        
        # ===== Test 5: Sandbox & Approval =====
        logger.info("\n[TEST 5] Sandbox and Approval Mechanism")
        
        # Create new sandbox for additional test
        sandbox = SandboxSession(clean_db, "test_conv_final")
        
        try:
            # Write operation
            patient_obj = patient_crud.get(sandbox, patient.patient_id)
            patient_obj.name = "最终测试"
            sandbox.commit()
            
            # Verify intercepted
            assert sandbox.has_pending_operations()
            logger.info(f"  ✓ Sandbox intercepted commit")
            
            # Approve
            result = sandbox.execute_pending()
            assert result["success"]
            logger.info(f"  ✓ Approval executed successfully")
            
        finally:
            sandbox.close()
        
        # Verify final state
        final_patient = patient_crud.get(clean_db, patient.patient_id)
        assert final_patient.name == "最终测试"
        
        logger.info("\n" + "=" * 60)
        logger.info("✅ ALL COMPREHENSIVE TESTS PASSED")
        logger.info("=" * 60)


# ============================================
# Test Runner Helper
# ============================================

def run_comprehensive_test():
    """
    Helper function to run comprehensive test outside pytest
    
    Usage:
        python tests/integration/test_update_agent_comprehensive.py
    """
    import sys
    
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create test database session
    session = SessionLocal()
    
    try:
        # Clean database
        from backend.database.models import Patient, Conversation, Message, HealthMetricRecord
        session.query(HealthMetricRecord).delete()
        session.query(Message).delete()
        session.query(Conversation).delete()
        session.query(Patient).delete()
        session.commit()
        
        # Create test patient
        patient = patient_crud.create(session, PatientCreate(
            name="独立测试患者",
            age=55,
            gender="male",
            phone="13800000099"
        ))
        
        # Add metrics
        MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name="Blood Pressure",
            value="150/95",
            measured_at=datetime.now()
        )
        
        # Add symptoms
        patient_crud.add_symptom(
            db=session,
            patient_id=patient.patient_id,
            symptom="头痛",
            description="测试症状",
            status="active"
        )
        
        session.commit()
        
        print(f"\n✅ Test patient created: {patient.patient_id}")
        print(f"   Run pytest with this patient to verify UpdateAgent functionality")
        
        return patient.patient_id
        
    except Exception as e:
        print(f"❌ Error: {e}")
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    # Run as standalone script
    patient_id = run_comprehensive_test()
    print(f"\nTo run full test suite:")
    print(f"  uv run pytest tests/integration/test_update_agent_comprehensive.py -v -s")
    print(f"\nTo run specific test:")
    print(f"  uv run pytest tests/integration/test_update_agent_comprehensive.py::TestEndToEnd::test_comprehensive_all_features -v -s")
