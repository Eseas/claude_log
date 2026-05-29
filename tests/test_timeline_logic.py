"""Tests for timeline pure-logic modules (entry_processing, token_analyzer)."""

from datetime import datetime, timedelta

from claude_log_organizer.models.task_data import TimelineEntry, TokenUsage
from claude_log_organizer.generators.timeline.entry_processing import (
    infer_end_times,
    merge_same_requests,
)
from claude_log_organizer.generators.timeline.token_analyzer import analyze_token_usage


def _entry(session="abc12345-0000", label="task", start=None, **kwargs):
    start = start or datetime(2026, 5, 27, 14, 0, 0)
    return TimelineEntry(
        session_id=session,
        session_short=session[:8],
        start_time=start,
        end_time=start,
        label=label,
        task_file="t.md",
        **kwargs,
    )


class TestInferEndTimes:
    def test_gap_within_max_becomes_next_start(self):
        default = timedelta(minutes=10)
        max_gap = timedelta(minutes=30)
        e1 = _entry(start=datetime(2026, 5, 27, 14, 0, 0))
        e2 = _entry(start=datetime(2026, 5, 27, 14, 15, 0))
        infer_end_times([e1, e2], default, max_gap)
        assert e1.end_time == e2.start_time

    def test_gap_exceeding_max_uses_default_duration(self):
        default = timedelta(minutes=10)
        max_gap = timedelta(minutes=30)
        e1 = _entry(start=datetime(2026, 5, 27, 14, 0, 0))
        e2 = _entry(start=datetime(2026, 5, 27, 18, 0, 0))  # 4h gap
        infer_end_times([e1, e2], default, max_gap)
        assert e1.end_time == e1.start_time + default

    def test_last_entry_uses_default_duration(self):
        default = timedelta(minutes=10)
        e1 = _entry(start=datetime(2026, 5, 27, 14, 0, 0))
        infer_end_times([e1], default, timedelta(minutes=30))
        assert e1.end_time == e1.start_time + default


class TestMergeSameRequests:
    def test_empty_returns_empty(self):
        assert merge_same_requests([]) == []

    def test_merges_consecutive_same_label_same_session(self):
        e1 = _entry(label="동일 작업", start=datetime(2026, 5, 27, 14, 0, 0))
        e1.end_time = datetime(2026, 5, 27, 14, 10, 0)
        e2 = _entry(label="동일 작업", start=datetime(2026, 5, 27, 14, 10, 0))
        e2.end_time = datetime(2026, 5, 27, 14, 20, 0)
        merged = merge_same_requests([e1, e2])
        assert len(merged) == 1
        assert merged[0].end_time == datetime(2026, 5, 27, 14, 20, 0)

    def test_different_labels_not_merged(self):
        e1 = _entry(label="작업 A")
        e2 = _entry(label="작업 B")
        assert len(merge_same_requests([e1, e2])) == 2

    def test_different_sessions_not_merged(self):
        e1 = _entry(session="aaaa1111-0000", label="동일 작업")
        e2 = _entry(session="bbbb2222-0000", label="동일 작업")
        assert len(merge_same_requests([e1, e2])) == 2

    def test_merge_aggregates_token_usage(self):
        e1 = _entry(label="작업", token_usage=TokenUsage(input_tokens=100, request_count=1))
        e2 = _entry(label="작업", token_usage=TokenUsage(input_tokens=200, request_count=1))
        merged = merge_same_requests([e1, e2])
        assert merged[0].token_usage.input_tokens == 300
        assert merged[0].token_usage.request_count == 2

    def test_merge_does_not_mutate_originals(self):
        e1 = _entry(label="작업", files_modified=["a.py"])
        e2 = _entry(label="작업", files_modified=["b.py"])
        merge_same_requests([e1, e2])
        assert e1.files_modified == ["a.py"]  # clone protects original


class TestAnalyzeTokenUsage:
    def test_returns_empty_with_fewer_than_two_token_entries(self):
        e1 = _entry(token_usage=TokenUsage(input_tokens=100))
        assert analyze_token_usage([e1]) == []

    def test_returns_empty_when_no_high_usage(self):
        # All equal → none exceeds 1.5x average
        entries = [
            _entry(token_usage=TokenUsage(input_tokens=1000, request_count=1)),
            _entry(token_usage=TokenUsage(input_tokens=1000, request_count=1)),
        ]
        assert analyze_token_usage(entries) == []

    def test_identifies_high_usage_session(self):
        entries = [
            _entry(label="작은 작업", token_usage=TokenUsage(input_tokens=1000, request_count=1)),
            _entry(label="작은 작업2", token_usage=TokenUsage(input_tokens=1000, request_count=1)),
            _entry(label="거대 작업", token_usage=TokenUsage(input_tokens=50000, request_count=2)),
        ]
        lines = analyze_token_usage(entries)
        assert lines  # non-empty
        joined = "\n".join(lines)
        assert "Token Usage Analysis" in joined
        assert "High Usage Sessions" in joined
