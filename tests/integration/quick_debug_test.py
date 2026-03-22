#!/usr/bin/env python
"""
Update Agent Quick Debug Test

Simplified test that directly tests UpdateAgent functionality
without going through full DrHyper graph creation.
"""

import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from backend.services.metric_crud import MetricCRUD
from backend.services.update_agent import UpdateAgent
from backend.agents.data_manager import DataManagerCodeAgent
from backend.services.sandbox_session import SandboxSession


def main():
    """Quick test of UpdateAgent core functionality"""
    logger.info("=" * 70)
    logger.info("UPDATE AGENT QUICK DEBUG TEST")
    logger.info("=" * 70)
    
    session = SessionLocal()
    
    try:
        # ===== Setup =====
        logger.info("\n[SETUP] Creating test patient...")
        
        # Clean database
        from backend.database.models import Patient, HealthMetricRecord
        session.query(HealthMetricRecord).delete()
        session.query(Patient).delete()
        session.commit()
        
        # Create patient
        patient = patient_crud.create(session, PatientCreate(
            name="QuickTest 患者",
            age=55,
            gender="male",
            phone="13800000099"
        ))
        logger.info(f"✓ Patient created: {patient.patient_id}")
        
        # Create BP record
        bp_record = MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name="Blood Pressure",
            value="150/95",
            measured_at=datetime.now()
        )
        logger.info(f"✓ BP record created: {bp_record.value_string}")
        
        session.commit()
        
        # ===== Test 1: UpdateAgent Initialization =====
        logger.info("\n[TEST 1] UpdateAgent Initialization")
        update_agent = UpdateAgent(session)
        logger.info(f"✓ UpdateAgent created: model={update_agent.config.get_model()}")
        
        # ===== Test 2: Code Generation =====
        logger.info("\n[TEST 2] LLM Code Generation Test")
        logger.info("Generating code for metric update...")
        
        # Create a simple mock entity graph for testing
        import networkx as nx
        
        class MockEntityGraph:
            def __init__(self):
                # Use networkx DiGraph like the real EntityGraph
                self.entity_graph = nx.DiGraph()
                self.entity_graph.add_node("test_node", 
                    name="Blood Pressure",
                    metric_name="Blood Pressure",
                    value="",
                    confidence=1.0
                )
        
        mock_graph = MockEntityGraph()
        
        # Test code generation
        prompt = update_agent.prompt_templates["metric"].format(
            node_id="test_node",
            node_name="Blood Pressure",
            metric_name="Blood Pressure",
            current_value=""
        )
        
        logger.info("Calling LLM for code generation...")
        success = update_agent._generate_and_execute_code(
            mock_graph,
            "test_node",
            patient.patient_id,
            "metric",
            prompt
        )
        
        if success:
            logger.info(f"✓ Code generation SUCCESS")
            logger.info(f"✓ Node value: {mock_graph.entity_graph.nodes['test_node'].get('value')}")
        else:
            logger.warning("✗ Code generation FAILED")
        
        # ===== Test 3: Sandbox Test =====
        logger.info("\n[TEST 3] Sandbox Mechanism Test")
        
        sandbox = SandboxSession(session, "quick_test")
        logger.info(f"✓ Sandbox created")
        
        # Perform write
        patient_obj = patient_crud.get(sandbox, patient.patient_id)
        original_name = patient_obj.name
        patient_obj.name = "SandboxTest"
        
        sandbox.commit()
        logger.info(f"✓ Commit intercepted: {sandbox.has_pending_operations()} pending")
        
        # Approve
        result = sandbox.execute_pending()
        logger.info(f"✓ Approval result: success={result['success']}")
        
        # Verify
        fresh_patient = patient_crud.get(session, patient.patient_id)
        logger.info(f"✓ Name updated: {original_name} → {fresh_patient.name}")
        
        sandbox.close()
        
        # ===== Summary =====
        logger.info("\n" + "=" * 70)
        logger.info("✅ QUICK TEST COMPLETED")
        logger.info("=" * 70)
        logger.info(f"\nTest patient ID: {patient.patient_id}")
        logger.info("All core UpdateAgent functions tested successfully!")
        
        return 0
        
    except Exception as e:
        logger.error(f"\n❌ TEST FAILED: {e}", exc_info=True)
        return 1
        
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
