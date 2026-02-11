"""
Test Patient Information Preloading for Entity Graph

Tests the conversion of patient medical data into graph nodes that can be
pre-loaded into the EntityGraph before conversation starts.

Uses TDD approach: tests are written first, then implementation follows.
"""
import pytest
from datetime import datetime
from backend.database.models import Patient


@pytest.mark.unit
class TestPatientDataExtraction:
    """Test extraction of patient data into graph-compatible format"""

    def test_extract_basic_patient_info_to_nodes(self):
        """
        Test extracting basic patient info (age, gender) into graph nodes

        Expected: Should generate nodes for age and gender with proper structure
        """
        from drhyper.core.patient_loader import PatientDataExtractor

        patient_data = {
            "name": "张三",
            "age": 45,
            "gender": "male"
        }

        extractor = PatientDataExtractor()
        nodes = extractor.extract_patient_data(patient_data, target="高血压诊断")

        # Should have nodes for basic demographics
        assert len(nodes) > 0, "Should extract at least some nodes from patient data"

        # Check node structure
        for node in nodes:
            assert "id" in node, "Node should have an id"
            assert "name" in node, "Node should have a name"
            assert "description" in node, "Node should have a description"
            assert "value" in node, "Node should have a value"
            assert "confidential_level" in node, "Node should have confidence level"

    def test_extract_medical_history_to_nodes(self):
        """
        Test extracting medical history into graph nodes

        Expected: Should create nodes with condition names and diagnosis details
        """
        from drhyper.core.patient_loader import PatientDataExtractor

        patient_data = {
            "name": "李四",
            "medical_history": [
                {
                    "condition": "高血压",
                    "diagnosis_date": "2023-01-15T00:00:00",
                    "status": "chronic",
                    "notes": "确诊为原发性高血压"
                },
                {
                    "condition": "糖尿病",
                    "diagnosis_date": "2022-06-10T00:00:00",
                    "status": "chronic",
                    "notes": "2型糖尿病"
                }
            ]
        }

        extractor = PatientDataExtractor()
        nodes = extractor.extract_patient_data(patient_data, target="高血压诊断")

        # Should have nodes for medical history conditions
        condition_nodes = [n for n in nodes if "高血压" in n.get("name", "") or "糖尿病" in n.get("name", "")]
        assert len(condition_nodes) >= 2, "Should extract at least 2 medical history conditions"

        # Check that medical history nodes have higher confidence
        for node in condition_nodes:
            assert node["confidential_level"] >= 0.7, "Historical conditions should have high confidence"
            assert node["status"] == 2, "Historical conditions should be marked as accomplished"

    def test_extract_medications_to_nodes(self):
        """
        Test extracting medications into graph nodes

        Expected: Should create nodes for current medications with dosage info
        """
        from drhyper.core.patient_loader import PatientDataExtractor

        patient_data = {
            "name": "王五",
            "medications": [
                {
                    "medication_name": "氨氯地平",
                    "dosage": "5mg",
                    "frequency": "每日一次",
                    "start_date": "2023-01-15T00:00:00",
                    "notes": "降压药"
                }
            ]
        }

        extractor = PatientDataExtractor()
        nodes = extractor.extract_patient_data(patient_data, target="高血压诊断")

        # Should have medication node
        medication_nodes = [n for n in nodes if "氨氯地平" in n.get("name", "")]
        assert len(medication_nodes) >= 1, "Should extract medication information"

        # Check medication node contains dosage info
        med_node = medication_nodes[0]
        assert "5mg" in med_node.get("value", ""), "Medication value should contain dosage"
        assert med_node["confidential_level"] >= 0.7, "Current medications should have high confidence"

    def test_extract_health_metrics_to_nodes(self):
        """
        Test extracting health metrics into graph nodes

        Expected: Should create nodes for vital signs with numeric values
        """
        from drhyper.core.patient_loader import PatientDataExtractor

        patient_data = {
            "name": "赵六",
            "health_metrics": [
                {
                    "metric_name": "收缩压",
                    "value": 145,
                    "unit": "mmHg",
                    "recorded_at": "2026-01-27T09:00:00",
                    "notes": "早晨测量"
                },
                {
                    "metric_name": "舒张压",
                    "value": 90,
                    "unit": "mmHg",
                    "recorded_at": "2026-01-27T09:00:00",
                    "notes": "早晨测量"
                }
            ]
        }

        extractor = PatientDataExtractor()
        nodes = extractor.extract_patient_data(patient_data, target="高血压诊断")

        # Should have nodes for blood pressure metrics
        bp_nodes = [n for n in nodes if "血压" in n.get("name", "") or "BP" in n.get("name", "")]
        assert len(bp_nodes) >= 1, "Should extract blood pressure metrics"

        # Check that values include numeric data
        for node in bp_nodes:
            value = node.get("value", "")
            assert any(str(v) in value for v in [145, 90]), "BP values should contain numeric measurements"

    def test_extract_allergies_to_nodes(self):
        """
        Test extracting allergies into graph nodes

        Expected: Should create nodes with allergy information and severity
        """
        from drhyper.core.patient_loader import PatientDataExtractor

        patient_data = {
            "name": "孙七",
            "allergies": [
                {
                    "allergen": "青霉素",
                    "severity": "severe",
                    "reaction": "皮疹、呼吸困难",
                    "diagnosed_date": "2020-05-10T00:00:00"
                }
            ]
        }

        extractor = PatientDataExtractor()
        nodes = extractor.extract_patient_data(patient_data, target="高血压诊断")

        # Should have allergy node
        allergy_nodes = [n for n in nodes if "青霉素" in n.get("name", "")]
        assert len(allergy_nodes) >= 1, "Should extract allergy information"

        # Check severity is noted
        allergy_node = allergy_nodes[0]
        assert "severe" in allergy_node.get("value", "").lower() or "严重" in allergy_node.get("value", ""), \
            "Allergy node should indicate severity"


