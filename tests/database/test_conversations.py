"""
Test Conversation CRUD operations
"""
import pytest
from backend.database.crud import conversation_crud, message_crud, patient_crud
from backend.database.schemas import (
    PatientCreate,
    ConversationCreate,
    ConversationUpdate,
    MessageCreate
)
from backend.database.models import Conversation, Message


@pytest.mark.unit
class TestConversationCRUD:
    """Test conversation CRUD operations"""

    def test_create_conversation(self, clean_db, patient):
        """Test creating a new conversation"""
        conv_data = ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        )

        conv = conversation_crud.create(clean_db, conv_data)

        assert conv is not None
        assert conv.conversation_id is not None
        assert conv.patient_id == patient.patient_id
        assert conv.target == "高血压诊断"
        assert conv.model_type == "DrHyper"
        assert conv.status == "active"
        assert conv.drhyper_state is not None
        assert "entity_graph" in conv.drhyper_state
        assert "relation_graph" in conv.drhyper_state
        assert conv.created_at is not None

    def test_get_conversation(self, clean_db, conversation):
        """Test retrieving a conversation by ID"""
        found = conversation_crud.get(clean_db, conversation.conversation_id)

        assert found is not None
        assert found.conversation_id == conversation.conversation_id
        assert found.target == conversation.target

    def test_get_nonexistent_conversation(self, clean_db):
        """Test retrieving a non-existent conversation"""
        found = conversation_crud.get(clean_db, "non-existent-id")

        assert found is None

    def test_list_conversations_by_patient(self, clean_db, patient):
        """Test listing all conversations for a patient"""
        # Create multiple conversations
        for i in range(3):
            conversation_crud.create(clean_db, ConversationCreate(
                patient_id=patient.patient_id,
                target=f"诊断目标{i}",
                model_type="DrHyper"
            ))

        conversations, total = conversation_crud.list_by_patient(
            clean_db, patient.patient_id
        )

        assert total >= 3
        assert len(conversations) >= 3
        assert all(c.patient_id == patient.patient_id for c in conversations)

    def test_list_all_conversations(self, clean_db):
        """Test listing all conversations with pagination"""
        # Create a patient first
        patient = patient_crud.create(clean_db, PatientCreate(
            name="测试患者",
            age=35,
            gender="male"
        ))

        # Create multiple conversations
        for i in range(5):
            conversation_crud.create(clean_db, ConversationCreate(
                patient_id=patient.patient_id,
                target=f"目标{i}",
                model_type="DrHyper"
            ))

        conversations, total = conversation_crud.list_all(clean_db, skip=0, limit=10)

        assert total >= 5
        assert len(conversations) >= 5

    def test_list_conversations_by_status(self, clean_db, conversation):
        """Test filtering conversations by status"""
        # Update conversation status
        conversation_crud.update(clean_db, conversation.conversation_id,
                                ConversationUpdate(status="completed"))

        # List active conversations
        active_convs, _ = conversation_crud.list_all(
            clean_db, skip=0, limit=10, status="active"
        )

        # List completed conversations
        completed_convs, _ = conversation_crud.list_all(
            clean_db, skip=0, limit=10, status="completed"
        )

        assert len(completed_convs) >= 1
        assert any(c.status == "completed" for c in completed_convs)

    def test_update_conversation(self, clean_db, conversation):
        """Test updating conversation information"""
        updated = conversation_crud.update(clean_db, conversation.conversation_id,
                                        ConversationUpdate(target="新的诊断目标"))

        assert updated is not None
        assert updated.target == "新的诊断目标"
        # Original fields should remain
        assert updated.patient_id == conversation.patient_id

    def test_update_drhyper_state(self, clean_db, conversation):
        """Test updating DrHyper state"""
        new_state = {
            "entity_graph": {
                "nodes": [
                    {"id": "symptom_1", "type": "symptom"}
                ],
                "edges": []
            },
            "relation_graph": {"nodes": [], "edges": []},
            "current_hint": "测试提示",
            "step": 1,
            "accomplish": False
        }

        updated = conversation_crud.update_drhyper_state(
            clean_db, conversation.conversation_id, new_state
        )

        assert updated is not None
        assert updated.drhyper_state is not None
        assert updated.drhyper_state["current_hint"] == "测试提示"
        assert updated.drhyper_state["step"] == 1

    def test_close_conversation(self, clean_db, conversation):
        """Test closing a conversation"""
        closed = conversation_crud.close(clean_db, conversation.conversation_id)

        assert closed is not None
        assert closed.status == "completed"

    def test_delete_conversation(self, clean_db, conversation):
        """Test deleting a conversation"""
        conv_id = conversation.conversation_id

        result = conversation_crud.delete(clean_db, conv_id)

        assert result is True

        # Verify conversation is deleted
        deleted = conversation_crud.get(clean_db, conv_id)
        assert deleted is None

    def test_delete_nonexistent_conversation(self, clean_db):
        """Test deleting a non-existent conversation"""
        result = conversation_crud.delete(clean_db, "non-existent-id")

        assert result is False


