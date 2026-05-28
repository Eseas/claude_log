"""Time inference and entry merging for timeline entries."""

from datetime import timedelta
from typing import List

from claude_log_organizer.models.task_data import TimelineEntry


def infer_end_times(
    entries: List[TimelineEntry],
    default_duration: timedelta,
    max_gap: timedelta,
) -> List[TimelineEntry]:
    """Infer end times for entries based on gaps between consecutive entries."""
    for i, entry in enumerate(entries):
        if i + 1 < len(entries):
            next_start = entries[i + 1].start_time
            gap = next_start - entry.start_time
            if gap <= max_gap and gap > timedelta(0):
                entry.end_time = next_start
            else:
                entry.end_time = entry.start_time + default_duration
        else:
            entry.end_time = entry.start_time + default_duration
    return entries


def merge_same_requests(entries: List[TimelineEntry]) -> List[TimelineEntry]:
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