@pytest.mark.unit
class TestPatientDataIntegration:
    """Test integration of patient data into EntityGraph"""

    def test_preload_patient_data_to_graph(self):
        """
        Test preloading patient data into EntityGraph before conversation

        Expected: Graph should have pre-populated nodes from patient data
        """
        from drhyper.core.graph import EntityGraph
        from drhyper.core.patient_loader import PatientDataExtractor
        from unittest.mock import MagicMock

        # Create mock models (we don't want to call actual LLM in unit tests)
        mock_conv_model = MagicMock()
        mock_graph_model = MagicMock()

        patient_data = {
            "name": "测试患者",
            "age": 45,
            "gender": "male",
            "medical_history": [
                {
                    "condition": "高血压",
                    "diagnosis_date": "2023-01-15T00:00:00",
                    "status": "chronic"
                }
            ],
            "medications": [
                {
                    "medication_name": "氨氯地平",
                    "dosage": "5mg",
                    "frequency": "每日一次"
                }
            ]
        }

        # Create EntityGraph instance
        graph = EntityGraph(
            target="高血压诊断",
            graph_model=mock_graph_model,
            conv_model=mock_conv_model
        )

        # Extract patient data to nodes
        extractor = PatientDataExtractor()
        patient_nodes = extractor.extract_patient_data(patient_data, target="高血压诊断")

        # Preload nodes into graph
        result = graph.preload_patient_data(patient_nodes)

        assert result is True, "Preloading should succeed"
        assert graph.entity_graph.number_of_nodes() > 0, "Graph should have preloaded nodes"

        # Check that preloaded nodes have proper attributes
        for node_id, node_data in graph.entity_graph.nodes(data=True):
            if node_data.get("source") == "patient_record":
                assert "temporal_confidence" in node_data, "Preloaded nodes should have temporal_confidence"
                assert node_data["temporal_confidence"] >= 0.7, "Patient record data should have high confidence"
                assert node_data["status"] == 2, "Preloaded historical data should be marked as accomplished"

    def test_preloaded_nodes_have_correct_temporal_attributes(self):
        """
        Test that preloaded nodes have proper temporal attributes

        Expected: Preloaded nodes should have recorded_at timestamps and proper freshness
        """
        from drhyper.core.patient_loader import PatientDataExtractor
        from datetime import datetime, timedelta

        patient_data = {
            "name": "时间测试患者",
            "medical_history": [
                {
                    "condition": "高血压",
                    "diagnosis_date": "2023-01-15T00:00:00",
                    "status": "chronic"
                }
            ]
        }

        extractor = PatientDataExtractor()
        nodes = extractor.extract_patient_data(patient_data, target="高血压诊断")

        # Check temporal attributes on nodes
        for node in nodes:
            if node.get("source") == "patient_record":
                assert "extracted_at" in node, "Preloaded nodes should have extracted_at timestamp"
                assert "last_updated_at" in node, "Preloaded nodes should have last_updated_at"
                assert "original_confidential_level" in node, "Preloaded nodes should track original confidence"
                assert "freshness" in node, "Preloaded nodes should have freshness score"

                # Freshness should be based on data age
                # For very old records, freshness might be lower
                assert 0 <= node["freshness"] <= 1, "Freshness should be between 0 and 1"

    def test_preload_handles_empty_patient_data(self):
        """
        Test that preloading handles empty patient data gracefully

        Expected: Should not fail, just return empty node list
        """
        from drhyper.core.patient_loader import PatientDataExtractor

        extractor = PatientDataExtractor()
        nodes = extractor.extract_patient_data({}, target="高血压诊断")

        assert nodes == [], "Empty patient data should return empty node list"

    def test_preload_with_irrelevant_data(self):
        """
        Test that irrelevant data is filtered out during preloading

        Expected: Only relevant nodes should be extracted based on target
        """
        from drhyper.core.patient_loader import PatientDataExtractor

        patient_data = {
            "name": "患者",
            "medical_history": [
                {"condition": "高血压", "status": "chronic"},
                {"condition": "骨折", "status": "resolved"}  # Less relevant for hypertension diagnosis
            ],
            "health_metrics": [
                {"metric_name": "收缩压", "value": 145},
                {"metric_name": "视力", "value": 1.0}  # Less relevant
            ]
        }

        extractor = PatientDataExtractor()
        nodes = extractor.extract_patient_data(patient_data, target="高血压诊断")

        # Should still extract all data but mark relevance
        # The implementation can use relevance scores to prioritize
        assert len(nodes) > 0, "Should extract some relevant data"


@pytest.mark.integration
class TestPatientDataLoadingEndToEnd:
    """End-to-end tests for patient data loading in conversation"""

    def test_conversation_service_passes_patient_data(self, clean_db, patient_with_history):
        """
        Test that ConversationService passes patient data to EntityGraph

        Expected: When creating conversation, patient data should be preloaded
        """
        # This will be implemented after the basic functionality works
        # For now, it's a placeholder for integration testing
        pass

    def test_preloaded_data_survives_conversation_roundtrip(self, clean_db, patient_with_history):
        """
        Test that preloaded patient data persists through conversation save/load

        Expected: Nodes from patient records should be in drhyper_state
        """
        # This will be implemented after basic functionality
        pass
