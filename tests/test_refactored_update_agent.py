#!/usr/bin/env python
"""
Test Refactored UpdateAgent

Tests the new UpdateAgent implementation with:
1. Result variable pattern (no direct entity_graph access)
2. Dynamic metric metadata
3. Async parallel updates
"""

import sys
import asyncio
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from sqlalchemy.orm import Session
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from backend.services.metric_crud import MetricCRUD
from backend.services.update_agent import UpdateAgent


def test_metric_metadata():
    """Test 1: Metric metadata retrieval"""
    print("=" * 70)
    print("TEST 1: Metric Metadata Retrieval")
    print("=" * 70)
    
    session = SessionLocal()
    
    try:
        # Create test patient
        patient = patient_crud.create(session, PatientCreate(
            name="Metadata 测试患者",
            age=50,
            gender="male",
            phone="13800000001"
        ))
        
        # Create multiple BP records
        now = datetime.now()
        for i in range(10):
            MetricCRUD.create_record(
                db=session,
                patient_id=patient.patient_id,
                metric_name="Blood Pressure",
                value=f"{140+i}/{90+i}",
                measured_at=now - timedelta(days=i),
                context="test reading"
            )
        
        # Create glucose records
        for i in range(5):
            MetricCRUD.create_record(
                db=session,
                patient_id=patient.patient_id,
                metric_name="Glucose",
                value=100 + i * 5,
                unit="mg/dL",
                measured_at=now - timedelta(days=i*7)
            )
        
        session.commit()
        
        # Test metadata retrieval
        bp_metadata = MetricCRUD.get_metric_metadata(session, patient.patient_id, "Blood Pressure")
        
        print(f"\n✓ Blood Pressure Metadata:")
        print(f"  Available: {bp_metadata['available']}")
        print(f"  Record count: {bp_metadata['record_count']}")
        print(f"  Date range: {bp_metadata['date_range']['earliest']} to {bp_metadata['date_range']['latest']}")
        print(f"  Available fields: {bp_metadata['available_fields']}")
        print(f"  Value types: {bp_metadata['value_types']}")
        
        assert bp_metadata['available'] == True
        assert bp_metadata['record_count'] == 10
        assert 'value_string' in bp_metadata['available_fields']
        
        # Test glucose metadata
        glucose_metadata = MetricCRUD.get_metric_metadata(session, patient.patient_id, "Glucose")
        print(f"\n✓ Glucose Metadata:")
        print(f"  Record count: {glucose_metadata['record_count']}")
        print(f"  Value types: {glucose_metadata['value_types']}")
        
        assert glucose_metadata['record_count'] == 5
        assert 'value_numeric' in glucose_metadata['available_fields']
        
        print("\n✅ TEST 1 PASSED: Metric metadata retrieval working")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


def test_result_variable_pattern():
    """Test 2: Result variable pattern (no direct entity_graph access)"""
    print("\n" + "=" * 70)
    print("TEST 2: Result Variable Pattern")
    print("=" * 70)
    
    session = SessionLocal()
    
    try:
        # Create test patient
        patient = patient_crud.create(session, PatientCreate(
            name="结果变量测试患者",
            age=55,
            gender="female",
            phone="13800000002"
        ))
        
        # Create BP record
        MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name="Blood Pressure",
            value="150/95",
            measured_at=datetime.now()
        )
        session.commit()
        
        # Create mock entity graph
        import networkx as nx
        
        class MockEntityGraph:
            def __init__(self):
                self.entity_graph = nx.DiGraph()
                self.entity_graph.add_node("test_bp_node",
                    name="Blood Pressure",
                    metric_name="Blood Pressure",
                    value="",
                    confidence=1.0
                )
        
        mock_graph = MockEntityGraph()
        
        # Create UpdateAgent
        update_agent = UpdateAgent(session)
        
        # Test update
        print(f"\n✓ Testing metric update with result variable pattern...")
        success = update_agent._update_metric_node(
            mock_graph,
            "test_bp_node",
            "Blood Pressure",
            patient.patient_id
        )
        
        # Verify result
        node_value = mock_graph.entity_graph.nodes["test_bp_node"].get("value")
        print(f"  Update success: {success}")
        print(f"  Node value: {node_value}")
        
        assert success == True, "Update should succeed"
        assert node_value == "150/95", f"Expected '150/95', got '{node_value}'"
        
        print("\n✅ TEST 2 PASSED: Result variable pattern working")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


