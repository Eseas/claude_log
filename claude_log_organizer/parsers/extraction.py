"""Shared extraction utilities for log parsers.

Centralizes tag-based regex patterns and common extraction logic
used across session_parser, conversation_parser, and other modules.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from claude_log_organizer.models.task_data import TokenUsage


# Pre-compiled tag boundary pattern — matches any known tag start
_TAG_BOUNDARY = r'\[(?:USER|ASSISTANT|TOOL|THINKING|TOOL_RESULT|DOCUMENT|SNAPSHOT|COMPACT|USAGE)\]'

# Tag extraction patterns: each captures content until the next tag or end of string
TAG_PATTERNS: Dict[str, re.Pattern] = {
    "user": re.compile(
        rf'\[USER\]\s*(.+?)(?=\n{_TAG_BOUNDARY}|\n=|$)', re.DOTALL
    ),
    "assistant": re.compile(
        rf'\[ASSISTANT\]\s*(.+?)(?=\n{_TAG_BOUNDARY}|\n=|$)', re.DOTALL
    ),
    "tool": re.compile(
        rf'\[TOOL\]\s*(\w+)\s*→\s*(.+?)(?=\n\[|\n\n|$)', re.DOTALL
    ),
    "thinking": re.compile(
        rf'\[THINKING\]\s*(.+?)(?=\n{_TAG_BOUNDARY}|\n=|$)', re.DOTALL
    ),
    "tool_result": re.compile(
        rf'\[TOOL_RESULT\]\s*(.+?)(?=\n{_TAG_BOUNDARY}|\n=|$)', re.DOTALL
    ),
    "document": re.compile(
        r'\[DOCUMENT\]\s*(.+?)(?:\n|$)'
    ),
    "compact": re.compile(r'\[COMPACT\]'),
    "usage": re.compile(
        r'\[USAGE\]\s*input:(\d+)\s+cache_read:(\d+)\s+cache_write:(\d+)\s+output:(\d+)'
    ),
}

# Filename patterns
SESSION_FILENAME_PATTERN = re.compile(
    r'(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})(\d{2})_([a-f0-9-]+)\.(?:log|md)'
)

TASK_FILENAME_PATTERN = re.compile(
    r'task-(\d{4})-(\d{2})-(\d{2})_(\d{2})(\d{2})(\d{2})_([a-f0-9-]+)\.md'
)

SESSION_ID_FROM_FILENAME = re.compile(
    r'(?:\d{4}-\d{2}-\d{2}_\d{6}_)?([a-f0-9-]+)\.(?:log|md)'
)

UUID_PATTERN = re.compile(
    r'([a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12})'
)


def extract_by_tag(content: str, tag: str) -> List[str]:
    """Extract all occurrences of a tagged section from log content.

    Args:
        content: Raw .log file content
        tag: Tag name (e.g. 'user', 'assistant', 'thinking')

    Returns:
        List of extracted text blocks
    """
    pattern = TAG_PATTERNS.get(tag)
    if not pattern:
        return []

    results = []
    for match in pattern.finditer(content):
        text = match.group(1).strip()
        if text:
            results.append(text)
    return results


def extract_tool_uses(content: str) -> List[Dict[str, str]]:
    """Extract tool name and action pairs from [TOOL] tags.

    Returns:
        List of {'tool': name, 'action': action_text} dicts
    """
    tools = []
    for match in TAG_PATTERNS["tool"].finditer(content):
        tools.append({
            "tool": match.group(1).strip(),
            "action": match.group(2).strip(),
        })
    return tools


def extract_compact_count(content: str) -> int:
    """Count [COMPACT] occurrences."""
    return len(TAG_PATTERNS["compact"].findall(content))


def extract_token_usage(content: str) -> Optional[TokenUsage]:
    """Aggregate token usage from all [USAGE] tags."""
    matches = TAG_PATTERNS["usage"].findall(content)
    if not matches:
        return None

    total_input = total_output = total_cache_read = total_cache_write = 0
    for m in matches:
        total_input += int(m[0])
        total_cache_read += int(m[1])
        total_cache_write += int(m[2])
        total_output += int(m[3])

    return TokenUsage(
        input_tokens=total_input,
        output_tokens=total_output,
        cache_read_tokens=total_cache_read,
        cache_write_tokens=total_cache_write,
        request_count=len(matches),
    )


def extract_documents(content: str) -> List[str]:
    """Extract referenced document names from [DOCUMENT] tags."""
    docs = []
    for match in TAG_PATTERNS["document"].finditer(content):
        name = match.group(1).strip()
        if name and name != "untitled":
            docs.append(name)
    return docs


def extract_session_id_from_filename(filename: str) -> Optional[str]:
    """Extract session UUID from a log or task filename.

    Handles formats:
        YYYY-MM-DD_HHMMSS_<uuid>.log
        task-YYYY-MM-DD_HHMMSS_<uuid>.md
        <uuid>.log
    """
    match = SESSION_ID_FROM_FILENAME.search(filename)
    return match.group(1) if match else None


def extract_datetime_from_filename(filename: str) -> Optional[datetime]:
    """Extract datetime from a session-style filename.

    Handles: YYYY-MM-DD_HHMMSS_<uuid>.log or task-YYYY-MM-DD_HHMMSS_<uuid>.md
    """
    match = SESSION_FILENAME_PATTERN.search(filename)
    if not match:
        match = TASK_FILENAME_PATTERN.search(filename)
    if match:
        return datetime(
            int(match.group(1)), int(match.group(2)), int(match.group(3)),
            int(match.group(4)), int(match.group(5)), int(match.group(6)),
        )
    return None


def extract_uuid_from_string(text: str) -> Optional[str]:
    """Extract the first UUID from an arbitrary string."""
    match = UUID_PATTERN.search(text)
    return match.group(1) if match else None


def extract_files_from_tool_actions(
    tool_uses: List[Dict[str, str]],
    target_tools: List[str],
) -> List[str]:
    """Extract file paths from tool action text.

    Args:
        tool_uses: List of {'tool': name, 'action': text} dicts
        target_tools: Only consider these tool names (e.g. ['Edit', 'Write'])

    Returns:
        Sorted, deduplicated list of file paths (max 20)
    """
    files = set()
    for tool in tool_uses:
        if tool["tool"] not in target_tools:
            continue
        paths = re.findall(r'[~/][\w/.-]+\.\w+', tool["action"])
        files.update(paths)
    return sorted(files)[:20]


def extract_thinking_summaries(content: str, max_count: int = 20) -> List[str]:
    """Extract first meaningful sentence from each [THINKING] block."""
    summaries = []
    for match in TAG_PATTERNS["thinking"].finditer(content):
        text = match.group(1).strip()
        if not text or len(text) < 10:
            continue
        for line in text.split('\n'):
            line = line.strip()
            if line and len(line) > 15 and not line.startswith('---'):
                summaries.append(line[:200])
                break
    return summaries[:max_count]


def extract_tool_results(content: str, max_count: int = 30) -> List[str]:
    """Extract first line of each [TOOL_RESULT] block."""
    results = []
    for match in TAG_PATTERNS["tool_result"].finditer(content):
        text = match.group(1).strip()
        if text and len(text) > 5:
            first_line = text.split('\n')[0].strip()[:200]
            results.append(first_line)
    return results[:max_count]
