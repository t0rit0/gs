"""
E2E Tests for Update Agent Full Workflow

These tests verify the complete workflow:
1. Create conversation → UpdateAgent updates nodes → Save state → Restore conversation

Requires valid LLM API configuration in config.yaml.
Run with: uv run pytest tests/e2e/test_update_agent_full_workflow.py -v -s
"""

import pytest
from datetime import datetime, timedelta

from backend.services.entity_graph_manager import entity_graph_manager, EntityGraphManager
from backend.services.metric_crud import MetricCRUD
from backend.database.crud import patient_crud, conversation_crud
from backend.database.schemas import PatientCreate, ConversationCreate
from backend.database.base import SessionLocal


@pytest.mark.e2e
@pytest.mark.slow
class TestUpdateAgentFullWorkflow:
    """End-to-end tests for complete UpdateAgent workflow"""
    
    @pytest.fixture
    def db_session(self):
        """Provide fresh database session"""
        session = SessionLocal()
        try:
            yield session
        finally:
            session.close()
    
    @pytest.fixture
    def patient_with_bp_record(self, db_session):
        """Create patient with blood pressure record"""
        patient = patient_crud.create(db_session, PatientCreate(
            name="E2E 测试患者",
            age=50,
            gender="male",
            phone="13800000000"
        ))
        
        # Create BP record 150/95
        MetricCRUD.create_record(
            db=db_session,
            patient_id=patient.patient_id,
            metric_name="Blood Pressure",
            value="150/95",
            measured_at=datetime.now()
        )
        
        db_session.commit()
        return patient
    
    @pytest.fixture
    def patient_with_symptom(self, db_session):
        """Create patient with symptom record"""
        patient = patient_crud.create(db_session, PatientCreate(
            name="E2E 症状患者",
            age=45,
            gender="female",
            phone="13900000000"
        ))
        
        # Add symptom "头痛" with status "active"
        patient_crud.add_symptom(
            db=db_session,
            patient_id=patient.patient_id,
            symptom="头痛",
            description="持续 5 天，中度疼痛",
            status="active"
        )
        
        db_session.commit()
        return patient
    
    def test_conversation_start_with_metric_update(self, db_session, patient_with_bp_record):
        """
        E2E Test: Conversation start triggers metric update
        
        Given: Patient has BP record 150/95
        When: New conversation starts
        Then: EntityGraph metric node should be updated to 150/95
        """
        # Create conversation
        conv = conversation_crud.create(db_session, ConversationCreate(
            patient_id=patient_with_bp_record.patient_id,
            target="Hypertension diagnosis",
            model_type="DrHyper"
        ))
        
        # Get or create EntityGraph (triggers UpdateAgent)
        manager = EntityGraphManager()
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient_with_bp_record.patient_id
        )
        
        # Assert: BP node should be updated to 150/95
        bp_node = entity_graph.entity_graph.nodes.get("metric_blood_pressure")
        if bp_node:
            assert bp_node["value"] == "150/95"
        else:
            # Node might have different ID, search by metric_name
            found_bp = False
            for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
                if node_data.get("metric_name") == "Blood Pressure":
                    assert node_data["value"] == "150/95"
                    found_bp = True
                    break
            assert found_bp, "Blood Pressure node not found"
    
    def test_full_conversation_with_symptom_update(self, db_session, patient_with_symptom):
        """
        E2E Test: Complete conversation with symptom update
        
        Given: Patient has symptom "头痛" with status "active"
        When: Conversation starts and UpdateAgent runs
        Then: Symptom node should be updated to status=2 (confirmed)
        """
        conv = conversation_crud.create(db_session, ConversationCreate(
            patient_id=patient_with_symptom.patient_id,
            target="Hypertension diagnosis",
            model_type="DrHyper"
        ))
        
        manager = EntityGraphManager()
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient_with_symptom.patient_id
        )
        
        # Find symptom node
        found_symptom = False
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            if "头痛" in node_data.get("name", "") or node_data.get("type") == "symptom":
                # Symptom should be updated to status=2 (confirmed)
                assert node_data["status"] == 2
                found_symptom = True
                break
        
        assert found_symptom, "Symptom node for 头痛 not found"
    
    def test_time_decay_applied_on_conversation_resume(self, db_session, patient_with_bp_record):
        """
        E2E Test: Time decay applied when resuming conversation
        
        Given: EntityGraph with 7-day-old nodes
        When: Conversation is resumed
        Then: All nodes should have time decay applied
        """
        conv = conversation_crud.create(db_session, ConversationCreate(
            patient_id=patient_with_bp_record.patient_id,
            target="Hypertension diagnosis",
            model_type="DrHyper"
        ))
        
        manager = EntityGraphManager()
        
        # First load (creates graph)
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient_with_bp_record.patient_id
        )
        
        # Manually age a node for testing
        old_date = datetime.now() - timedelta(days=7)
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_data["last_updated"] = old_date
            node_data["confidence"] = 1.0
            break
        
        # Save state
        manager.save_state(conv.conversation_id, patient_with_bp_record.patient_id)
        
        # Invalidate cache
        manager.invalidate(conv.conversation_id)
        
        # Reload (should apply time decay)
        entity_graph2 = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient_with_bp_record.patient_id
        )
        
        # Check that time decay was applied
        for node_id, node_data in entity_graph2.entity_graph.nodes(data=True):
            if "last_updated" in node_data:
                # Confidence should be reduced due to 7-day age
                assert node_data["confidence"] < 1.0
    
    def test_end_to_end_with_real_conversation(self, db_session, patient_with_bp_record):
        """
        E2E Test: Complete end-to-end workflow
        
        Given: Real patient and conversation
        When: Full conversation flow (create → update → save → restore)
        Then: All updates should be correctly persisted
        """
        # Step 1: Create conversation
        conv = conversation_crud.create(db_session, ConversationCreate(
            patient_id=patient_with_bp_record.patient_id,
            target="Hypertension diagnosis",
            model_type="DrHyper"
        ))
        
        manager = EntityGraphManager()
        
        # Step 2: Get or create (triggers UpdateAgent)
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient_with_bp_record.patient_id
        )
        
        # Step 3: Verify BP node updated
        found_bp = False
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            if node_data.get("metric_name") == "Blood Pressure":
                assert node_data["value"] == "150/95"
                found_bp = True
                break
        assert found_bp
        
        # Step 4: Save state
        manager.save_state(conv.conversation_id, patient_with_bp_record.patient_id)
        
        # Step 5: Invalidate cache
        manager.invalidate(conv.conversation_id)
        
        # Step 6: Restore from database
        entity_graph2 = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient_with_bp_record.patient_id
        )
        
        # Step 7: Verify restored node value
        for node_id, node_data in entity_graph2.entity_graph.nodes(data=True):
            if node_data.get("metric_name") == "Blood Pressure":
                assert node_data["value"] == "150/95"
                break
    
    def test_multiple_patients_concurrent_updates(self, db_session, patient_with_bp_record, patient_with_symptom):
        """
        E2E Test: Multiple patients with concurrent updates
        
        Given: Two patients with different metrics/symptoms
        When: Both start conversations
        Then: Each should have correct updates
        """
        # Create conversations for both patients
        conv1 = conversation_crud.create(db_session, ConversationCreate(
            patient_id=patient_with_bp_record.patient_id,
            target="Hypertension diagnosis",
            model_type="DrHyper"
        ))
        
        conv2 = conversation_crud.create(db_session, ConversationCreate(
            patient_id=patient_with_symptom.patient_id,
            target="Hypertension diagnosis",
            model_type="DrHyper"
        ))
        
        manager = EntityGraphManager()
        
        # Load both graphs
        eg1 = manager.get_or_create(conv1.conversation_id, patient_with_bp_record.patient_id)
        eg2 = manager.get_or_create(conv2.conversation_id, patient_with_symptom.patient_id)
        
        # Verify patient 1 has BP updated
        found_bp = False
        for node_id, node_data in eg1.entity_graph.nodes(data=True):
            if node_data.get("metric_name") == "Blood Pressure":
                assert node_data["value"] == "150/95"
                found_bp = True
                break
        assert found_bp
        
        # Verify patient 2 has symptom updated
        found_symptom = False
        for node_id, node_data in eg2.entity_graph.nodes(data=True):
            if "头痛" in node_data.get("name", ""):
                assert node_data["status"] == 2
                found_symptom = True
                break
        assert found_symptom