async def test_async_parallel_updates():
    """Test 3: Async parallel node updates"""
    print("\n" + "=" * 70)
    print("TEST 3: Async Parallel Updates")
    print("=" * 70)
    
    session = SessionLocal()
    
    try:
        # Create test patient with multiple metrics
        patient = patient_crud.create(session, PatientCreate(
            name="异步更新测试患者",
            age=60,
            gender="male",
            phone="13800000003"
        ))
        
        now = datetime.now()
        
        # Create multiple metric records
        metrics = [
            ("Blood Pressure", "150/95"),
            ("Heart Rate", "78"),
            ("Glucose", "110"),
            ("Weight", "75"),
        ]
        
        for metric_name, value in metrics:
            MetricCRUD.create_record(
                db=session,
                patient_id=patient.patient_id,
                metric_name=metric_name,
                value=value,
                measured_at=now
            )
        
        session.commit()
        
        # Create mock entity graph with multiple nodes
        import networkx as nx
        
        class MockEntityGraph:
            def __init__(self):
                self.entity_graph = nx.DiGraph()
                for i, (metric_name, _) in enumerate(metrics):
                    node_id = f"node_{i}"
                    self.entity_graph.add_node(node_id,
                        name=metric_name,
                        metric_name=metric_name,
                        value="",
                        confidence=1.0
                    )
        
        mock_graph = MockEntityGraph()
        
        # Create UpdateAgent
        update_agent = UpdateAgent(session)
        
        # Test async parallel update
        print(f"\n✓ Testing async parallel update for {len(metrics)} nodes...")
        
        import time
        start_time = time.time()
        
        stats = await update_agent.update_all_nodes_async(
            mock_graph,
            patient.patient_id,
            max_concurrency=3
        )
        
        elapsed_time = time.time() - start_time
        
        print(f"  Elapsed time: {elapsed_time:.2f}s")
        print(f"  Metrics updated: {stats['metric_updated']}")
        print(f"  Time decay applied: {stats['time_decay_applied']}")
        
        # Verify all nodes were updated
        for i, (metric_name, expected_value) in enumerate(metrics):
            node_id = f"node_{i}"
            node_value = mock_graph.entity_graph.nodes[node_id].get("value")
            print(f"  {metric_name}: {node_value}")
            assert node_value == expected_value, f"Expected {expected_value}, got {node_value}"
        
        print("\n✅ TEST 3 PASSED: Async parallel updates working")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


def test_code_validation():
    """Test 4: Code validation (reject direct entity_graph access)"""
    print("\n" + "=" * 70)
    print("TEST 4: Code Validation")
    print("=" * 70)
    
    session = SessionLocal()
    
    try:
        update_agent = UpdateAgent(session)
        
        # Test 1: Code with return statement should be rejected
        bad_code_1 = """
result["updated"] = True
return
"""
        is_valid, error = update_agent._validate_code(bad_code_1, "test_node")
        print(f"\n✓ Code with 'return' rejected: {not is_valid}")
        assert not is_valid, "Code with return should be rejected"
        
        # Test 2: Code with direct entity_graph access should be rejected
        bad_code_2 = """
entity_graph.nodes[node_id]["value"] = "150/95"
result["updated"] = True
"""
        is_valid, error = update_agent._validate_code(bad_code_2, "test_node")
        print(f"✓ Code with direct entity_graph access rejected: {not is_valid}")
        assert not is_valid, "Code with direct entity_graph access should be rejected"
        
        # Test 3: Good code should be accepted
        good_code = """
record = MetricCRUD.get_latest_record(sandbox, patient_id, "Blood Pressure")
if record:
    result["node_value"] = record.value_string
    result["updated"] = True
else:
    result["updated"] = False
    result["reason"] = "No records found"
"""
        is_valid, error = update_agent._validate_code(good_code, "test_node")
        print(f"✓ Good code accepted: {is_valid}")
        assert is_valid, "Good code should be accepted"
        
        print("\n✅ TEST 4 PASSED: Code validation working")
        return True
        
    except Exception as e:
        print(f"\n❌ TEST 4 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


def main():
    """Run all tests"""
    print("=" * 70)
    print("REFACTORED UPDATEAGENT TESTS")
    print("=" * 70)
    
    results = []
    
    # Test 1: Metric metadata
    results.append(("Metric Metadata", test_metric_metadata()))
    
    # Test 2: Result variable pattern
    results.append(("Result Variable Pattern", test_result_variable_pattern()))
    
    # Test 3: Async parallel updates
    results.append(("Async Parallel Updates", asyncio.run(test_async_parallel_updates())))
    
    # Test 4: Code validation
    results.append(("Code Validation", test_code_validation()))
    
    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for test_name, passed in results:
        status = "✅ PASSED" if passed else "❌ FAILED"
        print(f"  {test_name}: {status}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
