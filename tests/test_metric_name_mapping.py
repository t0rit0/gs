#!/usr/bin/env python
"""
Test Metric Name Mapping Fix

Tests the metric name normalization feature that maps DrHyper node names
to database metric names.
"""

import sys
from pathlib import Path

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


def test_metric_name_mapping():
    """Test 1: Metric name mapping"""
    print("=" * 70)
    print("TEST 1: Metric Name Mapping")
    print("=" * 70)
    
    session = SessionLocal()
    
    try:
        # Create UpdateAgent (we'll use it for mapping only)
        update_agent = UpdateAgent(session)
        
        # Test cases: (DrHyper name, expected DB name)
        test_cases = [
            # Blood Pressure variants
            ("systolic blood pressure", "Systolic BP"),
            ("systolic", "Systolic BP"),
            ("systolic bp", "Systolic BP"),
            ("diastolic blood pressure", "Diastolic BP"),
            ("diastolic", "Diastolic BP"),
            ("blood pressure", "Blood Pressure"),
            ("bp", "Blood Pressure"),
            
            # Heart Rate
            ("heart rate", "Heart Rate"),
            ("hr", "Heart Rate"),
            ("pulse", "Heart Rate"),
            
            # Glucose
            ("glucose", "Glucose"),
            ("blood glucose", "Glucose"),
            ("blood sugar", "Glucose"),
            
            # Weight and BMI
            ("weight", "Weight"),
            ("body weight", "Weight"),
            ("bmi", "BMI"),
            ("body mass index", "BMI"),
            
            # Cholesterol
            ("total cholesterol", "Total Cholesterol"),
            ("ldl", "LDL Cholesterol"),
            ("hdl cholesterol", "HDL Cholesterol"),
            ("triglycerides", "Triglycerides"),
            
            # Lab values
            ("hba1c", "HbA1c"),
            ("creatinine", "Creatinine"),
            ("egfr", "eGFR"),
            
            # Abstract nodes (should be detected)
            ("Number of elevated readings", None),  # Abstract
            ("Time period of measurements", None),  # Abstract
            ("count of readings", None),  # Abstract
        ]
        
        passed = 0
        failed = 0
        
        for drhyper_name, expected_db_name in test_cases:
            normalized, is_abstract = update_agent._normalize_metric_name(drhyper_name)
            
            if expected_db_name is None:
                # Expected to be abstract
                if is_abstract:
                    print(f"  ✓ {drhyper_name} -> [Abstract]")
                    passed += 1
                else:
                    print(f"  ✗ {drhyper_name} -> {normalized} (expected abstract)")
                    failed += 1
            else:
                # Expected to map to specific DB name
                if normalized == expected_db_name:
                    print(f"  ✓ {drhyper_name} -> {normalized}")
                    passed += 1
                else:
                    print(f"  ✗ {drhyper_name} -> {normalized} (expected {expected_db_name})")
                    failed += 1
        
        print(f"\nResults: {passed} passed, {failed} failed")
        
        # Should have >90% accuracy
        accuracy = passed / len(test_cases)
        if accuracy >= 0.9:
            print(f"✅ TEST 1 PASSED: Mapping accuracy = {accuracy:.1%}")
            return True
        else:
            print(f"❌ TEST 1 FAILED: Mapping accuracy = {accuracy:.1%} (< 90%)")
            return False
        
    except Exception as e:
        print(f"\n❌ TEST 1 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


def test_abstract_node_detection():
    """Test 2: Abstract node detection"""
    print("\n" + "=" * 70)
    print("TEST 2: Abstract Node Detection")
    print("=" * 70)
    
    session = SessionLocal()
    
    try:
        update_agent = UpdateAgent(session)
        
        # Abstract node patterns
        abstract_nodes = [
            "Number of elevated blood pressure readings",
            "Time period of blood pressure measurements",
            "Count of high glucose readings",
            "Frequency of medication intake",
            "Duration of symptoms",
            "Trend of blood pressure",
            "Pattern of heart rate variability",
            "Current medications affecting blood pressure",
            "Medication compliance rate",
            "Lifestyle factors",
            "Risk factors for cardiovascular disease",
        ]
        
        # Non-abstract nodes (should NOT be detected as abstract)
        non_abstract_nodes = [
            "Blood Pressure",
            "Heart Rate",
            "Glucose",
            "Systolic BP",
            "Diastolic BP",
        ]
        
        passed = 0
        failed = 0
        
        # Test abstract nodes
        print("\nTesting abstract nodes:")
        for node_name in abstract_nodes:
            is_abstract = update_agent._is_abstract_node(node_name)
            if is_abstract:
                print(f"  ✓ {node_name} -> [Abstract]")
                passed += 1
            else:
                print(f"  ✗ {node_name} -> [Not Abstract] (expected abstract)")
                failed += 1
        
        # Test non-abstract nodes
        print("\nTesting non-abstract nodes:")
        for node_name in non_abstract_nodes:
            is_abstract = update_agent._is_abstract_node(node_name)
            if not is_abstract:
                print(f"  ✓ {node_name} -> [Metric]")
                passed += 1
            else:
                print(f"  ✗ {node_name} -> [Abstract] (expected metric)")
                failed += 1
        
        print(f"\nResults: {passed} passed, {failed} failed")
        
        if failed == 0:
            print(f"✅ TEST 2 PASSED: All abstract nodes correctly identified")
            return True
        else:
            print(f"❌ TEST 2 FAILED: {failed} misclassified")
            return False
        
    except Exception as e:
        print(f"\n❌ TEST 2 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


def test_end_to_end_with_mapping():
    """Test 3: End-to-end update with name mapping"""
    print("\n" + "=" * 70)
    print("TEST 3: End-to-End Update with Name Mapping")
    print("=" * 70)
    
    session = SessionLocal()
    
    try:
        # Create test patient with various metrics
        patient = patient_crud.create(session, PatientCreate(
            name="名称映射测试患者",
            age=55,
            gender="male",
            phone="13800000001"
        ))
        
        # Create metric records using DATABASE names
        now = __import__('datetime').datetime.now()
        metrics_to_create = [
            ("Systolic BP", "145"),
            ("Diastolic BP", "92"),
            ("Blood Pressure", "145/92"),
            ("Heart Rate", "78"),
            ("Glucose", "110"),
            ("Weight", "75"),
            ("BMI", "26.5"),
        ]
        
        for metric_name, value in metrics_to_create:
            MetricCRUD.create_record(
                db=session,
                patient_id=patient.patient_id,
                metric_name=metric_name,
                value=value,
                measured_at=now
            )
        
        session.commit()
        print(f"✓ Created patient with {len(metrics_to_create)} metric records")
        
        # Create mock entity graph with DrHyper node names
        import networkx as nx
        
        class MockEntityGraph:
            def __init__(self):
                self.entity_graph = nx.DiGraph()
                
                # Add nodes with DrHyper names (NOT database names)
                drhyper_nodes = [
                    ("node_systolic", "systolic blood pressure"),
                    ("node_diastolic", "diastolic blood pressure"),
                    ("node_bp", "blood pressure"),
                    ("node_hr", "heart rate"),
                    ("node_glucose", "glucose"),
                    ("node_weight", "weight"),
                    ("node_bmi", "bmi"),
                    ("node_abstract", "Number of elevated readings"),
                ]
                
                for node_id, node_name in drhyper_nodes:
                    self.entity_graph.add_node(node_id,
                        name=node_name,
                        metric_name=node_name,
                        value="",
                        confidence=1.0
                    )
        
        mock_graph = MockEntityGraph()
        
        # Create UpdateAgent and test update
        update_agent = UpdateAgent(session)
        
        print("\n✓ Testing updates with DrHyper node names...")
        
        # Test each node
        results = {}
        for node_id, node_data in mock_graph.entity_graph.nodes(data=True):
            node_name = node_data.get("name", "")
            metric_name = node_name  # In real scenario, this comes from DrHyper
            
            # Normalize name
            normalized, is_abstract = update_agent._normalize_metric_name(metric_name)
            
            if is_abstract:
                print(f"  - {node_id} ({node_name}) -> [Abstract, skipping]")
                results[node_id] = "abstract"
            else:
                print(f"  - {node_id} ({node_name}) -> {normalized}")
                
                # Try to get record
                record = MetricCRUD.get_latest_record(session, patient.patient_id, normalized)
                if record:
                    print(f"      Found: {record.value_string}")
                    results[node_id] = "success"
                else:
                    print(f"      No records found")
                    results[node_id] = "no_records"
        
        # Count results
        success_count = sum(1 for v in results.values() if v == "success")
        abstract_count = sum(1 for v in results.values() if v == "abstract")
        no_records_count = sum(1 for v in results.values() if v == "no_records")
        
        print(f"\nResults:")
        print(f"  Success: {success_count}")
        print(f"  Abstract (skipped): {abstract_count}")
        print(f"  No records: {no_records_count}")
        
        # Should have at least 6 successful mappings
        if success_count >= 6:
            print(f"\n✅ TEST 3 PASSED: {success_count} nodes successfully mapped and updated")
            return True
        else:
            print(f"\n❌ TEST 3 FAILED: Only {success_count} nodes mapped successfully")
            return False
        
    except Exception as e:
        print(f"\n❌ TEST 3 FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


def main():
    """Run all tests"""
    print("=" * 70)
    print("METRIC NAME MAPPING FIX TESTS")
    print("=" * 70)
    
    results = []
    
    # Test 1: Metric name mapping
    results.append(("Metric Name Mapping", test_metric_name_mapping()))
    
    # Test 2: Abstract node detection
    results.append(("Abstract Node Detection", test_abstract_node_detection()))
    
    # Test 3: End-to-end with mapping
    results.append(("End-to-End with Mapping", test_end_to_end_with_mapping()))
    
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
        print("\nThe metric name mapping fix is working correctly.")
        print("DrHyper node names will now be mapped to database metric names.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
