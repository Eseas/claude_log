"""Routes file events to appropriate processors."""

import logging
import threading
from pathlib import Path
from typing import Dict

from claude_log_organizer.parsers.parser_factory import ParserFactory
from claude_log_organizer.generators.markdown_generator import MarkdownGenerator
from claude_log_organizer.storage.processed_tracker import ProcessedTracker
from claude_log_organizer.config import Config
from claude_log_organizer.pipeline import Pipeline, PipelineContext, build_default_pipeline
from claude_log_organizer.pipeline.base import InvalidFileFormatError, ParsingError

logger = logging.getLogger(__name__)

# Re-exported for backward compatibility (previously defined here).
__all__ = ["EventDispatcher", "InvalidFileFormatError", "ParsingError"]


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

        # Processing pipeline (extensible: add_step to insert custom stages)
        self.pipeline = build_default_pipeline()

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
        """Process a newly created/changed log file through the pipeline.

        Error-handling semantics are preserved from the original flow:
        ParsingError marks the file processed (avoid repeated failures); all
        other errors leave it unmarked so it can be retried.

        Args:
            file_path: Path to log file
        """
        ctx = PipelineContext(
            file_path=file_path,
            config=self.config,
            parser_factory=self.parser_factory,
            generator=self.generator,
            tracker=self.tracker,
        )

        try:
            self.pipeline.execute(ctx)

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
