"""Main application orchestrator."""

import logging
from pathlib import Path
import fnmatch
from typing import Optional

from claude_log_organizer.config import Config
from claude_log_organizer.watcher.file_watcher import ConversationLogWatcher
from claude_log_organizer.watcher.event_dispatcher import EventDispatcher
from claude_log_organizer.parsers.parser_factory import ParserFactory
from claude_log_organizer.generators.markdown_generator import MarkdownGenerator
from claude_log_organizer.storage.processed_tracker import ProcessedTracker

logger = logging.getLogger(__name__)


class LogOrganizerApp:
    """Main application orchestrator."""

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize log organizer application.

        Args:
            config_path: Path to configuration file (optional)
        """
        # Load configuration
        self.config = Config(config_path)

        # Setup logging
        self._setup_logging()

        # Get template directory
        template_dir = Path(self.config.get("templates.directory", "./templates"))

        # Make template directory absolute if relative
        if not template_dir.is_absolute():
            # Relative to current working directory
            template_dir = Path.cwd() / template_dir

        # Initialize components
        self.parser_factory = ParserFactory()
        self.generator = MarkdownGenerator(template_dir=template_dir, config=self.config)

        # Get processed log path
        processed_log_path = Path(
            self.config.get("storage.processed_log", ".processed.json")
        )

        self.tracker = ProcessedTracker(storage_path=processed_log_path)

        self.dispatcher = EventDispatcher(
            parser_factory=self.parser_factory,
            generator=self.generator,
            tracker=self.tracker,
            config=self.config,
        )

        self.watcher = ConversationLogWatcher(self.config)

    def _setup_logging(self) -> None:
        """Configure logging."""
        log_level = self.config.get("logging.level", "INFO")
        log_file = self.config.get("logging.file", "organizer.log")
        log_format = self.config.get(
            "logging.format", "[%(asctime)s] [%(levelname)s] %(message)s"
        )

        # Convert string level to logging constant
        level = getattr(logging, log_level.upper(), logging.INFO)

        # Configure root logger
        logging.basicConfig(
            level=level,
            format=log_format,
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler(),
            ],
        )

    def watch(self) -> None:
        """Start watching for new log files.

        This is a blocking operation that will run until interrupted.
        """
        # Get watch directories (support both old and new config format)
        watch_dirs = self.config.get("watch.directories")
        if watch_dirs is None:
            # Backward compatibility
            single_dir = self.config.get("watch.directory", "./logs")
            watch_dirs = [single_dir]
        elif isinstance(watch_dirs, str):
            watch_dirs = [watch_dirs]

        output_dir = Path(self.config.get("output.directory", "./tasks"))

        logger.info("=" * 60)
        logger.info("Starting Claude Log Organizer in watch mode")
        logger.info("=" * 60)

        # Display all watch directories
        if len(watch_dirs) == 1:
            logger.info(f"Watching: {Path(watch_dirs[0]).absolute()}")
        else:
            logger.info(f"Watching {len(watch_dirs)} directories:")
            for i, watch_dir in enumerate(watch_dirs, 1):
                logger.info(f"  [{i}] {Path(watch_dir).absolute()}")

        logger.info(f"Output: {output_dir.absolute()}")
        logger.info(f"Patterns: {self.config.get('watch.patterns')}")
        logger.info("Press Ctrl+C to stop")
        logger.info("=" * 60)

        try:
            self.watcher.start(callback=self.dispatcher.dispatch_file_event)
        except KeyboardInterrupt:
            logger.info("Stopping log organizer...")
            self.watcher.stop()
            logger.info("Stopped")

    def process_file(self, file_path: Path) -> None:
        """Process a single log file.

        Args:
            file_path: Path to log file to process
        """
        logger.info(f"Processing: {file_path}")

        if not file_path.exists():
            logger.error(f"File not found: {file_path}")
            return

        self.dispatcher.dispatch_file_event(file_path, "created")

    def process_directory(self, directory: Path, force: bool = False) -> None:
        """Process all log files in directory.

        Args:
            directory: Directory to process
            force: If True, reprocess all files even if already processed
        """
        if not directory.exists():
            logger.error(f"Directory not found: {directory}")
            return

        patterns = self.config.get("watch.patterns", ["conversation-task-*.log"])

        logger.info(f"Scanning directory: {directory}")
        logger.info(f"Patterns: {patterns}")

        # Find all matching files
        matching_files = []
        for file_path in directory.rglob("*") if self.config.get("watch.recursive") else directory.glob("*"):
            if file_path.is_file():
                if any(fnmatch.fnmatch(file_path.name, pattern) for pattern in patterns):
                    matching_files.append(file_path)

        logger.info(f"Found {len(matching_files)} matching files")

        # Process each file
        for i, file_path in enumerate(matching_files, 1):
            logger.info(f"[{i}/{len(matching_files)}] Processing: {file_path.name}")

            if force:
                # Remove from processed tracker to force reprocessing
                self.tracker.remove(file_path)

            self.dispatcher.dispatch_file_event(file_path, "created")

        logger.info(f"Completed processing {len(matching_files)} files")
