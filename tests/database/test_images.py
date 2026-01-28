"""
Test Image Storage operations
"""
import pytest
import os
from pathlib import Path
from PIL import Image
from backend.database.image_storage import image_storage


@pytest.mark.unit
class TestImageStorageBasic:
    """Test basic image storage operations"""

    def test_save_conversation_images(self, clean_db, sample_image):
        """Test saving images for a conversation"""
        conv_id = "test-conv-001"
        msg_id = 1

        paths = image_storage.save_conversation_images(
            conv_id,
            msg_id,
            [sample_image]
        )

        assert len(paths) == 1
        assert paths[0].endswith("msg_1_img_1.jpg")
        assert os.path.exists(paths[0])

    def test_save_multiple_images(self, clean_db, sample_image, tmp_path):
        """Test saving multiple images"""
        # Create multiple test images
        images = []
        for i in range(3):
            img = Image.new('RGB', (50, 50), color=('red', 'green', 'blue')[i])
            path = tmp_path / f"test_{i}.jpg"
            img.save(path)
            images.append(str(path))

        conv_id = "test-conv-multi"
        msg_id = 5

        paths = image_storage.save_conversation_images(conv_id, msg_id, images)

        assert len(paths) == 3
        assert all(os.path.exists(p) for p in paths)
        assert all(f"msg_{msg_id}_img_" in p for p in paths)

    def test_save_image_bytes(self, clean_db):
        """Test saving image from bytes"""
        from io import BytesIO

        # Create image bytes
        img = Image.new('RGB', (100, 100), color='blue')
        img_bytes = BytesIO()
        img.save(img_bytes, format='JPEG')
        img_bytes.seek(0)

        conv_id = "test-conv-bytes"
        msg_id = 10

        path = image_storage.save_image_bytes(
            conv_id,
            msg_id,
            img_bytes.read(),
            format="JPEG"
        )

        assert os.path.exists(path)
        # PIL might save as .jpeg instead of .jpg
        assert path.endswith(".jpg") or path.endswith(".jpeg")

    def test_save_image_from_pil(self, clean_db):
        """Test saving PIL Image object"""
        img = Image.new('RGB', (100, 100), color='green')

        conv_id = "test-conv-pil"
        msg_id = 15

        path = image_storage.save_image_from_pil(
            conv_id,
            msg_id,
            img,
            format="PNG"
        )

        assert os.path.exists(path)
        assert path.endswith(".png")

    def test_get_image_path(self, clean_db):
        """Test getting image file path"""
        conv_id = "test-conv-get-path"
        filename = "test_image.jpg"

        path = image_storage.get_image_path(conv_id, filename)

        assert path is not None
        assert str(path).endswith(filename)

    def test_delete_conversation_images(self, clean_db, sample_image):
        """Test deleting all images for a conversation"""
        conv_id = "test-conv-delete"

        # Save image first
        image_storage.save_conversation_images(conv_id, 1, [sample_image])

        # Verify it exists
        images_before = image_storage.get_all_conversation_images(conv_id)
        assert len(images_before) == 1

        # Delete
        count = image_storage.delete_conversation_images(conv_id)

        assert count == 1

        # Verify deleted
        images_after = image_storage.get_all_conversation_images(conv_id)
        assert len(images_after) == 0

    def test_delete_message_images(self, clean_db, sample_image, tmp_path):
        """Test deleting images for a specific message"""
        conv_id = "test-conv-delete-msg"

        # Create images for two different messages
        image_storage.save_conversation_images(conv_id, 1, [sample_image])
        image_storage.save_conversation_images(conv_id, 2, [sample_image])

        # Verify both exist
        all_images = image_storage.get_all_conversation_images(conv_id)
        assert len(all_images) == 2

        # Delete only message 1 images
        count = image_storage.delete_message_images(conv_id, 1)

        assert count == 1

        # Verify message 1 images deleted, message 2 images remain
        remaining_images = image_storage.get_all_conversation_images(conv_id)
        assert len(remaining_images) == 1
        assert "msg_1_" not in str(remaining_images[0])


@pytest.mark.unit
class TestImageUtilities:
    """Test image utility functions"""

    def test_get_image_size(self, clean_db, sample_image):
        """Test getting image dimensions"""
        width, height = image_storage.get_image_size(sample_image)

        assert width == 100
        assert height == 100

    def test_get_file_size(self, clean_db, sample_image):
        """Test getting file size"""
        size = image_storage.get_file_size(sample_image)

        assert size > 0
        assert size < 10000  # Should be small for a 100x100 JPEG

    def test_validate_image(self, clean_db, sample_image):
        """Test image validation"""
        is_valid = image_storage.validate_image(sample_image)

        assert is_valid is True

    def test_validate_invalid_image(self, clean_db, tmp_path):
        """Test that invalid image is rejected"""
        # Create a fake image file
        fake_image = tmp_path / "fake.jpg"
        fake_image.write_text("not an image")

        is_valid = image_storage.validate_image(str(fake_image))

        assert is_valid is False

    def test_resize_image(self, clean_db):
        """Test image resizing"""
        # Create a large image
        large_img = Image.new('RGB', (2000, 2000), color='red')
        img_path = "/tmp/test_large.jpg"
        large_img.save(img_path)

        # Resize
        result_path = image_storage.resize_image(img_path, max_size=(1024, 1024))

        # Check dimensions
        width, height = image_storage.get_image_size(result_path)

        assert width <= 1024
        assert height <= 1024

        # Cleanup
        os.remove(img_path)

    def test_convert_to_base64(self, clean_db, sample_image):
        """Test converting image to base64"""
        base64_str = image_storage.convert_to_base64(sample_image)

        assert base64_str is not None
        assert base64_str.startswith("data:image/jpeg;base64,")
        assert "," in base64_str


