"""Parser for Claude Code session logs with structured format."""

import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from claude_log_organizer.parsers.base_parser import BaseLogParser
from claude_log_organizer.parsers.extraction import (
    TAG_PATTERNS,
    SESSION_FILENAME_PATTERN,
    extract_by_tag,
    extract_tool_uses,
    extract_compact_count,
    extract_token_usage,
    extract_documents,
    extract_thinking_summaries,
    extract_tool_results,
    extract_files_from_tool_actions,
    extract_session_id_from_filename,
)
from claude_log_organizer.models.task_data import TaskData, CodeSnippet, TokenUsage


class ClaudeSessionLogParser(BaseLogParser):
    """Parser for Claude Code session logs."""

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle Claude session logs.

        Looks for files with pattern: YYYY-MM-DD_HHMMSS_session-id.log
        or checks for session log header.
        """
        if re.match(r'\d{4}-\d{2}-\d{2}_\d{6}_[a-f0-9-]+\.log', file_path.name):
            return True

        try:
            content = self._read_file(file_path)
            return content.startswith("=== Claude Code Session Log ===")
        except Exception:
            return False

    def parse(self, file_path: Path) -> TaskData:
        """Extract key information from Claude session logs."""
        content = self._read_file(file_path)

        session_id = self._extract_session_id(content, file_path)
        project_path = self._extract_project_path(content)
        timestamp = self._extract_timestamp(content)

        user_messages = extract_by_tag(content, "user")
        user_messages = [m for m in user_messages if len(m) > 5]
        tool_uses_list = extract_tool_uses(content)
        assistant_responses = extract_by_tag(content, "assistant")
        assistant_responses = [r for r in assistant_responses if len(r) > 10]

        thinking_blocks = extract_thinking_summaries(content)
        tool_results_list = extract_tool_results(content)
        documents = extract_documents(content)
        compact_count_val = extract_compact_count(content)
        token_usage_val = extract_token_usage(content)

        work_summary = self._generate_work_summary(user_messages, tool_uses_list, assistant_responses)

        files_modified = extract_files_from_tool_actions(tool_uses_list, ['Edit', 'Write'])
        files_created = extract_files_from_tool_actions(tool_uses_list, ['Write'])

        key_decisions = self._extract_key_points(assistant_responses)
        key_decisions.extend(self._extract_thinking_decisions(thinking_blocks))
        key_decisions = key_decisions[:15]

        return TaskData(
            task_id=session_id,
            timestamp=timestamp,
            work_summary=work_summary,
            key_decisions=key_decisions,
            files_modified=files_modified,
            files_created=files_created,
            thinking_summary=thinking_blocks,
            tool_results_summary=tool_results_list,
            referenced_documents=documents,
            token_usage=token_usage_val,
            status="completed",
            metadata={
                "project_path": project_path,
                "user_message_count": len(user_messages),
                "tool_use_count": len(tool_uses_list),
                "assistant_response_count": len(assistant_responses),
                "thinking_count": len(thinking_blocks),
                "compact_count": compact_count_val,
                "has_thinking": len(thinking_blocks) > 0,
            }
        )

    def _extract_session_id(self, content: str, file_path: Path) -> str:
        """Extract session ID from log header or filename."""
        match = re.search(r'Session ID:\s*([a-f0-9-]+)', content)
        if match:
            return match.group(1)

        sid = extract_session_id_from_filename(file_path.name)
        return sid or file_path.stem

    def _extract_project_path(self, content: str) -> Optional[str]:
        """Extract project path from log header."""
        match = re.search(r'Project(?:-Root-Path)?:\s*(.+)', content)
        if match:
            return match.group(1).strip()
        return None

    def _extract_timestamp(self, content: str) -> Optional[datetime]:
        """Extract timestamp from log header."""
        match = re.search(r'Saved at:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', content)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
            except Exception:
                pass
        return None

    def _generate_work_summary(
        self,
        user_messages: List[str],
        tool_uses: List[Dict[str, str]],
        assistant_responses: List[str]
    ) -> str:
        """Generate work summary from conversation.

        Args:
            user_messages: List of user messages
            tool_uses: List of tool uses
            assistant_responses: List of assistant responses

        Returns:
            Summary string
        """
        if not user_messages:
            return "No work summary available"

        # Start with first user message as context
        summary_parts = [f"**초기 요청**: {user_messages[0][:500]}"]

        # Summarize tool usage
        if tool_uses:
            tool_summary = self._summarize_tool_usage(tool_uses)
            summary_parts.append(f"\n\n**수행 작업**:\n{tool_summary}")

        # Add detailed assistant responses
        if assistant_responses:
            # Include all assistant responses, not just the last one
            summary_parts.append(f"\n\n**대화 내용**:")
            for i, response in enumerate(assistant_responses, 1):
                # Take more content (first 1500 chars of each response)
                response_preview = response[:1500]
                if len(response) > 1500:
                    response_preview += "..."
                summary_parts.append(f"\n\n**응답 {i}**:\n{response_preview}")

        return ''.join(summary_parts)

    def _summarize_tool_usage(self, tool_uses: List[Dict[str, str]]) -> str:
        """Summarize tool usage into readable format.

        Args:
            tool_uses: List of tool uses

        Returns:
            Formatted summary string
        """
        # Count by tool type
        tool_counts = {}
        for tool in tool_uses:
            tool_name = tool['tool']
            tool_counts[tool_name] = tool_counts.get(tool_name, 0) + 1

        # Format summary
        lines = []
        for tool_name, count in tool_counts.items():
            if count == 1:
                lines.append(f"- {tool_name} 사용")
            else:
                lines.append(f"- {tool_name} {count}회 사용")

        return '\n'.join(lines)

    def _extract_thinking_decisions(self, thinking_blocks: List[str]) -> List[str]:
        """Extract decision-related sentences from thinking summaries."""
        decisions = []
        decision_patterns = [
            r'(?:I should|I need to|Let me|I\'ll|결정|선택|방법|접근|전략)',
        ]
        for block in thinking_blocks:
            for pattern in decision_patterns:
                if re.search(pattern, block, re.IGNORECASE):
                    decisions.append(block)
                    break
        return decisions[:5]

    def _extract_key_points(self, assistant_responses: List[str]) -> List[str]:
        """Extract key points from assistant responses.

        Args:
            assistant_responses: List of assistant responses

        Returns:
            List of key decision points
        """
        key_points = []

        for response in assistant_responses:
            # Look for bullet points or numbered lists
            bullets = re.findall(r'^\s*[-*•]\s*(.+)$', response, re.MULTILINE)
            key_points.extend([b.strip() for b in bullets if len(b.strip()) > 20])

            # Look for "수정", "변경", "구현" patterns
            decisions = re.findall(
                r'(?:수정|변경|구현|추가|삭제|생성)(?:했습니다|함|됨|완료)[:：]?\s*(.{10,100})',
                response
            )
            key_points.extend([d.strip() for d in decisions])

        return key_points[:10]  # Limit to top 10 key points
