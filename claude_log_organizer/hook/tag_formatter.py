"""Convert parsed JSONL transcript entries into tagged log blocks.

Each function takes a decoded JSONL entry (dict) and returns a list of
"blocks". A block is a string that will be written followed by a blank line,
mirroring the original bash hook's `echo "..."; echo ""` sequence.

Tags produced: [USER], [DOCUMENT], [TOOL_RESULT], [THINKING], [ASSISTANT],
[TOOL], [USAGE], [SNAPSHOT], [COMPACT].
"""

from typing import Any, List

TOOL_RESULT_MAX_CHARS = 300

# Tools whose first input field is surfaced after the arrow.
_TOOL_PARAM_FIELDS = {
    "Bash": "command",
    "Read": "file_path",
    "Write": "file_path",
    "Edit": "file_path",
    "Glob": "pattern",
    "Grep": "pattern",
}


def _content_list(message: Any) -> list:
    """Return message.content if it is a list, else an empty list."""
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, list):
            return content
    return []


def _join_text_content(message: Any) -> str:
    """Extract text from a message's content (array of blocks or plain string)."""
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, list):
        texts = [b.get("text", "") for b in content
                 if isinstance(b, dict) and b.get("type") == "text"]
        return "\n".join(texts)
    if isinstance(content, str):
        return content
    return ""


def format_user_message(message: Any) -> List[str]:
    """Build [USER], [DOCUMENT], and [TOOL_RESULT] blocks from a user entry."""
    blocks: List[str] = []

    text = _join_text_content(message)
    if text:
        blocks.append(f"[USER] {text}")

    documents = [
        f"[DOCUMENT] {b.get('title') or 'untitled'}"
        for b in _content_list(message)
        if isinstance(b, dict) and b.get("type") == "document"
    ]
    if documents:
        blocks.append("\n".join(documents))

    tool_results = []
    for b in _content_list(message):
        if not (isinstance(b, dict) and b.get("type") == "tool_result"):
            continue
        content = b.get("content")
        if isinstance(content, list):
            joined = " ".join(
                c.get("text", "")[:TOOL_RESULT_MAX_CHARS]
                for c in content
                if isinstance(c, dict) and c.get("type") == "text"
            )
        elif isinstance(content, str):
            joined = content[:TOOL_RESULT_MAX_CHARS]
        else:
            joined = ""
        tool_results.append(f"[TOOL_RESULT] {joined}")
    if tool_results:
        blocks.append("\n".join(tool_results))

    return blocks


def _format_tool_use(block: dict) -> str:
    """Format a single tool_use block as `[TOOL] Name → param` (or no arrow)."""
    name = block.get("name", "")
    field = _TOOL_PARAM_FIELDS.get(name)
    if field is None:
        return f"[TOOL] {name}"
    value = (block.get("input") or {}).get(field) or ""
    if name == "Bash":
        value = value.split("\n")[0]
    return f"[TOOL] {name} → {value}"


def format_assistant_message(message: Any) -> List[str]:
    """Build [THINKING], [ASSISTANT], [TOOL], and [USAGE] blocks."""
    blocks: List[str] = []

    thinking = [
        b.get("thinking", "")
        for b in _content_list(message)
        if isinstance(b, dict) and b.get("type") == "thinking"
    ]
    if thinking:
        blocks.append("[THINKING] " + "\n---\n".join(thinking))

    text = _join_text_content(message)
    if text and text != "\n\n":
        blocks.append(f"[ASSISTANT] {text}")

    tools = [
        _format_tool_use(b)
        for b in _content_list(message)
        if isinstance(b, dict) and b.get("type") == "tool_use"
    ]
    if tools:
        blocks.append("\n".join(tools))

    usage = message.get("usage") if isinstance(message, dict) else None
    if usage:
        blocks.append(
            "[USAGE] "
            f"input:{usage.get('input_tokens', 0)} "
            f"cache_read:{usage.get('cache_read_input_tokens', 0)} "
            f"cache_write:{usage.get('cache_creation_input_tokens', 0)} "
            f"output:{usage.get('output_tokens', 0)}"
        )

    return blocks


def format_snapshot(entry: dict) -> List[str]:
    """Build the [SNAPSHOT] line. Returns [] when no files are tracked."""
    snapshot = entry.get("snapshot") or {}
    backups = snapshot.get("trackedFileBackups") or {}
    count = len(backups)
    if count:
        return [f"[SNAPSHOT] {count} files tracked"]
    return []


def format_compact(entry: dict) -> bool:
    """Return True if this system entry is a context-compression boundary."""
    return entry.get("subtype") == "compact_boundary"
