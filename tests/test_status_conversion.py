#!/usr/bin/env python
"""
Test Status Conversion Fix

Tests that string statuses from LLM are correctly converted to numeric values.
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

import networkx as nx
from backend.services.update_agent import UpdateAgent
from backend.database.base import SessionLocal


def test_status_conversion():
    """Test status string to numeric conversion"""
    print("=" * 70)
    print("TEST: Status Conversion")
    print("=" * 70)
    
    session = SessionLocal()
    
    try:
        # Create UpdateAgent
        update_agent = UpdateAgent(session)
        
        # Create mock entity graph
        class MockEntityGraph:
            def __init__(self):
                self.entity_graph = nx.DiGraph()
                self.entity_graph.add_node("test_node",
                    name="Blood Pressure",
                    value="",
                    status=0
                )
        
        mock_graph = MockEntityGraph()
        
        # Test cases: (input_status, expected_numeric)
        test_cases = [
            # High confidence (should map to 2)
            ("updated", 2),
            ("active", 2),
            ("confirmed", 2),
            ("verified", 2),
            ("high_confidence", 2),
            (2, 2),  # Already numeric
            
            # Low confidence (should map to 0 or 1)
            ("resolved", 0),
            ("inactive", 0),
            ("unconfirmed", 0),
            ("unknown", 0),
            ("no_data", 0),
            (0, 0),  # Already numeric
            
            # Unknown strings (should default to 1)
            ("random_string", 1),
            ("", 1),
        ]
        
        passed = 0
        failed = 0
        
        for input_status, expected in test_cases:
            # Reset node status
            mock_graph.entity_graph.nodes["test_node"]["status"] = 0
            
            # Create result dict
            result = {
                "updated": True,
                "node_value": "150/95",
                "node_status": input_status
            }
            
            # Apply result
            success = update_agent._apply_result_to_graph(
                mock_graph, "test_node", "metric", result
            )
            
            # Check status
            actual_status = mock_graph.entity_graph.nodes["test_node"]["status"]
            
            if actual_status == expected:
                print(f"  ✓ '{input_status}' → {actual_status} (expected {expected})")
                passed += 1
            else:
                print(f"  ✗ '{input_status}' → {actual_status} (expected {expected})")
                failed += 1
        
        print(f"\nResults: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("✅ TEST PASSED: All status conversions working correctly")
            return True
        else:
            print(f"❌ TEST FAILED: {failed} conversions failed")
            return False
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


def test_invalid_status_handling():
    """Test handling of invalid status values"""
    print("\n" + "=" * 70)
    print("TEST: Invalid Status Handling")
    print("=" * 70)
    
    session = SessionLocal()
    
    try:
        update_agent = UpdateAgent(session)
        
        class MockEntityGraph:
            def __init__(self):
                self.entity_graph = nx.DiGraph()
                self.entity_graph.add_node("test_node",
                    name="Test",
                    value="",
                    status=0
                )
        
        mock_graph = MockEntityGraph()
        
        # Test invalid status values (should default to 1)
        invalid_statuses = [3, -1, 100, 2.5, None]
        
        passed = 0
        failed = 0
        
        for invalid_status in invalid_statuses:
            # Reset node status
            mock_graph.entity_graph.nodes["test_node"]["status"] = 0
            
            result = {
                "updated": True,
                "node_value": "test",
                "node_status": invalid_status
            }
            
            # Apply result (should handle gracefully)
            try:
                success = update_agent._apply_result_to_graph(
                    mock_graph, "test_node", "metric", result
                )
                
                actual_status = mock_graph.entity_graph.nodes["test_node"]["status"]
                
                # Invalid statuses should default to 1
                if actual_status == 1:
                    print(f"  ✓ Invalid status {invalid_status} → defaulted to 1")
                    passed += 1
                else:
                    print(f"  ✗ Invalid status {invalid_status} → {actual_status} (expected 1)")
                    failed += 1
                    
            except Exception as e:
                print(f"  ✗ Invalid status {invalid_status} raised exception: {e}")
                failed += 1
        
        print(f"\nResults: {passed} passed, {failed} failed")
        
        if failed == 0:
            print("✅ TEST PASSED: Invalid status handling working correctly")
            return True
        else:
            print(f"❌ TEST FAILED: {failed} invalid status tests failed")
            return False
        
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        session.close()


def main():
    """Run all tests"""
    print("=" * 70)
    print("STATUS CONVERSION FIX TESTS")
    print("=" * 70)
    
    results = []
    
    # Test 1: Status conversion
    results.append(("Status Conversion", test_status_conversion()))
    
    # Test 2: Invalid status handling
    results.append(("Invalid Status Handling", test_invalid_status_handling()))
    
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
        print("\nThe status conversion fix is working correctly.")
        print("String statuses from LLM will be converted to numeric values.")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
