"""Parser for Claude Code session logs with structured format."""

import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from claude_log_organizer.parsers.base_parser import BaseLogParser
from claude_log_organizer.models.task_data import TaskData, CodeSnippet


class ClaudeSessionLogParser(BaseLogParser):
    """Parser for Claude Code session logs."""

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle Claude session logs.

        Looks for files with pattern: YYYY-MM-DD_HHMMSS_session-id.log
        or checks for session log header.
        """
        # Check filename pattern
        if re.match(r'\d{4}-\d{2}-\d{2}_\d{6}_[a-f0-9-]+\.log', file_path.name):
            return True

        # Check file content for session log header
        try:
            content = self._read_file(file_path)
            return content.startswith("=== Claude Code Session Log ===")
        except:
            return False

    def parse(self, file_path: Path) -> TaskData:
        """Extract key information from Claude session logs.

        Args:
            file_path: Path to session log file

        Returns:
            TaskData object with extracted information
        """
        content = self._read_file(file_path)

        # Extract header information
        session_id = self._extract_session_id(content, file_path)
        project_path = self._extract_project_path(content)
        timestamp = self._extract_timestamp(content)

        # Parse conversation
        user_messages = self._extract_user_messages(content)
        tool_uses = self._extract_tool_uses(content)
        assistant_responses = self._extract_assistant_responses(content)

        # Generate work summary
        work_summary = self._generate_work_summary(user_messages, tool_uses, assistant_responses)

        # Extract file operations
        files_modified = self._extract_files_from_tools(tool_uses, ['Edit', 'Write'])
        files_created = self._extract_files_from_tools(tool_uses, ['Write'])

        # Extract key decisions from assistant responses
        key_decisions = self._extract_key_points(assistant_responses)

        return TaskData(
            task_id=session_id,
            timestamp=timestamp,
            work_summary=work_summary,
            key_decisions=key_decisions,
            files_modified=files_modified,
            files_created=files_created,
            status="completed",
            metadata={
                "project_path": project_path,
                "user_message_count": len(user_messages),
                "tool_use_count": len(tool_uses),
                "assistant_response_count": len(assistant_responses),
            }
        )

    def _extract_session_id(self, content: str, file_path: Path) -> str:
        """Extract session ID from log header or filename.

        Args:
            content: Log file content
            file_path: Path to log file

        Returns:
            Session ID string
        """
        # Try to extract from header
        match = re.search(r'Session ID:\s*([a-f0-9-]+)', content)
        if match:
            return match.group(1)

        # Try to extract from filename: YYYY-MM-DD_HHMMSS_session-id.log
        match = re.search(r'\d{4}-\d{2}-\d{2}_\d{6}_([a-f0-9-]+)\.log', file_path.name)
        if match:
            return match.group(1)

        # Fallback to filename without extension
        return file_path.stem

    def _extract_project_path(self, content: str) -> Optional[str]:
        """Extract project path from log header.

        Args:
            content: Log file content

        Returns:
            Project path or None
        """
        match = re.search(r'Project:\s*(.+)', content)
        if match:
            return match.group(1).strip()
        return None

    def _extract_timestamp(self, content: str) -> Optional[datetime]:
        """Extract timestamp from log header.

        Args:
            content: Log file content

        Returns:
            Datetime object or None
        """
        match = re.search(r'Saved at:\s*(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', content)
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
            except:
                pass
        return None

    def _extract_user_messages(self, content: str) -> List[str]:
        """Extract user messages from log.

        Args:
            content: Log file content

        Returns:
            List of user messages
        """
        messages = []
        pattern = r'\[USER\]\s*(.+?)(?=\n\[(?:USER|TOOL|ASSISTANT)\]|\n=|$)'

        for match in re.finditer(pattern, content, re.DOTALL):
            message = match.group(1).strip()
            if message and len(message) > 5:  # Filter out very short messages
                messages.append(message)

        return messages

    def _extract_tool_uses(self, content: str) -> List[Dict[str, str]]:
        """Extract tool usage information from log.

        Args:
            content: Log file content

        Returns:
            List of dictionaries with tool name and action
        """
        tools = []
        # Pattern: [TOOL] ToolName → action/command
        pattern = r'\[TOOL\]\s*(\w+)\s*→\s*(.+?)(?=\n\[|\n\n|$)'

        for match in re.finditer(pattern, content, re.DOTALL):
            tool_name = match.group(1).strip()
            action = match.group(2).strip()

            tools.append({
                'tool': tool_name,
                'action': action
            })

        return tools

    def _extract_assistant_responses(self, content: str) -> List[str]:
        """Extract assistant responses from log.

        Args:
            content: Log file content

        Returns:
            List of assistant responses
        """
        responses = []
        pattern = r'\[ASSISTANT\]\s*(.+?)(?=\n\[(?:USER|TOOL|ASSISTANT)\]|\n=|$)'

        for match in re.finditer(pattern, content, re.DOTALL):
            response = match.group(1).strip()
            if response and len(response) > 10:
                responses.append(response)

        return responses

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

    def _extract_files_from_tools(
        self,
        tool_uses: List[Dict[str, str]],
        target_tools: List[str]
    ) -> List[str]:
        """Extract file paths from specific tool uses.

        Args:
            tool_uses: List of tool uses
            target_tools: List of tool names to extract from

        Returns:
            List of file paths
        """
        files = set()

        for tool in tool_uses:
            if tool['tool'] not in target_tools:
                continue

            action = tool['action']

            # Try to extract file path from action
            # Pattern: /path/to/file or ~/path/to/file
            paths = re.findall(r'[~/][\w/.-]+\.\w+', action)
            files.update(paths)

        return sorted(list(files))[:20]  # Limit to 20 files

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
