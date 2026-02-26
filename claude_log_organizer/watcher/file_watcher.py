"""Monitors directory for conversation log files using watchdog."""

import time
import fnmatch
from pathlib import Path
from typing import Callable, List
import logging

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from claude_log_organizer.config import Config

logger = logging.getLogger(__name__)


class LogFileEventHandler(FileSystemEventHandler):
    """Event handler for log file creation/modification."""

    def __init__(
        self, patterns: List[str], callback: Callable[[Path, str], None]
    ):
        """Initialize event handler.

        Args:
            patterns: List of file patterns to match (e.g., ['*.log'])
            callback: Function to call with (file_path, event_type)
        """
        self.patterns = patterns
        self.callback = callback

    def on_created(self, event: FileSystemEvent) -> None:
        """Handle file creation event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        if self._matches_pattern(file_path):
            logger.info(f"New file detected: {file_path}")
            try:
                self.callback(file_path, "created")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")

    def on_modified(self, event: FileSystemEvent) -> None:
        """Handle file modification event.

        Args:
            event: File system event
        """
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        if self._matches_pattern(file_path):
            logger.debug(f"File modified: {file_path}")
            try:
                self.callback(file_path, "modified")
            except Exception as e:
                logger.error(f"Error processing file {file_path}: {e}")

    def _matches_pattern(self, file_path: Path) -> bool:
        """Check if file matches any of the patterns.

        Args:
            file_path: Path to file

        Returns:
            True if file matches any pattern
        """
        filename = file_path.name

        for pattern in self.patterns:
            if fnmatch.fnmatch(filename, pattern):
                return True

        return False


class ConversationLogWatcher:
    """Monitors multiple directories for conversation log files using watchdog."""

    def __init__(self, config: Config):
        """Initialize file watcher.

        Args:
            config: Configuration object
        """
        self.config = config

        # Support both old single directory and new multiple directories format
        directories = config.get("watch.directories")

        # Backward compatibility: check for old 'directory' config
        if directories is None or (isinstance(directories, list) and len(directories) == 0):
            single_dir = config.get("watch.directory")
            if single_dir:
                directories = [single_dir]
            else:
                # No directories configured
                directories = []

        # Handle case where directories is a string (convert to list)
        if isinstance(directories, str):
            directories = [directories]

        # Process paths: expand ~, then use absolute paths
        # Note: MUST use ABSOLUTE PATHS in config (~ will be expanded)
        self.watch_paths = []
        for d in directories:
            # First expand ~ to home directory
            path = Path(d).expanduser()

            # Then ensure it's absolute
            if not path.is_absolute():
                # Relative path - resolve from CWD (not recommended)
                path = path.absolute()

            self.watch_paths.append(path)

        self.patterns = config.get("watch.patterns", ["conversation-task-*.log"])
        self.recursive = config.get("watch.recursive", False)

        self.observers = []  # List of observers for multiple directories

    def start(self, callback: Callable[[Path, str], None]) -> None:
        """Start monitoring multiple directories for new log files.

        Args:
            callback: Function to call when file is created/modified
                     Signature: callback(file_path: Path, event_type: str)

        Raises:
            FileNotFoundError if watch directory doesn't exist
        """
        # Start monitoring each directory
        for watch_path in self.watch_paths:
            # Ensure watch directory exists
            if not watch_path.exists():
                watch_path.mkdir(parents=True, exist_ok=True)
                logger.info(f"Created watch directory: {watch_path}")

            # Create event handler for this directory
            event_handler = LogFileEventHandler(self.patterns, callback)

            # Create observer for this directory
            observer = Observer()
            observer.schedule(
                event_handler, str(watch_path), recursive=self.recursive
            )

            # Start observing
            observer.start()

            self.observers.append(observer)
            logger.info(f"Started watching: {watch_path}")

        logger.info(f"Total directories watching: {len(self.observers)}")
        logger.info(f"Patterns: {self.patterns}")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def stop(self) -> None:
        """Stop monitoring all directories."""
        for observer in self.observers:
            observer.stop()
            observer.join()
        logger.info(f"Stopped {len(self.observers)} file watcher(s)")

    def is_running(self) -> bool:
        """Check if any watcher is running.

        Returns:
            True if at least one watcher is running
        """
        return any(observer.is_alive() for observer in self.observers)
