"""Generates draw.io (.drawio) timeline diagrams and companion markdown from task files."""

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from collections import OrderedDict

from claude_log_organizer.models.task_data import TimelineEntry


@dataclass
class ProcessStep:
    """A single process step with type classification."""
    type: str  # analysis, decision, implementation, verification, summary
    summary: str
    details: List[str] = field(default_factory=list)


# Step type visual config: (fill_color, stroke_color, icon)
STEP_TYPE_STYLES = {
    "analysis":       ("#e1f5fe", "#0288d1", "🔍"),  # light blue
    "decision":       ("#fff8e1", "#f9a825", "⚡"),  # amber/yellow
    "implementation": ("#e8f5e9", "#388e3c", "🔧"),  # green
    "verification":   ("#f3e5f5", "#7b1fa2", "✅"),  # purple
    "summary":        ("#efebe9", "#5d4037", "📋"),  # brown/gray
}


# Session color palette
COLORS = [
    ("#dae8fc", "#6c8ebf"),  # blue
    ("#d5e8d4", "#82b366"),  # green
    ("#fff2cc", "#d6b656"),  # yellow
    ("#f8cecc", "#b85450"),  # red
    ("#e1d5e7", "#9673a6"),  # purple
    ("#ffe6cc", "#d79b00"),  # orange
]

# Gantt layout constants
TITLE_Y = 20
TITLE_HEIGHT = 40
TIME_AXIS_Y = 80
TIME_AXIS_HEIGHT = 25
SESSION_LABEL_WIDTH = 120
TIME_AREA_X = 140
ROW_HEIGHT = 70
BAR_HEIGHT = 36
BAR_Y_OFFSET = 22
PX_PER_MINUTE = 4
MIN_BAR_WIDTH = 50

