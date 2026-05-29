#!/usr/bin/env python3
"""Claude Code Stop-event hook: convert JSONL transcript → incremental .log.

Python replacement for save-conversation-log.sh. Stdlib-only (no jq).

Reads a JSON context object from stdin with keys: transcript_path, session_id,
cwd. The extraction logic lives in `claude_log_organizer.hook` so it can be
unit-tested; this launcher just makes that package importable and runs it.

Fails silently (exit 0) on any error so a hook problem never blocks Claude Code.
"""

import json
import sys
from pathlib import Path


def _make_importable(project_dir: str) -> None:
    """Ensure `claude_log_organizer` can be imported regardless of cwd."""
    candidates = [
        project_dir,
        str(Path(__file__).resolve().parent.parent.parent),  # project-local hook
    ]
    for path in candidates:
        if path and path not in sys.path and (Path(path) / "claude_log_organizer").is_dir():
            sys.path.insert(0, path)


def main() -> None:
    try:
        raw = sys.stdin.read()
        context = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, OSError):
        return

    transcript_path = context.get("transcript_path", "")
    session_id = context.get("session_id", "")
    project_dir = context.get("cwd", "")
    if not (transcript_path and session_id and project_dir):
        return

    _make_importable(project_dir)
    try:
        from claude_log_organizer.hook import ConversationExtractor
    except ImportError:
        return

    try:
        ConversationExtractor(
            transcript_path=transcript_path,
            session_id=session_id,
            project_dir=project_dir,
        ).run()
    except Exception:
        # Never let a hook failure surface to the user.
        return


if __name__ == "__main__":
    main()
    sys.exit(0)
