"""
Conversation Service - Integrates DrHyper and Database

This Service layer is responsible for:
1. Calling DrHyper's conversation engine
2. Persisting conversation state to database
3. Managing conversation lifecycle

Reference: drhyper/api/server.py ConversationManager
"""
import os
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
    """

    def __init__(self):
        self.config = ConfigManager()
        self.working_dir = self.config.system.working_directory
        self.prompts = ConversationPrompts()

        logger.info("ConversationService initialized (database-backed cache)")

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

            # Initialize graph structures for this conversation
            logger.info("Initializing graph structures for new conversation...")
            drhyper_conv.init_graph(save=False)  # Don't save to global files

            # Initialize conversation, get first AI message
            logger.info("Initializing conversation...")
            ai_message, _ = drhyper_conv.init()

        else:
            raise ValueError(f"Unsupported model type: {model_type}")

        # 4. Save complete DrHyper state to database
        # Using to_cache_dict() which includes graph structures
        drhyper_state = drhyper_conv.to_cache_dict()
        conversation_crud.update_drhyper_state(db, conversation_id, drhyper_state)

        # 5. Save AI message to database
        message_crud.create(db, MessageCreate(
            conversation_id=conversation_id,
            role="ai",
            content=ai_message
        ))


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

        # 1. Load DrHyper conversation from database
        drhyper_conv, patient = self._load_drhyper_conversation(db, conversation_id)

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

        # 6. Update complete DrHyper state in database
        drhyper_state = drhyper_conv.to_cache_dict()
        conversation_crud.update_drhyper_state(db, conversation_id, drhyper_state)

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

        # 1. Load conversation to get final state
        drhyper_conv, _ = self._load_drhyper_conversation(db, conversation_id)
        drhyper_state = drhyper_conv.to_cache_dict()

        # 2. Update database status to completed
        conversation_crud.close(db, conversation_id)
        conversation_crud.update_drhyper_state(db, conversation_id, drhyper_state)

        # Note: State stays in database for historical records

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

    def delete_conversation(
        self,
        db: Session,
        conversation_id: str
    ) -> bool:
        """
        Delete a conversation (cascade deletes messages and images)

        Args:
            db: Database session
            conversation_id: Conversation ID

        Returns:
            True if deleted, False otherwise

        Raises:
            ValueError: If conversation doesn't exist
        """
        logger.info(f"Deleting conversation {conversation_id}")

        # 1. Verify conversation exists
        conv = conversation_crud.get(db, conversation_id)
        if not conv:
            raise ValueError(f"Conversation not found: {conversation_id}")

        # 2. Delete associated images from file system
        try:
            deleted_count = image_storage.delete_conversation_images(conversation_id)
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} images for conversation {conversation_id}")
        except Exception as e:
            logger.warning(f"Failed to delete images for conversation {conversation_id}: {e}")
            # Continue with deletion even if image deletion fails

        # 3. Delete conversation (cascade will delete messages)
        success = conversation_crud.delete(db, conversation_id)

        if success:
            logger.info(f"Conversation {conversation_id} deleted successfully")
        else:
            logger.error(f"Failed to delete conversation {conversation_id}")

        return success

    # ========================================
    # Private helper methods
    # ========================================

    def _load_drhyper_conversation(
        self,
        db: Session,
        conversation_id: str
    ):
        """
        Load DrHyper conversation from database.

        Returns:
            Tuple of (drhyper_conv, patient)

        Raises:
            ValueError: If conversation doesn't exist or state is invalid
        """
        # 1. Get conversation record from database
        db_conv = conversation_crud.get(db, conversation_id)
        if not db_conv:
            raise ValueError(f"Conversation not found: {conversation_id}")

        # 2. Get patient
        patient = patient_crud.get(db, db_conv.patient_id)
        if not patient:
            raise ValueError(f"Patient not found: {db_conv.patient_id}")

        # 3. Get DrHyper state from database
        drhyper_state = db_conv.drhyper_state
        if not drhyper_state:
            raise ValueError(f"Conversation state is empty: {conversation_id}")

        metadata = drhyper_state.get("metadata", {})
        version = metadata.get("version", "unknown")

        logger.info(f"Loading conversation from database v{version}: {conversation_id}")
        logger.info(f"State cached at: {metadata.get('cached_at', 'unknown')}")
        logger.info(f"Message count: {metadata.get('message_count', 0)}")
        logger.info(f"Entity graph nodes: {metadata.get('entity_graph_nodes', 0)}")

        # 4. Load models (needed for conversation restoration)
        logger.info("Loading models for conversation restoration...")
        conv_model, graph_model = load_models(verbose=False)

        # 5. Restore conversation from cached state
        drhyper_conv = LongConversation.from_cache_dict(
            cache_dict=drhyper_state,
            conv_model=conv_model,
            graph_model=graph_model
        )

        logger.info(f"Conversation restored successfully from database")

        return drhyper_conv, patient


# Export singleton
conversation_service = ConversationService()
