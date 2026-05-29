"""Orchestrates JSONL transcript → .log conversion for the Stop hook.

Incremental: each run appends only transcript lines not seen before, writing
them to a fresh timestamped .log file. Stdlib-only (no jq, no third-party deps).
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from claude_log_organizer.hook import tag_formatter as fmt
from claude_log_organizer.hook.state_manager import StateManager

HOOK_PROMPT_MAX_CHARS = 100


class ConversationExtractor:
    """Converts a Claude Code transcript into an incremental .log file."""

    def __init__(self, transcript_path: str, session_id: str, project_dir: str,
                 now: Optional[datetime] = None):
        self.transcript_path = Path(transcript_path) if transcript_path else None
        self.session_id = session_id
        self.project_dir = project_dir
        self._now = now  # injectable for tests

        self.log_dir = Path(project_dir) / ".claude" / "logs"
        self.state = StateManager(self.log_dir / ".state")

    def run(self) -> Optional[Path]:
        """Process the transcript. Returns the written log path, or None if no-op."""
        if not self.transcript_path or not self.transcript_path.exists():
            return None

        processed = self.state.get_processed_lines(self.session_id)
        lines = self._read_lines()
        total = len(lines)
        if total <= processed:
            return None

        now = self._now or datetime.now()
        self.log_dir.mkdir(parents=True, exist_ok=True)
        log_file = self.log_dir / f"{now.strftime('%Y-%m-%d_%H%M%S')}_{self.session_id}.log"

        parts: List[str] = [self._header(processed, total, now)]

        if processed == 0:
            parts.append(self._hook_contexts())

        for raw in lines[processed:]:
            parts.append(self._render_line(raw))

        log_file.write_text("".join(parts), encoding="utf-8")
        self.state.set_processed_lines(self.session_id, total)
        return log_file

    # --- internals ---

    def _read_lines(self) -> List[str]:
        raw = self.transcript_path.read_text(encoding="utf-8", errors="replace")
        lines = raw.split("\n")
        if lines and lines[-1] == "":
            lines.pop()  # match `wc -l` semantics for trailing newline
        return lines

    def _header(self, processed: int, total: int, now: datetime) -> str:
        return (
            "=== Claude Code Session Log ===\n"
            f"Session ID: {self.session_id}\n"
            f"Project-Root-Path: {self.project_dir}\n"
            f"Saved at: {now.strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"Lines: {processed + 1}-{total} of {total}\n"
            "================================\n"
            "\n"
        )

    def _hook_contexts(self) -> str:
        ctx_file = Path.home() / ".claude" / "hook-contexts" / f"{self.session_id}.jsonl"
        if not ctx_file.exists():
            return ""

        out = ["--- Hook Contexts (UserPromptSubmit) ---\n"]
        for line in ctx_file.read_text(encoding="utf-8", errors="replace").split("\n"):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            ts = entry.get("timestamp") or ""
            prompt = (entry.get("prompt") or "")[:HOOK_PROMPT_MAX_CHARS]
            context = entry.get("context") or ""
            out.append(f"[HOOK {ts}] prompt: {prompt}...\n")
            out.append(f"  context: {context}\n")
            out.append("\n")
        out.append("--- End Hook Contexts ---\n")
        out.append("\n")

        try:
            ctx_file.unlink()
        except OSError:
            pass
        return "".join(out)

    def _render_line(self, raw: str) -> str:
        if not raw.strip():
            return ""
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            return ""

        entry_type = entry.get("type")
        if entry_type == "user":
            return self._blocks(fmt.format_user_message(entry.get("message")))
        if entry_type == "assistant":
            return self._blocks(fmt.format_assistant_message(entry.get("message")))
        if entry_type == "file-history-snapshot":
            snapshot = fmt.format_snapshot(entry)
            # Snapshot lines have no trailing blank line (matches bash hook).
            return "".join(f"{line}\n" for line in snapshot)
        if entry_type == "system" and fmt.format_compact(entry):
            return "\n[COMPACT] === Context compression ===\n\n"
        return ""

    @staticmethod
    def _blocks(blocks: List[str]) -> str:
        """Each block is followed by a blank line, mirroring `echo x; echo ""`."""
        return "".join(f"{block}\n\n" for block in blocks)
