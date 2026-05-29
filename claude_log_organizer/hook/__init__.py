"""Stop-event hook logic: convert Claude Code JSONL transcripts into .log files.

This package is intentionally stdlib-only so the hook can run in any
environment (including as a global hook across projects) without third-party
dependencies such as `jq`.
"""

from claude_log_organizer.hook.extractor import ConversationExtractor

__all__ = ["ConversationExtractor"]
