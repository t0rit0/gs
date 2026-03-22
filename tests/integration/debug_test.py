#!/usr/bin/env python
"""
Update Agent Debug Test Script

Runs a simplified version of the comprehensive test with detailed debugging output.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud, conversation_crud
from backend.database.schemas import PatientCreate, ConversationCreate
from backend.services.metric_crud import MetricCRUD
from backend.services.entity_graph_manager import EntityGraphManager
from backend.services.update_agent import UpdateAgent
from backend.agents.data_manager import DataManagerCodeAgent
from backend.services.sandbox_session import SandboxSession
from backend.services.session_sandbox_manager import sandbox_session_manager


def setup_test_data():
    """Setup test database with patient, metrics, and symptoms"""
    logger.info("=" * 70)
    logger.info("STEP 1: Setting up test database")
    logger.info("=" * 70)
    
    session = SessionLocal()
    
    try:
        # Clean existing data
        from backend.database.models import Patient, Conversation, Message, HealthMetricRecord
        session.query(HealthMetricRecord).delete()
        session.query(Message).delete()
        session.query(Conversation).delete()
        session.query(Patient).delete()
        session.commit()
        logger.info("✓ Database cleaned")
        
        # Create patient
        patient = patient_crud.create(session, PatientCreate(
            name="Debug 测试患者",
            age=55,
            gender="male",
            phone="13800000099"
        ))
        logger.info(f"✓ Patient created: {patient.patient_id}")
        
        # Create metric records
        now = datetime.now()
        
        bp_record = MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name="Blood Pressure",
            value="150/95",
            measured_at=now
        )
        logger.info(f"✓ BP record created: {bp_record.value_string}")
        
        hr_record = MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name="Heart Rate",
            value="82",
            measured_at=now
        )
        logger.info(f"✓ Heart Rate record created: {hr_record.value_string}")
        
        # Add symptoms
        patient_crud.add_symptom(
            db=session,
            patient_id=patient.patient_id,
            symptom="头痛",
            description="持续 3 天，中度疼痛",
            status="active"
        )
        logger.info("✓ Symptom 头痛 added")
        
        session.commit()
        logger.info("✓ Test data setup complete")
        
        return session, patient
        
    except Exception as e:
        logger.error(f"❌ Error setting up test data: {e}", exc_info=True)
        session.rollback()
        raise


def test_node_connection(session, patient):
    """Test 1: Node connection to metric/symptom nodes"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 2: Testing Node Connection")
    logger.info("=" * 70)
    
    try:
        # Create conversation
        conv = conversation_crud.create(session, ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        logger.info(f"✓ Conversation created: {conv.conversation_id}")
        
        # Get EntityGraph
        manager = EntityGraphManager()
        logger.info("Creating EntityGraph...")
        entity_graph = manager.get_or_create(
            conversation_id=conv.conversation_id,
            patient_id=patient.patient_id
        )
        logger.info(f"✓ EntityGraph created with {entity_graph.entity_graph.number_of_nodes()} nodes")
        
        # Analyze nodes
        nodes_by_type = {"metric": 0, "symptom": 0, "other": 0}
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_type, metric_name = manager.classify_node_type(node_data)
            if node_type in nodes_by_type:
                nodes_by_type[node_type] += 1
            
            if node_type == "metric":
                logger.debug(f"  Metric node: {node_id}, metric_name={metric_name}, value={node_data.get('value')}")
            elif node_type == "symptom":
                logger.debug(f"  Symptom node: {node_id}, name={node_data.get('name')}, status={node_data.get('status')}")
        
        logger.info(f"✓ Node classification: {nodes_by_type}")
        
        # Verify nodes exist
        assert nodes_by_type["metric"] > 0 or nodes_by_type["symptom"] > 0, "No metric or symptom nodes found"
        logger.info("✅ Test 1 PASSED: Node connection working")
        
        return session, patient, entity_graph, conv.conversation_id
        
    except Exception as e:
        logger.error(f"❌ Test 1 FAILED: {e}", exc_info=True)
        raise


def test_update_agent(session, patient, entity_graph, conversation_id):
    """Test 2: UpdateAgent code generation and application"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 3: Testing UpdateAgent Code Generation")
    logger.info("=" * 70)
    
    try:
        # Create UpdateAgent
        update_agent = UpdateAgent(session)
        logger.info(f"✓ UpdateAgent created: {update_agent}")
        
        # Run update
        logger.info("Running UpdateAgent.update_all_nodes()...")
        stats = update_agent.update_all_nodes(entity_graph, patient.patient_id)
        
        logger.info(f"✓ UpdateAgent stats: {stats}")
        
        # Verify updates
        assert stats["metric_updated"] >= 0, "Metric update count should be non-negative"
        assert stats["symptom_updated"] >= 0, "Symptom update count should be non-negative"
        assert stats["time_decay_applied"] > 0, "Time decay should be applied"
        
        logger.info("✅ Test 2 PASSED: UpdateAgent code generation working")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ Test 2 FAILED: {e}", exc_info=True)
        raise


def test_data_manager(session, patient, conversation_id):
    """Test 3: DataManager database update trigger"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 4: Testing DataManager Database Trigger")
    logger.info("=" * 70)
    
    try:
        # Create DataManager
        data_manager = DataManagerCodeAgent()
        logger.info(f"✓ DataManager created: {data_manager}")
        
        # Request write operation
        user_request = f"Update patient {patient.patient_id} name to 'DataManager 测试'"
        logger.info(f"Request: {user_request}")
        
        result = data_manager.process_request(user_request, conversation_id=conversation_id)
        logger.info(f"DataManager result: {result}")
        
        # Check pending operations
        pending_ops = data_manager.get_pending_operations(conversation_id)
        logger.info(f"Pending operations: {len(pending_ops)}")
        
        if pending_ops:
            logger.info(f"Operations: {pending_ops}")
            
            # Approve
            approval_result = data_manager.approve_and_execute_all(conversation_id)
            logger.info(f"Approval result: {approval_result}")
            
            # Verify update
            fresh_patient = patient_crud.get(session, patient.patient_id)
            logger.info(f"Patient name after approval: {fresh_patient.name}")
            
            assert fresh_patient.name == "DataManager 测试", "Name should be updated after approval"
        
        logger.info("✅ Test 3 PASSED: DataManager trigger working")
        
    except Exception as e:
        logger.error(f"❌ Test 3 FAILED: {e}", exc_info=True)
        raise


