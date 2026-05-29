"""Tests for the Python Stop-event hook (claude_log_organizer.hook)."""

import json
from datetime import datetime

import pytest

from claude_log_organizer.hook import tag_formatter as fmt
from claude_log_organizer.hook.state_manager import StateManager
from claude_log_organizer.hook.extractor import ConversationExtractor
from claude_log_organizer.parsers.session_parser import ClaudeSessionLogParser

FIXED_NOW = datetime(2026, 5, 28, 14, 30, 0)
SESSION_ID = "abc12345-6789-0000-1111-222233334444"


# --- JSONL entry builders ---

def user_text(text):
    return {"type": "user", "message": {"role": "user",
            "content": [{"type": "text", "text": text}]}}


def assistant_with(text=None, thinking=None, tools=None, usage=None):
    content = []
    if thinking:
        content.append({"type": "thinking", "thinking": thinking})
    if text:
        content.append({"type": "text", "text": text})
    for t in tools or []:
        content.append({"type": "tool_use", "name": t[0], "input": t[1]})
    msg = {"role": "assistant", "content": content}
    if usage:
        msg["usage"] = usage
    return {"type": "assistant", "message": msg}


class TestTagFormatterUser:
    def test_user_text_block(self):
        blocks = fmt.format_user_message({"content": [{"type": "text", "text": "수정해줘"}]})
        assert blocks == ["[USER] 수정해줘"]

    def test_user_string_content(self):
        blocks = fmt.format_user_message({"content": "plain string"})
        assert blocks == ["[USER] plain string"]

    def test_documents(self):
        blocks = fmt.format_user_message({"content": [
            {"type": "document", "title": "spec.md"},
            {"type": "document"},  # missing title → untitled
        ]})
        assert blocks == ["[DOCUMENT] spec.md\n[DOCUMENT] untitled"]

    def test_tool_result_truncated_to_300(self):
        long = "x" * 500
        blocks = fmt.format_user_message({"content": [
            {"type": "tool_result", "content": [{"type": "text", "text": long}]}
        ]})
        assert blocks[0] == "[TOOL_RESULT] " + "x" * 300

    def test_tool_result_string_content(self):
        blocks = fmt.format_user_message({"content": [
            {"type": "tool_result", "content": "ok done"}
        ]})
        assert blocks == ["[TOOL_RESULT] ok done"]

    def test_empty_message_no_blocks(self):
        assert fmt.format_user_message({"content": []}) == []


class TestTagFormatterAssistant:
    def test_thinking_joined(self):
        blocks = fmt.format_assistant_message({"content": [
            {"type": "thinking", "thinking": "first"},
            {"type": "thinking", "thinking": "second"},
        ]})
        assert blocks == ["[THINKING] first\n---\nsecond"]

    def test_text_block(self):
        blocks = fmt.format_assistant_message({"content": [{"type": "text", "text": "응답"}]})
        assert blocks == ["[ASSISTANT] 응답"]

    def test_tool_use_with_known_params(self):
        blocks = fmt.format_assistant_message({"content": [
            {"type": "tool_use", "name": "Read", "input": {"file_path": "/a/b.py"}},
            {"type": "tool_use", "name": "Bash", "input": {"command": "ls -la\nsecond line"}},
        ]})
        assert blocks == ["[TOOL] Read → /a/b.py\n[TOOL] Bash → ls -la"]

    def test_tool_use_unknown_has_no_arrow(self):
        blocks = fmt.format_assistant_message({"content": [
            {"type": "tool_use", "name": "TodoWrite", "input": {"todos": []}},
        ]})
        assert blocks == ["[TOOL] TodoWrite"]

    def test_usage_block(self):
        blocks = fmt.format_assistant_message({
            "content": [],
            "usage": {"input_tokens": 100, "cache_read_input_tokens": 50,
                      "cache_creation_input_tokens": 20, "output_tokens": 30},
        })
        assert blocks == ["[USAGE] input:100 cache_read:50 cache_write:20 output:30"]

    def test_usage_missing_fields_default_zero(self):
        blocks = fmt.format_assistant_message({"content": [], "usage": {"input_tokens": 5}})
        assert blocks == ["[USAGE] input:5 cache_read:0 cache_write:0 output:0"]

    def test_block_order_thinking_text_tool_usage(self):
        blocks = fmt.format_assistant_message(assistant_with(
            text="t", thinking="th", tools=[("Read", {"file_path": "/x"})],
            usage={"input_tokens": 1},
        )["message"])
        assert blocks[0].startswith("[THINKING]")
        assert blocks[1].startswith("[ASSISTANT]")
        assert blocks[2].startswith("[TOOL]")
        assert blocks[3].startswith("[USAGE]")


class TestTagFormatterSnapshotCompact:
    def test_snapshot_counts_files(self):
        entry = {"type": "file-history-snapshot",
                 "snapshot": {"trackedFileBackups": {"a": 1, "b": 2}}}
        assert fmt.format_snapshot(entry) == ["[SNAPSHOT] 2 files tracked"]

    def test_snapshot_empty_no_output(self):
        entry = {"type": "file-history-snapshot", "snapshot": {"trackedFileBackups": {}}}
        assert fmt.format_snapshot(entry) == []

    def test_compact_boundary(self):
        assert fmt.format_compact({"type": "system", "subtype": "compact_boundary"}) is True
        assert fmt.format_compact({"type": "system", "subtype": "other"}) is False


