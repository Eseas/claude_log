"""Factory for creating appropriate parsers."""

from pathlib import Path
from typing import List

from claude_log_organizer.parsers.base_parser import BaseLogParser
from claude_log_organizer.parsers.session_parser import ClaudeSessionLogParser
from claude_log_organizer.parsers.conversation_parser import ConversationLogParser
from claude_log_organizer.parsers.timeline_parser import TimelineLogParser


class ParserFactory:
    """Factory for creating appropriate parsers."""

    def __init__(self):
        """Initialize parser factory with default parsers."""
        self.parsers: List[BaseLogParser] = [
            ClaudeSessionLogParser(),  # Try session parser first (more specific)
            ConversationLogParser(),
            TimelineLogParser(),
        ]

    def get_parser(self, file_path: Path) -> BaseLogParser:
        """Select appropriate parser for file.

        Args:
            file_path: Path to log file

        Returns:
            Parser instance that can handle the file

        Raises:
            ValueError if no parser can handle the file
        """
        for parser in self.parsers:
            if parser.can_parse(file_path):
                return parser

        raise ValueError(f"No parser found for: {file_path}")

    def register_parser(self, parser: BaseLogParser) -> None:
        """Register custom parser.

        Args:
            parser: Parser instance to register
        """
        self.parsers.append(parser)

    def unregister_parser(self, parser_class: type) -> None:
        """Unregister parser by class.

        Args:
            parser_class: Parser class to remove
        """
        self.parsers = [p for p in self.parsers if not isinstance(p, parser_class)]
