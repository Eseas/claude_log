"""Tests for log parsers (session, conversation, timeline) and the factory."""

from datetime import datetime
from pathlib import Path

import pytest

from claude_log_organizer.parsers.session_parser import ClaudeSessionLogParser
from claude_log_organizer.parsers.conversation_parser import ConversationLogParser
from claude_log_organizer.parsers.timeline_parser import TimelineLogParser
from claude_log_organizer.parsers.parser_factory import ParserFactory


class TestSessionParserCanParse:
    def test_matches_filename_pattern(self, write_log, sample_session_log):
        path = write_log(sample_session_log)
        assert ClaudeSessionLogParser().can_parse(path)

    def test_matches_header_without_filename(self, tmp_path, sample_session_log):
        path = tmp_path / "random_name.log"
        path.write_text(sample_session_log, encoding="utf-8")
        assert ClaudeSessionLogParser().can_parse(path)

    def test_rejects_unrelated_file(self, tmp_path):
        path = tmp_path / "notes.log"
        path.write_text("just some text", encoding="utf-8")
        assert not ClaudeSessionLogParser().can_parse(path)


class TestSessionParserParse:
    def test_extracts_session_id_from_header(self, write_log, sample_session_log, session_id):
        task = ClaudeSessionLogParser().parse(write_log(sample_session_log))
        assert task.task_id == session_id

    def test_extracts_timestamp(self, write_log, sample_session_log):
        task = ClaudeSessionLogParser().parse(write_log(sample_session_log))
        assert task.timestamp == datetime(2026, 5, 27, 14, 30, 0)

    def test_extracts_files_modified(self, write_log, sample_session_log):
        task = ClaudeSessionLogParser().parse(write_log(sample_session_log))
        assert "/Users/test/project/main.py" in task.files_modified

    def test_aggregates_token_usage(self, write_log, sample_session_log):
        task = ClaudeSessionLogParser().parse(write_log(sample_session_log))
        assert task.token_usage.total_tokens == 5700

    def test_metadata_counts(self, write_log, sample_session_log):
        task = ClaudeSessionLogParser().parse(write_log(sample_session_log))
        assert task.metadata["user_message_count"] == 1
        assert task.metadata["tool_use_count"] == 2
        assert task.metadata["assistant_response_count"] == 2
        assert task.metadata["has_thinking"] is True

    def test_status_completed(self, write_log, sample_session_log):
        task = ClaudeSessionLogParser().parse(write_log(sample_session_log))
        assert task.status == "completed"

    def test_referenced_documents(self, write_log, sample_session_log):
        task = ClaudeSessionLogParser().parse(write_log(sample_session_log))
        assert "design-spec.md" in task.referenced_documents

    def test_minimal_log_does_not_crash(self, write_log, minimal_session_log):
        task = ClaudeSessionLogParser().parse(write_log(minimal_session_log))
        assert task.token_usage is None
        assert task.metadata["tool_use_count"] == 0

    def test_session_id_falls_back_to_filename(self, tmp_path):
        # No "Session ID:" header → must read from filename
        content = "=== Claude Code Session Log ===\n\n[USER]\nhello there friend\n"
        path = tmp_path / "2026-05-27_143000_deadbeef-1234.log"
        path.write_text(content, encoding="utf-8")
        task = ClaudeSessionLogParser().parse(path)
        assert task.task_id == "deadbeef-1234"


class TestConversationParser:
    def test_can_parse_conversation_file(self, tmp_path):
        path = tmp_path / "conversation-task-123.log"
        path.write_text("content", encoding="utf-8")
        assert ConversationLogParser().can_parse(path)

    def test_rejects_non_conversation(self, tmp_path):
        path = tmp_path / "session.log"
        path.write_text("content", encoding="utf-8")
        assert not ConversationLogParser().can_parse(path)

    def test_extracts_task_id_from_filename(self, tmp_path):
        path = tmp_path / "conversation-task-20260212-130624.log"
        path.write_text("Summary: did things\ncompleted", encoding="utf-8")
        task = ConversationLogParser().parse(path)
        assert task.task_id == "20260212-130624"

    def test_status_detection(self, tmp_path):
        path = tmp_path / "conversation-x.log"
        path.write_text("The build failed with an error", encoding="utf-8")
        task = ConversationLogParser().parse(path)
        assert task.status == "failed"


class TestTimelineParser:
    def test_can_parse_timeline_file(self, tmp_path):
        path = tmp_path / "timeline-task.log"
        path.write_text("content", encoding="utf-8")
        assert TimelineLogParser().can_parse(path)

    def test_parses_phases_and_duration(self, tmp_path):
        content = (
            "[2026-05-27T14:00:00] [PHASE] validation_start\n"
            "[2026-05-27T14:05:00] [PHASE] implementation\n"
            "[2026-05-27T14:10:00] [PHASE] complete\n"
        )
        path = tmp_path / "timeline-task.log"
        path.write_text(content, encoding="utf-8")
        task = TimelineLogParser().parse(path)
        assert len(task.phases) == 3
        assert task.total_duration == 600.0  # 10 minutes
        assert task.status == "completed"

    def test_parses_checkpoints(self, tmp_path):
        content = "[2026-05-27T14:00:00] [CHECKPOINT] review (approved)\n"
        path = tmp_path / "timeline-task.log"
        path.write_text(content, encoding="utf-8")
        task = TimelineLogParser().parse(path)
        assert len(task.checkpoints) == 1
        assert task.checkpoints[0].status == "approved"


class TestParserFactory:
    def test_selects_session_parser(self, write_log, sample_session_log):
        path = write_log(sample_session_log)
        parser = ParserFactory().get_parser(path)
        assert isinstance(parser, ClaudeSessionLogParser)

    def test_selects_conversation_parser(self, tmp_path):
        path = tmp_path / "conversation-task-1.log"
        path.write_text("content", encoding="utf-8")
        parser = ParserFactory().get_parser(path)
        assert isinstance(parser, ConversationLogParser)

    def test_selects_timeline_parser(self, tmp_path):
        path = tmp_path / "timeline-task.log"
        path.write_text("content", encoding="utf-8")
        parser = ParserFactory().get_parser(path)
        assert isinstance(parser, TimelineLogParser)

    def test_raises_when_no_parser_matches(self, tmp_path):
        path = tmp_path / "unknown.txt"
        path.write_text("nothing", encoding="utf-8")
        with pytest.raises(ValueError):
            ParserFactory().get_parser(path)

    def test_register_custom_parser(self, tmp_path):
        factory = ParserFactory()
        initial = len(factory.parsers)
        factory.register_parser(ClaudeSessionLogParser())
        assert len(factory.parsers) == initial + 1

    def test_unregister_parser(self):
        factory = ParserFactory()
        factory.unregister_parser(TimelineLogParser)
        assert not any(isinstance(p, TimelineLogParser) for p in factory.parsers)
