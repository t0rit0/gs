"""
EntityGraphManager - Manages EntityGraph instances with cache and persistence

Features:
- LRU cache for active EntityGraph instances
- Database persistence for graph state
- Thread-safe operations
- Lazy loading and creation
- Automatic symptom extraction from graph nodes
"""

import logging
from typing import Optional, Dict, Any, List
from threading import Lock
from datetime import datetime
import networkx as nx

from backend.database.base import SessionLocal
from backend.database.crud import conversation_crud, patient_crud
from drhyper.core.graph import EntityGraph
from drhyper.utils.llm_loader import load_chat_model
from drhyper.config.settings import ConfigManager as DrHyperConfig
from backend.config.config_manager import get_config
from backend.services.symptom_extractor import SymptomExtractorFactory
from backend.services.time_decay_executor import TimeDecayExecutor

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
        # Initialize symptom extractor
        self.symptom_extractor = SymptomExtractorFactory.get_extractor("keyword")
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

    def save_state(self, conversation_id: str, patient_id: str = None) -> bool:
        """
        Save EntityGraph state to database and extract symptoms to Patient

        Args:
            conversation_id: Conversation identifier
            patient_id: Patient identifier (optional, for symptom extraction)

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

                # Extract symptoms from graph
                symptoms = self._extract_symptoms_from_graph(state_dict)

                # Save to database
                with SessionLocal() as db:
                    # 1. Update conversation's entity_graph_state
                    conversation_crud.update_entity_graph_state(
                        db, conversation_id, state_dict
                    )

                    # 2. Update patient's symptoms if patient_id provided
                    if patient_id and symptoms:
                        self._update_patient_symptoms(db, patient_id, symptoms)
                    elif patient_id:
                        logger.debug(f"No symptoms to extract for conversation: {conversation_id}")

                logger.info(f"EntityGraph state saved with {len(symptoms)} symptoms extracted")
                return True

            except Exception as e:
                logger.error(f"Error saving EntityGraph state: {e}")
                return False

    def _extract_symptoms_from_graph(self, state_dict: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Extract symptoms from serialized graph state

        Args:
            state_dict: Serialized EntityGraph state

        Returns:
            List of symptom records
        """
        nodes = state_dict.get("entity_graph", {}).get("nodes", [])
        return self.symptom_extractor.extract_symptoms(nodes)

    def _update_patient_symptoms(
        self,
        db: SessionLocal,
        patient_id: str,
        new_symptoms: List[Dict[str, Any]]
    ):
        """
        Update patient symptoms with newly extracted ones

        Strategy:
        - Merge new symptoms into existing list
        - Avoid duplicates (same symptom + same timestamp)

        Args:
            db: Database session
            patient_id: Patient identifier
            new_symptoms: List of newly extracted symptom records
        """
        patient = patient_crud.get(db, patient_id)
        if not patient:
            logger.warning(f"Patient not found: {patient_id}")
            return

        existing_symptoms = patient.symptoms or []

        # Create deduplication key set
        existing_keys = {
            (s.get("symptom"), s.get("timestamp"))
            for s in existing_symptoms
        }

        # Add new symptoms (avoid duplicates)
        for symptom in new_symptoms:
            key = (symptom.get("symptom"), symptom.get("timestamp"))
            if key not in existing_keys:
                existing_symptoms.append(symptom)
                existing_keys.add(key)

        # Sort by timestamp descending
        existing_symptoms.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

        patient.symptoms = existing_symptoms
        patient.updated_at = datetime.now()

        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(patient, "symptoms")
        db.commit()

        logger.info(f"Updated patient {patient_id} with {len(new_symptoms)} symptoms")

    def _apply_updates_to_graph(
        self,
        entity_graph,
        patient_id: str,
        conversation_id: str
    ) -> None:
        """
        Apply UpdateAgent updates to EntityGraph nodes
        
        This method:
        1. Uses UpdateAgent to update metric nodes from database
        2. Updates symptom nodes from patient.symptoms
        3. Applies time decay to all nodes
        
        Args:
            entity_graph: EntityGraph instance
            patient_id: Patient identifier
            conversation_id: Conversation identifier (for logging)
        """
        try:
            logger.info(f"[conv:{conversation_id[:8]}] Applying UpdateAgent updates to EntityGraph")
            
            # Import UpdateAgent here to avoid circular imports
            from backend.services.update_agent import UpdateAgent
            
            # Create UpdateAgent with database session
            with SessionLocal() as db:
                update_agent = UpdateAgent(db)
                
                # Update all nodes (metrics, symptoms, time decay)
                stats = update_agent.update_all_nodes(entity_graph, patient_id)
                
                logger.info(
                    f"[conv:{conversation_id[:8]}] UpdateAgent complete: "
                    f"{stats['metric_updated']} metrics updated, "
                    f"{stats['symptom_updated']} symptoms updated, "
                    f"{stats['time_decay_applied']} nodes with time decay applied"
                )
        
        except Exception as e:
            logger.error(f"[conv:{conversation_id[:8]}] Error applying UpdateAgent updates: {e}")
            # Apply time decay even if UpdateAgent fails
            try:
                decay_executor = TimeDecayExecutor()
                decay_executor.apply_decay_to_all_nodes(entity_graph)
                logger.info(f"[conv:{conversation_id[:8]}] Time decay applied (UpdateAgent failed)")
            except Exception as decay_error:
                logger.error(f"[conv:{conversation_id[:8]}] Error applying time decay: {decay_error}")

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

        # Create EntityGraph with max_nodes parameter
        config = get_config()
        max_nodes = config.get("main_agent.max_nodes", None)

        entity_graph = EntityGraph(
            target=target,
            graph_model=graph_model,
            conv_model=conv_model,
            max_nodes=max_nodes
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

        # Apply UpdateAgent to refresh metric and symptom nodes from database
        self._apply_updates_to_graph(entity_graph, patient_id, conversation_id)

        node_count = entity_graph.entity_graph.number_of_nodes()
        logger.info(f"EntityGraph created and initialized for: {conversation_id} with {node_count} nodes")

        return entity_graph

    def _serialize_entity_graph(self, entity_graph: EntityGraph) -> Dict[str, Any]:
        """
        Serialize EntityGraph to dict for database storage

        Args:
            entity_graph: EntityGraph instance

        Returns:
            Dict with serialized state
        """
        from datetime import datetime

        # Helper function to convert datetime objects to ISO strings
        def make_json_serializable(obj):
            """Recursively convert datetime objects to ISO format strings."""
            if isinstance(obj, datetime):
                return obj.isoformat()
            elif isinstance(obj, dict):
                return {k: make_json_serializable(v) for k, v in obj.items()}
            elif isinstance(obj, (list, tuple)):
                return [make_json_serializable(item) for item in obj]
            return obj

        # Convert NetworkX graphs to node-link format with datetime serialization
        entity_graph_raw = nx.node_link_data(entity_graph.entity_graph)
        relation_graph_raw = nx.node_link_data(entity_graph.relation_graph)

        # Convert datetime objects in nodes
        entity_graph_data = {
            "nodes": [make_json_serializable(dict(node)) for node in entity_graph_raw.get("nodes", [])],
            "links": [make_json_serializable(dict(link)) for link in entity_graph_raw.get("links", [])],
            "directed": entity_graph_raw.get("directed", True),
            "multigraph": entity_graph_raw.get("multigraph", False),
            "graph": entity_graph_raw.get("graph", {})
        }
        relation_graph_data = {
            "nodes": [make_json_serializable(dict(node)) for node in relation_graph_raw.get("nodes", [])],
            "links": [make_json_serializable(dict(link)) for link in relation_graph_raw.get("links", [])],
            "directed": relation_graph_raw.get("directed", True),
            "multigraph": relation_graph_raw.get("multigraph", False),
            "graph": relation_graph_raw.get("graph", {})
        }

        return {
            "entity_graph": entity_graph_data,
            "relation_graph": relation_graph_data,
            # Basic state
            "step": entity_graph.step,
            "accomplish": entity_graph.accomplish,
            "prev_node": entity_graph.prev_node,
            "target": entity_graph.target,
            "language": entity_graph.language,
            # Graph parameters - critical for consistent behavior after restart
            "node_hit_threshold": entity_graph.node_hit_threshold,
            "confidential_threshold": entity_graph.confidential_threshold,
            "relevance_threshold": entity_graph.relevance_threshold,
            "weight_threshold": entity_graph.weight_threshold,
            "alpha": entity_graph.alpha,
            "beta": entity_graph.beta,
            "gamma": entity_graph.gamma,
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
        from datetime import datetime

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

        # Build params dict with only non-None values from state_dict
        graph_params = {}
        param_keys = [
            "node_hit_threshold", "confidential_threshold", "relevance_threshold",
            "weight_threshold", "alpha", "beta", "gamma"
        ]
        for key in param_keys:
            if key in state_dict and state_dict[key] is not None:
                graph_params[key] = state_dict[key]

        # Create EntityGraph instance with serialized parameters
        entity_graph = EntityGraph(
            target=state_dict.get("target", target),
            graph_model=graph_model,
            conv_model=conv_model,
            **graph_params  # Pass only non-None parameters
        )

        # Helper function to convert ISO strings back to datetime objects
        def parse_datetime_strings(obj):
            """Recursively convert ISO datetime strings to datetime objects."""
            if isinstance(obj, dict):
                result = {}
                for k, v in obj.items():
                    # Check for common datetime field names
                    if k in ('extracted_at', 'last_updated_at') and isinstance(v, str):
                        try:
                            result[k] = datetime.fromisoformat(v)
                        except (ValueError, TypeError):
                            result[k] = v
                    else:
                        result[k] = parse_datetime_strings(v)
                return result
            elif isinstance(obj, (list, tuple)):
                return [parse_datetime_strings(item) for item in obj]
            return obj

        # Restore graph structures
        entity_graph_data = parse_datetime_strings(state_dict["entity_graph"])
        relation_graph_data = parse_datetime_strings(state_dict["relation_graph"])

        entity_graph.entity_graph = nx.node_link_graph(entity_graph_data, edges="links")
        entity_graph.relation_graph = nx.node_link_graph(relation_graph_data, edges="links")

        # Restore basic state
        entity_graph.step = state_dict.get("step", 0)
        entity_graph.accomplish = state_dict.get("accomplish", False)
        entity_graph.prev_node = state_dict.get("prev_node")
        entity_graph.language = state_dict.get("language", "English")

        # Recalculate temporal decay for all nodes
        self._recalculate_temporal_decay(entity_graph)

        logger.info(f"EntityGraph deserialized from database state with {entity_graph.entity_graph.number_of_nodes()} nodes")

        return entity_graph

    def _recalculate_temporal_decay(self, entity_graph: EntityGraph) -> None:
        """
        Recalculate temporal decay for all nodes after deserialization.

        This ensures that freshness and temporal_confidence are up-to-date
        based on the current time, not the time of serialization.

        Args:
            entity_graph: EntityGraph instance to update
        """
        updated_count = 0
        for node_id in entity_graph.entity_graph.nodes():
            node_data = entity_graph.entity_graph.nodes[node_id]
            extracted_at = node_data.get("extracted_at")
            original_conf = node_data.get("original_confidential_level", 0.5)

            if extracted_at:
                # Recalculate temporal decay
                updated_attrs = entity_graph.temporal_calculator.update_node_attributes(
                    extracted_at=extracted_at,
                    original_confidential_level=original_conf
                )
                # Update only temporal-related attributes
                for key in ["temporal_confidence", "uncertainty", "freshness"]:
                    if key in updated_attrs:
                        node_data[key] = updated_attrs[key]

                # Update status based on new temporal_confidence
                temporal_conf = updated_attrs.get("temporal_confidence", node_data.get("temporal_confidence", 0.5))
                if temporal_conf >= 0.7:
                    node_data["status"] = 2
                elif temporal_conf >= 0.4:
                    node_data["status"] = 1
                else:
                    node_data["status"] = 0

                updated_count += 1

        if updated_count > 0:
            logger.info(f"Recalculated temporal decay for {updated_count} nodes")


# Singleton instance
entity_graph_manager = EntityGraphManager()
