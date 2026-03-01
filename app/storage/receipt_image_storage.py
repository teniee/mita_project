"""
Receipt Image Storage Service
Handles persistent storage of receipt images with automatic cleanup.
"""

import shutil
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.core.logger import get_logger

logger = get_logger(__name__)


class ReceiptImageStorage:
    """
    Service for storing and retrieving receipt images.
    Supports local filesystem storage with automatic cleanup.
    """

    def __init__(self, base_path: str = "/app/data/receipts"):
        """
        Initialize receipt image storage.

        Args:
            base_path: Base directory for storing receipt images
        """
        self.base_path = Path(base_path)
        self.base_path.mkdir(parents=True, exist_ok=True)

    def save_image(
        self,
        temp_path: str,
        user_id: int,
        job_id: str
    ) -> tuple[str, str]:
        """
        Save receipt image to persistent storage.

        Args:
            temp_path: Path to temporary uploaded file
            user_id: User ID
            job_id: OCR job ID

        Returns:
            Tuple of (storage_path, image_url)
        """
        try:
            # Create user directory
            user_dir = self.base_path / f"user_{user_id}"
            user_dir.mkdir(parents=True, exist_ok=True)

            # Generate unique filename
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            file_extension = Path(temp_path).suffix or ".jpg"
            filename = f"{job_id}_{timestamp}{file_extension}"

            # Save file
            storage_path = user_dir / filename
            shutil.copy2(temp_path, storage_path)

            # Generate URL (relative to /data/receipts)
            image_url = f"/receipts/user_{user_id}/{filename}"

            logger.info(f"Saved receipt image: {storage_path}")
            return str(storage_path), image_url

        except Exception as e:
            logger.error(f"Failed to save receipt image: {e}")
            raise

    def get_image_path(self, user_id: int, filename: str) -> Optional[str]:
        """
        Get full path to receipt image.

        Args:
            user_id: User ID
            filename: Image filename

        Returns:
            Full path to image file, or None if not found
        """
        image_path = self.base_path / f"user_{user_id}" / filename

        if image_path.exists() and image_path.is_file():
            return str(image_path)

        return None

    def delete_image(self, storage_path: str) -> bool:
        """
        Delete receipt image from storage.

        Args:
            storage_path: Full path to image file

        Returns:
            True if deleted successfully, False otherwise
        """
        try:
            path = Path(storage_path)
            if path.exists() and path.is_file():
                path.unlink()
                logger.info(f"Deleted receipt image: {storage_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete receipt image: {e}")
            return False

    def cleanup_old_images(self, days: int = 90) -> int:
        """
        Clean up receipt images older than specified days.

        Args:
            days: Delete images older than this many days

        Returns:
            Number of deleted images
        """
        deleted_count = 0
        cutoff_date = datetime.now() - timedelta(days=days)

        try:
            for user_dir in self.base_path.iterdir():
                if not user_dir.is_dir():
                    continue

                for image_file in user_dir.iterdir():
                    if not image_file.is_file():
                        continue

                    # Check file modification time
                    mtime = datetime.fromtimestamp(image_file.stat().st_mtime)
                    if mtime < cutoff_date:
                        image_file.unlink()
                        deleted_count += 1
                        logger.debug(f"Deleted old receipt image: {image_file}")

            logger.info(f"Cleaned up {deleted_count} old receipt images (older than {days} days)")
            return deleted_count

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            return deleted_count

    def get_user_images(self, user_id: int, limit: int = 100) -> list[dict]:
        """
        Get list of receipt images for a user.

        Args:
            user_id: User ID
            limit: Maximum number of images to return

        Returns:
            List of image metadata dictionaries
        """
        user_dir = self.base_path / f"user_{user_id}"

        if not user_dir.exists():
            return []

        images = []
        for image_file in sorted(user_dir.iterdir(), key=lambda f: f.stat().st_mtime, reverse=True):
            if not image_file.is_file():
                continue

            stat = image_file.stat()
            images.append({
                "filename": image_file.name,
                "path": str(image_file),
                "url": f"/receipts/user_{user_id}/{image_file.name}",
                "size": stat.st_size,
                "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
            })

            if len(images) >= limit:
                break

        return images

    def get_storage_stats(self) -> dict:
        """
        Get storage statistics.

        Returns:
            Dictionary with storage statistics
        """
        total_size = 0
        total_files = 0
        user_count = 0

        for user_dir in self.base_path.iterdir():
            if not user_dir.is_dir():
                continue

            user_count += 1
            for image_file in user_dir.iterdir():
                if image_file.is_file():
                    total_files += 1
                    total_size += image_file.stat().st_size

        return {
            "total_users": user_count,
            "total_files": total_files,
            "total_size_bytes": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "base_path": str(self.base_path),
        }


# Global instance
_storage_instance: Optional[ReceiptImageStorage] = None


def get_receipt_storage() -> ReceiptImageStorage:
    """
    Get or create global receipt storage instance.

    Returns:
        ReceiptImageStorage instance
    """
    global _storage_instance
    if _storage_instance is None:
        _storage_instance = ReceiptImageStorage()
    return _storage_instance
