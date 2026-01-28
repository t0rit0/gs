"""
Image Storage Service

Handles file system storage for conversation images.
Images are stored as files, with paths saved in the database.
"""
import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional, Tuple
from PIL import Image
import io


class ImageStorage:
    """
    Image storage manager

    Stores images in the file system and returns file paths.
    Supports saving, retrieving, and deleting images.
    """

    def __init__(self, base_dir: str = "data/images"):
        """
        Initialize image storage

        Args:
            base_dir: Base directory for image storage
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def save_conversation_images(
        self,
        conversation_id: str,
        message_id: int,
        image_files: List[str]
    ) -> List[str]:
        """
        Save images for a conversation message

        Args:
            conversation_id: Conversation UUID
            message_id: Message ID (database primary key)
            image_files: List of image file paths to save

        Returns:
            List of saved image paths (relative to base_dir)

        Example:
            >>> storage = ImageStorage()
            >>> paths = storage.save_conversation_images(
            ...     "conv-123", 5, ["/tmp/upload1.jpg", "/tmp/upload2.png"]
            ... )
            >>> print(paths)
            ['data/images/conversations/conv-123/msg_5_img_1.jpg',
             'data/images/conversations/conv-123/msg_5_img_2.png']
        """
        # Create conversation directory
        conv_dir = self.base_dir / "conversations" / conversation_id
        conv_dir.mkdir(parents=True, exist_ok=True)

        saved_paths = []

        for idx, image_file in enumerate(image_files):
            # Get file extension
            ext = Path(image_file).suffix

            # Generate filename
            filename = f"msg_{message_id}_img_{idx + 1}{ext}"
            dest_path = conv_dir / filename

            # Copy file
            shutil.copy2(image_file, dest_path)

            # Store relative path
            saved_paths.append(str(dest_path))

        return saved_paths

    def save_image_bytes(
        self,
        conversation_id: str,
        message_id: int,
        image_data: bytes,
        format: str = "JPEG"
    ) -> str:
        """
        Save image from bytes data

        Args:
            conversation_id: Conversation UUID
            message_id: Message ID
            image_data: Image bytes data
            format: Image format (JPEG, PNG, etc.)

        Returns:
            Saved image path
        """
        # Create conversation directory
        conv_dir = self.base_dir / "conversations" / conversation_id
        conv_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        unique_id = uuid.uuid4().hex[:8]
        filename = f"msg_{message_id}_img_{unique_id}.{format.lower()}"
        dest_path = conv_dir / filename

        # Save image
        with open(dest_path, "wb") as f:
            f.write(image_data)

        return str(dest_path)

    def save_image_from_pil(
        self,
        conversation_id: str,
        message_id: int,
        pil_image: Image.Image,
        format: str = "JPEG"
    ) -> str:
        """
        Save PIL Image object

        Args:
            conversation_id: Conversation UUID
            message_id: Message ID
            pil_image: PIL Image object
            format: Image format

        Returns:
            Saved image path
        """
        # Create conversation directory
        conv_dir = self.base_dir / "conversations" / conversation_id
        conv_dir.mkdir(parents=True, exist_ok=True)

        # Generate unique filename
        unique_id = uuid.uuid4().hex[:8]
        filename = f"msg_{message_id}_img_{unique_id}.{format.lower()}"
        dest_path = conv_dir / filename

        # Save image
        pil_image.save(dest_path, format=format)

        return str(dest_path)

    def get_image_path(self, conversation_id: str, filename: str) -> Path:
        """
        Get full path for an image file

        Args:
            conversation_id: Conversation UUID
            filename: Image filename

        Returns:
            Full path to the image
        """
        return self.base_dir / "conversations" / conversation_id / filename

    def get_all_conversation_images(self, conversation_id: str) -> List[Path]:
        """
        Get all image files for a conversation

        Args:
            conversation_id: Conversation UUID

        Returns:
            List of image file paths
        """
        conv_dir = self.base_dir / "conversations" / conversation_id

        if not conv_dir.exists():
            return []

        # Get all image files
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
        images = [
            f for f in conv_dir.iterdir()
            if f.is_file() and f.suffix.lower() in image_extensions
        ]

        return sorted(images)

    def resize_image(
        self,
        image_path: str,
        max_size: Tuple[int, int] = (1024, 1024),
        quality: int = 85
    ) -> str:
        """
        Resize an image to reduce file size

        Args:
            image_path: Path to image file
            max_size: Maximum dimensions (width, height)
            quality: JPEG quality (1-100)

        Returns:
            Path to resized image (same as input)

        Raises:
            IOError: If image cannot be opened or saved
        """
        img = Image.open(image_path)

        # Resize if necessary
        if img.size[0] > max_size[0] or img.size[1] > max_size[1]:
            img.thumbnail(max_size, Image.Resampling.LANCZOS)

        # Save with compression
        img.save(image_path, quality=quality, optimize=True)

        return image_path

    def get_image_size(self, image_path: str) -> Tuple[int, int]:
        """
        Get image dimensions

        Args:
            image_path: Path to image file

        Returns:
            Tuple of (width, height)
        """
        with Image.open(image_path) as img:
            return img.size

    def get_file_size(self, image_path: str) -> int:
        """
        Get file size in bytes

        Args:
            image_path: Path to image file

        Returns:
            File size in bytes
        """
        return os.path.getsize(image_path)

    def delete_conversation_images(self, conversation_id: str) -> int:
        """
        Delete all images for a conversation

        Args:
            conversation_id: Conversation UUID

        Returns:
            Number of images deleted
        """
        conv_dir = self.base_dir / "conversations" / conversation_id

        if not conv_dir.exists():
            return 0

        # Count files before deletion
        file_count = len(list(conv_dir.iterdir()))

        # Delete directory and all contents
        shutil.rmtree(conv_dir)

        return file_count

    def delete_message_images(
        self,
        conversation_id: str,
        message_id: int
    ) -> int:
        """
        Delete images for a specific message

        Args:
            conversation_id: Conversation UUID
            message_id: Message ID

        Returns:
            Number of images deleted
        """
        conv_dir = self.base_dir / "conversations" / conversation_id

        if not conv_dir.exists():
            return 0

        # Find and delete images matching message ID
        deleted_count = 0
        for image_file in conv_dir.iterdir():
            if image_file.name.startswith(f"msg_{message_id}_"):
                image_file.unlink()
                deleted_count += 1

        return deleted_count

    def validate_image(self, image_path: str) -> bool:
        """
        Validate if a file is a valid image

        Args:
            image_path: Path to image file

        Returns:
            True if valid image, False otherwise
        """
        try:
            with Image.open(image_path) as img:
                img.verify()
            return True
        except Exception:
            return False

    def save_base64_images(
        self,
        conversation_id: str,
        message_id: int,
        base64_images: List[str]
    ) -> List[str]:
        """
        Save base64-encoded images (for DrHyper integration)

        Args:
            conversation_id: Conversation UUID
            message_id: Message ID
            base64_images: List of base64-encoded image strings

        Returns:
            List of saved image paths
        """
        import base64
        import re

        saved_paths = []

        for idx, base64_img in enumerate(base64_images):
            # Extract the base64 data
            if "," in base64_img:
                # Data URI format: "data:image/jpeg;base64,..."
                match = re.match(r'data:image/(\w+);base64,', base64_img)
                if match:
                    format = match.group(1).upper()
                    if format == "JPG":
                        format = "JPEG"
                    base64_data = base64_img.split(",", 1)[1]
                else:
                    format = "JPEG"
                    base64_data = base64_img.split(",", 1)[1] if "," in base64_img else base64_img
            else:
                # Raw base64 format
                format = "JPEG"
                base64_data = base64_img

            # Decode and save
            image_bytes = base64.b64decode(base64_data)
            path = self.save_image_bytes(
                conversation_id,
                message_id,
                image_bytes,
                format
            )
            saved_paths.append(path)

        return saved_paths

    def convert_to_base64(self, image_path: str) -> str:
        """
        Convert image to base64 string

        Args:
            image_path: Path to image file

        Returns:
            Base64 encoded string with data URI prefix

        Example:
            >>> base64_str = storage.convert_to_base64("image.jpg")
            >>> print(base64_str[:50])
            data:image/jpeg;base64,/9j/4AAQSkZJRgABAQAA...
        """
        import base64

        # Get image format
        with Image.open(image_path) as img:
            format = img.format or "JPEG"

        # Read file and encode
        with open(image_path, "rb") as f:
            image_bytes = f.read()
            base64_str = base64.b64encode(image_bytes).decode('utf-8')

        return f"data:image/{format.lower()};base64,{base64_str}"

    def get_storage_stats(self) -> dict:
        """
        Get storage statistics

        Returns:
            Dictionary with storage information
        """
        total_size = 0
        image_count = 0
        conversation_count = 0

        conv_dir = self.base_dir / "conversations"

        if conv_dir.exists():
            for conv_path in conv_dir.iterdir():
                if conv_path.is_dir():
                    conversation_count += 1
                    for img_file in conv_path.iterdir():
                        if img_file.is_file():
                            image_count += 1
                            total_size += img_file.stat().st_size

        return {
            "total_conversations": conversation_count,
            "total_images": image_count,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2)
        }


# ============================================
# Singleton instance
# ============================================

# Global image storage instance
image_storage = ImageStorage()


# ============================================
# Convenience functions
# ============================================

def save_uploaded_images(
    conversation_id: str,
    message_id: int,
    uploaded_files: List[str]
) -> List[str]:
    """
    Convenience function to save uploaded images

    Args:
        conversation_id: Conversation UUID
        message_id: Message ID
        uploaded_files: List of uploaded file paths

    Returns:
        List of saved image paths
    """
    return image_storage.save_conversation_images(
        conversation_id,
        message_id,
        uploaded_files
    )


def cleanup_conversation_images(conversation_id: str) -> int:
    """
    Convenience function to clean up conversation images

    Args:
        conversation_id: Conversation UUID

    Returns:
        Number of images deleted
    """
    return image_storage.delete_conversation_images(conversation_id)
