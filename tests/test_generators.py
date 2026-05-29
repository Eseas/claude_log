"""Tests for output generators (markdown + timeline)."""

from datetime import datetime
from pathlib import Path

from claude_log_organizer.config import Config
from claude_log_organizer.models.task_data import TaskData, TokenUsage
from claude_log_organizer.generators.markdown_generator import MarkdownGenerator
from claude_log_organizer.generators.timeline import TimelineDiagramGenerator

PROJECT_ROOT = Path(__file__).parent.parent
TEMPLATE_DIR = PROJECT_ROOT / "templates"


class TestMarkdownGeneratorFilters:
    def test_status_emoji_known(self):
        assert MarkdownGenerator._status_emoji("completed") == "✅"
        assert MarkdownGenerator._status_emoji("failed") == "❌"

    def test_status_emoji_unknown(self):
        assert MarkdownGenerator._status_emoji("weird") == "❓"

    def test_truncate_text_short(self):
        assert MarkdownGenerator._truncate_text("hi", 100) == "hi"

    def test_truncate_text_long(self):
        out = MarkdownGenerator._truncate_text("x" * 200, 100)
        assert out.endswith("...")
        assert len(out) == 103

    def test_format_number_with_commas(self):
        assert MarkdownGenerator._format_number(1234567) == "1,234,567"

    def test_format_number_none(self):
        assert MarkdownGenerator._format_number(None) == "0"

    def test_format_timestamp_iso(self):
        out = MarkdownGenerator._format_timestamp("2026-05-27T14:30:00")
        assert out == "2026-05-27 14:30:00"

    def test_format_timestamp_empty(self):
        assert MarkdownGenerator._format_timestamp("") == "N/A"

    def test_format_seconds_minutes(self):
        assert MarkdownGenerator._format_seconds(125) == "2m 5s"


class TestMarkdownGeneratorRender:
    def test_generate_creates_file(self, tmp_path):
        gen = MarkdownGenerator(TEMPLATE_DIR, Config(None))
        task = TaskData(
            task_id="abc123",
            timestamp=datetime(2026, 5, 27, 14, 30, 0),
            work_summary="작업 요약입니다",
            status="completed",
            files_modified=["main.py"],
            token_usage=TokenUsage(input_tokens=100, output_tokens=50, request_count=1),
        )
        out = tmp_path / "task-abc123.md"
        gen.generate(task, out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "abc123" in content
        assert "작업 요약입니다" in content

    def test_generate_makes_parent_dir(self, tmp_path):
        gen = MarkdownGenerator(TEMPLATE_DIR, Config(None))
        task = TaskData(task_id="t1")
        out = tmp_path / "nested" / "deep" / "task.md"
        gen.generate(task, out)
        assert out.exists()


class TestTimelineGenerator:
    def _write_task(self, tmp_path, markdown,
                    name="task-2026-05-27_143000_abc12345-6789-0000-1111-222233334444.md"):
        path = tmp_path / name
        path.write_text(markdown, encoding="utf-8")
        return path

    def test_parse_task_files(self, tmp_path, sample_task_markdown):
        path = self._write_task(tmp_path, sample_task_markdown)
        gen = TimelineDiagramGenerator()
        entries = gen.parse_task_files([path])
        assert len(entries) == 1
        e = entries[0]
        assert e.session_short == "abc12345"
        assert e.token_usage.total_tokens == 5700
        assert e.tool_use_count == 3
        assert len(e.process_steps) == 3

    def test_parse_skips_files_without_datetime(self, tmp_path, sample_task_markdown):
        path = self._write_task(tmp_path, sample_task_markdown, name="task-no-date.md")
        gen = TimelineDiagramGenerator()
        assert gen.parse_task_files([path]) == []

    def test_generate_produces_drawio_and_md(self, tmp_path, sample_task_markdown):
        path = self._write_task(tmp_path, sample_task_markdown)
        gen = TimelineDiagramGenerator()
        out = tmp_path / "out" / "daily-2026-05-27_timeline.drawio"
        result = gen.generate([path], "daily-2026-05-27", out)
        assert result.exists()
        assert result.with_suffix(".md").exists()

    def test_generated_drawio_is_valid_xml(self, tmp_path, sample_task_markdown):
        import xml.etree.ElementTree as ET
        path = self._write_task(tmp_path, sample_task_markdown)
        gen = TimelineDiagramGenerator()
        out = tmp_path / "daily-2026-05-27_timeline.drawio"
        gen.generate([path], "daily-2026-05-27", out)
        # Must parse without raising
        ET.parse(str(out))
