"""
Time Decay Executor

Applies time-based confidence decay to EntityGraph nodes.

Supports multiple decay strategies:
- Exponential decay (for vital signs, lab metrics)
- Step decay (for symptoms)

Decay is applied based on node type and time since last update.
"""

from datetime import datetime, timedelta
from typing import Dict, Any, Optional
import logging

from drhyper.utils.logging import get_logger

logger = get_logger(__name__)


class TimeDecayExecutor:
    """
    Apply time-based confidence decay to EntityGraph nodes
    
    Decay strategies:
    - vital_signs: half_life=3 days, exponential (BP, Heart Rate)
    - lab_metabolism: half_life=30 days, exponential (Glucose, HbA1c)
    - symptom: half_life=7 days, step decay (0.8 per week)
    - default: half_life=14 days, exponential
    
    All strategies enforce a confidence floor of 0.1
    """
    
    # Decay strategy configuration
    VITAL_SIGNS_KEYWORDS = [
        "血压", "心率", "脉搏",
        "blood pressure", "bp", "heart rate", "pulse"
    ]
    
    LAB_METABOLISM_KEYWORDS = [
        "血糖", "糖化", "胆固醇", "甘油三酯",
        "glucose", "hba1c", "cholesterol", "triglyceride"
    ]
    
    CONFIDENCE_FLOOR = 0.1
    
    def __init__(self):
        """Initialize Time Decay Executor"""
        pass
    
    def apply_decay(
        self,
        entity_graph,
        node_id: str,
        node_type: str = "time_decay"
    ) -> float:
        """
        Apply time decay to a node's confidence
        
        Args:
            entity_graph: EntityGraph instance
            node_id: ID of node to apply decay to
            node_type: Type of node (metric/symptom/other)
        
        Returns:
            New confidence value after decay
        """
        node_data = entity_graph.entity_graph.nodes[node_id]
        
        # Get last update time
        last_updated = node_data.get("last_updated")
        if not last_updated:
            # No timestamp, use original confidence
            return node_data.get("confidence", 1.0)
        
        # Handle both datetime objects and ISO strings
        if isinstance(last_updated, str):
            try:
                last_updated = datetime.fromisoformat(last_updated)
            except (ValueError, TypeError):
                logger.warning(f"Invalid timestamp for node {node_id}: {last_updated}")
                return node_data.get("confidence", 1.0)
        
        # Calculate days since last update
        days_old = (datetime.now() - last_updated).days
        
        # Get current confidence
        current_confidence = node_data.get("confidence", 1.0)
        node_name = node_data.get("name", "")
        
        # Select and apply decay strategy
        if node_type == "metric":
            new_confidence = self._apply_metric_decay(
                current_confidence, days_old, node_name
            )
        elif node_type == "symptom":
            new_confidence = self._apply_symptom_decay(
                current_confidence, days_old
            )
        else:
            new_confidence = self._apply_default_decay(
                current_confidence, days_old
            )
        
        # Enforce confidence floor
        new_confidence = max(self.CONFIDENCE_FLOOR, new_confidence)
        
        # Update node confidence
        entity_graph.entity_graph.nodes[node_id]["confidence"] = new_confidence
        
        # Also update temporal_confidence and freshness if present
        if "temporal_confidence" in node_data:
            node_data["temporal_confidence"] = new_confidence
        if "freshness" in node_data:
            node_data["freshness"] = new_confidence
        
        logger.debug(
            f"Applied time decay to node {node_id}: "
            f"{current_confidence:.3f} → {new_confidence:.3f} ({days_old} days old)"
        )
        
        return new_confidence
    
    def _apply_metric_decay(
        self,
        confidence: float,
        days_old: int,
        node_name: str
    ) -> float:
        """
        Apply decay to metric node
        
        Args:
            confidence: Current confidence value
            days_old: Days since last update
            node_name: Name of the metric
        
        Returns:
            New confidence value
        """
        node_name_lower = node_name.lower() if node_name else ""
        
        # Check for vital signs (3-day half-life)
        if self._contains_keywords(node_name_lower, self.VITAL_SIGNS_KEYWORDS):
            half_life = 3
            new_confidence = confidence * (0.5 ** (days_old / half_life))
            logger.debug(f"Applying vital signs decay (half_life={half_life}d)")
        
        # Check for lab metabolism metrics (30-day half-life)
        elif self._contains_keywords(node_name_lower, self.LAB_METABOLISM_KEYWORDS):
            half_life = 30
            new_confidence = confidence * (0.5 ** (days_old / half_life))
            logger.debug(f"Applying lab metabolism decay (half_life={half_life}d)")
        
        # Default metric (14-day half-life)
        else:
            half_life = 14
            new_confidence = confidence * (0.5 ** (days_old / half_life))
            logger.debug(f"Applying default metric decay (half_life={half_life}d)")
        
        return new_confidence
    
    def _apply_symptom_decay(
        self,
        confidence: float,
        days_old: int
    ) -> float:
        """
        Apply step decay to symptom node
        
        Symptoms decay weekly: 0.8 per week
        
        Args:
            confidence: Current confidence value
            days_old: Days since last update
        
        Returns:
            New confidence value
        """
        weeks_old = days_old // 7
        new_confidence = confidence * (0.8 ** weeks_old)
        logger.debug(f"Applying symptom step decay (weeks={weeks_old})")
        return new_confidence
    
    def _apply_default_decay(
        self,
        confidence: float,
        days_old: int
    ) -> float:
        """
        Apply default exponential decay
        
        Default half-life: 14 days
        
        Args:
            confidence: Current confidence value
            days_old: Days since last update
        
        Returns:
            New confidence value
        """
        half_life = 14
        new_confidence = confidence * (0.5 ** (days_old / half_life))
        logger.debug(f"Applying default decay (half_life={half_life}d)")
        return new_confidence
    
    def _contains_keywords(
        self,
        text: str,
        keywords: list
    ) -> bool:
        """
        Check if text contains any of the keywords
        
        Args:
            text: Text to search
            keywords: List of keywords to match
        
        Returns:
            True if any keyword is found
        """
        for keyword in keywords:
            if keyword in text:
                return True
        return False
    
    def apply_decay_to_all_nodes(
        self,
        entity_graph
    ) -> Dict[str, float]:
        """
        Apply time decay to all nodes in EntityGraph
        
        Args:
            entity_graph: EntityGraph instance
        
        Returns:
            Dictionary mapping node_id to new confidence values
        """
        results = {}
        
        for node_id, node_data in entity_graph.entity_graph.nodes(data=True):
            # Classify node type
            from backend.services.node_type_matcher import NodeTypeMatcher
            node_type, _ = NodeTypeMatcher.classify_node(node_data)
            
            # Apply decay
            new_confidence = self.apply_decay(entity_graph, node_id, node_type)
            results[node_id] = new_confidence
        
        logger.info(f"Applied time decay to {len(results)} nodes")
        return results