@pytest.mark.unit
class TestMessageCRUD:
    """Test message CRUD operations"""

    def test_create_message(self, clean_db, conversation):
        """Test creating a new message"""
        msg_data = MessageCreate(
            conversation_id=conversation.conversation_id,
            role="human",
            content="测试消息"
        )

        msg = message_crud.create(clean_db, msg_data)

        assert msg is not None
        assert msg.id is not None
        assert msg.conversation_id == conversation.conversation_id
        assert msg.role == "human"
        assert msg.content == "测试消息"
        assert msg.turn_number == 1
        assert msg.timestamp is not None

    def test_create_message_with_metadata(self, clean_db, conversation):
        """Test creating a message with metadata"""
        msg_data = MessageCreate(
            conversation_id=conversation.conversation_id,
            role="ai",
            content="AI回复",
            think_content="AI思考过程",
            message_metadata={"hint": "提示信息"},
            image_paths=["path/to/image.jpg"]
        )

        msg = message_crud.create(clean_db, msg_data)

        assert msg is not None
        assert msg.think_content == "AI思考过程"
        assert msg.message_metadata is not None
        assert msg.message_metadata["hint"] == "提示信息"
        assert msg.image_paths == ["path/to/image.jpg"]

    def test_message_turn_number_increments(self, clean_db, conversation):
        """Test that message turn numbers increment correctly"""
        # Create multiple messages
        msg1 = message_crud.create(clean_db, MessageCreate(
            conversation_id=conversation.conversation_id,
            role="human",
            content="消息1"
        ))

        msg2 = message_crud.create(clean_db, MessageCreate(
            conversation_id=conversation.conversation_id,
            role="ai",
            content="消息2"
        ))

        msg3 = message_crud.create(clean_db, MessageCreate(
            conversation_id=conversation.conversation_id,
            role="human",
            content="消息3"
        ))

        assert msg1.turn_number == 1
        assert msg2.turn_number == 2
        assert msg3.turn_number == 3

    def test_get_message(self, clean_db, conversation):
        """Test retrieving a message by ID"""
        msg = message_crud.create(clean_db, MessageCreate(
            conversation_id=conversation.conversation_id,
            role="human",
            content="测试消息"
        ))

        found = message_crud.get(clean_db, msg.id)

        assert found is not None
        assert found.id == msg.id
        assert found.content == "测试消息"

    def test_list_messages_by_conversation(self, clean_db, conversation):
        """Test listing all messages in a conversation"""
        # Create multiple messages
        messages_data = [
            ("ai", "您好"),
            ("human", "你好"),
            ("ai", "有什么可以帮助您？"),
        ]

        for role, content in messages_data:
            message_crud.create(clean_db, MessageCreate(
                conversation_id=conversation.conversation_id,
                role=role,
                content=content
            ))

        messages = message_crud.list_by_conversation(clean_db, conversation.conversation_id)

        assert len(messages) == 3
        assert messages[0].role == "ai"
        assert messages[0].content == "您好"
        assert messages[1].role == "human"
        # Verify they are ordered by turn_number
        for i in range(len(messages) - 1):
            assert messages[i].turn_number < messages[i + 1].turn_number

    def test_delete_message(self, clean_db, conversation):
        """Test deleting a message"""
        msg = message_crud.create(clean_db, MessageCreate(
            conversation_id=conversation.conversation_id,
            role="human",
            content="要删除的消息"
        ))

        msg_id = msg.id
        result = message_crud.delete(clean_db, msg_id)

        assert result is True

        # Verify message is deleted
        deleted = message_crud.get(clean_db, msg_id)
        assert deleted is None


