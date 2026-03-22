#!/usr/bin/env python
"""
Update Agent Comprehensive Test Runner

This script provides a unified interface to run all UpdateAgent integration tests.
It supports running individual test categories or the complete test suite.

Features:
- Run all tests or specific test categories
- Real LLM API calls (no mocking)
- Real database operations
- Detailed logging and reporting
- Test result summary

Usage:
    # Run all tests
    uv run python tests/integration/run_update_agent_tests.py

    # Run specific test category
    uv run python tests/integration/run_update_agent_tests.py --category node_connection
    uv run python tests/integration/run_update_agent_tests.py --category code_generation
    uv run python tests/integration/run_update_agent_tests.py --category data_manager
    uv run python tests/integration/run_update_agent_tests.py --category time_decay
    uv run python tests/integration/run_update_agent_tests.py --category sandbox
    uv run python tests/integration/run_update_agent_tests.py --category end_to_end

    # Run with verbose output
    uv run python tests/integration/run_update_agent_tests.py --verbose

    # Run pytest directly with markers
    uv run pytest tests/integration/test_update_agent_comprehensive.py -v -s
"""

import argparse
import logging
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from backend.services.metric_crud import MetricCRUD
from backend.config.config_manager import get_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ============================================
# Test Categories
# ============================================

TEST_CATEGORIES = {
    "node_connection": {
        "class": "TestNodeConnection",
        "description": "Test node connection to metric/symptom nodes",
        "tests": [
            "test_metric_node_classification",
            "test_symptom_node_classification",
            "test_node_connection_with_update_agent"
        ]
    },
    "code_generation": {
        "class": "TestCodeGeneration",
        "description": "Test LLM code generation and application",
        "tests": [
            "test_metric_code_generation",
            "test_symptom_code_generation",
            "test_code_generation_retry_mechanism"
        ]
    },
    "data_manager": {
        "class": "TestDataManagerTrigger",
        "description": "Test data manager database update triggers",
        "tests": [
            "test_data_manager_write_operation",
            "test_sandbox_intercepts_commit",
            "test_operation_accumulation_across_requests"
        ]
    },
    "time_decay": {
        "class": "TestTimeDecay",
        "description": "Test time decay code execution",
        "tests": [
            "test_time_decay_application",
            "test_time_decay_different_strategies",
            "test_time_decay_confidence_floor"
        ]
    },
    "sandbox": {
        "class": "TestSandboxApproval",
        "description": "Test sandbox and approval mechanism",
        "tests": [
            "test_sandbox_blocks_direct_commit",
            "test_approval_executes_operations",
            "test_rejection_discards_operations",
            "test_session_sandbox_manager_lifecycle"
        ]
    },
    "end_to_end": {
        "class": "TestEndToEnd",
        "description": "End-to-end comprehensive workflow",
        "tests": [
            "test_full_conversation_workflow",
            "test_comprehensive_all_features"
        ]
    }
}


# ============================================
# Test Setup
# ============================================

def check_llm_config() -> bool:
    """
    Check if LLM configuration is valid
    
    Returns:
        True if configuration is valid, False otherwise
    """
    try:
        config = get_config()
        api_key = config.get_api_key()
        base_url = config.get_base_url()
        model = config.get_model()
        
        if not api_key or api_key == "your-api-key":
            logger.error("❌ LLM API key not configured in config.yaml")
            return False
        
        if not base_url:
            logger.error("❌ LLM base URL not configured in config.yaml")
            return False
        
        logger.info(f"✓ LLM configuration: model={model}, base_url={base_url}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error checking LLM config: {e}")
        return False


def setup_test_database() -> Session:
    """
    Setup clean test database
    
    Returns:
        Database session
    """
    logger.info("Setting up test database...")
    
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
        return session
        
    except Exception as e:
        logger.error(f"❌ Error setting up database: {e}")
        session.rollback()
        raise


def create_test_patient(session: Session) -> str:
    """
    Create comprehensive test patient
    
    Args:
        session: Database session
    
    Returns:
        Patient ID
    """
    logger.info("Creating test patient with metrics and symptoms...")
    
    # Create patient
    patient = patient_crud.create(session, PatientCreate(
        name="UpdateAgent 测试患者",
        age=55,
        gender="male",
        phone="13800000099",
        medical_history=[
            {
                "condition": "高血压",
                "diagnosis_date": "2024-01-15T00:00:00",
                "status": "chronic",
                "notes": "原发性高血压"
            }
        ]
    ))
    
    # Create metric records
    now = datetime.now()
    
    MetricCRUD.create_record(
        db=session,
        patient_id=patient.patient_id,
        metric_name="Blood Pressure",
        value="150/95",
        measured_at=now
    )
    
    MetricCRUD.create_record(
        db=session,
        patient_id=patient.patient_id,
        metric_name="Heart Rate",
        value="82",
        measured_at=now
    )
    
    MetricCRUD.create_record(
        db=session,
        patient_id=patient.patient_id,
        metric_name="Glucose",
        value="6.5",
        measured_at=now - timedelta(days=2)
    )
    
    # Add symptoms
    patient_crud.add_symptom(
        db=session,
        patient_id=patient.patient_id,
        symptom="头痛",
        description="持续 3 天，中度疼痛",
        status="active"
    )
    
    patient_crud.add_symptom(
        db=session,
        patient_id=patient.patient_id,
        symptom="头晕",
        description="偶尔发作",
        status="active"
    )
    
    session.commit()
    
    logger.info(f"✓ Test patient created: {patient.patient_id}")
    return patient.patient_id


