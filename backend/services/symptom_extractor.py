"""
Symptom Extractor

Extracts symptom information from EntityGraph nodes.

Supports multiple extraction strategies through a plugin architecture:
- Keyword-based extraction (default)
- Type-based extraction (future)
- LLM-based extraction (future)
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime


class SymptomExtractor(ABC):
    """
    Abstract base class for symptom extractors
    
    Subclasses implement different strategies for identifying
    and extracting symptom information from EntityGraph nodes.
    """
    
    @abstractmethod
    def extract_symptoms(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract symptoms from graph nodes
        
        Args:
            nodes: List of node dictionaries from entity_graph["nodes"]
        
        Returns:
            List of symptom records, each containing:
            - timestamp: ISO format timestamp
            - symptom: Symptom name
            - description: Symptom description
            - status: active/resolved/chronic
            - source: conversation/manual
        """
        pass
    
    @abstractmethod
    def _is_symptom_node(self, node: Dict[str, Any]) -> bool:
        """
        Determine if a node represents a symptom
        
        Args:
            node: Graph node dictionary
        
        Returns:
            True if the node represents a symptom
        """
        pass
    
    def _extract_description(self, node: Dict[str, Any]) -> Optional[str]:
        """
        Extract symptom description from node
        
        Args:
            node: Graph node dictionary
        
        Returns:
            Description string or None
        """
        return node.get("value") or node.get("description")
    
    def _determine_status(self, node: Dict[str, Any]) -> str:
        """
        Determine symptom status from node status
        
        Args:
            node: Graph node dictionary
        
        Returns:
            Status string: "active", "resolved", or "chronic"
        """
        node_status = node.get("status", 0)
        
        # Map node status to symptom status
        # 0 = unconfirmed, 1 = suspected, 2 = confirmed
        if node_status == 2:
            return "active"
        elif node_status == 1:
            return "active"
        else:
            return "resolved"
    
    def _format_timestamp(self, node: Dict[str, Any]) -> str:
        """
        Extract and format timestamp from node
        
        Args:
            node: Graph node dictionary
        
        Returns:
            ISO format timestamp string
        """
        # Prefer last_updated_at, fall back to extracted_at
        ts = node.get("last_updated_at") or node.get("extracted_at")
        
        if ts:
            if isinstance(ts, datetime):
                return ts.isoformat()
            # Assume already ISO string
            return ts
        
        # Default to current time
        return datetime.now().isoformat()


class KeywordSymptomExtractor(SymptomExtractor):
    """
    Keyword-based symptom extractor
    
    Identifies symptom nodes by matching keywords in node name,
    description, and value fields.
    
    Supports:
    - Symptom keywords (头痛，腹痛，etc.)
    - Lifestyle keywords (抽烟，喝酒，etc.)
    - Custom keyword lists
    """
    
    # Default symptom keywords
    DEFAULT_SYMPTOM_KEYWORDS = [
        # Common symptoms
        "痛", "疼", "晕", "晕厥", "恶心", "呕吐", "乏力", "疲劳",
        "心悸", "胸闷", "气短", "呼吸困难", "咳嗽", "发热", "发烧",
        "腹痛", "肚子痛", "头痛", "头疼", "头晕", "胸痛",
        "水肿", "浮肿", "出血", "皮疹", "瘙痒",
        
        # Chronic conditions
        "高血压", "糖尿病", "高血脂", "冠心病",
        
        # Lifestyle factors (treated as symptoms)
        "抽烟", "吸烟", "喝酒", "饮酒", "熬夜",
    ]
    
    def __init__(self, keywords: Optional[List[str]] = None):
        """
        Initialize keyword extractor
        
        Args:
            keywords: Custom keyword list. If None, uses default list.
        """
        self.keywords = keywords or self.DEFAULT_SYMPTOM_KEYWORDS
    
    def _is_symptom_node(self, node: Dict[str, Any]) -> bool:
        """
        Check if node contains symptom keywords
        
        Searches in name, description, and value fields.
        
        Args:
            node: Graph node dictionary
        
        Returns:
            True if any keyword is found
        """
        name = node.get("name", "")
        description = node.get("description", "")
        value = node.get("value", "")
        
        # Combine all text for matching
        text_to_check = f"{name} {description} {value}".lower()
        
        for keyword in self.keywords:
            if keyword in text_to_check:
                return True
        
        return False
    
    def extract_symptoms(self, nodes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Extract all symptom nodes from graph
        
        Args:
            nodes: List of graph node dictionaries
        
        Returns:
            List of symptom records
        """
        symptoms = []
        
        for node in nodes:
            if self._is_symptom_node(node):
                symptom_record = {
                    "timestamp": self._format_timestamp(node),
                    "symptom": node.get("name", ""),
                    "description": self._extract_description(node),
                    "status": self._determine_status(node),
                    "source": "conversation"
                }
                symptoms.append(symptom_record)
        
        return symptoms


class SymptomExtractorFactory:
    """
    Factory for creating symptom extractors
    
    Supports multiple extraction strategies:
    - "keyword": Keyword-based extraction (default)
    - Custom extractors can be registered dynamically
    """
    
    _extractors = {
        "keyword": KeywordSymptomExtractor,
    }
    
    @classmethod
    def get_extractor(
        cls, 
        extractor_type: str = "keyword",
        **kwargs
    ) -> SymptomExtractor:
        """
        Get a symptom extractor instance
        
        Args:
            extractor_type: Type of extractor ("keyword", etc.)
            **kwargs: Arguments passed to extractor constructor
        
        Returns:
            SymptomExtractor instance
        
        Raises:
            ValueError: If extractor type is unknown
        """
        extractor_class = cls._extractors.get(extractor_type)
        if not extractor_class:
            raise ValueError(f"Unknown extractor type: {extractor_type}")
        return extractor_class(**kwargs)
    
    @classmethod
    def register_extractor(cls, name: str, extractor_class: type):
        """
        Register a new extractor type
        
        Args:
            name: Name to register the extractor under
            extractor_class: Extractor class (must inherit from SymptomExtractor)
        """
        cls._extractors[name] = extractor_class
