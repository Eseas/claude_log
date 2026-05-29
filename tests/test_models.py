"""Tests for data models (TaskData, TokenUsage, etc.)."""

from datetime import datetime

from claude_log_organizer.models.task_data import (
    TokenUsage,
    CodeSnippet,
    TaskData,
    TaskInteraction,
    ProcessPhase,
    TimelineEntry,
)


class TestTokenUsage:
    def test_total_computed_in_post_init(self):
        tu = TokenUsage(input_tokens=100, output_tokens=50,
                        cache_read_tokens=30, cache_write_tokens=20)
        assert tu.total_tokens == 200

    def test_empty_usage_totals_zero(self):
        assert TokenUsage().total_tokens == 0

    def test_add_merges_all_fields(self):
        a = TokenUsage(input_tokens=100, output_tokens=50,
                       cache_read_tokens=10, cache_write_tokens=5, request_count=1)
        b = TokenUsage(input_tokens=200, output_tokens=80,
                       cache_read_tokens=20, cache_write_tokens=15, request_count=2)
        merged = a.add(b)
        assert merged.input_tokens == 300
        assert merged.output_tokens == 130
        assert merged.cache_read_tokens == 30
        assert merged.cache_write_tokens == 20
        assert merged.request_count == 3
        assert merged.total_tokens == 480

    def test_add_returns_new_instance(self):
        a = TokenUsage(input_tokens=100)
        b = TokenUsage(input_tokens=200)
        merged = a.add(b)
        assert merged is not a
        assert a.input_tokens == 100  # original unchanged

    def test_to_dict_roundtrip(self):
        tu = TokenUsage(input_tokens=10, output_tokens=20, request_count=3)
        d = tu.to_dict()
        assert d["input_tokens"] == 10
        assert d["output_tokens"] == 20
        assert d["total_tokens"] == 30
        assert d["request_count"] == 3


class TestCodeSnippet:
    def test_defaults_empty_description(self):
        cs = CodeSnippet(language="python", code="print(1)")
        assert cs.description == ""

    def test_to_dict(self):
        cs = CodeSnippet(language="go", code="fmt.Println()", description="hello")
        assert cs.to_dict() == {
            "language": "go",
            "code": "fmt.Println()",
            "description": "hello",
        }


class TestTaskData:
    def test_minimal_construction(self):
        td = TaskData(task_id="t1")
        assert td.task_id == "t1"
        assert td.status == "unknown"
        assert td.files_modified == []
        assert td.token_usage is None

    def test_mutable_defaults_are_independent(self):
        a = TaskData(task_id="a")
        b = TaskData(task_id="b")
        a.files_modified.append("x.py")
        assert b.files_modified == []

    def test_format_duration_none(self):
        assert TaskData(task_id="t").format_duration() == "N/A"

    def test_format_duration_seconds(self):
        assert TaskData(task_id="t", total_duration=45).format_duration() == "45s"

    def test_format_duration_minutes(self):
        assert TaskData(task_id="t", total_duration=125).format_duration() == "2m 5s"

    def test_format_duration_hours(self):
        assert TaskData(task_id="t", total_duration=3725).format_duration() == "1h 2m 5s"

    def test_to_dict_serializes_timestamp(self):
        ts = datetime(2026, 5, 27, 14, 30, 0)
        td = TaskData(task_id="t", timestamp=ts)
        assert td.to_dict()["timestamp"] == ts.isoformat()

    def test_to_dict_none_timestamp(self):
        assert TaskData(task_id="t").to_dict()["timestamp"] is None

    def test_to_dict_includes_token_usage(self):
        td = TaskData(task_id="t", token_usage=TokenUsage(input_tokens=10))
        assert td.to_dict()["token_usage"]["input_tokens"] == 10

    def test_to_dict_nested_code_snippets(self):
        td = TaskData(task_id="t", code_snippets=[CodeSnippet("py", "x=1")])
        d = td.to_dict()
        assert d["code_snippets"][0]["language"] == "py"


class TestTaskInteraction:
    def test_defaults(self):
        ti = TaskInteraction(request="do something")
        assert ti.feedback is None
        assert ti.heuristic_confidence == 0.0
        assert ti.assistant_work == []

    def test_to_dict_contains_analysis_fields(self):
        ti = TaskInteraction(request="r", heuristic_result="success",
                             heuristic_confidence=0.8)
        d = ti.to_dict()
        assert d["heuristic_result"] == "success"
        assert d["heuristic_confidence"] == 0.8


class TestProcessPhase:
    def test_to_dict(self):
        p = ProcessPhase(phase_name="분석", primary_type="analysis",
                         step_count=3, summary="코드 분석", key_details=["a", "b"])
        d = p.to_dict()
        assert d["phase_name"] == "분석"
        assert d["step_count"] == 3
        assert d["key_details"] == ["a", "b"]


class TestTimelineEntry:
    def test_construction_with_required_fields(self):
        now = datetime(2026, 5, 27, 14, 0, 0)
        entry = TimelineEntry(
            session_id="abc123", session_short="abc123"[:8],
            start_time=now, end_time=now, label="task", task_file="t.md",
        )
        assert entry.status == "completed"
        assert entry.compact_count == 0
        assert entry.token_usage is None
