"""Track which files have been processed to avoid duplicates."""

import json
import hashlib
from pathlib import Path
from typing import Dict
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ProcessedTracker:
    """Track which files have been processed to avoid duplicates."""

    def __init__(self, storage_path: Path):
        """Initialize processed file tracker.

        Args:
            storage_path: Path to JSON file for storing processed file info
        """
        self.storage_path = storage_path
        self.processed: Dict[str, dict] = self._load()

    def _load(self) -> Dict[str, dict]:
        """Load processed files registry.

        Returns:
            Dictionary mapping file paths to processing info
        """
        if not self.storage_path.exists():
            return {}

        try:
            with open(self.storage_path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.warning(f"Failed to load processed registry: {e}")
            return {}

    def _save(self) -> None:
        """Save processed files registry."""
        try:
            # Ensure directory exists
            self.storage_path.parent.mkdir(parents=True, exist_ok=True)

            with open(self.storage_path, "w") as f:
                json.dump(self.processed, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save processed registry: {e}")

    def is_processed(self, file_path: Path) -> bool:
        """Check if file has been processed.

        Uses file hash to detect if content has changed.

        Args:
            file_path: Path to file to check

        Returns:
            True if file has been processed and content hasn't changed
        """
        if not file_path.exists():
            return False

        file_key = str(file_path.absolute())

        if file_key not in self.processed:
            return False

        # Check if content has changed by comparing hashes
        try:
            current_hash = self._compute_hash(file_path)
            stored_hash = self.processed[file_key].get("hash")

            if current_hash != stored_hash:
                # Content changed, should reprocess
                logger.debug(f"File content changed: {file_path}")
                return False

            return True

        except Exception as e:
            logger.warning(f"Error checking if file processed: {e}")
            return False

    def mark_processed(self, file_path: Path) -> None:
        """Mark file as processed.

        Args:
            file_path: Path to file that was processed
        """
        try:
            file_key = str(file_path.absolute())
            file_hash = self._compute_hash(file_path)

            self.processed[file_key] = {
                "hash": file_hash,
                "processed_at": datetime.now().isoformat(),
                "size": file_path.stat().st_size,
            }

            self._save()
            logger.debug(f"Marked as processed: {file_path}")

        except Exception as e:
            logger.error(f"Failed to mark file as processed: {e}")

    def _compute_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file.

        Args:
            file_path: Path to file

        Returns:
            Hexadecimal hash string

        Raises:
            IOError if file cannot be read
        """
        sha256 = hashlib.sha256()

        with open(file_path, "rb") as f:
            while chunk := f.read(8192):
                sha256.update(chunk)

        return sha256.hexdigest()

    def clear(self) -> None:
        """Clear processed files registry."""
        self.processed = {}
        self._save()
        logger.info("Cleared processed files registry")

    def remove(self, file_path: Path) -> None:
        """Remove specific file from processed registry.

        Args:
            file_path: Path to file to remove
        """
        file_key = str(file_path.absolute())

        if file_key in self.processed:
            del self.processed[file_key]
            self._save()
            logger.debug(f"Removed from processed registry: {file_path}")