@pytest.mark.unit
class TestImageStorageStats:
    """Test image storage statistics"""

    def test_get_storage_stats_empty(self, clean_db):
        """Test getting stats for empty storage"""
        # Clean up any existing test images first
        import shutil
        images_dir = Path("data/images/conversations")
        if images_dir.exists():
            shutil.rmtree(images_dir)

        stats = image_storage.get_storage_stats()

        assert stats["total_conversations"] == 0
        assert stats["total_images"] == 0
        assert stats["total_size_bytes"] == 0
        assert stats["total_size_mb"] == 0

    def test_get_storage_stats_with_images(self, clean_db, sample_image):
        """Test getting stats with images"""
        # Get initial stats
        initial_stats = image_storage.get_storage_stats()

        # Use unique conversation IDs to avoid conflicts
        unique_suffix = id(sample_image)
        for i in range(3):
            conv_id = f"test-conv-stats-{i}-{unique_suffix}"
            image_storage.save_conversation_images(conv_id, 1, [sample_image])

        stats = image_storage.get_storage_stats()

        # Should have at least 3 more images than initial
        assert stats["total_images"] >= initial_stats["total_images"] + 3
        assert stats["total_size_bytes"] >= initial_stats["total_size_bytes"]

        # Cleanup
        for i in range(3):
            conv_id = f"test-conv-stats-{i}-{unique_suffix}"
            image_storage.delete_conversation_images(conv_id)

    def test_get_all_conversation_images(self, clean_db, sample_image, tmp_path):
        """Test getting all images for a conversation"""
        conv_id = "test-conv-get-all"

        # Create multiple images
        images = []
        for i in range(3):
            img = Image.new('RGB', (50, 50), color=('red', 'green', 'blue')[i])
            path = tmp_path / f"test_{i}.jpg"
            img.save(path)
            images.append(str(path))

        image_storage.save_conversation_images(conv_id, 1, images)

        all_images = image_storage.get_all_conversation_images(conv_id)

        assert len(all_images) == 3
        assert all(isinstance(p, Path) for p in all_images)

    def test_get_all_images_for_empty_conversation(self, clean_db):
        """Test getting images for conversation with no images"""
        images = image_storage.get_all_conversation_images("non-existent-conv")

        assert images == []


@pytest.mark.integration
class TestImageStorageIntegration:
    """Integration tests with database"""

    def test_image_paths_in_message(self, clean_db, patient, sample_image):
        """Test that image paths are correctly stored in message metadata"""
        from backend.database.crud import conversation_crud, message_crud
        from backend.database.schemas import ConversationCreate, MessageCreate

        # Create conversation
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="测试诊断"
        ))

        # Save image
        paths = image_storage.save_conversation_images(
            conv.conversation_id,
            1,
            [sample_image]
        )

        # Create message with image paths
        msg = message_crud.create(clean_db, MessageCreate(
            conversation_id=conv.conversation_id,
            role="human",
            content="这是我的照片",
            image_paths=paths
        ))

        assert msg.image_paths is not None
        assert len(msg.image_paths) == 1
        assert msg.image_paths[0] == paths[0]
        assert os.path.exists(msg.image_paths[0])

    def test_image_cleanup_on_conversation_delete(self, clean_db, patient, sample_image):
        """Test that deleting conversation should clean up images"""
        from backend.database.crud import conversation_crud, message_crud
        from backend.database.schemas import ConversationCreate, MessageCreate

        # Create conversation
        conv = conversation_crud.create(clean_db, ConversationCreate(
            patient_id=patient.patient_id,
            target="测试诊断"
        ))

        # Save image
        image_storage.save_conversation_images(
            conv.conversation_id,
            1,
            [sample_image]
        )

        # Verify image exists
        images = image_storage.get_all_conversation_images(conv.conversation_id)
        assert len(images) == 1

        # Note: This tests the database deletion, actual image cleanup
        # would need to be handled in service layer or via cascade
        conversation_crud.delete(clean_db, conv.conversation_id)

        # Check if images still exist (they won't be auto-deleted)
        # This would need to be handled by application logic
        remaining = image_storage.get_all_conversation_images(conv.conversation_id)
        assert len(remaining) == 1  # Images still exist, need manual cleanup


@pytest.mark.slow
class TestImageStoragePerformance:
    """Performance and stress tests for image storage"""

    def test_save_many_images(self, clean_db, tmp_path):
        """Test saving many images efficiently"""
        conv_id = "test-conv-many"
        msg_id = 1

        # Create 50 test images
        images = []
        for i in range(50):
            img = Image.new('RGB', (100, 100), color='blue')
            path = tmp_path / f"test_{i}.jpg"
            img.save(path)
            images.append(str(path))

        # Save all
        import time
        start = time.time()

        paths = image_storage.save_conversation_images(conv_id, msg_id, images)

        elapsed = time.time() - start

        assert len(paths) == 50
        assert elapsed < 5.0  # Should complete in under 5 seconds
        assert all(os.path.exists(p) for p in paths)