# Process flow layout constants
FLOW_BOX_WIDTH = 220
FLOW_BOX_HEIGHT = 50
FLOW_H_GAP = 30
FLOW_V_GAP = 30
FLOW_ARROW_STYLE = "edgeStyle=orthogonalEdgeStyle;rounded=1;orthogonalLoop=1;jettySize=auto;exitX=1;exitY=0.5;exitDx=0;exitDy=0;entryX=0;entryY=0.5;entryDx=0;entryDy=0;strokeColor=#999999;"
FLOW_SESSION_TITLE_HEIGHT = 30
FLOW_LEFT_MARGIN = 20
FLOW_MAX_COLS = 4


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

        entries = self._infer_end_times(entries)

        # Keep unmerged entries for process detail
        all_entries = list(entries)

        merged_entries = self._merge_same_requests(entries)

        title = date_label.replace("daily-", "").replace("weekly-", "").replace("_to_", " ~ ")
        title_display = f"{title} Daily Timeline"

        xml_content = self._build_drawio_xml(merged_entries, all_entries, title_display)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(xml_content, encoding="utf-8")

        # Generate companion markdown
        md_path = output_path.with_suffix(".md")
        md_content = self._build_markdown(merged_entries, all_entries, title)
        md_path.write_text(md_content, encoding="utf-8")

        return output_path

    # ===== Data extraction =====

    def parse_task_files(self, files: List[Path]) -> List[TimelineEntry]:
        """Parse task files into TimelineEntry list."""
        entries = []
        for file_path in files:
            dt = self._extract_datetime_from_filename(file_path.name)
            session_id = self._extract_session_from_filename(file_path.name)

            if not dt or not session_id:
                continue

            content = self._read_file(file_path)
            label = self._extract_label(content, file_path)
            process_steps = self._extract_process_steps(content)
            tools_used = self._extract_tools_used(content)
            files_modified = self._extract_files_modified(content)
            thinking_summary = self._extract_thinking_summary(content)
            compact_count = self._extract_compact_count(content)
            referenced_documents = self._extract_referenced_documents(content)

            entry = TimelineEntry(
                session_id=session_id,
                session_short=session_id[:8],
                start_time=dt,
                end_time=dt,
                label=label,
                task_file=file_path.name,
                process_steps=process_steps,
                tools_used=tools_used,
                files_modified=files_modified,
                thinking_summary=thinking_summary,
                compact_count=compact_count,
                referenced_documents=referenced_documents,
            )
            entries.append(entry)

        entries.sort(key=lambda e: e.start_time)
        return entries

    def _read_file(self, file_path: Path) -> str:
        try:
            return file_path.read_text(encoding="utf-8")
        except Exception:
            return ""

    def _extract_datetime_from_filename(self, filename: str) -> Optional[datetime]:
        match = re.match(
            r"task-(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})(\d{2})_", filename
        )
        if match:
            return datetime(
                int(match.group(1)), int(match.group(2)), int(match.group(3)),
                int(match.group(4)), int(match.group(5)), int(match.group(6)),
            )
        return None

    def _extract_session_from_filename(self, filename: str) -> Optional[str]:
        match = re.search(r"task-\d{4}-\d{2}-\d{2}_\d{6}_([a-f0-9-]+)\.md", filename)
        return match.group(1) if match else None

    def _extract_label(self, content: str, file_path: Path) -> str:
        """Extract task label from file content. No truncation."""
        if not content:
            return file_path.stem

        match = re.search(r"\*\*초기 요청\*\*:\s*(.+?)(?:\n|$)", content)
        if not match:
            return file_path.stem

        label = match.group(1).strip()
        label = re.sub(r"@[\w/.~-]+", "", label).strip()
        label = re.sub(r"^Implement the following plan:\s*", "", label, flags=re.IGNORECASE).strip()

        for _ in range(3):
            cleaned = re.sub(r"^[와과의에서을를이가은는로으]+\s+", "", label).strip()
            if cleaned == label:
                break
            label = cleaned

        label = re.sub(r"\s+", " ", label).strip()

        if label.startswith("[Request interrupted"):
            label = ""

        if not label:
            heading_match = re.search(r"\*\*초기 요청\*\*:.*?\n+#\s+(.+?)(?:\n|$)", content)
            if heading_match:
                label = heading_match.group(1).strip()

        if not label:
            resp_match = re.search(r"\*\*응답 1\*\*:\s*\n(.+?)(?:\n|$)", content)
            if resp_match:
                resp_text = resp_match.group(1).strip()
                if len(resp_text) > 5 and not resp_text.startswith("```"):
                    label = resp_text

        if not label:
            label = file_path.stem

        return label

    def _extract_process_steps(self, content: str) -> List['ProcessStep']:
        """Extract enriched process steps from **응답 N**: blocks.

        Each step is classified as: analysis, decision, implementation, verification, or summary.
        Returns list of ProcessStep(type, summary, details) tuples.
        """
        steps = []
        matches = re.finditer(r"\*\*응답 (\d+)\*\*:\s*\n(.+?)(?=\n\*\*응답 \d+\*\*:|\n---|\Z)", content, re.DOTALL)
        for m in matches:
            resp_body = m.group(2).strip()

            # Extract summary (first meaningful line)
            summary = ""
            details = []
            in_code_block = False
            for line in resp_body.split("\n"):
                stripped = line.strip()
                if stripped.startswith("```"):
                    in_code_block = not in_code_block
                    continue
                if in_code_block:
                    continue
                if not stripped or stripped.startswith("---"):
                    continue

                clean = re.sub(r"^#+\s*", "", stripped)
                clean = re.sub(r"^\*\*(.+?)\*\*", r"\1", clean)

                if not summary:
                    summary = clean
                else:
                    # Collect key detail lines (bullets, headings, findings)
                    if stripped.startswith("- ") or stripped.startswith("* ") or stripped.startswith("### "):
                        detail = re.sub(r"^[-*]\s*", "", stripped)
                        detail = re.sub(r"^#+\s*", "", detail)
                        if len(detail) > 10:
                            details.append(detail)

            if not summary:
                continue

            # Classify step type
            step_type = self._classify_step(summary, details)
            steps.append(ProcessStep(type=step_type, summary=summary, details=details[:5]))

        return steps

    def _classify_step(self, summary: str, details: List[str]) -> str:
        """Classify a process step into: analysis, decision, implementation, verification, summary."""
        s_lower = summary.lower()

        # Verification patterns
        if re.search(r"(확인|검증|테스트|빌드|검토|verify|test|build|check|review)", s_lower):
            if re.search(r"(수정|변경|추가|생성|구현|implement|fix|add|create)", s_lower):
                return "implementation"
            return "verification"

        # Decision patterns
        if re.search(r"(결정|선택|판단|방법|접근|전략|decide|choose|approach|should|원인|발견|이슈|버그|문제|bug|issue|found)", s_lower):
            return "decision"

        # Implementation patterns
        if re.search(r"(수정|변경|추가|생성|삭제|구현|적용|implement|fix|add|create|update|modify|edit|remove|이제|시작)", s_lower):
            return "implementation"

        # Summary/completion patterns
        if re.search(r"(완료|정리|요약|결과|summary|complete|done|finish|결론)", s_lower):
            return "summary"

        # Analysis patterns
        if re.search(r"(분석|파악|조사|읽|탐색|확인|analyze|investigate|read|explore|찾|search|살펴)", s_lower):
            return "analysis"

        return "analysis"

    def _extract_tools_used(self, content: str) -> str:
        match = re.search(r"\*\*수행 작업\*\*:\s*\n((?:- .+\n?)+)", content)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_files_modified(self, content: str) -> List[str]:
        files = []
        in_files_section = False
        for line in content.split("\n"):
            if "### Files Modified" in line or "### Files Created" in line:
                in_files_section = True
                continue
            if in_files_section:
                if line.startswith("- "):
                    path = line[2:].strip().strip("`")
                    # Shorten path
                    parts = path.split("/")
                    if len(parts) > 2:
                        path = "/".join(parts[-2:])
                    files.append(path)
                elif line.startswith("#") or (line.strip() and not line.startswith("-")):
                    in_files_section = False
        return files

    def _extract_thinking_summary(self, content: str) -> List[str]:
        """Extract thinking process from ### Thinking Process section."""
        summaries = []
        in_section = False
        for line in content.split("\n"):
            if "### Thinking Process" in line:
                in_section = True
                continue
            if in_section:
                if line.startswith("- "):
                    summaries.append(line[2:].strip())
                elif line.startswith("#") or (line.strip() and not line.startswith("-") and line.strip() != ""):
                    if not line.startswith("- "):
                        in_section = False
        return summaries

    def _extract_compact_count(self, content: str) -> int:
        """Extract context compression count."""
        match = re.search(r"\*\*Context Compressions\*\*:\s*(\d+)", content)
        if match:
            return int(match.group(1))
        return 0

    def _extract_referenced_documents(self, content: str) -> List[str]:
        """Extract referenced documents from ### Referenced Documents section."""
        docs = []
        in_section = False
        for line in content.split("\n"):
            if "### Referenced Documents" in line:
                in_section = True
                continue
            if in_section:
                if line.startswith("- "):
                    doc = line[2:].strip().strip("`")
                    docs.append(doc)
                elif line.startswith("#") or (line.strip() and not line.startswith("-") and line.strip() != ""):
                    if not line.startswith("- "):
                        in_section = False
        return docs

    def _infer_end_times(self, entries: List[TimelineEntry]) -> List[TimelineEntry]:
        for i, entry in enumerate(entries):
            if i + 1 < len(entries):
                next_start = entries[i + 1].start_time
                gap = next_start - entry.start_time
                if gap <= self.max_gap and gap > timedelta(0):
                    entry.end_time = next_start
                else:
                    entry.end_time = entry.start_time + self.default_duration
            else:
                entry.end_time = entry.start_time + self.default_duration
        return entries

    def _merge_same_requests(self, entries: List[TimelineEntry]) -> List[TimelineEntry]:
        """Merge consecutive entries with same label in same session.
        Uses the last entry's process data (most complete).
        """
        if not entries:
            return entries

        def _clone_entry(e):
            return TimelineEntry(
                session_id=e.session_id, session_short=e.session_short,
                start_time=e.start_time, end_time=e.end_time,
                label=e.label, task_file=e.task_file,
                process_steps=list(e.process_steps), tools_used=e.tools_used,
                files_modified=list(e.files_modified),
                thinking_summary=list(e.thinking_summary),
                compact_count=e.compact_count,
                referenced_documents=list(e.referenced_documents),
            )

        merged = [_clone_entry(entries[0])]

        for entry in entries[1:]:
            prev = merged[-1]
            if entry.session_id == prev.session_id and entry.label == prev.label:
                prev.end_time = max(prev.end_time, entry.end_time)
                if len(entry.process_steps) > len(prev.process_steps):
                    prev.process_steps = list(entry.process_steps)
                if entry.tools_used:
                    prev.tools_used = entry.tools_used
                for f in entry.files_modified:
                    if f not in prev.files_modified:
                        prev.files_modified.append(f)
                # Merge new fields
                if len(entry.thinking_summary) > len(prev.thinking_summary):
                    prev.thinking_summary = list(entry.thinking_summary)
                prev.compact_count = max(prev.compact_count, entry.compact_count)
                for d in entry.referenced_documents:
                    if d not in prev.referenced_documents:
                        prev.referenced_documents.append(d)
            else:
                merged.append(_clone_entry(entry))

        return merged

    # ===== draw.io XML generation =====

    def _build_drawio_xml(
        self,
        merged_entries: List[TimelineEntry],
        all_entries: List[TimelineEntry],
        title: str,
    ) -> str:
        """Build .drawio with Page 1 (Gantt) and Page 2 (Process Flow)."""
        mxfile = ET.Element("mxfile", host="Claude Log Organizer")

        # Page 1: Gantt Timeline
        self._build_gantt_page(mxfile, merged_entries, title)

        # Page 2: Process Flow
        self._build_process_page(mxfile, merged_entries, title)

        ET.indent(mxfile, space="  ")
        return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)

    def _build_gantt_page(self, mxfile: ET.Element, entries: List[TimelineEntry], title: str):
        """Build the Gantt timeline page."""
        min_time = min(e.start_time for e in entries)
        max_time = max(e.end_time for e in entries)

        axis_start = min_time.replace(minute=(min_time.minute // 30) * 30, second=0, microsecond=0)
        axis_end_minute = max_time.minute
        if axis_end_minute % 30 != 0:
            axis_end = max_time.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=((axis_end_minute // 30) + 1) * 30)
        else:
            axis_end = max_time.replace(second=0, microsecond=0)
        axis_end += timedelta(minutes=30)

        sessions: Dict[str, List[TimelineEntry]] = OrderedDict()
        for entry in entries:
            if entry.session_short not in sessions:
                sessions[entry.session_short] = []
            sessions[entry.session_short].append(entry)

        total_minutes = (axis_end - axis_start).total_seconds() / 60
        time_axis_width = int(total_minutes * PX_PER_MINUTE)
        page_width = TIME_AREA_X + time_axis_width + 40
        num_sessions = len(sessions)
        rows_start_y = TIME_AXIS_Y + TIME_AXIS_HEIGHT + 10
        page_height = rows_start_y + num_sessions * ROW_HEIGHT + 40

        diagram = ET.SubElement(mxfile, "diagram", name="Timeline", id="gantt")
        graph_model = ET.SubElement(
            diagram, "mxGraphModel",
            dx=str(page_width), dy=str(page_height),
            grid="1", gridSize="10", guides="1", tooltips="1",
            connect="0", arrows="0", fold="1", page="1", pageScale="1",
            pageWidth=str(page_width), pageHeight=str(page_height),
        )
        root = ET.SubElement(graph_model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")
        cell_id = 2

        # Title
        cell_id = self._add_cell(root, cell_id, title,
            "text;html=1;align=center;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=18;fontStyle=1;",
            (page_width - 400) // 2, TITLE_Y, 400, TITLE_HEIGHT)

        # Time axis line
        cell_id = self._add_cell(root, cell_id, "",
            "line;strokeWidth=2;strokeColor=#666666;fillColor=none;align=left;verticalAlign=middle;spacingTop=-1;spacingLeft=3;spacingRight=3;rotatable=0;labelPosition=left;points=[];portConstraint=eastwest;",
            TIME_AREA_X, TIME_AXIS_Y + TIME_AXIS_HEIGHT, time_axis_width, 1)

        # Time ticks and gridlines
        current_time = axis_start
        while current_time <= axis_end:
            x_pos = self._time_to_x(current_time, axis_start)
            cell_id = self._add_cell(root, cell_id, current_time.strftime("%H:%M"),
                "text;html=1;align=center;verticalAlign=bottom;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=11;fontColor=#666666;",
                x_pos - 20, TIME_AXIS_Y, 40, TIME_AXIS_HEIGHT)
            cell_id = self._add_cell(root, cell_id, "",
                "line;strokeWidth=1;strokeColor=#EEEEEE;fillColor=none;direction=south;",
                x_pos, rows_start_y, 1, num_sessions * ROW_HEIGHT)
            current_time += timedelta(minutes=30)

        # Session rows and bars
        for session_idx, (session_short, session_entries) in enumerate(sessions.items()):
            color_fill, color_stroke = COLORS[session_idx % len(COLORS)]
            row_y = rows_start_y + session_idx * ROW_HEIGHT

            cell_id = self._add_cell(root, cell_id, session_short,
                f"text;html=1;align=right;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=11;fontStyle=1;fontColor={color_stroke};",
                0, row_y + BAR_Y_OFFSET - 5, SESSION_LABEL_WIDTH, 30)

            if session_idx % 2 == 0:
                cell_id = self._add_cell(root, cell_id, "",
                    "rounded=0;whiteSpace=wrap;html=1;fillColor=#F9F9F9;strokeColor=none;opacity=50;",
                    TIME_AREA_X, row_y, time_axis_width, ROW_HEIGHT)

            for entry in session_entries:
                bar_x = self._time_to_x(entry.start_time, axis_start)
                bar_end_x = self._time_to_x(entry.end_time, axis_start)
                bar_width = max(bar_end_x - bar_x, MIN_BAR_WIDTH)
                bar_y = row_y + BAR_Y_OFFSET
                time_range = f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}"

                # Shorten label for bar display (keep full in tooltip)
                bar_label = entry.label if len(entry.label) <= 50 else entry.label[:50]
                tooltip_lines = [entry.label, time_range, entry.task_file]
                if entry.process_steps:
                    tooltip_lines.append("")
                    for i, step in enumerate(entry.process_steps[:5], 1):
                        if isinstance(step, ProcessStep):
                            icon = STEP_TYPE_STYLES.get(step.type, STEP_TYPE_STYLES["analysis"])[2]
                            tooltip_lines.append(f"{i}. {icon} [{step.type}] {step.summary}")
                        else:
                            tooltip_lines.append(f"{i}. {step}")
                if entry.thinking_summary:
                    tooltip_lines.append("")
                    tooltip_lines.append("[Thinking]")
                    for t in entry.thinking_summary[:3]:
                        tooltip_lines.append(f"  - {t[:100]}")
                if entry.referenced_documents:
                    tooltip_lines.append("")
                    tooltip_lines.append("[Documents]")
                    for d in entry.referenced_documents:
                        tooltip_lines.append(f"  - {d}")

                # Dashed border for tasks with context compression
                bar_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={color_fill};strokeColor={color_stroke};fontSize=10;fontColor=#333333;align=left;verticalAlign=middle;spacingLeft=6;overflow=hidden;"
                if entry.compact_count > 0:
                    bar_style += "dashed=1;dashPattern=5 3;"

                cell_id = self._add_cell(root, cell_id, bar_label,
                    bar_style,
                    bar_x, bar_y, bar_width, BAR_HEIGHT,
                    tooltip="\n".join(tooltip_lines))

                cell_id = self._add_cell(root, cell_id, time_range,
                    "text;html=1;align=left;verticalAlign=top;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=8;fontColor=#999999;",
                    bar_x, bar_y + BAR_HEIGHT, bar_width, 14)

    def _build_process_page(self, mxfile: ET.Element, entries: List[TimelineEntry], title: str):
        """Build the process flow page showing work steps for each entry."""
        sessions: Dict[str, List[TimelineEntry]] = OrderedDict()
        for entry in entries:
            if entry.session_short not in sessions:
                sessions[entry.session_short] = []
            sessions[entry.session_short].append(entry)

        # Calculate page dimensions (accounting for variable box heights)
        max_steps = 0
        total_estimated_height = 0
        legend_height = 80  # space for step type legend
        for session_entries in sessions.values():
            for entry in session_entries:
                n_steps = len(entry.process_steps)
                if n_steps > 0:
                    grid_rows = (n_steps + FLOW_MAX_COLS - 1) // FLOW_MAX_COLS
                    # Estimate extra height from detail lines
                    max_details = max(
                        (min(len(s.details), 3) * 14 if isinstance(s, ProcessStep) and s.details else 0)
                        for s in entry.process_steps
                    ) if entry.process_steps else 0
                    total_estimated_height += grid_rows * (FLOW_BOX_HEIGHT + max_details + FLOW_V_GAP)
                    max_steps = max(max_steps, min(n_steps, FLOW_MAX_COLS))
                else:
                    total_estimated_height += FLOW_BOX_HEIGHT + FLOW_V_GAP
                # Entry header + documents + thinking
                total_estimated_height += FLOW_BOX_HEIGHT + 20
                total_estimated_height += len(entry.referenced_documents) * 35
                total_estimated_height += min(len(entry.thinking_summary), 3) * 22
            total_estimated_height += FLOW_SESSION_TITLE_HEIGHT + 30  # session header

        page_width = FLOW_LEFT_MARGIN + max(max_steps, 1) * (FLOW_BOX_WIDTH + FLOW_H_GAP) + 100
        page_height = 80 + total_estimated_height + legend_height + 60

        diagram = ET.SubElement(mxfile, "diagram", name="Process Flow", id="process")
        graph_model = ET.SubElement(
            diagram, "mxGraphModel",
            dx=str(page_width), dy=str(page_height),
            grid="1", gridSize="10", guides="1", tooltips="1",
            connect="1", arrows="1", fold="1", page="1", pageScale="1",
            pageWidth=str(page_width), pageHeight=str(page_height),
        )
        root = ET.SubElement(graph_model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")
        cell_id = 2

        # Title
        cell_id = self._add_cell(root, cell_id,
            title.replace("Daily Timeline", "Work Process"),
            "text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=18;fontStyle=1;",
            FLOW_LEFT_MARGIN, 20, 500, 40)

        # Legend - step type color reference
        legend_y = 65
        legend_x = FLOW_LEFT_MARGIN
        for step_type, (fill, stroke, icon) in STEP_TYPE_STYLES.items():
            legend_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};fontSize=8;fontColor=#333333;align=center;verticalAlign=middle;"
            if step_type == "decision":
                legend_style = f"shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;fixedSize=1;size=5;fillColor={fill};strokeColor={stroke};fontSize=8;fontColor=#333333;align=center;verticalAlign=middle;"
            elif step_type == "verification":
                legend_style += "dashed=1;dashPattern=3 2;"
            cell_id = self._add_cell(root, cell_id,
                f"{icon} {step_type.capitalize()}",
                legend_style,
                legend_x, legend_y, 100, 24)
            legend_x += 110

        y_cursor = legend_y + 40

        for session_idx, (session_short, session_entries) in enumerate(sessions.items()):
            color_fill, color_stroke = COLORS[session_idx % len(COLORS)]

            # Session header
            cell_id = self._add_cell(root, cell_id,
                f"Session {session_short}",
                f"text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=14;fontStyle=1;fontColor={color_stroke};",
                FLOW_LEFT_MARGIN, y_cursor, 300, FLOW_SESSION_TITLE_HEIGHT)
            y_cursor += FLOW_SESSION_TITLE_HEIGHT + 10

            for entry in session_entries:
                time_str = f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}"

                # Compact indicator
                compact_label = f" [compact x{entry.compact_count}]" if entry.compact_count > 0 else ""

                # Entry label box (dashed if compact)
                entry_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={color_fill};strokeColor={color_stroke};fontSize=11;fontColor=#333333;align=left;verticalAlign=middle;spacingLeft=8;spacingRight=8;"
                if entry.compact_count > 0:
                    entry_style += "dashed=1;dashPattern=5 3;"

                cell_id = self._add_cell(root, cell_id,
                    f"<b>{time_str}</b>{compact_label}<br/>{entry.label}",
                    entry_style,
                    FLOW_LEFT_MARGIN, y_cursor, FLOW_BOX_WIDTH + 80, FLOW_BOX_HEIGHT)

                y_cursor += FLOW_BOX_HEIGHT + 10

                # Referenced documents as separate nodes
                if entry.referenced_documents:
                    for doc in entry.referenced_documents:
                        cell_id = self._add_cell(root, cell_id,
                            f"📄 {doc}",
                            f"rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#cccccc;fontSize=9;fontColor=#666666;fontStyle=2;align=left;verticalAlign=middle;spacingLeft=6;",
                            FLOW_LEFT_MARGIN + 40, y_cursor, FLOW_BOX_WIDTH, 30)
                        y_cursor += 35

                if not entry.process_steps:
                    y_cursor += FLOW_V_GAP
                    continue

                # Process steps as connected boxes in grid layout with type-based colors
                prev_cell_id = None
                for step_idx, step in enumerate(entry.process_steps):
                    col = step_idx % FLOW_MAX_COLS
                    row = step_idx // FLOW_MAX_COLS

                    box_x = FLOW_LEFT_MARGIN + 40 + col * (FLOW_BOX_WIDTH + FLOW_H_GAP)
                    box_y = y_cursor + row * (FLOW_BOX_HEIGHT + FLOW_V_GAP)

                    if isinstance(step, ProcessStep):
                        fill, stroke, icon = STEP_TYPE_STYLES.get(step.type, STEP_TYPE_STYLES["analysis"])
                        summary_text = step.summary if len(step.summary) <= 70 else step.summary[:70] + "..."
                        step_label = f"<b>{icon} {step_idx + 1}</b>. {summary_text}"

                        # Build tooltip with details
                        step_tooltip = f"[{step.type.upper()}] {step.summary}"
                        if step.details:
                            step_tooltip += "\n" + "\n".join(f"  - {d}" for d in step.details[:5])

                        # Taller box if step has details
                        box_height = FLOW_BOX_HEIGHT + (min(len(step.details), 3) * 14 if step.details else 0)

                        # Decision type gets diamond-like shape (hexagon)
                        if step.type == "decision":
                            step_style = f"shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;fixedSize=1;size=10;fillColor={fill};strokeColor={stroke};strokeWidth=2;fontSize=9;fontColor=#333333;align=left;verticalAlign=top;spacingLeft=12;spacingRight=12;spacingTop=4;"
                        elif step.type == "verification":
                            step_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=2;fontSize=9;fontColor=#333333;align=left;verticalAlign=top;spacingLeft=6;spacingRight=6;spacingTop=4;dashed=1;dashPattern=3 2;"
                        else:
                            step_style = f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};strokeWidth=1;fontSize=9;fontColor=#333333;align=left;verticalAlign=top;spacingLeft=6;spacingRight=6;spacingTop=4;"

                        # Add detail lines inside box
                        if step.details:
                            detail_html = "<br/>".join(
                                f"<font style='font-size:8px' color='#666666'>· {d[:60]}</font>"
                                for d in step.details[:3]
                            )
                            step_label += f"<br/>{detail_html}"

                        current_cell_id = cell_id
                        cell_id = self._add_cell(root, cell_id, step_label,
                            step_style,
                            box_x, box_y, FLOW_BOX_WIDTH, box_height,
                            tooltip=step_tooltip)
                    else:
                        # Fallback for plain string steps
                        step_text = step if len(step) <= 80 else step[:80]
                        step_label = f"<b>{step_idx + 1}</b>. {step_text}"
                        box_height = FLOW_BOX_HEIGHT
                        current_cell_id = cell_id
                        cell_id = self._add_cell(root, cell_id, step_label,
                            f"rounded=1;whiteSpace=wrap;html=1;fillColor=#FFFFFF;strokeColor={color_stroke};fontSize=9;fontColor=#333333;align=left;verticalAlign=middle;spacingLeft=6;spacingRight=6;",
                            box_x, box_y, FLOW_BOX_WIDTH, FLOW_BOX_HEIGHT)

                    # Arrow from previous step
                    if prev_cell_id is not None and col > 0:
                        cell_id = self._add_edge(root, cell_id, prev_cell_id, current_cell_id, color_stroke)
                    prev_cell_id = current_cell_id

                # Update cursor - account for variable height boxes
                n_rows = (len(entry.process_steps) + FLOW_MAX_COLS - 1) // FLOW_MAX_COLS
                avg_extra_height = 0
                for s in entry.process_steps:
                    if isinstance(s, ProcessStep) and s.details:
                        avg_extra_height = max(avg_extra_height, min(len(s.details), 3) * 14)
                y_cursor += n_rows * (FLOW_BOX_HEIGHT + avg_extra_height + FLOW_V_GAP) + 10

                # Thinking summary after process steps (italic gray)
                if entry.thinking_summary:
                    for thought in entry.thinking_summary[:3]:
                        thought_display = thought[:120] if len(thought) > 120 else thought
                        cell_id = self._add_cell(root, cell_id,
                            f"<i>💭 {thought_display}</i>",
                            f"text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=8;fontColor=#999999;fontStyle=2;",
                            FLOW_LEFT_MARGIN + 40, y_cursor, FLOW_BOX_WIDTH * 2, 20)
                        y_cursor += 22

                y_cursor += 10

            y_cursor += 20

    # ===== Markdown generation =====

    def _build_markdown(
        self,
        merged_entries: List[TimelineEntry],
        all_entries: List[TimelineEntry],
        date_title: str,
    ) -> str:
        """Build companion markdown with detailed work process."""
        lines = [
            f"# {date_title} Daily Report",
            "",
            f"**Total tasks**: {len(all_entries)}",
            f"**Sessions**: {len(set(e.session_short for e in merged_entries))}",
        ]

        if merged_entries:
            start = min(e.start_time for e in merged_entries).strftime("%H:%M")
            end = max(e.end_time for e in merged_entries).strftime("%H:%M")
            lines.append(f"**Time range**: {start} - {end}")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Overview table
        lines.append("## Overview")
        lines.append("")
        lines.append("| Time | Session | Task |")
        lines.append("|------|---------|------|")
        for entry in merged_entries:
            time_str = f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}"
            lines.append(f"| {time_str} | `{entry.session_short}` | {entry.label} |")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Step type legend
        lines.append("## Step Types")
        lines.append("")
        lines.append("| Icon | Type | Description |")
        lines.append("|------|------|-------------|")
        lines.append("| 🔍 | ANALYSIS | 코드 분석, 파일 탐색, 구조 파악 |")
        lines.append("| ⚡ | DECISION | 의사결정, 문제 발견, 접근 방법 결정 |")
        lines.append("| 🔧 | IMPLEMENTATION | 코드 작성, 수정, 파일 생성 |")
        lines.append("| ✅ | VERIFICATION | 테스트, 검증, 빌드 확인 |")
        lines.append("| 📋 | SUMMARY | 결과 정리, 요약, 완료 보고 |")
        lines.append("")
        lines.append("---")
        lines.append("")

        # Detailed process for each entry
        lines.append("## Detailed Work Process")
        lines.append("")

        sessions: Dict[str, List[TimelineEntry]] = OrderedDict()
        for entry in merged_entries:
            if entry.session_short not in sessions:
                sessions[entry.session_short] = []
            sessions[entry.session_short].append(entry)

        for session_short, session_entries in sessions.items():
            lines.append(f"### Session `{session_short}`")
            lines.append("")

            for entry in session_entries:
                time_str = f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}"
                compact_mark = f" (compact x{entry.compact_count})" if entry.compact_count > 0 else ""
                lines.append(f"#### {time_str} | {entry.label}{compact_mark}")
                lines.append("")

                if entry.referenced_documents:
                    lines.append("**Referenced documents**:")
                    for d in entry.referenced_documents:
                        lines.append(f"- `{d}`")
                    lines.append("")

                if entry.tools_used:
                    lines.append("**Tools used**:")
                    lines.append(entry.tools_used)
                    lines.append("")

                if entry.thinking_summary:
                    lines.append("**Thinking process**:")
                    lines.append("")
                    for t in entry.thinking_summary:
                        lines.append(f"- {t}")
                    lines.append("")

                if entry.process_steps:
                    lines.append("**Work process**:")
                    lines.append("")
                    for i, step in enumerate(entry.process_steps, 1):
                        if isinstance(step, ProcessStep):
                            icon = STEP_TYPE_STYLES.get(step.type, STEP_TYPE_STYLES["analysis"])[2]
                            lines.append(f"{i}. {icon} **[{step.type.upper()}]** {step.summary}")
                            if step.details:
                                for detail in step.details[:5]:
                                    lines.append(f"   - {detail}")
                        else:
                            lines.append(f"{i}. {step}")
                    lines.append("")

                if entry.files_modified:
                    lines.append("**Files modified**:")
                    for f in entry.files_modified:
                        lines.append(f"- `{f}`")
                    lines.append("")

                lines.append("---")
                lines.append("")

        return "\n".join(lines)

    # ===== Helpers =====

    def _time_to_x(self, dt: datetime, axis_start: datetime) -> int:
        minutes = (dt - axis_start).total_seconds() / 60
        return TIME_AREA_X + int(minutes * PX_PER_MINUTE)

    def _add_cell(self, root, cell_id, value, style, x, y, width, height, tooltip=""):
        attrs = {
            "id": str(cell_id), "value": value, "style": style,
            "vertex": "1", "parent": "1",
        }
        if tooltip:
            attrs["tooltip"] = tooltip
        cell = ET.SubElement(root, "mxCell", **attrs)
        ET.SubElement(cell, "mxGeometry", x=str(x), y=str(y),
                      width=str(width), height=str(height), **{"as": "geometry"})
        return cell_id + 1

    def _add_edge(self, root, cell_id, source_id, target_id, color):
        ET.SubElement(root, "mxCell", **{
            "id": str(cell_id),
            "value": "",
            "style": f"edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor={color};",
            "edge": "1", "parent": "1",
            "source": str(source_id), "target": str(target_id),
        })
        return cell_id + 1
