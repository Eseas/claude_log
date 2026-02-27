"""Generates draw.io (.drawio) timeline diagrams and companion markdown from task files."""

import hashlib
import json
import logging
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional, Dict, Tuple
from collections import OrderedDict

from claude_log_organizer.models.task_data import TimelineEntry, ProcessPhase, TokenUsage

logger = logging.getLogger(__name__)


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
BAR_LANE_GAP = 4
ROW_BOTTOM_PADDING = 16
PX_PER_MINUTE = 4
MIN_BAR_WIDTH = 50

# Per-entry page layout constants
ENTRY_PAGE_WIDTH = 520
ENTRY_PAGE_LEFT_MARGIN = 30
ENTRY_BOX_WIDTH = 450
ENTRY_BOX_MIN_HEIGHT = 60
ENTRY_LINE_HEIGHT = 16
ENTRY_V_GAP = 10
ENTRY_ARROW_GAP = 20
ENTRY_TITLE_HEIGHT = 50
ENTRY_META_HEIGHT = 30
ENTRY_TAB_MAX_CHARS = 40


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

        # Summarize process steps into phases for entries with many steps
        for entry in merged_entries:
            if len(entry.process_steps) > 8:
                entry.process_phases = self._summarize_process_steps(entry.process_steps)

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
            token_usage = self._extract_token_usage(content)
            session_stats = self._extract_session_stats(content)

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
                token_usage=token_usage,
                **session_stats,
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
        # Strip IDE metadata tags
        label = re.sub(r"<ide_opened_file>.*?</ide_opened_file>\s*", "", label).strip()
        label = re.sub(r"<ide_opened_file>.*$", "", label).strip()
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

    def _extract_token_usage(self, content: str) -> Optional[TokenUsage]:
        """Extract token usage from ### Token Usage table in task markdown."""
        match = re.search(
            r'\| Input \| ([\d,]+) \|.*?'
            r'\| Output \| ([\d,]+) \|.*?'
            r'\| Cache Read \| ([\d,]+) \|.*?'
            r'\| Cache Write \| ([\d,]+) \|.*?'
            r'\| \*\*Total\*\* \| \*\*([\d,]+)\*\* \|.*?'
            r'\*\*API Requests\*\*:\s*(\d+)',
            content, re.DOTALL,
        )
        if not match:
            return None

        def parse_num(s: str) -> int:
            return int(s.replace(',', ''))

        return TokenUsage(
            input_tokens=parse_num(match.group(1)),
            output_tokens=parse_num(match.group(2)),
            cache_read_tokens=parse_num(match.group(3)),
            cache_write_tokens=parse_num(match.group(4)),
            request_count=int(match.group(6)),
        )

    def _extract_session_stats(self, content: str) -> dict:
        """Extract session stats from ### Session Stats table in task markdown."""
        stats = {
            "user_message_count": 0,
            "tool_use_count": 0,
            "assistant_response_count": 0,
            "thinking_count": 0,
        }
        patterns = {
            "user_message_count": r'\| User Messages \| (\d+) \|',
            "assistant_response_count": r'\| Assistant Responses \| (\d+) \|',
            "tool_use_count": r'\| Tool Uses \| (\d+) \|',
            "thinking_count": r'\| Thinking Blocks \| (\d+) \|',
        }
        for key, pattern in patterns.items():
            match = re.search(pattern, content)
            if match:
                stats[key] = int(match.group(1))
        return stats

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
                token_usage=e.token_usage,
                user_message_count=e.user_message_count,
                tool_use_count=e.tool_use_count,
                assistant_response_count=e.assistant_response_count,
                thinking_count=e.thinking_count,
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
                # Merge token usage
                if entry.token_usage:
                    if prev.token_usage:
                        prev.token_usage = prev.token_usage.add(entry.token_usage)
                    else:
                        prev.token_usage = entry.token_usage
                # Merge session stats (take max - later entries are more complete)
                prev.user_message_count = max(prev.user_message_count, entry.user_message_count)
                prev.tool_use_count = max(prev.tool_use_count, entry.tool_use_count)
                prev.assistant_response_count = max(prev.assistant_response_count, entry.assistant_response_count)
                prev.thinking_count = max(prev.thinking_count, entry.thinking_count)
            else:
                merged.append(_clone_entry(entry))

        return merged

    # ===== Process step summarization =====

    def _summarize_process_steps(self, steps: List['ProcessStep']) -> List[ProcessPhase]:
        """Two-stage summarization: algorithmic grouping + optional AI refinement."""
        # Stage 1: algorithmic grouping (merge consecutive same-type)
        phases = self._group_consecutive_steps(steps)

        # If already compact enough, return
        if len(phases) <= 8:
            return phases

        # Stage 2: AI summarization
        steps_hash = self._get_steps_hash(steps)
        cached = self._load_cached_phases(steps_hash)
        if cached is not None:
            logger.info(f"Using cached phase summary ({len(cached)} phases)")
            return cached

        ai_phases = self._ai_summarize_phases(steps)
        if ai_phases is not None:
            logger.info(f"AI summarized {len(steps)} steps into {len(ai_phases)} phases")
            self._save_cached_phases(steps_hash, ai_phases)
            return ai_phases

        # Stage 3: Algorithmic condensation (fallback when AI unavailable)
        condensed = self._condense_phases(phases)
        logger.info(f"Algorithmically condensed {len(phases)} phases into {len(condensed)} phases")
        return condensed

    def _group_consecutive_steps(self, steps: List['ProcessStep']) -> List[ProcessPhase]:
        """Group consecutive same-type steps into phases."""
        if not steps:
            return []

        phases = []
        current_type = None
        current_steps: List['ProcessStep'] = []

        for step in steps:
            step_type = step.type if isinstance(step, ProcessStep) else "analysis"
            if step_type != current_type and current_steps:
                phases.append(self._steps_to_phase(current_steps, current_type))
                current_steps = []
            current_type = step_type
            current_steps.append(step)

        if current_steps:
            phases.append(self._steps_to_phase(current_steps, current_type))

        return phases

    def _steps_to_phase(self, steps: List['ProcessStep'], step_type: str) -> ProcessPhase:
        """Convert a group of same-type steps into a single ProcessPhase."""
        first = steps[0]
        summary = first.summary if isinstance(first, ProcessStep) else str(first)

        # Collect key details from steps that have them
        details = []
        for s in steps:
            if isinstance(s, ProcessStep) and s.details:
                for d in s.details[:2]:
                    if d not in details:
                        details.append(d)
                        if len(details) >= 5:
                            break
            if len(details) >= 5:
                break

        icon = STEP_TYPE_STYLES.get(step_type, STEP_TYPE_STYLES["analysis"])[2]
        type_label = step_type.capitalize()

        return ProcessPhase(
            phase_name=f"{summary}" if len(steps) == 1 else f"{type_label}: {summary}",
            primary_type=step_type,
            step_count=len(steps),
            summary=summary,
            key_details=details,
        )

    def _condense_phases(self, phases: List[ProcessPhase]) -> List[ProcessPhase]:
        """Condense many algorithmic phases into ~6 by equal-sized chunking."""
        if len(phases) <= 8:
            return phases

        target_count = 6
        chunk_size = max(1, len(phases) // target_count)
        condensed = []

        for i in range(0, len(phases), chunk_size):
            chunk = phases[i:i + chunk_size]

            # Dominant type by step_count
            type_counts: Dict[str, int] = {}
            for p in chunk:
                type_counts[p.primary_type] = type_counts.get(p.primary_type, 0) + p.step_count
            dominant_type = max(type_counts, key=type_counts.get)

            total_steps = sum(p.step_count for p in chunk)

            # Aggregate unique key_details (max 5)
            aggregated_details: List[str] = []
            for p in chunk:
                for d in p.key_details:
                    if d not in aggregated_details:
                        aggregated_details.append(d)
                    if len(aggregated_details) >= 5:
                        break
                if len(aggregated_details) >= 5:
                    break

            condensed.append(ProcessPhase(
                phase_name=chunk[0].phase_name,
                primary_type=dominant_type,
                step_count=total_steps,
                summary=chunk[0].summary,
                key_details=aggregated_details,
            ))

        return condensed

    def _ai_summarize_phases(self, steps: List['ProcessStep']) -> Optional[List[ProcessPhase]]:
        """Use Claude CLI to summarize steps into 5-8 meaningful phases."""
        if shutil.which("claude") is None:
            logger.info("Claude CLI not available, using algorithmic grouping")
            return None

        prompt = self._build_summarization_prompt(steps)

        try:
            result = subprocess.run(
                ["claude", "--print"],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                logger.warning(f"Claude CLI failed: {result.stderr[:200]}")
                return None

            return self._parse_ai_phases(result.stdout.strip())
        except subprocess.TimeoutExpired:
            logger.warning("Claude CLI timed out for phase summarization")
            return None
        except Exception as e:
            logger.warning(f"Claude CLI error: {e}")
            return None

    def _build_summarization_prompt(self, steps: List['ProcessStep']) -> str:
        """Build prompt for AI phase summarization."""
        # Limit to first 100 steps to avoid overly long prompts
        display_steps = steps[:100]
        step_lines = []
        for i, step in enumerate(display_steps, 1):
            if isinstance(step, ProcessStep):
                step_lines.append(f"{i}. [{step.type}] {step.summary}")
            else:
                step_lines.append(f"{i}. [analysis] {step}")

        if len(steps) > 100:
            step_lines.append(f"... (총 {len(steps)}개 중 처음 100개만 표시)")

        steps_text = "\n".join(step_lines)

        return f"""다음은 하나의 Claude 작업 세션에서 추출된 {len(steps)}개의 작업 단계입니다.
이 단계들을 5~8개의 의미 있는 작업 페이즈(phase)로 그룹화해주세요.

각 페이즈는 반드시 다음 형식으로 출력해주세요:
PHASE: [페이즈 이름]
TYPE: [analysis|decision|implementation|verification|summary]
STEPS: [시작번호]-[끝번호]
SUMMARY: [이 페이즈에서 한 일을 한 문장으로 요약]
DETAILS:
- [핵심 세부사항 1]
- [핵심 세부사항 2]
- [핵심 세부사항 3]
---

규칙:
- 반드시 5~8개의 페이즈로 그룹화
- 각 페이즈 사이에 "---"를 넣어주세요
- TYPE은 반드시 analysis, decision, implementation, verification, summary 중 하나
- STEPS는 시작번호와 끝번호를 하이픈으로 연결
- DETAILS는 최대 3개

작업 단계:
{steps_text}"""

    def _parse_ai_phases(self, response: str) -> Optional[List[ProcessPhase]]:
        """Parse structured AI response into ProcessPhase objects."""
        phases = []
        blocks = response.split("---")

        valid_types = {"analysis", "decision", "implementation", "verification", "summary"}

        for block in blocks:
            block = block.strip()
            if not block:
                continue

            phase_match = re.search(r"PHASE:\s*(.+)", block)
            type_match = re.search(r"TYPE:\s*(\w+)", block)
            steps_match = re.search(r"STEPS:\s*(\d+)\s*-\s*(\d+)", block)
            summary_match = re.search(r"SUMMARY:\s*(.+)", block)

            if not all([phase_match, type_match, steps_match, summary_match]):
                continue

            phase_type = type_match.group(1).strip().lower()
            if phase_type not in valid_types:
                phase_type = "analysis"

            start_idx = int(steps_match.group(1))
            end_idx = int(steps_match.group(2))
            step_count = max(end_idx - start_idx + 1, 1)

            details = re.findall(r"^- (.+)$", block, re.MULTILINE)

            phases.append(ProcessPhase(
                phase_name=phase_match.group(1).strip(),
                primary_type=phase_type,
                step_count=step_count,
                summary=summary_match.group(1).strip(),
                key_details=details[:5],
            ))

        if len(phases) < 3 or len(phases) > 12:
            logger.warning(f"AI returned {len(phases)} phases (expected 3-12), falling back")
            return None

        return phases

    # ===== Phase cache =====

    def _get_steps_hash(self, steps: List['ProcessStep']) -> str:
        content = "|".join(
            f"{s.type}:{s.summary[:50]}" if isinstance(s, ProcessStep) else str(s)[:50]
            for s in steps
        )
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def _load_cached_phases(self, steps_hash: str) -> Optional[List[ProcessPhase]]:
        cache_path = Path("summaries/.phase_cache.json")
        if not cache_path.exists():
            return None
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
            if steps_hash in cache:
                return [ProcessPhase(**p) for p in cache[steps_hash]]
        except Exception:
            pass
        return None

    def _save_cached_phases(self, steps_hash: str, phases: List[ProcessPhase]):
        cache_path = Path("summaries/.phase_cache.json")
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8")) if cache_path.exists() else {}
        except Exception:
            cache = {}
        cache[steps_hash] = [p.to_dict() for p in phases]
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception as e:
            logger.warning(f"Failed to save phase cache: {e}")

    # ===== draw.io XML generation =====

    def _build_drawio_xml(
        self,
        merged_entries: List[TimelineEntry],
        all_entries: List[TimelineEntry],
        title: str,
    ) -> str:
        """Build .drawio with Page 1 (Gantt) and per-entry pages (Process Flow)."""
        mxfile = ET.Element("mxfile", host="Claude Log Organizer")

        # Page 1: Gantt Timeline
        self._build_gantt_page(mxfile, merged_entries, title)

        # Pages 2..N: One page per merged entry
        sessions_seen: List[str] = []
        for entry in merged_entries:
            if entry.session_short not in sessions_seen:
                sessions_seen.append(entry.session_short)

        for entry_idx, entry in enumerate(merged_entries):
            session_idx = sessions_seen.index(entry.session_short)
            color_fill, color_stroke = COLORS[session_idx % len(COLORS)]
            self._build_entry_page(mxfile, entry, entry_idx, color_fill, color_stroke)

        ET.indent(mxfile, space="  ")
        return ET.tostring(mxfile, encoding="unicode", xml_declaration=True)

    def _assign_lanes(self, entries: List[TimelineEntry], axis_start: datetime) -> List[int]:
        """Assign lanes to entries to avoid visual overlap on the Gantt chart.

        Returns a list of lane indices (0-based), one per entry.
        Entries that don't overlap share lane 0; overlapping ones go to higher lanes.
        """
        lanes: List[List[Tuple[int, int]]] = []  # each lane: list of (bar_x, bar_end_x)
        result: List[int] = []
        for entry in entries:
            bar_x = self._time_to_x(entry.start_time, axis_start)
            bar_end_x = self._time_to_x(entry.end_time, axis_start)
            bar_end_x = max(bar_end_x, bar_x + MIN_BAR_WIDTH)

            assigned = False
            for lane_idx, lane in enumerate(lanes):
                overlap = any(bar_x < lex and bar_end_x > lx for lx, lex in lane)
                if not overlap:
                    lane.append((bar_x, bar_end_x))
                    result.append(lane_idx)
                    assigned = True
                    break

            if not assigned:
                lanes.append([(bar_x, bar_end_x)])
                result.append(len(lanes) - 1)

        return result

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
        rows_start_y = TIME_AXIS_Y + TIME_AXIS_HEIGHT + 10

        # Pre-compute lanes for overlap detection and dynamic row heights
        session_lanes: Dict[str, List[int]] = {}
        session_max_lanes: Dict[str, int] = {}
        session_row_heights: Dict[str, int] = {}
        session_row_y: Dict[str, int] = {}
        cumulative_y = rows_start_y
        for session_short, session_entries in sessions.items():
            lanes = self._assign_lanes(session_entries, axis_start)
            session_lanes[session_short] = lanes
            max_l = (max(lanes) + 1) if lanes else 1
            session_max_lanes[session_short] = max_l
            row_h = BAR_Y_OFFSET + max_l * BAR_HEIGHT + (max_l - 1) * BAR_LANE_GAP + ROW_BOTTOM_PADDING
            session_row_heights[session_short] = row_h
            session_row_y[session_short] = cumulative_y
            cumulative_y += row_h
        total_rows_height = cumulative_y - rows_start_y
        page_height = cumulative_y + 40

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
                x_pos, rows_start_y, 1, total_rows_height)
            current_time += timedelta(minutes=30)

        # Session rows and bars
        for session_idx, (session_short, session_entries) in enumerate(sessions.items()):
            color_fill, color_stroke = COLORS[session_idx % len(COLORS)]
            row_y = session_row_y[session_short]
            row_height = session_row_heights[session_short]
            lanes = session_lanes[session_short]

            cell_id = self._add_cell(root, cell_id, session_short,
                f"text;html=1;align=right;verticalAlign=middle;resizable=0;points=[];autosize=1;strokeColor=none;fillColor=none;fontSize=11;fontStyle=1;fontColor={color_stroke};",
                0, row_y + BAR_Y_OFFSET - 5, SESSION_LABEL_WIDTH, 30)

            if session_idx % 2 == 0:
                cell_id = self._add_cell(root, cell_id, "",
                    "rounded=0;whiteSpace=wrap;html=1;fillColor=#F9F9F9;strokeColor=none;opacity=50;",
                    TIME_AREA_X, row_y, time_axis_width, row_height)

            for entry_local_idx, entry in enumerate(session_entries):
                lane = lanes[entry_local_idx]
                bar_x = self._time_to_x(entry.start_time, axis_start)
                bar_end_x = self._time_to_x(entry.end_time, axis_start)
                bar_width = max(bar_end_x - bar_x, MIN_BAR_WIDTH)
                bar_y = row_y + BAR_Y_OFFSET + lane * (BAR_HEIGHT + BAR_LANE_GAP)
                time_range = f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}"

                bar_label = entry.label
                tooltip_lines = [entry.label, time_range, entry.task_file]
                if entry.process_phases:
                    tooltip_lines.append("")
                    tooltip_lines.append("[Work Phases]")
                    for phase in entry.process_phases:
                        icon = STEP_TYPE_STYLES.get(phase.primary_type, STEP_TYPE_STYLES["analysis"])[2]
                        tooltip_lines.append(f"  {icon} {phase.phase_name} ({phase.step_count} steps)")
                elif entry.process_steps:
                    tooltip_lines.append("")
                    for i, step in enumerate(entry.process_steps, 1):
                        if isinstance(step, ProcessStep):
                            icon = STEP_TYPE_STYLES.get(step.type, STEP_TYPE_STYLES["analysis"])[2]
                            tooltip_lines.append(f"{i}. {icon} [{step.type}] {step.summary}")
                        else:
                            tooltip_lines.append(f"{i}. {step}")
                if entry.thinking_summary:
                    tooltip_lines.append("")
                    tooltip_lines.append("[Thinking]")
                    for t in entry.thinking_summary:
                        tooltip_lines.append(f"  - {t}")
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

    def _estimate_box_height(self, text_lines: int) -> int:
        """Estimate box height based on number of text lines."""
        return max(ENTRY_BOX_MIN_HEIGHT, 30 + text_lines * ENTRY_LINE_HEIGHT)

    def _build_entry_page(
        self,
        mxfile: ET.Element,
        entry: TimelineEntry,
        entry_idx: int,
        color_fill: str,
        color_stroke: str,
    ) -> None:
        """Build a single draw.io page for one entry with vertical phase/step flow."""
        # Page tab name: max 40 chars, word-boundary truncation (no ellipsis)
        tab_name = entry.label
        if len(tab_name) > ENTRY_TAB_MAX_CHARS:
            cut = tab_name[:ENTRY_TAB_MAX_CHARS].rfind(' ')
            tab_name = tab_name[:cut] if cut > 20 else tab_name[:ENTRY_TAB_MAX_CHARS]

        diagram_id = f"entry_{entry_idx}"
        diagram = ET.SubElement(mxfile, "diagram", name=tab_name, id=diagram_id)

        graph_model = ET.SubElement(
            diagram, "mxGraphModel",
            dx=str(ENTRY_PAGE_WIDTH), dy="2000",
            grid="1", gridSize="10", guides="1", tooltips="1",
            connect="1", arrows="1", fold="1", page="1", pageScale="1",
            pageWidth=str(ENTRY_PAGE_WIDTH), pageHeight="2000",
        )
        root = ET.SubElement(graph_model, "root")
        ET.SubElement(root, "mxCell", id="0")
        ET.SubElement(root, "mxCell", id="1", parent="0")

        # Cell ID offset to avoid collisions across pages
        cell_id = 2 + (entry_idx + 1) * 10000

        y_cursor = 20

        # --- Title ---
        cell_id = self._add_cell(root, cell_id, f"<b>{entry.label}</b>",
            "text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;"
            "strokeColor=none;fillColor=none;fontSize=14;fontStyle=1;whiteSpace=wrap;",
            ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, ENTRY_TITLE_HEIGHT)
        y_cursor += ENTRY_TITLE_HEIGHT

        # --- Meta: time + session ---
        time_str = f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}"
        meta_text = f"Session {entry.session_short} | {time_str}"
        if entry.compact_count > 0:
            meta_text += f" | compact x{entry.compact_count}"
        cell_id = self._add_cell(root, cell_id, meta_text,
            f"text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;"
            f"strokeColor=none;fillColor=none;fontSize=10;fontColor={color_stroke};",
            ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, ENTRY_META_HEIGHT)
        y_cursor += ENTRY_META_HEIGHT + 10

        # --- Referenced documents ---
        if entry.referenced_documents:
            for doc in entry.referenced_documents:
                cell_id = self._add_cell(root, cell_id,
                    f"📄 {doc}",
                    "rounded=1;whiteSpace=wrap;html=1;fillColor=#f5f5f5;strokeColor=#cccccc;"
                    "fontSize=9;fontColor=#666666;fontStyle=2;align=left;verticalAlign=middle;spacingLeft=6;",
                    ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, 26)
                y_cursor += 30
            y_cursor += 5

        # --- Legend ---
        legend_x = ENTRY_PAGE_LEFT_MARGIN
        for step_type, (fill, stroke, icon) in STEP_TYPE_STYLES.items():
            legend_style = (
                f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                f"fontSize=8;fontColor=#333333;align=center;verticalAlign=middle;"
            )
            cell_id = self._add_cell(root, cell_id,
                f"{icon} {step_type.capitalize()}",
                legend_style,
                legend_x, y_cursor, 88, 20)
            legend_x += 95
        y_cursor += 30

        # --- Phase/Step vertical flow ---
        items = entry.process_phases if entry.process_phases else entry.process_steps
        prev_cell_id = None

        if items:
            for idx, item in enumerate(items):
                if isinstance(item, ProcessPhase):
                    fill, stroke, icon = STEP_TYPE_STYLES.get(item.primary_type, STEP_TYPE_STYLES["analysis"])

                    label_parts = [f"<b>{icon} {idx + 1}. {item.phase_name}</b>"]
                    label_parts.append(
                        f"<br/><font style='font-size:9px' color='#666666'>"
                        f"({item.step_count} steps, {item.primary_type})</font>"
                    )
                    label_parts.append(f"<br/>{item.summary}")
                    for detail in item.key_details:
                        label_parts.append(
                            f"<br/><font style='font-size:8px' color='#555555'>- {detail}</font>"
                        )

                    label = "".join(label_parts)
                    text_lines = 3 + len(item.key_details)
                    box_height = self._estimate_box_height(text_lines)
                    item_type = item.primary_type

                elif isinstance(item, ProcessStep):
                    fill, stroke, icon = STEP_TYPE_STYLES.get(item.type, STEP_TYPE_STYLES["analysis"])

                    label_parts = [f"<b>{icon} {idx + 1}. {item.summary}</b>"]
                    for detail in item.details:
                        label_parts.append(
                            f"<br/><font style='font-size:8px' color='#555555'>- {detail}</font>"
                        )

                    label = "".join(label_parts)
                    text_lines = 1 + len(item.details)
                    box_height = self._estimate_box_height(text_lines)
                    item_type = item.type

                else:
                    label = f"<b>{idx + 1}.</b> {item}"
                    box_height = ENTRY_BOX_MIN_HEIGHT
                    item_type = "analysis"
                    fill, stroke, icon = STEP_TYPE_STYLES["analysis"]

                # Style by type
                if item_type == "decision":
                    style = (
                        f"shape=hexagon;perimeter=hexagonPerimeter2;whiteSpace=wrap;html=1;"
                        f"fixedSize=1;size=10;fillColor={fill};strokeColor={stroke};strokeWidth=2;"
                        f"fontSize=9;fontColor=#333333;align=left;verticalAlign=top;"
                        f"spacingLeft=12;spacingRight=12;spacingTop=6;"
                    )
                elif item_type == "verification":
                    style = (
                        f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                        f"strokeWidth=2;fontSize=9;fontColor=#333333;align=left;verticalAlign=top;"
                        f"spacingLeft=6;spacingRight=6;spacingTop=6;dashed=1;dashPattern=3 2;"
                    )
                else:
                    style = (
                        f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                        f"strokeWidth=1;fontSize=9;fontColor=#333333;align=left;verticalAlign=top;"
                        f"spacingLeft=6;spacingRight=6;spacingTop=6;"
                    )

                current_cell_id = cell_id
                cell_id = self._add_cell(root, cell_id, label, style,
                    ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, box_height)

                if prev_cell_id is not None:
                    cell_id = self._add_edge(root, cell_id, prev_cell_id, current_cell_id,
                                             color_stroke, vertical=True)

                prev_cell_id = current_cell_id
                y_cursor += box_height + ENTRY_ARROW_GAP

        # --- Thinking summary ---
        if entry.thinking_summary:
            y_cursor += 10
            cell_id = self._add_cell(root, cell_id, "<b>Thinking / Reasoning</b>",
                "text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;"
                "strokeColor=none;fillColor=none;fontSize=11;fontStyle=1;fontColor=#777777;",
                ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, 24)
            y_cursor += 28

            for thought in entry.thinking_summary:
                thought_lines = max(1, len(thought) // 70 + 1)
                thought_height = max(24, thought_lines * ENTRY_LINE_HEIGHT + 8)
                cell_id = self._add_cell(root, cell_id,
                    f"<i>💭 {thought}</i>",
                    "rounded=1;whiteSpace=wrap;html=1;fillColor=#fafafa;strokeColor=#e0e0e0;"
                    "fontSize=9;fontColor=#666666;fontStyle=2;align=left;verticalAlign=top;"
                    "spacingLeft=6;spacingRight=6;spacingTop=4;",
                    ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, thought_height)
                y_cursor += thought_height + 6

        # --- Files modified ---
        if entry.files_modified:
            y_cursor += 10
            cell_id = self._add_cell(root, cell_id, "<b>Files Modified</b>",
                "text;html=1;align=left;verticalAlign=middle;resizable=0;points=[];autosize=1;"
                "strokeColor=none;fillColor=none;fontSize=11;fontStyle=1;fontColor=#777777;",
                ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, 24)
            y_cursor += 28

            files_label = "<br/>".join(f"- {f}" for f in entry.files_modified)
            files_height = max(30, len(entry.files_modified) * ENTRY_LINE_HEIGHT + 12)
            cell_id = self._add_cell(root, cell_id, files_label,
                "rounded=1;whiteSpace=wrap;html=1;fillColor=#f0f4f8;strokeColor=#b0bec5;"
                "fontSize=9;fontColor=#37474f;align=left;verticalAlign=top;"
                "spacingLeft=6;spacingRight=6;spacingTop=4;",
                ENTRY_PAGE_LEFT_MARGIN, y_cursor, ENTRY_BOX_WIDTH, files_height)
            y_cursor += files_height + 10

        # --- Finalize page height ---
        actual_height = y_cursor + 30
        graph_model.set("dy", str(actual_height))
        graph_model.set("pageHeight", str(actual_height))

    # ===== Token usage analysis =====

    def _analyze_token_usage(self, entries: List[TimelineEntry]) -> List[str]:
        """Analyze token usage patterns, identify high-usage sessions, and suggest reductions.

        Returns list of markdown lines for the analysis section.
        """
        # Filter entries with token data
        with_tokens = [e for e in entries if e.token_usage and e.token_usage.total_tokens > 0]
        if len(with_tokens) < 2:
            return []

        totals = [e.token_usage.total_tokens for e in with_tokens]
        avg_tokens = sum(totals) / len(totals)
        threshold = avg_tokens * 1.5

        # Identify high-usage sessions
        high_usage = [e for e in with_tokens if e.token_usage.total_tokens >= threshold]
        if not high_usage:
            return []

        high_usage.sort(key=lambda e: e.token_usage.total_tokens, reverse=True)

        lines = [
            "## Token Usage Analysis",
            "",
        ]

        # High usage table
        lines.append("### High Usage Sessions")
        lines.append(f"> 평균 토큰: {avg_tokens:,.0f} / 기준 (1.5x): {threshold:,.0f}")
        lines.append("")
        lines.append("| Session | Task | Total Tokens | Requests | Tokens/Req | Factors |")
        lines.append("|---------|------|-------------|----------|------------|---------|")

        for entry in high_usage:
            tu = entry.token_usage
            tpr = tu.total_tokens // tu.request_count if tu.request_count else 0
            factors = self._identify_factors(entry)
            factor_str = ", ".join(factors) if factors else "-"
            label = entry.label[:40] + "..." if len(entry.label) > 40 else entry.label
            lines.append(
                f"| `{entry.session_short}` | {label} "
                f"| {tu.total_tokens:,} | {tu.request_count} | {tpr:,} | {factor_str} |"
            )

        lines.append("")

        # Per-session analysis
        lines.append("### Analysis")
        lines.append("")

        for entry in high_usage:
            tu = entry.token_usage
            label = entry.label[:50] + "..." if len(entry.label) > 50 else entry.label
            lines.append(f"#### `{entry.session_short}` - {label}")
            lines.append("")

            # Causes
            factors = self._identify_factors(entry)
            if factors:
                lines.append(f"- **주요 원인**: {', '.join(factors)}")

            # Cache efficiency
            input_side = tu.input_tokens + tu.cache_read_tokens + tu.cache_write_tokens
            if input_side > 0:
                cache_eff = (tu.cache_read_tokens / input_side) * 100
                avg_cache_eff = self._avg_cache_efficiency(with_tokens)
                quality = "양호" if cache_eff >= avg_cache_eff else "평균 대비 낮음"
                lines.append(f"- **캐시 효율**: {cache_eff:.0f}% ({quality})")

            # Output ratio
            if tu.total_tokens > 0:
                output_ratio = (tu.output_tokens / tu.total_tokens) * 100
                lines.append(f"- **출력 비율**: {output_ratio:.0f}%")

            lines.append("")

        # Reduction strategies
        strategies = self._suggest_strategies(high_usage, with_tokens)
        if strategies:
            lines.append("### Reduction Strategies")
            lines.append("")
            for i, strategy in enumerate(strategies, 1):
                lines.append(f"{i}. {strategy}")
            lines.append("")

        return lines

    def _identify_factors(self, entry: TimelineEntry) -> List[str]:
        """Identify factors that may explain high token usage."""
        factors = []
        if entry.compact_count > 0:
            factors.append(f"compact x{entry.compact_count}")
        if entry.tool_use_count > 15:
            factors.append(f"도구 {entry.tool_use_count}회")
        if entry.thinking_count > 10:
            factors.append(f"thinking {entry.thinking_count}블록")
        if entry.assistant_response_count > 20:
            factors.append(f"응답 {entry.assistant_response_count}회")
        if entry.token_usage and entry.token_usage.request_count > 0:
            tpr = entry.token_usage.total_tokens // entry.token_usage.request_count
            if tpr > 5000:
                factors.append(f"요청당 {tpr:,} tokens")
        return factors

    def _avg_cache_efficiency(self, entries: List[TimelineEntry]) -> float:
        """Calculate average cache efficiency across entries."""
        effs = []
        for e in entries:
            tu = e.token_usage
            input_side = tu.input_tokens + tu.cache_read_tokens + tu.cache_write_tokens
            if input_side > 0:
                effs.append((tu.cache_read_tokens / input_side) * 100)
        return sum(effs) / len(effs) if effs else 0

    def _suggest_strategies(
        self,
        high_usage: List[TimelineEntry],
        all_entries: List[TimelineEntry],
    ) -> List[str]:
        """Generate reduction strategies based on patterns found in high-usage sessions."""
        strategies = []

        compact_sessions = [e for e in high_usage if e.compact_count > 0]
        if compact_sessions:
            strategies.append(
                f"대화가 길어지기 전에 새 세션을 시작하세요"
                f" — 컨텍스트 압축이 발생한 세션이 {len(compact_sessions)}개 있습니다"
            )

        heavy_tool = [e for e in high_usage if e.tool_use_count > 15]
        if heavy_tool:
            strategies.append(
                f"구체적인 지시로 불필요한 탐색을 줄이세요"
                f" — 도구 호출이 15회 이상인 세션이 {len(heavy_tool)}개 있습니다"
            )

        heavy_thinking = [e for e in high_usage if e.thinking_count > 10]
        if heavy_thinking:
            strategies.append(
                f"단순 작업에는 thinking 제한을 고려하세요"
                f" — thinking 블록이 10개 이상인 세션이 {len(heavy_thinking)}개 있습니다"
            )

        low_cache = []
        avg_eff = self._avg_cache_efficiency(all_entries)
        for e in high_usage:
            tu = e.token_usage
            input_side = tu.input_tokens + tu.cache_read_tokens + tu.cache_write_tokens
            if input_side > 0:
                eff = (tu.cache_read_tokens / input_side) * 100
                if eff < avg_eff * 0.7:
                    low_cache.append(e)
        if low_cache:
            strategies.append(
                f"동일 세션 내에서 대화를 이어가 캐시 활용도를 높이세요"
                f" — 캐시 효율이 낮은 세션이 {len(low_cache)}개 있습니다"
            )

        verbose = []
        for e in high_usage:
            tu = e.token_usage
            if tu.total_tokens > 0 and (tu.output_tokens / tu.total_tokens) > 0.25:
                verbose.append(e)
        if verbose:
            strategies.append(
                f"간결한 응답을 요청하세요"
                f" — 출력 비율이 25% 이상인 세션이 {len(verbose)}개 있습니다"
            )

        high_tpr = []
        for e in high_usage:
            tu = e.token_usage
            if tu.request_count > 0 and tu.total_tokens // tu.request_count > 5000:
                high_tpr.append(e)
        if high_tpr:
            strategies.append(
                f"작업을 더 작은 단위로 분할하세요"
                f" — 요청당 5,000+ 토큰을 사용하는 세션이 {len(high_tpr)}개 있습니다"
            )

        return strategies

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

        # Daily total token usage
        daily_tokens = TokenUsage()
        for entry in merged_entries:
            if entry.token_usage:
                daily_tokens = daily_tokens.add(entry.token_usage)
        if daily_tokens.total_tokens > 0:
            lines.append(f"**Total tokens**: {daily_tokens.total_tokens:,} (input: {daily_tokens.input_tokens:,} / output: {daily_tokens.output_tokens:,} / cache read: {daily_tokens.cache_read_tokens:,} / cache write: {daily_tokens.cache_write_tokens:,})")
            lines.append(f"**API Requests**: {daily_tokens.request_count}")

        lines.append("")
        lines.append("---")
        lines.append("")

        # Overview table
        lines.append("## Overview")
        lines.append("")
        lines.append("| Time | Session | Task | Tokens |")
        lines.append("|------|---------|------|--------|")
        for entry in merged_entries:
            time_str = f"{entry.start_time.strftime('%H:%M')} - {entry.end_time.strftime('%H:%M')}"
            token_str = f"{entry.token_usage.total_tokens:,}" if entry.token_usage and entry.token_usage.total_tokens > 0 else "-"
            lines.append(f"| {time_str} | `{entry.session_short}` | {entry.label} | {token_str} |")

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

                if entry.process_phases:
                    lines.append(f"**Work phases** ({len(entry.process_steps)} steps):")
                    lines.append("")
                    for i, phase in enumerate(entry.process_phases, 1):
                        icon = STEP_TYPE_STYLES.get(phase.primary_type, STEP_TYPE_STYLES["analysis"])[2]
                        lines.append(f"{i}. {icon} **[{phase.primary_type.upper()}]** {phase.phase_name} ({phase.step_count} steps)")
                        lines.append(f"   *{phase.summary}*")
                        if phase.key_details:
                            for detail in phase.key_details:
                                lines.append(f"   - {detail}")
                    lines.append("")
                elif entry.process_steps:
                    lines.append("**Work process**:")
                    lines.append("")
                    for i, step in enumerate(entry.process_steps, 1):
                        if isinstance(step, ProcessStep):
                            icon = STEP_TYPE_STYLES.get(step.type, STEP_TYPE_STYLES["analysis"])[2]
                            lines.append(f"{i}. {icon} **[{step.type.upper()}]** {step.summary}")
                            if step.details:
                                for detail in step.details:
                                    lines.append(f"   - {detail}")
                        else:
                            lines.append(f"{i}. {step}")
                    lines.append("")

                if entry.files_modified:
                    lines.append("**Files modified**:")
                    for f in entry.files_modified:
                        lines.append(f"- `{f}`")
                    lines.append("")

                if entry.token_usage and entry.token_usage.total_tokens > 0:
                    tu = entry.token_usage
                    lines.append(f"**Token usage**: {tu.total_tokens:,} tokens ({tu.request_count} requests)")
                    lines.append(f"  - Input: {tu.input_tokens:,} / Output: {tu.output_tokens:,} / Cache Read: {tu.cache_read_tokens:,} / Cache Write: {tu.cache_write_tokens:,}")
                    lines.append("")

                lines.append("---")
                lines.append("")

        # Token usage analysis
        analysis_lines = self._analyze_token_usage(merged_entries)
        if analysis_lines:
            lines.extend(analysis_lines)

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

    def _add_edge(self, root, cell_id, source_id, target_id, color, vertical=False):
        style = f"edgeStyle=orthogonalEdgeStyle;rounded=1;strokeColor={color};"
        if vertical:
            style += "exitX=0.5;exitY=1;exitDx=0;exitDy=0;entryX=0.5;entryY=0;entryDx=0;entryDy=0;"
        ET.SubElement(root, "mxCell", **{
            "id": str(cell_id),
            "value": "",
            "style": style,
            "edge": "1", "parent": "1",
            "source": str(source_id), "target": str(target_id),
        })
        return cell_id + 1
