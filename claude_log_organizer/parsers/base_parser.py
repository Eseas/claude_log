"""Abstract base class for log parsers."""

from abc import ABC, abstractmethod
from pathlib import Path
from claude_log_organizer.models.task_data import TaskData


class BaseLogParser(ABC):
    """Abstract base class for log parsers."""

    @abstractmethod
    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle the file.

        Args:
            file_path: Path to the log file

        Returns:
            True if this parser can handle the file
        """
        pass

    @abstractmethod
    def parse(self, file_path: Path) -> TaskData:
        """Parse log file and return structured data.

        Args:
            file_path: Path to the log file

        Returns:
            TaskData object with extracted information

        Raises:
            Exception if parsing fails
        """
        pass

    def _read_file(self, file_path: Path) -> str:
        """Read file with error handling.

        Args:
            file_path: Path to the file

        Returns:
            File contents as string

        Raises:
            IOError if file cannot be read
        """
        try:
            return file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Try with latin-1 encoding as fallback
            try:
                return file_path.read_text(encoding="latin-1")
            except Exception as e:
                raise IOError(f"Failed to read file {file_path}: {e}")
        except Exception as e:
            raise IOError(f"Failed to read file {file_path}: {e}")