class TestStateManager:
    def test_zero_when_no_state(self, tmp_path):
        sm = StateManager(tmp_path / ".state")
        assert sm.get_processed_lines(SESSION_ID) == 0

    def test_roundtrip(self, tmp_path):
        sm = StateManager(tmp_path / ".state")
        sm.set_processed_lines(SESSION_ID, 42)
        assert sm.get_processed_lines(SESSION_ID) == 42

    def test_corrupt_state_returns_zero(self, tmp_path):
        sm = StateManager(tmp_path / ".state")
        sm.state_dir.mkdir(parents=True)
        (sm.state_dir / f"{SESSION_ID}.lines").write_text("not a number")
        assert sm.get_processed_lines(SESSION_ID) == 0


def _write_transcript(tmp_path, entries):
    path = tmp_path / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")
    return path


class TestExtractor:
    def test_no_transcript_returns_none(self, tmp_path):
        ex = ConversationExtractor(str(tmp_path / "missing.jsonl"), SESSION_ID,
                                   str(tmp_path), now=FIXED_NOW)
        assert ex.run() is None

    def test_writes_log_with_header(self, tmp_path):
        transcript = _write_transcript(tmp_path, [user_text("안녕하세요 작업 요청")])
        ex = ConversationExtractor(str(transcript), SESSION_ID, str(tmp_path), now=FIXED_NOW)
        log = ex.run()
        assert log is not None and log.exists()
        content = log.read_text(encoding="utf-8")
        assert "=== Claude Code Session Log ===" in content
        assert f"Session ID: {SESSION_ID}" in content
        assert "Lines: 1-1 of 1" in content
        assert "[USER] 안녕하세요 작업 요청" in content

    def test_log_filename_uses_timestamp_and_session(self, tmp_path):
        transcript = _write_transcript(tmp_path, [user_text("요청입니다")])
        log = ConversationExtractor(str(transcript), SESSION_ID, str(tmp_path),
                                    now=FIXED_NOW).run()
        assert log.name == f"2026-05-28_143000_{SESSION_ID}.log"

    def test_incremental_only_new_lines(self, tmp_path):
        transcript = _write_transcript(tmp_path, [user_text("첫 번째 요청 메시지")])
        ex1 = ConversationExtractor(str(transcript), SESSION_ID, str(tmp_path), now=FIXED_NOW)
        ex1.run()
        # Append a second line
        with transcript.open("a", encoding="utf-8") as f:
            f.write(json.dumps(assistant_with(text="두 번째 응답입니다")) + "\n")
        ex2 = ConversationExtractor(str(transcript), SESSION_ID, str(tmp_path), now=FIXED_NOW)
        log2 = ex2.run()
        content = log2.read_text(encoding="utf-8")
        assert "Lines: 2-2 of 2" in content
        assert "[ASSISTANT] 두 번째 응답입니다" in content
        assert "첫 번째 요청" not in content  # not re-emitted

    def test_no_new_lines_returns_none(self, tmp_path):
        transcript = _write_transcript(tmp_path, [user_text("한 번만 처리할 요청")])
        ConversationExtractor(str(transcript), SESSION_ID, str(tmp_path), now=FIXED_NOW).run()
        again = ConversationExtractor(str(transcript), SESSION_ID, str(tmp_path),
                                      now=FIXED_NOW).run()
        assert again is None

    def test_compact_and_snapshot_rendering(self, tmp_path):
        transcript = _write_transcript(tmp_path, [
            {"type": "system", "subtype": "compact_boundary"},
            {"type": "file-history-snapshot", "snapshot": {"trackedFileBackups": {"a": 1}}},
        ])
        log = ConversationExtractor(str(transcript), SESSION_ID, str(tmp_path),
                                    now=FIXED_NOW).run()
        content = log.read_text(encoding="utf-8")
        assert "[COMPACT] === Context compression ===" in content
        assert "[SNAPSHOT] 1 files tracked" in content

    def test_output_is_parseable_by_session_parser(self, tmp_path):
        """The whole point: hook output must round-trip through the parser."""
        transcript = _write_transcript(tmp_path, [
            user_text("main.py 파일을 수정해줘"),
            assistant_with(
                text="수정하겠습니다",
                tools=[("Edit", {"file_path": "/proj/main.py"})],
                usage={"input_tokens": 1500, "cache_read_input_tokens": 500,
                       "cache_creation_input_tokens": 200, "output_tokens": 800},
            ),
        ])
        log = ConversationExtractor(str(transcript), SESSION_ID, str(tmp_path),
                                    now=FIXED_NOW).run()
        task = ClaudeSessionLogParser().parse(log)
        assert task.task_id == SESSION_ID
        assert task.metadata["user_message_count"] == 1
        assert task.metadata["tool_use_count"] == 1
        assert "/proj/main.py" in task.files_modified
        assert task.token_usage.total_tokens == 3000
