"""Routes file events to appropriate processors."""

import re
import logging
import time
import threading
from pathlib import Path
from typing import Optional, Dict

from claude_log_organizer.parsers.parser_factory import ParserFactory
from claude_log_organizer.generators.markdown_generator import MarkdownGenerator
from claude_log_organizer.storage.processed_tracker import ProcessedTracker
from claude_log_organizer.config import Config

logger = logging.getLogger(__name__)


class InvalidFileFormatError(Exception):
    """Raised when file format is invalid."""

    pass


class ParsingError(Exception):
    """Raised when parsing fails."""

    pass


class EventDispatcher:
    """Routes file events to appropriate processors."""

    def __init__(
        self,
        parser_factory: ParserFactory,
        generator: MarkdownGenerator,
        tracker: ProcessedTracker,
        config: Config,
    ):
        """Initialize event dispatcher.

        Args:
            parser_factory: Factory for creating parsers
            generator: Markdown generator
            tracker: Processed file tracker
            config: Configuration object
        """
        self.parser_factory = parser_factory
        self.generator = generator
        self.tracker = tracker
        self.config = config

        # Debouncing: wait N seconds after last modification before processing
        self.debounce_delay = config.get("watch.debounce_delay", 3.0)
        self.pending_timers: Dict[str, threading.Timer] = {}

    def dispatch_file_event(self, file_path: Path, event_type: str) -> None:
        """Handle file creation/modification events.

        Both created and modified events use debouncing to wait for file writing to complete.

        Args:
            file_path: Path to the file
            event_type: Type of event ('created' or 'modified')
        """
        # Apply debouncing to both created and modified events
        # This ensures we wait for file writing to complete before processing
        if event_type == "created":
            logger.info(f"New file detected: {file_path}")

        # Use debouncing for both events
        self._process_with_debounce(file_path)

    def _process_new_file(self, file_path: Path) -> None:
        """Process newly created log file.

        Args:
            file_path: Path to log file
        """
        try:
            # Validate file
            if not self._validate_file(file_path):
                logger.warning(f"File validation failed: {file_path}")
                return

            # Check if already processed
            if self.tracker.is_processed(file_path):
                logger.info(f"File already processed: {file_path}")
                return

            # Extract task ID from filename
            task_id = self._extract_task_id(file_path)
            if not task_id:
                logger.error(f"Could not extract task ID from: {file_path}")
                return

            # Get appropriate parser
            try:
                parser = self.parser_factory.get_parser(file_path)
            except ValueError as e:
                logger.error(f"No parser available: {e}")
                return

            # Parse log file
            logger.info(f"Parsing: {file_path}")
            task_data = parser.parse(file_path)

            # Generate output path
            output_path = self._get_output_path(task_id)

            # Check if output already exists and overwrite is disabled
            if output_path.exists() and not self.config.get("output.overwrite", False):
                logger.warning(
                    f"Output file already exists (overwrite disabled): {output_path}"
                )
                # Still mark as processed to avoid repeated warnings
                self.tracker.mark_processed(file_path)
                return

            # Generate markdown
            self.generator.generate(task_data, output_path)

            # Mark as processed
            self.tracker.mark_processed(file_path)

            logger.info(f"✓ Generated: {output_path}")

        except InvalidFileFormatError as e:
            logger.error(f"Invalid file format {file_path}: {e}")
            # Don't mark as processed

        except ParsingError as e:
            logger.error(f"Parsing failed {file_path}: {e}")
            # Mark as processed to avoid repeated failures
            self.tracker.mark_processed(file_path)

        except IOError as e:
            logger.error(f"IO error {file_path}: {e}")
            # Don't mark as processed, might be temporary

        except Exception as e:
            logger.exception(f"Unexpected error processing {file_path}: {e}")
            # Don't mark as processed

    def _process_with_debounce(self, file_path: Path) -> None:
        """Process file with debouncing.

        Waits for file to stabilize (no modifications for N seconds) before processing.
        This prevents repeated processing while file is still being written.

        Applied to both newly created and modified files.

        Args:
            file_path: Path to log file
        """
        file_key = str(file_path.absolute())

        # Cancel existing timer if any
        if file_key in self.pending_timers:
            self.pending_timers[file_key].cancel()
            logger.debug(f"Debouncing: resetting timer for {file_path.name}")

        # Create new timer to process after delay
        def delayed_process():
            # Remove timer from pending
            if file_key in self.pending_timers:
                del self.pending_timers[file_key]

            # Check if file needs reprocessing
            if self.tracker.is_processed(file_path):
                # Hash matches, no need to reprocess
                logger.debug(f"File unchanged after debounce: {file_path.name}")
                return

            # File is new or content changed
            logger.info(f"File stabilized, processing: {file_path.name}")
            self._process_new_file(file_path)

        timer = threading.Timer(self.debounce_delay, delayed_process)
        self.pending_timers[file_key] = timer
        timer.start()

    def _validate_file(self, file_path: Path) -> bool:
        """Validate file before processing.

        Args:
            file_path: Path to file

        Returns:
            True if file is valid

        Raises:
            InvalidFileFormatError if file is invalid
        """
        # Check if file exists
        if not file_path.exists():
            raise InvalidFileFormatError(f"File does not exist: {file_path}")

        # Check if file is readable
        if not file_path.is_file():
            raise InvalidFileFormatError(f"Not a regular file: {file_path}")

        # Check minimum file size (at least 10 bytes)
        if file_path.stat().st_size < 10:
            logger.warning(f"File too small: {file_path}")
            return False

        # Check maximum file size (100MB)
        max_size = 100 * 1024 * 1024
        if file_path.stat().st_size > max_size:
            logger.warning(f"File too large: {file_path}")
            return False

        return True

    def _extract_task_id(self, file_path: Path) -> Optional[str]:
        """Extract task ID from filename.

        Args:
            file_path: Path to log file

        Returns:
            Task ID or None if not found

        Example:
            conversation-task-20260212-130624.log -> 20260212-130624
        """
        # Try to match conversation-task-{id}.log pattern
        match = re.search(r"conversation-task-(.+?)\.log", file_path.name)
        if match:
            return match.group(1)

        # Try to match task-{id} pattern
        match = re.search(r"task-(.+?)[-.]", file_path.name)
        if match:
            return match.group(1)

        # Fallback: use filename without extension
        return file_path.stem

    def _get_output_path(self, task_id: str) -> Path:
        """Get output path for task markdown.

        Args:
            task_id: Task identifier

        Returns:
            Path to output markdown file
        """
        output_dir = Path(self.config.get("output.directory", "./tasks"))
        filename_pattern = self.config.get(
            "output.filename_pattern", "task-{task_id}.md"
        )

        filename = filename_pattern.format(task_id=task_id)
        return output_dir / filename
