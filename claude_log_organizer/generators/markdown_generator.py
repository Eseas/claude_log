"""Generates markdown summaries from task data."""

from jinja2 import Environment, FileSystemLoader
from pathlib import Path
from datetime import datetime
import logging

from claude_log_organizer.models.task_data import TaskData
from claude_log_organizer.config import Config

logger = logging.getLogger(__name__)


class MarkdownGenerator:
    """Generates markdown summaries from task data."""

    def __init__(self, template_dir: Path, config: Config):
        """Initialize markdown generator.

        Args:
            template_dir: Directory containing Jinja2 templates
            config: Configuration object
        """
        self.template_dir = template_dir
        self.config = config

        # Initialize Jinja2 environment
        self.env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        self._register_filters()

    def generate(self, task_data: TaskData, output_path: Path) -> None:
        """Generate markdown file from task data.

        Args:
            task_data: TaskData object with extracted information
            output_path: Path where to save the markdown file

        Raises:
            Exception if generation fails
        """
        try:
            # Get template name from config
            template_name = self.config.get(
                "templates.default_template", "default.md.jinja2"
            )

            # Load template
            template = self.env.get_template(template_name)

            # Render template
            markdown_content = template.render(task=task_data.to_dict())

            # Ensure output directory exists
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Write to file
            output_path.write_text(markdown_content, encoding="utf-8")

            logger.info(f"Generated markdown: {output_path}")

        except Exception as e:
            logger.error(f"Failed to generate markdown: {e}")
            raise

    def _register_filters(self) -> None:
        """Register custom Jinja2 filters."""
        self.env.filters["format_timestamp"] = self._format_timestamp
        self.env.filters["status_emoji"] = self._status_emoji
        self.env.filters["truncate_text"] = self._truncate_text
        self.env.filters["format_seconds"] = self._format_seconds
        self.env.filters["format_number"] = self._format_number

    @staticmethod
    def _format_timestamp(timestamp: str) -> str:
        """Format timestamp for display.

        Args:
            timestamp: ISO format timestamp string

        Returns:
            Formatted timestamp string
        """
        if not timestamp:
            return "N/A"

        try:
            dt = datetime.fromisoformat(timestamp)
            return dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            return timestamp

    @staticmethod
    def _status_emoji(status: str) -> str:
        """Get emoji for status.

        Args:
            status: Status string

        Returns:
            Emoji character
        """
        emoji_map = {
            "completed": "✅",
            "failed": "❌",
            "in_progress": "⏳",
            "pending": "⏸️",
            "approved": "✅",
            "rejected": "❌",
            "waiting": "⏳",
            "unknown": "❓",
        }
        return emoji_map.get(status.lower(), "❓")

    @staticmethod
    def _truncate_text(text: str, length: int = 100) -> str:
        """Truncate long text.

        Args:
            text: Text to truncate
            length: Maximum length

        Returns:
            Truncated text
        """
        if not text:
            return ""

        if len(text) <= length:
            return text

        return text[:length] + "..."

    @staticmethod
    def _format_number(value: int) -> str:
        """Format number with comma separators.

        Args:
            value: Integer value

        Returns:
            Formatted string with commas
        """
        if value is None:
            return "0"
        return f"{int(value):,}"

    @staticmethod
    def _format_seconds(seconds: float) -> str:
        """Format seconds as human-readable duration.

        Args:
            seconds: Duration in seconds

        Returns:
            Formatted duration string
        """
        if seconds is None:
            return "N/A"

        total_seconds = int(seconds)

        if total_seconds < 60:
            return f"{total_seconds}s"
        elif total_seconds < 3600:
            minutes = total_seconds // 60
            secs = total_seconds % 60
            return f"{minutes}m {secs}s"
        else:
            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            return f"{hours}h {minutes}m"
