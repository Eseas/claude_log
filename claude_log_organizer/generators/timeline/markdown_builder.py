"""Companion markdown generation for timeline diagrams."""

from collections import OrderedDict
from typing import List, Dict

from claude_log_organizer.models.task_data import TimelineEntry, TokenUsage, ProcessPhase
from claude_log_organizer.generators.timeline.styles import ProcessStep, STEP_TYPE_STYLES
from claude_log_organizer.generators.timeline.token_analyzer import analyze_token_usage


def build_markdown(
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
    analysis_lines = analyze_token_usage(merged_entries)
    if analysis_lines:
        lines.extend(analysis_lines)

    return "\n".join(lines)
