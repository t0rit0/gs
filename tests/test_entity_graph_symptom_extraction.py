"""
Tests for EntityGraphManager Symptom Extraction

Tests the automatic symptom extraction from EntityGraph nodes.
"""
import pytest
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

from backend.services.entity_graph_manager import EntityGraphManager


class TestEntityGraphManagerSymptomExtraction:
    """Tests for symptom extraction in EntityGraphManager"""
    
    @pytest.fixture
    def manager(self):
        """Create EntityGraphManager instance"""
        return EntityGraphManager()
    
    @pytest.fixture
    def sample_graph_state(self):
        """Sample serialized graph state with symptom nodes"""
        return {
            "entity_graph": {
                "nodes": [
                    {
                        "id": "symptom_1",
                        "name": "头痛",
                        "description": "患者主诉头痛",
                        "value": "持续性钝痛",
                        "status": 2,
                        "extracted_at": datetime(2026, 3, 18, 14, 30),
                        "last_updated_at": datetime(2026, 3, 18, 14, 30)
                    },
                    {
                        "id": "symptom_2",
                        "name": "腹痛",
                        "description": "患者主诉腹痛",
                        "value": "饭后加重",
                        "status": 2,
                        "extracted_at": datetime(2026, 3, 18, 15, 0),
                        "last_updated_at": datetime(2026, 3, 18, 15, 0)
                    },
                    {
                        "id": "vital_1",
                        "name": "血压",
                        "description": "血压测量值",
                        "value": "145/92 mmHg",
                        "status": 2,
                        "extracted_at": datetime(2026, 3, 18, 14, 0),
                        "last_updated_at": datetime(2026, 3, 18, 14, 0)
                    },
                    {
                        "id": "symptom_3",
                        "name": "头晕",
                        "description": "患者主诉头晕",
                        "value": "",
                        "status": 1,
                        "extracted_at": datetime(2026, 3, 17, 10, 0),
                        "last_updated_at": None
                    }
                ],
                "links": [],
                "directed": True,
                "multigraph": False,
                "graph": {}
            },
            "relation_graph": {
                "nodes": [],
                "links": [],
                "directed": True,
                "multigraph": False,
                "graph": {}
            },
            "step": 0,
            "accomplish": False,
            "prev_node": None,
            "target": "Hypertension diagnosis"
        }
    
    def test_extract_symptoms_from_graph(self, manager, sample_graph_state):
        """Test symptom extraction from graph state"""
        symptoms = manager._extract_symptoms_from_graph(sample_graph_state)
        
        # Should extract 头痛，腹痛，头晕 (not 血压)
        assert len(symptoms) == 3
        
        symptom_names = [s["symptom"] for s in symptoms]
        assert "头痛" in symptom_names
        assert "腹痛" in symptom_names
        assert "头晕" in symptom_names
        assert "血压" not in symptom_names
    
    def test_extract_symptoms_correct_format(self, manager, sample_graph_state):
        """Test extracted symptoms have correct format"""
        symptoms = manager._extract_symptoms_from_graph(sample_graph_state)
        
        for symptom in symptoms:
            assert "timestamp" in symptom
            assert "symptom" in symptom
            assert "description" in symptom
            assert "status" in symptom
            assert "source" in symptom
            assert symptom["source"] == "conversation"
    
    def test_extract_symptoms_with_description(self, manager, sample_graph_state):
        """Test symptom description extraction"""
        symptoms = manager._extract_symptoms_from_graph(sample_graph_state)
        
        headache = next((s for s in symptoms if s["symptom"] == "头痛"), None)
        assert headache is not None
        assert headache["description"] == "持续性钝痛"
        
        abdominal = next((s for s in symptoms if s["symptom"] == "腹痛"), None)
        assert abdominal is not None
        assert abdominal["description"] == "饭后加重"
    
    def test_update_patient_symptoms_adds_new(self, manager):
        """Test updating patient symptoms adds new ones"""
        # Mock database session and patient
        mock_db = Mock()
        mock_patient = Mock()
        mock_patient.symptoms = []
        mock_patient.patient_id = "test-patient"
        
        new_symptoms = [
            {
                "timestamp": "2026-03-18T14:30:00",
                "symptom": "头痛",
                "description": "desc",
                "status": "active",
                "source": "conversation"
            }
        ]
        
        with patch('backend.services.entity_graph_manager.patient_crud') as mock_crud:
            mock_crud.get.return_value = mock_patient
            
            with patch('sqlalchemy.orm.attributes.flag_modified'):
                manager._update_patient_symptoms(mock_db, "test-patient", new_symptoms)
            
            # Verify symptom was added
            assert len(mock_patient.symptoms) == 1
            assert mock_patient.symptoms[0]["symptom"] == "头痛"
            
            # Verify database commit was called
            mock_db.commit.assert_called_once()
    
    def test_update_patient_symptoms_avoids_duplicates(self, manager):
        """Test that duplicate symptoms are not added"""
        mock_db = Mock()
        mock_patient = Mock()
        mock_patient.symptoms = [
            {
                "timestamp": "2026-03-18T14:30:00",
                "symptom": "头痛",
                "description": "desc",
                "status": "active",
                "source": "conversation"
            }
        ]
        
        # Try to add same symptom with same timestamp
        duplicate_symptoms = [
            {
                "timestamp": "2026-03-18T14:30:00",
                "symptom": "头痛",
                "description": "desc",
                "status": "active",
                "source": "conversation"
            }
        ]
        
        with patch('backend.services.entity_graph_manager.patient_crud') as mock_crud:
            mock_crud.get.return_value = mock_patient
            
            with patch('sqlalchemy.orm.attributes.flag_modified'):
                manager._update_patient_symptoms(mock_db, "test-patient", duplicate_symptoms)
            
            # Should still have only 1 symptom
            assert len(mock_patient.symptoms) == 1
    
    def test_update_patient_symptoms_merges_different_timestamps(self, manager):
        """Test that symptoms with different timestamps are both kept"""
        mock_db = Mock()
        mock_patient = Mock()
        mock_patient.symptoms = [
            {
                "timestamp": "2026-03-18T14:30:00",
                "symptom": "头痛",
                "description": "desc1",
                "status": "active",
                "source": "conversation"
            }
        ]
        
        # Add same symptom but different timestamp (e.g., symptom recurred)
        new_symptoms = [
            {
                "timestamp": "2026-03-19T10:00:00",
                "symptom": "头痛",
                "description": "desc2",
                "status": "active",
                "source": "conversation"
            }
        ]
        
        with patch('backend.services.entity_graph_manager.patient_crud') as mock_crud:
            mock_crud.get.return_value = mock_patient
            
            with patch('sqlalchemy.orm.attributes.flag_modified'):
                manager._update_patient_symptoms(mock_db, "test-patient", new_symptoms)
            
            # Should have 2 symptoms (different timestamps)
            assert len(mock_patient.symptoms) == 2
    
    def test_update_patient_symptoms_nonexistent_patient(self, manager):
        """Test updating symptoms for nonexistent patient"""
        mock_db = Mock()
        
        with patch('backend.services.entity_graph_manager.patient_crud') as mock_crud:
            mock_crud.get.return_value = None
            
            # Should not raise error
            manager._update_patient_symptoms(mock_db, "nonexistent", [])
    
    def test_extractor_initialized(self, manager):
        """Test that symptom extractor is initialized"""
        assert manager.symptom_extractor is not None
        
        # Should be keyword extractor by default
        from backend.services.symptom_extractor import KeywordSymptomExtractor
        assert isinstance(manager.symptom_extractor, KeywordSymptomExtractor)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
