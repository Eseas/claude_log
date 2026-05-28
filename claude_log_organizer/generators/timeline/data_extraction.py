"""Task file parsing — extract TimelineEntry data from task markdown files."""

import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from claude_log_organizer.models.task_data import TimelineEntry, TokenUsage
from claude_log_organizer.generators.timeline.styles import ProcessStep


def parse_task_files(files: List[Path]) -> List[TimelineEntry]:
    """Parse task files into TimelineEntry list."""
    entries = []
    for file_path in files:
        dt = _extract_datetime_from_filename(file_path.name)
        session_id = _extract_session_from_filename(file_path.name)

        if not dt or not session_id:
            continue

        content = _read_file(file_path)
        label = _extract_label(content, file_path)
        process_steps = _extract_process_steps(content)
        tools_used = _extract_tools_used(content)
        files_modified = _extract_files_modified(content)
        thinking_summary = _extract_thinking_summary(content)
        compact_count = _extract_compact_count(content)
        referenced_documents = _extract_referenced_documents(content)
        token_usage = _extract_token_usage(content)
        session_stats = _extract_session_stats(content)

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


def _read_file(file_path: Path) -> str:
    try:
        return file_path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _extract_datetime_from_filename(filename: str) -> Optional[datetime]:
    match = re.match(
        r"task-(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})(\d{2})_", filename
    )
    if match:
        return datetime(
            int(match.group(1)), int(match.group(2)), int(match.group(3)),
            int(match.group(4)), int(match.group(5)), int(match.group(6)),
        )
    return None


def _extract_session_from_filename(filename: str) -> Optional[str]:
    match = re.search(r"task-\d{4}-\d{2}-\d{2}_\d{6}_([a-f0-9-]+)\.md", filename)
    return match.group(1) if match else None


def _extract_label(content: str, file_path: Path) -> str:
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


def _extract_process_steps(content: str) -> List[ProcessStep]:
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
        step_type = _classify_step(summary, details)
        steps.append(ProcessStep(type=step_type, summary=summary, details=details[:5]))

    return steps


def _classify_step(summary: str, details: List[str]) -> str:
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


def _extract_tools_used(content: str) -> str:
    match = re.search(r"\*\*수행 작업\*\*:\s*\n((?:- .+\n?)+)", content)
    if match:
        return match.group(1).strip()
    return ""


def _extract_files_modified(content: str) -> List[str]:
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


def _extract_thinking_summary(content: str) -> List[str]:
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


def _extract_compact_count(content: str) -> int:
    """Extract context compression count."""
    match = re.search(r"\*\*Context Compressions\*\*:\s*(\d+)", content)
    if match:
        return int(match.group(1))
    return 0


def _extract_referenced_documents(content: str) -> List[str]:
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


def _extract_token_usage(content: str) -> Optional[TokenUsage]:
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


def _extract_session_stats(content: str) -> dict:
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
