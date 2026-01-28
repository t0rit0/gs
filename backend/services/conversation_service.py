"""
Conversation Service - Integrates DrHyper and Database

This Service layer is responsible for:
1. Calling DrHyper's conversation engine
2. Persisting conversation state to database
3. Managing conversation lifecycle

Reference: drhyper/api/server.py ConversationManager
"""
import os
import pickle
from pathlib import Path
from typing import Tuple, Dict, Any, Optional, List
from sqlalchemy.orm import Session

# DrHyper core components
from drhyper.core.conversation import LongConversation
from drhyper.config.settings import ConfigManager
from drhyper.prompts.templates import ConversationPrompts
from drhyper.utils.aux import load_models
from drhyper.utils.logging import get_logger

# Database components
from backend.database.crud import (
    patient_crud,
    conversation_crud,
    message_crud
)
from backend.database.schemas import (
    PatientCreate,
    ConversationCreate,
    MessageCreate
)
from backend.database.image_storage import image_storage

logger = get_logger("ConversationService")


class ConversationService:
    """
    Conversation Service - Integrates DrHyper conversation engine and database

    Reference: drhyper/api/server.py:ConversationManager implementation
    Key differences:
    - ConversationManager: Uses memory + pickle files
    - ConversationService: Uses database + pickle cache
    """

    def __init__(self):
        self.config = ConfigManager()
        self.working_dir = self.config.system.working_directory
        self.prompts = ConversationPrompts()

        # DrHyper object cache directory
        self.cache_dir = Path(self.working_dir) / "backend_cache"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"ConversationService initialized with cache dir: {self.cache_dir}")

    def create_conversation(
        self,
        db: Session,
        patient_id: str,
        target: str,
        model_type: str = "DrHyper"
    ) -> Tuple[str, str, Dict]:
        """
        Create a new conversation

        Reference: drhyper/api/server.py:ConversationManager.create_conversation()

        Args:
            db: Database session
            patient_id: Patient ID
            target: Conversation goal (e.g., "Hypertension diagnosis")
            model_type: Model type (currently only supports DrHyper)

        Returns:
            (conversation_id, ai_message, drhyper_state)

        Raises:
            ValueError: If patient doesn't exist or model type is not supported
        """
        # 1. Verify patient exists
        patient = patient_crud.get(db, patient_id)
        if not patient:
            raise ValueError(f"Patient not found: {patient_id}")

        logger.info(f"Creating conversation for patient {patient_id} with target: {target}")

        # 2. Create conversation record in database
        conv_data = ConversationCreate(
            patient_id=patient_id,
            target=target,
            model_type=model_type
        )
        db_conv = conversation_crud.create(db, conv_data)
        conversation_id = db_conv.conversation_id

        logger.info(f"Database conversation record created: {conversation_id}")

        # 3. Initialize DrHyper conversation engine
        if model_type == "DrHyper":
            # Get prompt templates
            prompt_target = self.prompts.get("HYPERTENSION_CONSULTATION_TARGET")
            routine = self.prompts.get("HYPERTENSION_ASSESSMENT_ROUTINE")

            # Build prompt with patient information
            patient_str = (
                f"Patient Name: {patient.name}, "
                f"Age: {patient.age}, "
                f"Gender: {patient.gender}"
            )
            full_prompt = f"{target}\n{patient_str}"

            # Load models
            logger.info("Loading DrHyper models...")
            conv_model, graph_model = load_models(verbose=False)

            # Create LongConversation instance
            drhyper_conv = LongConversation(
                target=full_prompt,
                conv_model=conv_model,
                graph_model=graph_model,
                routine=routine,
                visualize=False,
                weight_threshold=0.1,
                working_directory=self.working_dir,
            )

            # Initialize or load graph structures
            entity_graph_path = os.path.join(self.working_dir, "entity_graph.pkl")
            relation_graph_path = os.path.join(self.working_dir, "relation_graph.pkl")

            if os.path.exists(entity_graph_path) and os.path.exists(relation_graph_path):
                logger.info("Loading existing graph structures...")
                drhyper_conv.load_graph(entity_graph_path, relation_graph_path)
            else:
                logger.info("Initializing new graph structures...")
                drhyper_conv.init_graph(save=True)

            # Initialize conversation, get first AI message
            logger.info("Initializing conversation...")
            ai_message, _ = drhyper_conv.init()

        else:
            raise ValueError(f"Unsupported model type: {model_type}")

        # 4. Extract and save DrHyper state to database
        drhyper_state = self._extract_drhyper_state(drhyper_conv)
        conversation_crud.update_drhyper_state(db, conversation_id, drhyper_state)

        # 5. Save AI message to database
        message_crud.create(db, MessageCreate(
            conversation_id=conversation_id,
            role="ai",
            content=ai_message
        ))

        # 6. Persist DrHyper object to cache file
        self._save_drhyper_conversation(
            conversation_id,
            drhyper_conv,
            patient
        )

        logger.info(f"Conversation {conversation_id} created successfully")

        return conversation_id, ai_message, drhyper_state

    def process_message(
        self,
        db: Session,
        conversation_id: str,
        human_message: str,
        images: Optional[List[str]] = None
    ) -> Tuple[str, bool, Optional[Dict], Dict]:
        """
        Process user message

        Reference: drhyper/api/server.py:ConversationManager.process_message()

        Args:
            db: Database session
            conversation_id: Conversation ID
            human_message: User message
            images: Optional list of base64-encoded images

        Returns:
            (ai_response, accomplish, analysis_report, drhyper_state)

        Raises:
            ValueError: If conversation doesn't exist
        """
        logger.info(f"Processing message for conversation {conversation_id}")

        # 1. Load DrHyper conversation from cache
        drhyper_conv, patient = self._load_drhyper_conversation(conversation_id)

        # 2. Process images (if any)
        image_data = None
        saved_image_paths = []

        if images:
            logger.info(f"Processing {len(images)} image(s)")

            # Get current message count for naming
            messages = message_crud.list_by_conversation(db, conversation_id)
            next_msg_id = len(messages) + 1

            # Save images to file system
            # Note: images here are base64 strings, need to decode and save
            saved_image_paths = image_storage.save_base64_images(
                conversation_id,
                next_msg_id,
                images
            )

            # Format required by DrHyper
            image_data = images

        # 3. Call DrHyper to process message
        logger.info("Calling DrHyper conversation...")
        ai_response, accomplish, analysis_report, _ = drhyper_conv.conversation(
            human_message,
            image_data
        )

        # 4. Save user message to database
        user_msg = message_crud.create(db, MessageCreate(
            conversation_id=conversation_id,
            role="human",
            content=human_message,
            image_paths=saved_image_paths
        ))

        # 5. Save AI message to database
        message_metadata = {}
        if analysis_report:
            message_metadata["analysis_report"] = analysis_report

        ai_msg = message_crud.create(db, MessageCreate(
            conversation_id=conversation_id,
            role="ai",
            content=ai_response,
            message_metadata=message_metadata
        ))

        # 6. Update DrHyper state in database
        drhyper_state = self._extract_drhyper_state(drhyper_conv)
        conversation_crud.update_drhyper_state(db, conversation_id, drhyper_state)

        # 7. Re-cache DrHyper object
        self._save_drhyper_conversation(
            conversation_id,
            drhyper_conv,
            patient
        )

        logger.info(f"Message processed, accomplish={accomplish}")

        return ai_response, accomplish, analysis_report, drhyper_state

    def end_conversation(
        self,
        db: Session,
        conversation_id: str
    ) -> Dict:
        """
        End conversation

        Reference: drhyper/api/server.py:ConversationManager.end_conversation()

        Args:
            db: Database session
            conversation_id: Conversation ID

        Returns:
            Final DrHyper state

        Raises:
            ValueError: If conversation doesn't exist
        """
        logger.info(f"Ending conversation {conversation_id}")

        # 1. Load DrHyper conversation to get final state
        drhyper_conv, _ = self._load_drhyper_conversation(conversation_id)
        drhyper_state = self._extract_drhyper_state(drhyper_conv)

        # 2. Update database status to completed
        conversation_crud.close(db, conversation_id)
        conversation_crud.update_drhyper_state(db, conversation_id, drhyper_state)

        # 3. Clean up cache files
        self._cleanup_drhyper_conversation(conversation_id)

        logger.info(f"Conversation {conversation_id} ended")

        return drhyper_state

    def get_conversation_history(
        self,
        db: Session,
        conversation_id: str
    ) -> List[Dict]:
        """
        Get conversation history

        Args:
            db: Database session
            conversation_id: Conversation ID

        Returns:
            List of messages
        """
        messages = message_crud.list_by_conversation(db, conversation_id)

        return [
            {
                "role": msg.role,
                "content": msg.content,
                "turn_number": msg.turn_number,
                "timestamp": msg.timestamp.isoformat(),
                "has_images": bool(msg.image_paths)
            }
            for msg in messages
        ]

    # ========================================
    # Private helper methods
    # ========================================

    def _extract_drhyper_state(self, drhyper_conv: LongConversation) -> Dict:
        """
        Extract state from DrHyper object

        Needs to be implemented based on actual DrHyper API
        """
        # TODO: Extract state based on actual DrHyper API
        state = {
            "entity_graph": {
                "nodes": [],
                "edges": []
            },
            "relation_graph": {
                "nodes": [],
                "edges": []
            },
            "current_hint": getattr(drhyper_conv, 'current_hint', None),
            "step": getattr(drhyper_conv, 'step', 0),
            "accomplish": getattr(drhyper_conv, 'accomplish', False)
        }

        # Try to extract graph structures
        try:
            if hasattr(drhyper_conv, 'entity_graph'):
                entity_graph = drhyper_conv.entity_graph
                # Convert graph to serializable format
                # This needs to be implemented based on actual graph data structure
                state["entity_graph"] = self._serialize_graph(entity_graph)

            if hasattr(drhyper_conv, 'relation_graph'):
                relation_graph = drhyper_conv.relation_graph
                state["relation_graph"] = self._serialize_graph(relation_graph)
        except Exception as e:
            logger.warning(f"Failed to extract graph structure: {e}")

        return state

    def _serialize_graph(self, graph) -> Dict:
        """
        Serialize graph structure

        Needs to be implemented based on actual graph library (e.g., NetworkX)
        """
        # TODO: Implement graph serialization
        # This is a placeholder implementation
        return {
            "nodes": [],
            "edges": []
        }

    def _save_drhyper_conversation(
        self,
        conversation_id: str,
        drhyper_conv: LongConversation,
        patient
    ):
        """Persist DrHyper object to cache file"""
        filepath = self.cache_dir / f"{conversation_id}.pkl"

        try:
            with open(filepath, "wb") as f:
                pickle.dump({
                    "drhyper_conv": drhyper_conv,
                    "patient": patient
                }, f)

            logger.debug(f"DrHyper conversation saved to {filepath}")

        except Exception as e:
            logger.error(f"Failed to save DrHyper conversation: {e}")
            raise

    def _load_drhyper_conversation(self, conversation_id: str):
        """Load DrHyper object from cache file"""
        filepath = self.cache_dir / f"{conversation_id}.pkl"

        if not filepath.exists():
            raise ValueError(f"Conversation cache not found: {conversation_id}")

        try:
            with open(filepath, "rb") as f:
                data = pickle.load(f)

            logger.debug(f"DrHyper conversation loaded from {filepath}")

            return data["drhyper_conv"], data["patient"]

        except Exception as e:
            logger.error(f"Failed to load DrHyper conversation: {e}")
            raise

    def _cleanup_drhyper_conversation(self, conversation_id: str):
        """Clean up DrHyper cache files"""
        filepath = self.cache_dir / f"{conversation_id}.pkl"

        if filepath.exists():
            filepath.unlink()
            logger.debug(f"Cleaned up cache for {conversation_id}")


# Export singleton
conversation_service = ConversationService()