@pytest.mark.integration
class TestConversationIntegration:
    """Integration tests for conversation and message operations"""

    def test_conversation_message_relationship(self, clean_db, patient):
        """Test that conversation correctly tracks messages"""
        # Create conversation
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="测试诊断"
        ))

        # Add messages
        message_crud.create(clean_db, MessageCreate(
            conversation_id=conv.conversation_id,
            role="ai",
            content="您好"
        ))

        message_crud.create(clean_db, MessageCreate(
            conversation_id=conv.conversation_id,
            role="human",
            content="你好"
        ))

        # Refresh from database
        from backend.database.models import Conversation
        updated_conv = clean_db.query(Conversation).filter(
            Conversation.conversation_id == conv.conversation_id
        ).first()

        assert updated_conv is not None
        assert len(updated_conv.messages) == 2

    def test_deleting_conversation_cascade_deletes_messages(self, clean_db, patient):
        """Test that deleting conversation also deletes messages"""
        # Create conversation with messages
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="测试诊断"
        ))

        message_crud.create(clean_db, MessageCreate(
            conversation_id=conv.conversation_id,
            role="ai",
            content="测试消息"
        ))

        # Delete conversation
        conversation_crud.delete(clean_db, conv.conversation_id)

        # Verify messages are deleted
        messages = message_crud.list_by_conversation(clean_db, conv.conversation_id)

        assert len(messages) == 0

    def test_message_updates_conversation_timestamp(self, clean_db, patient):
        """Test that adding a message updates conversation timestamp"""
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="测试诊断"
        ))

        original_updated_at = conv.updated_at

        # Add message (this should update conversation's updated_at)
        import time
        time.sleep(0.01)  # Small delay to ensure timestamp difference

        message_crud.create(clean_db, MessageCreate(
            conversation_id=conv.conversation_id,
            role="human",
            content="测试消息"
        ))

        # Refresh conversation
        updated_conv = conversation_crud.get(clean_db, conv.conversation_id)

        assert updated_conv.updated_at > original_updated_at


@pytest.mark.integration
class TestConversationValidation:
    """Test data validation in conversations"""

    def test_invalid_role_raises_error(self, clean_db, conversation):
        """Test that invalid role raises validation error"""
        with pytest.raises(Exception):  # Pydantic validation error
            message_crud.create(clean_db, MessageCreate(
                conversation_id=conversation.conversation_id,
                role="invalid_role",  # Invalid role
                content="测试"
            ))

    def test_empty_content_raises_error(self, clean_db, conversation):
        """Test that empty content raises validation error"""
        with pytest.raises(Exception):  # Pydantic validation error
            message_crud.create(clean_db, MessageCreate(
                conversation_id=conversation.conversation_id,
                role="human",
                content=""  # Empty content
            ))

    def test_nonexistent_conversation_id(self, clean_db):
        """Test creating message with non-existent conversation ID"""
        # Create message - it won't fail until database commit
        # but should fail when trying to access it or update the conversation
        msg = message_crud.create(clean_db, MessageCreate(
            conversation_id="non-existent-conv-id",
            role="human",
            content="测试消息"
        ))

        # Message should be created even with invalid conversation_id
        # because SQLite doesn't enforce foreign keys by default
        assert msg is not None
        assert msg.content == "测试消息"
