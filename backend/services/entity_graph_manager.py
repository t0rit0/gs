"""
EntityGraphManager - Manages EntityGraph instances with cache and persistence

Features:
- LRU cache for active EntityGraph instances
- Database persistence for graph state
- Thread-safe operations
- Lazy loading and creation
"""

import logging
from typing import Optional, Dict, Any
from threading import Lock
import networkx as nx

from backend.database.base import SessionLocal
from backend.database.crud import conversation_crud
from drhyper.core.graph import EntityGraph
from drhyper.utils.llm_loader import load_chat_model
from drhyper.config.settings import ConfigManager as DrHyperConfig

logger = logging.getLogger(__name__)


class EntityGraphManager:
    """
    Manages EntityGraph instances with caching and persistence

    Uses conversation_id as key to retrieve/store EntityGraph instances.
    Graphs are cached in memory for performance and persisted to database
    for recovery across restarts.
    """

    def __init__(self, cache_size: int = 100):
        """
        Initialize EntityGraphManager

        Args:
            cache_size: Maximum number of EntityGraph instances to cache in memory
        """
        self.cache_size = cache_size
        self._cache: Dict[str, EntityGraph] = {}
        self._lock = Lock()
        logger.info(f"EntityGraphManager initialized (cache_size={cache_size})")

    def get_or_create(
        self,
        conversation_id: str,
        patient_id: str,
        target: str = "Hypertension diagnosis"
    ) -> Optional[EntityGraph]:
        """
        Get EntityGraph from cache or create if not exists

        Args:
            conversation_id: Conversation identifier
            patient_id: Patient identifier
            target: Diagnostic target

        Returns:
            EntityGraph instance or None if error occurs
        """
        with self._lock:
            # Check cache first
            if conversation_id in self._cache:
                logger.debug(f"EntityGraph cache hit: {conversation_id}")
                return self._cache[conversation_id]

            # Try to load from database
            try:
                entity_graph = self._load_from_database(conversation_id, patient_id, target)

                # Add to cache (evict oldest if cache is full)
                if len(self._cache) >= self.cache_size:
                    oldest_key = next(iter(self._cache))
                    del self._cache[oldest_key]
                    logger.debug(f"EntityGraph cache eviction: {oldest_key}")

                self._cache[conversation_id] = entity_graph
                logger.info(f"EntityGraph cached for conversation: {conversation_id}")

                return entity_graph

            except Exception as e:
                logger.error(f"Error creating/loading EntityGraph: {e}")
                return None

    def save_state(self, conversation_id: str) -> bool:
        """
        Save EntityGraph state to database

        Args:
            conversation_id: Conversation identifier

        Returns:
            True if saved successfully
        """
        with self._lock:
            if conversation_id not in self._cache:
                logger.warning(f"Cannot save: EntityGraph not in cache: {conversation_id}")
                return False

            entity_graph = self._cache[conversation_id]

            try:
                # Serialize EntityGraph state to dict
                state_dict = self._serialize_entity_graph(entity_graph)

                # Save to database
                with SessionLocal() as db:
                    conversation_crud.update_entity_graph_state(
                        db, conversation_id, state_dict
                    )

                logger.info(f"EntityGraph state saved to database: {conversation_id}")
                return True

            except Exception as e:
                logger.error(f"Error saving EntityGraph state: {e}")
                return False

    def invalidate(self, conversation_id: str) -> None:
        """
        Remove EntityGraph from cache (e.g., when conversation ends)

        Args:
            conversation_id: Conversation identifier
        """
        with self._lock:
            if conversation_id in self._cache:
                del self._cache[conversation_id]
                logger.info(f"EntityGraph removed from cache: {conversation_id}")

    def _load_from_database(
        self,
        conversation_id: str,
        patient_id: str,
        target: str
    ) -> EntityGraph:
        """
        Load EntityGraph from database or create new one

        Args:
            conversation_id: Conversation identifier
            patient_id: Patient identifier
            target: Diagnostic target

        Returns:
            EntityGraph instance
        """
        # Try to load from database
        with SessionLocal() as db:
            db_conv = conversation_crud.get(db, conversation_id)

            if db_conv and hasattr(db_conv, 'entity_graph_state') and db_conv.entity_graph_state:
                logger.info(f"Loading EntityGraph from database: {conversation_id}")
                return self._deserialize_entity_graph(
                    db_conv.entity_graph_state, patient_id, target
                )

        # Not in database - create new EntityGraph
        logger.info(f"Creating new EntityGraph for conversation: {conversation_id}")
        return self._create_entity_graph(conversation_id, patient_id, target)

    def _create_entity_graph(
        self,
        conversation_id: str,
        patient_id: str,
        target: str
    ) -> EntityGraph:
        """
        Create new EntityGraph instance

        Args:
            conversation_id: Conversation identifier
            patient_id: Patient identifier
            target: Diagnostic target

        Returns:
            Initialized EntityGraph instance
        """
        # Load DrHyper models
        drhyper_config = DrHyperConfig()

        conv_model = load_chat_model(
            provider=drhyper_config.conversation_llm.provider,
            model_name=drhyper_config.conversation_llm.model,
            api_key=drhyper_config.conversation_llm.api_key,
            base_url=drhyper_config.conversation_llm.base_url,
            temperature=drhyper_config.conversation_llm.temperature,
            max_tokens=drhyper_config.conversation_llm.max_tokens
        )

        graph_model = load_chat_model(
            provider=drhyper_config.graph_llm.provider,
            model_name=drhyper_config.graph_llm.model,
            api_key=drhyper_config.graph_llm.api_key,
            base_url=drhyper_config.graph_llm.base_url,
            temperature=drhyper_config.graph_llm.temperature,
            max_tokens=drhyper_config.graph_llm.max_tokens
        )

        # Create EntityGraph
        entity_graph = EntityGraph(
            target=target,
            graph_model=graph_model,
            conv_model=conv_model
        )

        # Load patient context
        from backend.services.patient_context_builder import PatientContextBuilder
        patient_context_builder = PatientContextBuilder()

        with SessionLocal() as db:
            patient_context = patient_context_builder.build(db, patient_id)

        # Convert to dict format expected by EntityGraph
        patient_context_dict = {
            "patient_id": patient_context.patient_id,
            "basic_info": patient_context.basic_info,
            "patient_text_records": patient_context.patient_text_records
        }

        # Initialize EntityGraph with patient context
        entity_graph.init(save=False, patient_context=patient_context_dict)

        logger.info(f"EntityGraph created and initialized for: {conversation_id}")

        return entity_graph

    def _serialize_entity_graph(self, entity_graph: EntityGraph) -> Dict[str, Any]:
        """
        Serialize EntityGraph to dict for database storage

        Args:
            entity_graph: EntityGraph instance

        Returns:
            Dict with serialized state
        """
        # Convert NetworkX graphs to node-link format
        entity_graph_data = nx.node_link_data(entity_graph.entity_graph)
        relation_graph_data = nx.node_link_data(entity_graph.relation_graph)

        return {
            "entity_graph": entity_graph_data,
            "relation_graph": relation_graph_data,
            "step": entity_graph.step,
            "accomplish": entity_graph.accomplish,
            "prev_node": entity_graph.prev_node,
            "target": entity_graph.target,
            "language": entity_graph.language
        }

    def _deserialize_entity_graph(
        self,
        state_dict: Dict[str, Any],
        patient_id: str,
        target: str
    ) -> EntityGraph:
        """
        Deserialize EntityGraph from database state

        Args:
            state_dict: Serialized state dict
            patient_id: Patient identifier
            target: Diagnostic target

        Returns:
            Restored EntityGraph instance
        """
        # Load DrHyper models
        drhyper_config = DrHyperConfig()

        conv_model = load_chat_model(
            provider=drhyper_config.conversation_llm.provider,
            model_name=drhyper_config.conversation_llm.model,
            api_key=drhyper_config.conversation_llm.api_key,
            base_url=drhyper_config.conversation_llm.base_url,
            temperature=drhyper_config.conversation_llm.temperature,
            max_tokens=drhyper_config.conversation_llm.max_tokens
        )

        graph_model = load_chat_model(
            provider=drhyper_config.graph_llm.provider,
            model_name=drhyper_config.graph_llm.model,
            api_key=drhyper_config.graph_llm.api_key,
            base_url=drhyper_config.graph_llm.base_url,
            temperature=drhyper_config.graph_llm.temperature,
            max_tokens=drhyper_config.graph_llm.max_tokens
        )

        # Create EntityGraph instance
        entity_graph = EntityGraph(
            target=target,
            graph_model=graph_model,
            conv_model=conv_model
        )

        # Restore graph structures
        entity_graph.entity_graph = nx.node_link_graph(state_dict["entity_graph"])
        entity_graph.relation_graph = nx.node_link_graph(state_dict["relation_graph"])
        entity_graph.step = state_dict.get("step", 0)
        entity_graph.accomplish = state_dict.get("accomplish", False)
        entity_graph.prev_node = state_dict.get("prev_node")
        entity_graph.language = state_dict.get("language", "English")

        logger.info(f"EntityGraph deserialized from database state")

        return entity_graph


# Singleton instance
entity_graph_manager = EntityGraphManager()
