"""Configuration management for the log organizer."""

import logging
import yaml
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class Config:
    """Configuration management for the log organizer."""

    DEFAULT_CONFIG = {
        "watch": {
            # Support both single directory (string) and multiple directories (list)
            # Use ABSOLUTE PATHS for directories (relative paths will be resolved from CWD)
            "directories": [],  # Empty by default - must be configured by user
            "patterns": ["*.log"],
            "poll_interval": 1.0,
            "recursive": False,
        },
        "output": {
            "directory": "./tasks",  # Relative to current working directory
            "filename_pattern": "task-{task_id}.md",
            "overwrite": False,
        },
        "parsing": {
            "extract_code_snippets": True,
            "max_snippet_lines": 50,
            "extract_phases": True,
            "extract_decisions": True,
            "extract_file_changes": True,
        },
        "templates": {
            "directory": "./templates",
            "default_template": "default.md.jinja2",
        },
        "storage": {
            "processed_log": ".processed.json",
            "enable_cache": True,
        },
        "logging": {
            "level": "INFO",
            "file": "organizer.log",
            "format": "[%(asctime)s] [%(levelname)s] %(message)s",
        },
        "summarization": {
            "weekly_start": "monday",  # "monday" (월~일) or "sunday" (일~토)
        },
    }

    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration.

        Args:
            config_path: Path to YAML config file. If None or file doesn't exist,
                        uses default configuration.
        """
        self.config_path = config_path
        self.data = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from YAML file."""
        # Start with default config
        config = self._deep_copy(self.DEFAULT_CONFIG)

        # If config path is provided and exists, merge it
        if self.config_path and self.config_path.exists():
            try:
                with open(self.config_path, "r") as f:
                    user_config = yaml.safe_load(f)

                if user_config:
                    self._deep_merge(config, user_config)
            except Exception as e:
                logger.warning(
                    "Failed to load config from %s: %s. Using default configuration.",
                    self.config_path, e,
                )

        return config

    def _deep_copy(self, obj: Any) -> Any:
        """Create a deep copy of nested dictionaries."""
        if isinstance(obj, dict):
            return {key: self._deep_copy(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._deep_copy(item) for item in obj]
        else:
            return obj

    def _deep_merge(self, base: dict, update: dict) -> None:
        """Deep merge update into base dictionary.

        Args:
            base: Base dictionary to merge into
            update: Dictionary with updates
        """
        for key, value in update.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value

    def get(self, key_path: str, default: Any = None) -> Any:
        """Get config value using dot notation.

        Args:
            key_path: Path to config value using dots (e.g., 'watch.directory')
            default: Default value if key not found

        Returns:
            Configuration value or default

        Example:
            >>> config.get('watch.directory')
            './logs'
            >>> config.get('watch.patterns')
            ['conversation-task-*.log']
        """
        keys = key_path.split(".")
        value = self.data

        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default

        return value

    @classmethod
    def create_default(cls, output_path: Path) -> None:
        """Create default configuration file.

        Args:
            output_path: Path where to save the config file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w") as f:
            yaml.dump(
                cls.DEFAULT_CONFIG,
                f,
                default_flow_style=False,
                sort_keys=False,
                indent=2,
            )

        logger.debug("Created default configuration at: %s", output_path)
