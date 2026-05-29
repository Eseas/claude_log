"""Tracks how many transcript lines have been processed per session.

Mirrors the bash hook's `.state/{session_id}.lines` files so incremental
runs only append newly-added transcript lines.
"""

from pathlib import Path


class StateManager:
    """Reads/writes per-session processed-line counts."""

    def __init__(self, state_dir: Path):
        self.state_dir = Path(state_dir)

    def _state_file(self, session_id: str) -> Path:
        return self.state_dir / f"{session_id}.lines"

    def get_processed_lines(self, session_id: str) -> int:
        """Return the number of lines already processed (0 if no state yet)."""
        state_file = self._state_file(session_id)
        if not state_file.exists():
            return 0
        try:
            return int(state_file.read_text(encoding="utf-8").strip() or 0)
        except (ValueError, OSError):
            return 0

    def set_processed_lines(self, session_id: str, count: int) -> None:
        """Persist the processed-line count for a session."""
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._state_file(session_id).write_text(str(count), encoding="utf-8")
