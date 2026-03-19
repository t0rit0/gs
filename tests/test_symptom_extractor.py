"""
Tests for Symptom Extractor

Tests the symptom extraction functionality from EntityGraph nodes.
"""
import pytest
from datetime import datetime
from typing import List, Dict, Any

from backend.services.symptom_extractor import (
    SymptomExtractor,
    KeywordSymptomExtractor,
    SymptomExtractorFactory
)


class TestSymptomExtractorAbstract:
    """Tests for the abstract base class"""
    
    def test_abstract_class_cannot_be_instantiated(self):
        """Abstract base class should not be instantiable"""
        with pytest.raises(TypeError):
            SymptomExtractor()


class TestKeywordSymptomExtractor:
    """Tests for keyword-based symptom extractor"""
    
    @pytest.fixture
    def extractor(self) -> KeywordSymptomExtractor:
        """Create a keyword extractor instance"""
        return KeywordSymptomExtractor()
    
    @pytest.fixture
    def sample_nodes(self) -> List[Dict[str, Any]]:
        """Sample graph nodes for testing"""
        return [
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
            },
            {
                "id": "habit_1",
                "name": "吸烟史",
                "description": "患者有吸烟习惯",
                "value": "每天 10 支",
                "status": 2,
                "extracted_at": datetime(2026, 3, 18, 14, 0),
                "last_updated_at": datetime(2026, 3, 18, 14, 0)
            },
            {
                "id": "lab_1",
                "name": "血糖",
                "description": "空腹血糖",
                "value": "6.5 mmol/L",
                "status": 2,
                "extracted_at": datetime(2026, 3, 18, 14, 0),
                "last_updated_at": datetime(2026, 3, 18, 14, 0)
            }
        ]
    
    def test_is_symptom_node_detects_symptom_keywords(self, extractor):
        """Test symptom node detection with keywords"""
        # Nodes with symptom keywords should be detected
        assert extractor._is_symptom_node({"name": "头痛", "value": ""}) is True
        assert extractor._is_symptom_node({"name": "腹痛", "value": ""}) is True
        assert extractor._is_symptom_node({"name": "头晕", "value": ""}) is True
        assert extractor._is_symptom_node({"name": "高血压", "value": ""}) is True
    
    def test_is_symptom_node_detects_lifestyle_keywords(self, extractor):
        """Test lifestyle keyword detection"""
        assert extractor._is_symptom_node({"name": "吸烟", "value": ""}) is True
        assert extractor._is_symptom_node({"name": "喝酒", "value": ""}) is True
        assert extractor._is_symptom_node({"name": "熬夜", "value": ""}) is True
    
    def test_is_symptom_node_checks_all_fields(self, extractor):
        """Test that all node fields are checked for keywords"""
        # Keyword in name
        assert extractor._is_symptom_node({
            "name": "头痛",
            "description": "",
            "value": ""
        }) is True
        
        # Keyword in description
        assert extractor._is_symptom_node({
            "name": "不适",
            "description": "患者主诉头痛",
            "value": ""
        }) is True
        
        # Keyword in value
        assert extractor._is_symptom_node({
            "name": "症状",
            "description": "",
            "value": "头痛"
        }) is True
    
    def test_is_symptom_node_rejects_non_symptoms(self, extractor):
        """Test that non-symptom nodes are rejected"""
        assert extractor._is_symptom_node({"name": "血压", "value": "145/92"}) is False
        assert extractor._is_symptom_node({"name": "血糖", "value": "6.5"}) is False
        assert extractor._is_symptom_node({"name": "心率", "value": "80"}) is False
        assert extractor._is_symptom_node({"name": "年龄", "value": "55"}) is False
    
    def test_extract_symptoms_extracts_correct_nodes(self, extractor, sample_nodes):
        """Test symptom extraction from graph nodes"""
        symptoms = extractor.extract_symptoms(sample_nodes)
        
        # Should extract symptoms, not vitals or labs
        assert len(symptoms) >= 3  # At least 头痛，腹痛，头晕
        
        # Check symptom names
        symptom_names = [s["symptom"] for s in symptoms]
        assert "头痛" in symptom_names
        assert "腹痛" in symptom_names
        assert "头晕" in symptom_names
        
        # Should NOT include non-symptoms
        assert "血压" not in symptom_names
        assert "血糖" not in symptom_names
    
    def test_extract_symptoms_correct_timestamp(self, extractor, sample_nodes):
        """Test timestamp extraction"""
        symptoms = extractor.extract_symptoms(sample_nodes)
        
        headache = next((s for s in symptoms if s["symptom"] == "头痛"), None)
        assert headache is not None
        assert "timestamp" in headache
        assert "2026-03-18" in headache["timestamp"]
    
    def test_extract_symptoms_uses_last_updated_at(self, extractor, sample_nodes):
        """Test that last_updated_at is preferred over extracted_at"""
        symptoms = extractor.extract_symptoms(sample_nodes)
        
        # Find 头晕 which has last_updated_at = None
        dizziness = next((s for s in symptoms if s["symptom"] == "头晕"), None)
        assert dizziness is not None
        # Should fall back to extracted_at
        assert "2026-03-17" in dizziness["timestamp"]
    
    def test_extract_symptoms_correct_description(self, extractor, sample_nodes):
        """Test description extraction"""
        symptoms = extractor.extract_symptoms(sample_nodes)
        
        headache = next((s for s in symptoms if s["symptom"] == "头痛"), None)
        assert headache is not None
        assert headache["description"] == "持续性钝痛"
        
        abdominal = next((s for s in symptoms if s["symptom"] == "腹痛"), None)
        assert abdominal is not None
        assert abdominal["description"] == "饭后加重"
    
    def test_extract_symptoms_correct_status(self, extractor, sample_nodes):
        """Test status mapping from node status"""
        symptoms = extractor.extract_symptoms(sample_nodes)
        
        # status=2 (confirmed) -> "active"
        headache = next((s for s in symptoms if s["symptom"] == "头痛"), None)
        assert headache is not None
        assert headache["status"] == "active"
        
        # status=1 (suspected) -> "active"
        dizziness = next((s for s in symptoms if s["symptom"] == "头晕"), None)
        assert dizziness is not None
        assert dizziness["status"] == "active"
    
    def test_extract_symptoms_source_is_conversation(self, extractor, sample_nodes):
        """Test that source is set to 'conversation'"""
        symptoms = extractor.extract_symptoms(sample_nodes)
        
        for symptom in symptoms:
            assert symptom["source"] == "conversation"
    
    def test_custom_keywords(self):
        """Test custom keyword list"""
        custom_keywords = ["custom_symptom", "special_condition"]
        extractor = KeywordSymptomExtractor(keywords=custom_keywords)
        
        assert extractor._is_symptom_node({"name": "custom_symptom", "value": ""}) is True
        assert extractor._is_symptom_node({"name": "头痛", "value": ""}) is False  # Not in custom list