def test_time_decay(session, patient, entity_graph, conversation_id):
    """Test 4: Time decay code execution"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 5: Testing Time Decay")
    logger.info("=" * 70)
    
    try:
        # Age nodes
        old_date = datetime.now() - timedelta(days=10)
        logger.info(f"Aging nodes by 10 days: {old_date}")
        
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            node_data["last_updated"] = old_date
            node_data["confidence"] = 1.0
        
        # Apply time decay
        update_agent2 = UpdateAgent(session)
        logger.info("Applying time decay...")
        decay_stats = update_agent2.update_all_nodes(entity_graph, patient.patient_id)
        
        # Check results
        decayed_count = 0
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            confidence = node_data.get("confidence", 1.0)
            if confidence < 1.0:
                decayed_count += 1
                logger.debug(f"  Node {node_id}: confidence={confidence:.4f}")
        
        logger.info(f"✓ Time decay applied to {decayed_count} nodes")
        
        # Verify confidence floor
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            confidence = node_data.get("confidence", 1.0)
            assert 0.1 <= confidence <= 1.0, f"Confidence {confidence} out of range"
        
        logger.info("✅ Test 4 PASSED: Time decay working")
        
    except Exception as e:
        logger.error(f"❌ Test 4 FAILED: {e}", exc_info=True)
        raise


def test_sandbox_approval(session, patient):
    """Test 5: Sandbox and approval mechanism"""
    logger.info("\n" + "=" * 70)
    logger.info("STEP 6: Testing Sandbox and Approval")
    logger.info("=" * 70)
    
    try:
        # Create sandbox
        sandbox = SandboxSession(session, "test_sandbox_debug")
        logger.info(f"✓ Sandbox created: {sandbox}")
        
        # Perform write operation
        patient_obj = patient_crud.get(sandbox, patient.patient_id)
        original_name = patient_obj.name
        logger.info(f"Original name: {original_name}")
        
        patient_obj.name = "Sandbox 测试"
        logger.info("Modified name to 'Sandbox 测试'")
        
        # Commit (should be intercepted)
        sandbox.commit()
        logger.info("Called sandbox.commit()")
        
        # Check pending
        assert sandbox.has_pending_operations(), "Should have pending operations"
        pending_ops = sandbox.get_pending_operations()
        logger.info(f"✓ Pending operations: {len(pending_ops)}")
        
        # Execute pending (approve)
        result = sandbox.execute_pending()
        logger.info(f"Execute result: {result}")
        
        assert result["success"], f"Execution should succeed: {result}"
        
        # Verify update
        fresh_patient = patient_crud.get(session, patient.patient_id)
        logger.info(f"Final name: {fresh_patient.name}")
        
        assert fresh_patient.name == "Sandbox 测试", "Name should be updated"
        
        sandbox.close()
        logger.info("✅ Test 5 PASSED: Sandbox and approval working")
        
    except Exception as e:
        logger.error(f"❌ Test 5 FAILED: {e}", exc_info=True)
        raise
        raise


def main():
    """Main test runner"""
    logger.info("\n" + "=" * 70)
    logger.info("UPDATE AGENT DEBUG TEST - Starting")
    logger.info("=" * 70)
    
    session = None
    try:
        # Setup
        session, patient = setup_test_data()
        
        # Test 1: Node Connection
        session, patient, entity_graph, conv_id = test_node_connection(session, patient)
        
        # Test 2: UpdateAgent
        test_update_agent(session, patient, entity_graph, conv_id)
        
        # Test 3: DataManager
        test_data_manager(session, patient, conv_id)
        
        # Test 4: Time Decay
        test_time_decay(session, patient, entity_graph, conv_id)
        
        # Test 5: Sandbox
        test_sandbox_approval(session, patient)
        
        # Summary
        logger.info("\n" + "=" * 70)
        logger.info("✅ ALL DEBUG TESTS PASSED!")
        logger.info("=" * 70)
        logger.info(f"\nTest patient ID: {patient.patient_id}")
        logger.info("You can use this ID to verify database changes manually.")
        
        return 0
        
    except Exception as e:
        logger.error("\n" + "=" * 70)
        logger.error(f"❌ DEBUG TEST FAILED: {e}")
        logger.error("=" * 70)
        logger.error("\nCheck the detailed logs above for the error.")
        return 1
        
    finally:
        if session:
            session.close()


if __name__ == "__main__":
    sys.exit(main())
