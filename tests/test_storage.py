"""Tests for ProcessedTracker (hash-based deduplication)."""

from claude_log_organizer.storage.processed_tracker import ProcessedTracker


def _make_file(tmp_path, name="sample.log", content="hello"):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


class TestProcessedTracker:
    def test_unprocessed_file_returns_false(self, tmp_path):
        tracker = ProcessedTracker(tmp_path / ".processed.json")
        f = _make_file(tmp_path)
        assert tracker.is_processed(f) is False

    def test_nonexistent_file_returns_false(self, tmp_path):
        tracker = ProcessedTracker(tmp_path / ".processed.json")
        assert tracker.is_processed(tmp_path / "ghost.log") is False

    def test_mark_then_is_processed(self, tmp_path):
        tracker = ProcessedTracker(tmp_path / ".processed.json")
        f = _make_file(tmp_path)
        tracker.mark_processed(f)
        assert tracker.is_processed(f) is True

    def test_content_change_triggers_reprocess(self, tmp_path):
        tracker = ProcessedTracker(tmp_path / ".processed.json")
        f = _make_file(tmp_path, content="original")
        tracker.mark_processed(f)
        assert tracker.is_processed(f) is True
        f.write_text("modified", encoding="utf-8")
        assert tracker.is_processed(f) is False

    def test_persistence_across_instances(self, tmp_path):
        storage = tmp_path / ".processed.json"
        f = _make_file(tmp_path)
        ProcessedTracker(storage).mark_processed(f)
        # New instance loads from disk
        assert ProcessedTracker(storage).is_processed(f) is True

    def test_clear_resets_registry(self, tmp_path):
        storage = tmp_path / ".processed.json"
        tracker = ProcessedTracker(storage)
        f = _make_file(tmp_path)
        tracker.mark_processed(f)
        tracker.clear()
        assert tracker.is_processed(f) is False
        assert tracker.processed == {}

    def test_remove_specific_file(self, tmp_path):
        storage = tmp_path / ".processed.json"
        tracker = ProcessedTracker(storage)
        f1 = _make_file(tmp_path, "a.log")
        f2 = _make_file(tmp_path, "b.log")
        tracker.mark_processed(f1)
        tracker.mark_processed(f2)
        tracker.remove(f1)
        assert tracker.is_processed(f1) is False
        assert tracker.is_processed(f2) is True

    def test_corrupt_registry_loads_empty(self, tmp_path):
        storage = tmp_path / ".processed.json"
        storage.write_text("{ not valid json", encoding="utf-8")
        tracker = ProcessedTracker(storage)
        assert tracker.processed == {}
