"""Tests for shared extraction utilities (parsers/extraction.py)."""

from datetime import datetime

from claude_log_organizer.parsers import extraction


class TestExtractByTag:
    def test_extracts_user_messages(self, sample_session_log):
        users = extraction.extract_by_tag(sample_session_log, "user")
        assert len(users) == 1
        assert "main.py" in users[0]

    def test_extracts_assistant_messages(self, sample_session_log):
        responses = extraction.extract_by_tag(sample_session_log, "assistant")
        assert len(responses) == 2

    def test_unknown_tag_returns_empty(self, sample_session_log):
        assert extraction.extract_by_tag(sample_session_log, "nonexistent") == []

    def test_empty_content(self):
        assert extraction.extract_by_tag("", "user") == []


class TestExtractToolUses:
    def test_extracts_tool_name_and_action(self, sample_session_log):
        tools = extraction.extract_tool_uses(sample_session_log)
        assert len(tools) == 2
        assert tools[0]["tool"] == "Read"
        assert tools[1]["tool"] == "Edit"
        assert "/Users/test/project/main.py" in tools[0]["action"]

    def test_no_tools(self, minimal_session_log):
        assert extraction.extract_tool_uses(minimal_session_log) == []


class TestExtractCompactCount:
    def test_counts_compact_tags(self, session_log_with_compact):
        assert extraction.extract_compact_count(session_log_with_compact) == 2

    def test_zero_when_absent(self, sample_session_log):
        assert extraction.extract_compact_count(sample_session_log) == 0


class TestExtractTokenUsage:
    def test_aggregates_multiple_usage_tags(self, sample_session_log):
        tu = extraction.extract_token_usage(sample_session_log)
        assert tu is not None
        assert tu.input_tokens == 2700
        assert tu.output_tokens == 1400
        assert tu.cache_read_tokens == 1300
        assert tu.cache_write_tokens == 300
        assert tu.request_count == 2

    def test_returns_none_when_no_usage(self, minimal_session_log):
        assert extraction.extract_token_usage(minimal_session_log) is None


class TestExtractDocuments:
    def test_extracts_document_names(self, sample_session_log):
        docs = extraction.extract_documents(sample_session_log)
        assert "design-spec.md" in docs

    def test_skips_untitled(self):
        assert extraction.extract_documents("[DOCUMENT] untitled\n") == []


class TestFilenameExtraction:
    def test_session_id_from_log_filename(self):
        sid = extraction.extract_session_id_from_filename(
            "2026-05-27_143000_abc12345-6789-0000-1111-222233334444.log"
        )
        assert sid == "abc12345-6789-0000-1111-222233334444"

    def test_session_id_from_task_filename(self):
        sid = extraction.extract_session_id_from_filename(
            "task-2026-05-27_143000_abc12345-6789.md"
        )
        assert sid == "abc12345-6789"

    def test_datetime_from_log_filename(self):
        dt = extraction.extract_datetime_from_filename(
            "2026-05-27_143000_abc.log"
        )
        assert dt == datetime(2026, 5, 27, 14, 30, 0)

    def test_datetime_from_task_filename(self):
        dt = extraction.extract_datetime_from_filename(
            "task-2026-01-02_090530_abc12345-6789-0000-1111-222233334444.md"
        )
        assert dt == datetime(2026, 1, 2, 9, 5, 30)

    def test_datetime_none_for_unmatched(self):
        assert extraction.extract_datetime_from_filename("random.log") is None

    def test_uuid_from_string(self):
        uuid = extraction.extract_uuid_from_string(
            "task-2026-05-27_143000_abc12345-6789-0000-1111-222233334444.md"
        )
        assert uuid == "abc12345-6789-0000-1111-222233334444"

    def test_uuid_none_when_absent(self):
        assert extraction.extract_uuid_from_string("no-uuid-here") is None


class TestExtractFilesFromToolActions:
    def test_extracts_target_tool_paths(self, sample_session_log):
        tools = extraction.extract_tool_uses(sample_session_log)
        files = extraction.extract_files_from_tool_actions(tools, ["Edit"])
        assert "/Users/test/project/main.py" in files

    def test_filters_by_target_tools(self, sample_session_log):
        tools = extraction.extract_tool_uses(sample_session_log)
        # Read is excluded; only Write target → no matches
        files = extraction.extract_files_from_tool_actions(tools, ["Write"])
        assert files == []

    def test_deduplicates(self):
        tools = [
            {"tool": "Edit", "action": "/a/b.py"},
            {"tool": "Edit", "action": "/a/b.py"},
        ]
        files = extraction.extract_files_from_tool_actions(tools, ["Edit"])
        assert files == ["/a/b.py"]


class TestExtractThinkingAndResults:
    def test_thinking_summaries_first_line(self, sample_session_log):
        thinking = extraction.extract_thinking_summaries(sample_session_log)
        assert len(thinking) == 1
        assert "verify" in thinking[0].lower()

    def test_tool_results_first_line(self, sample_session_log):
        results = extraction.extract_tool_results(sample_session_log)
        assert len(results) == 2
        assert "def main" in results[0]