# ============================================
# Test Runner
# ============================================

def run_pytest_tests(
    category: Optional[str] = None,
    test_name: Optional[str] = None,
    verbose: bool = False
) -> int:
    """
    Run tests using pytest
    
    Args:
        category: Test category to run (None = all)
        test_name: Specific test name (None = all in category)
        verbose: Enable verbose output
    
    Returns:
        Exit code (0 = success)
    """
    import subprocess
    
    # Build pytest command
    cmd = [
        "uv", "run", "pytest",
        "tests/integration/test_update_agent_comprehensive.py",
        "-v", "-s"  # Always verbose for integration tests
    ]
    
    # Add test selection
    if category:
        if category not in TEST_CATEGORIES:
            logger.error(f"Invalid category: {category}")
            logger.info(f"Valid categories: {list(TEST_CATEGORIES.keys())}")
            return 1
        
        class_name = TEST_CATEGORIES[category]["class"]
        
        if test_name:
            # Run specific test
            cmd.append(f"::Test{category.replace('_', '').title()}::{test_name}")
        else:
            # Run entire class
            cmd.append(f"::{class_name}")
    
    # Run pytest
    logger.info(f"Running: {' '.join(cmd)}")
    
    result = subprocess.run(cmd, cwd=project_root)
    
    return result.returncode


def print_test_summary(results: Dict[str, Any]) -> None:
    """
    Print test run summary
    
    Args:
        results: Test results dictionary
    """
    print("\n" + "=" * 70)
    print("TEST RUN SUMMARY")
    print("=" * 70)
    
    total = results.get("total", 0)
    passed = results.get("passed", 0)
    failed = results.get("failed", 0)
    skipped = results.get("skipped", 0)
    duration = results.get("duration", 0)
    
    print(f"Total tests:  {total}")
    print(f"Passed:       {passed} ✓")
    print(f"Failed:       {failed} {'✗' if failed > 0 else ''}")
    print(f"Skipped:      {skipped}")
    print(f"Duration:     {duration:.2f} seconds")
    
    if failed > 0:
        print(f"\n❌ SOME TESTS FAILED")
    else:
        print(f"\n✅ ALL TESTS PASSED")
    
    print("=" * 70)


# ============================================
# Main Entry Point
# ============================================

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Update Agent Comprehensive Test Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run all tests
  python run_update_agent_tests.py

  # Run specific category
  python run_update_agent_tests.py --category node_connection

  # Run specific test
  python run_update_agent_tests.py --category code_generation --test test_metric_code_generation

  # Run with custom config
  python run_update_agent_tests.py --config /path/to/config.yaml
        """
    )
    
    parser.add_argument(
        "--category", "-c",
        choices=list(TEST_CATEGORIES.keys()),
        help="Test category to run"
    )
    
    parser.add_argument(
        "--test", "-t",
        help="Specific test name to run"
    )
    
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose output"
    )
    
    parser.add_argument(
        "--config",
        help="Path to config.yaml file"
    )
    
    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Only setup test database, don't run tests"
    )
    
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available tests and exit"
    )
    
    args = parser.parse_args()
    
    # Set logging level
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # List tests
    if args.list:
        print("\nAvailable Test Categories:")
        print("-" * 70)
        
        for cat_name, cat_info in TEST_CATEGORIES.items():
            print(f"\n{cat_name}:")
            print(f"  Description: {cat_info['description']}")
            print(f"  Class: {cat_info['class']}")
            print(f"  Tests:")
            for test in cat_info["tests"]:
                print(f"    - {test}")
        
        print()
        return 0
    
    # Check LLM configuration
    logger.info("=" * 70)
    logger.info("UPDATE AGENT COMPREHENSIVE TEST SUITE")
    logger.info("=" * 70)
    
    if not check_llm_config():
        logger.error("\n❌ LLM configuration check failed.")
        logger.error("Please configure your LLM API in config.yaml")
        return 1
    
    # Setup database
    try:
        session = setup_test_database()
        
        # Create test patient
        patient_id = create_test_patient(session)
        logger.info(f"Test patient ID: {patient_id}")
        
        session.close()
        
    except Exception as e:
        logger.error(f"❌ Database setup failed: {e}")
        return 1
    
    # Setup only mode
    if args.setup_only:
        logger.info("\n✓ Database setup complete. Run pytest separately.")
        return 0
    
    # Run tests
    start_time = time.time()
    
    logger.info("\n" + "=" * 70)
    logger.info("RUNNING TESTS")
    logger.info("=" * 70)
    
    exit_code = run_pytest_tests(
        category=args.category,
        test_name=args.test,
        verbose=args.verbose
    )
    
    duration = time.time() - start_time
    
    # Print summary
    logger.info(f"\nTest run completed in {duration:.2f} seconds")
    
    if exit_code == 0:
        logger.info("✅ All tests passed!")
    else:
        logger.error("❌ Some tests failed. Check output above for details.")
    
    return exit_code


if __name__ == "__main__":
    from datetime import timedelta  # Import here to avoid circular dependency
    sys.exit(main())
