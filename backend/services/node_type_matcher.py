"""
Node Type Matcher

Classifies EntityGraph nodes into update strategies:
- metric: Health metric nodes (blood pressure, glucose, etc.)
- symptom: Symptom nodes (headache, fever, etc.)
- time_decay: Nodes that only need time decay (demographic, static info)

Classification priority:
1. node.type field → "health_metric" or "symptom"
2. node.metric_name field → metric node
3. node.name matches symptom keywords → symptom node
4. node.name matches metric keywords → metric node
5. Default → time_decay only
"""

from typing import Dict, Tuple, Optional, List


class NodeTypeMatcher:
    """
    Match EntityGraph nodes to update strategies
    
    Classifies nodes based on their type, metric_name, or name keywords.
    Returns a tuple of (node_type, metric_name) for update strategies.
    """
    
    # Symptom keywords (Chinese and English)
    SYMPTOM_KEYWORDS: List[str] = [
        # Common symptoms
        "痛", "疼", "晕", "恶心", "呕吐", "乏力", "疲劳",
        "心悸", "胸闷", "气短", "咳嗽", "发热", "发烧",
        "瘙痒", "皮疹", "水肿", "浮肿", "出血",
        
        # Chronic conditions (treated as symptoms)
        "高血压", "糖尿病", "高血脂", "冠心病",
        
        # Lifestyle factors (treated as symptoms)
        "吸烟", "抽烟", "喝酒", "饮酒", "熬夜",
        
        # English keywords
        "pain", "ache", "dizzy", "nausea", "vomiting", "fatigue",
        "palpitation", "cough", "fever", "itching",
    ]
    
    # Metric keywords (Chinese and English)
    METRIC_KEYWORDS: List[str] = [
        # Vital signs
        "血压", "心率", "血糖", "体重", "体温", "脉搏",
        
        # English keywords
        "blood pressure", "bp", "heart rate", "glucose", "weight",
        "temperature", "pulse",
        
        # Lab metrics
        "胆固醇", "甘油三酯", "血红蛋白", "白细胞",
        "cholesterol", "triglyceride", "hemoglobin",
    ]
    
    @classmethod
    def classify_node(cls, node_data: Dict[str, any]) -> Tuple[str, Optional[str]]:
        """
        Classify node and return (node_type, metric_name)
        
        Args:
            node_data: Dictionary containing node information from EntityGraph
        
        Returns:
            Tuple of:
            - node_type: "metric", "symptom", or "time_decay"
            - metric_name: Name of metric if applicable, None otherwise
        
        Classification priority:
        1. Check node.type field
        2. Check node.metric_name field
        3. Check node.name against symptom keywords
        4. Check node.name against metric keywords
        5. Default to time_decay
        """
        node_type_field = node_data.get("type", "")
        metric_name = node_data.get("metric_name", "")
        node_name = node_data.get("name", "")
        
        # Priority 1: Explicit type field
        if node_type_field in ("health_metric", "metric"):
            return ("metric", metric_name or node_name)
        
        if node_type_field == "symptom":
            return ("symptom", None)
        
        # Priority 2: metric_name field exists → metric node
        if metric_name:
            return ("metric", metric_name)
        
        # Priority 3: Check name against symptom keywords
        if cls._matches_keywords(node_name, cls.SYMPTOM_KEYWORDS):
            return ("symptom", None)
        
        # Priority 4: Check name against metric keywords
        if cls._matches_keywords(node_name, cls.METRIC_KEYWORDS):
            return ("metric", node_name)
        
        # Priority 5: Default to time_decay only
        return ("time_decay", None)
    
    @classmethod
    def _matches_keywords(cls, text: str, keywords: List[str]) -> bool:
        """
        Check if text contains any of the keywords
        
        Args:
            text: Text to search
            keywords: List of keywords to match
        
        Returns:
            True if any keyword is found in text
        """
        if not text:
            return False
        
        text_lower = text.lower()
        for keyword in keywords:
            if keyword.lower() in text_lower:
                return True
        return False
    
    @classmethod
    def is_metric_node(cls, node_data: Dict[str, any]) -> bool:
        """
        Check if node is a metric node
        
        Args:
            node_data: Node information dictionary
        
        Returns:
            True if node should be updated as a metric
        """
        node_type, _ = cls.classify_node(node_data)
        return node_type == "metric"
    
    @classmethod
    def is_symptom_node(cls, node_data: Dict[str, any]) -> bool:
        """
        Check if node is a symptom node
        
        Args:
            node_data: Node information dictionary
        
        Returns:
            True if node should be updated as a symptom
        """
        node_type, _ = cls.classify_node(node_data)
        return node_type == "symptom"
    
    @classmethod
    def needs_time_decay(cls, node_data: Dict[str, any]) -> bool:
        """
        Check if node needs time decay
        
        All nodes need time decay, but this returns True for nodes
        that ONLY need time decay (no database update).
        
        Args:
            node_data: Node information dictionary
        
        Returns:
            True if node only needs time decay
        """
        node_type, _ = cls.classify_node(node_data)
        return node_type == "time_decay"
