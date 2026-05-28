"""Main orchestrator class for timeline diagram generation."""

import logging
from datetime import timedelta
from pathlib import Path
from typing import List

from claude_log_organizer.models.task_data import TimelineEntry
from claude_log_organizer.generators.timeline.data_extraction import parse_task_files as _parse_task_files
from claude_log_organizer.generators.timeline.entry_processing import infer_end_times, merge_same_requests
from claude_log_organizer.generators.timeline.phase_summarizer import summarize_process_steps
from claude_log_organizer.generators.timeline.drawio_builder import build_drawio_xml
from claude_log_organizer.generators.timeline.token_analyzer import analyze_token_usage
from claude_log_organizer.generators.timeline.markdown_builder import build_markdown

logger = logging.getLogger(__name__)


class TimelineDiagramGenerator:
    """Generates draw.io timeline diagrams and companion markdown from task files."""

    def __init__(
        self,
        default_duration_minutes: int = 10,
        max_gap_minutes: int = 30,
    ):
        self.default_duration = timedelta(minutes=default_duration_minutes)
        self.max_gap = timedelta(minutes=max_gap_minutes)

    def generate(self, files: List[Path], date_label: str, output_path: Path) -> Path:
        """Full pipeline: parse -> infer -> generate .drawio + .md.

        Args:
            files: List of task markdown files
            date_label: Label like "daily-2026-02-19"
            output_path: Where to save the .drawio file

        Returns:
            Path to saved .drawio file
        """
        entries = self.parse_task_files(files)
        if not entries:
            raise ValueError("No valid timeline entries found in the provided files.")

        entries = infer_end_times(entries, self.default_duration, self.max_gap)

        # Keep unmerged entries for process detail
        all_entries = list(entries)

        merged_entries = merge_same_requests(entries)

        # Summarize process steps into phases for entries with many steps
        for entry in merged_entries:
            if len(entry.process_steps) > 8:
                entry.process_phases = summarize_process_steps(entry.process_steps)

        title = date_label.replace("daily-", "").replace("weekly-", "").replace("_to_", " ~ ")
        title_display = f"{title} Daily Timeline"

        xml_content = build_drawio_xml(merged_entries, all_entries, title_display)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(xml_content, encoding="utf-8")

        # Generate companion markdown
        md_path = output_path.with_suffix(".md")
        md_content = build_markdown(merged_entries, all_entries, title)
        md_path.write_text(md_content, encoding="utf-8")

        return output_path

    def parse_task_files(self, files: List[Path]) -> List[TimelineEntry]:
        """Parse task files into TimelineEntry list."""
        return _parse_task_files(files)

    def _analyze_token_usage(self, entries: List[TimelineEntry]) -> List[str]:
        """Analyze token usage patterns, identify high-usage sessions, and suggest reductions.

        Returns list of markdown lines for the analysis section.
        """
        return analyze_token_usage(entries)