class TestSymptomExtractorFactory:
    """Tests for the extractor factory"""
    
    def test_get_keyword_extractor(self):
        """Test getting keyword extractor"""
        extractor = SymptomExtractorFactory.get_extractor("keyword")
        assert isinstance(extractor, KeywordSymptomExtractor)
    
    def test_get_extractor_with_custom_keywords(self):
        """Test getting extractor with custom keywords"""
        extractor = SymptomExtractorFactory.get_extractor(
            "keyword", 
            keywords=["custom"]
        )
        assert isinstance(extractor, KeywordSymptomExtractor)
        assert "custom" in extractor.keywords
    
    def test_get_unknown_extractor_raises_error(self):
        """Test that unknown extractor type raises error"""
        with pytest.raises(ValueError, match="Unknown extractor type"):
            SymptomExtractorFactory.get_extractor("unknown_type")
    
    def test_register_custom_extractor(self):
        """Test registering a custom extractor"""
        class CustomExtractor(SymptomExtractor):
            def extract_symptoms(self, nodes):
                return []
            
            def _is_symptom_node(self, node):
                return False
        
        # Register
        SymptomExtractorFactory.register_extractor("custom", CustomExtractor)
        
        # Get and verify
        extractor = SymptomExtractorFactory.get_extractor("custom")
        assert isinstance(extractor, CustomExtractor)
        
        # Clean up
        del SymptomExtractorFactory._extractors["custom"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
