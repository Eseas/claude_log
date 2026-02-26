"""Parser for conversation logs with full dialogue."""

import re
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

from claude_log_organizer.parsers.base_parser import BaseLogParser
from claude_log_organizer.models.task_data import TaskData, CodeSnippet


class ConversationLogParser(BaseLogParser):
    """Parser for conversation logs with full dialogue."""

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle conversation logs."""
        return "conversation" in file_path.name.lower() and file_path.suffix == ".log"

    def parse(self, file_path: Path) -> TaskData:
        """Extract key information from conversation logs.

        Args:
            file_path: Path to conversation log file

        Returns:
            TaskData object with extracted information
        """
        content = self._read_file(file_path)

        return TaskData(
            task_id=self._extract_task_id(file_path),
            timestamp=self._extract_timestamp(content),
            work_summary=self._extract_work_summary(content),
            key_decisions=self._extract_key_decisions(content),
            implementation_details=self._extract_implementation_details(content),
            code_snippets=self._extract_code_snippets(content),
            files_modified=self._extract_files_modified(content),
            files_created=self._extract_files_created(content),
            status=self._extract_status(content),
            metadata=self._extract_metadata(content),
        )

    def _extract_task_id(self, file_path: Path) -> str:
        """Extract task ID from filename.

        Args:
            file_path: Path to log file

        Returns:
            Task ID extracted from filename

        Example:
            conversation-task-20260212-130624.log -> 20260212-130624
        """
        match = re.search(r"conversation-task-(.+?)\.log", file_path.name)
        if match:
            return match.group(1)
        return file_path.stem  # Fallback to filename without extension

    def _extract_timestamp(self, content: str) -> Optional[datetime]:
        """Extract timestamp from log content.

        Args:
            content: Log file content

        Returns:
            Datetime object or None
        """
        # Look for ISO format timestamps
        match = re.search(
            r"(\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)", content
        )
        if match:
            try:
                timestamp_str = match.group(1).replace(" ", "T")
                # Handle fractional seconds
                if "." in timestamp_str:
                    return datetime.fromisoformat(timestamp_str)
                else:
                    return datetime.fromisoformat(timestamp_str)
            except Exception:
                pass
        return None

    def _extract_work_summary(self, content: str) -> str:
        """Extract summary of work performed.

        Args:
            content: Log file content

        Returns:
            Summary string
        """
        # Look for common summary patterns
        patterns = [
            r"(?:Summary|SUMMARY|Overview)[:：]\s*(.+?)(?:\n\n|\n[A-Z]|$)",
            r"(?:Implemented|Created|Added|Fixed|Updated)[:：]?\s*(.+?)(?:\n\n|\n[A-Z]|$)",
            r"(?:Task|작업)[:：]\s*(.+?)(?:\n\n|\n[A-Z]|$)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.DOTALL)
            if match:
                summary = match.group(1).strip()
                # Clean up and truncate if too long
                summary = re.sub(r"\s+", " ", summary)
                if len(summary) > 500:
                    summary = summary[:500] + "..."
                return summary

        # Fallback: Try to extract first meaningful paragraph
        lines = content.split("\n")
        for line in lines[:50]:  # Check first 50 lines
            line = line.strip()
            if len(line) > 50 and not line.startswith("#"):
                return line[:500]

        return "No summary available"

    def _extract_key_decisions(self, content: str) -> List[str]:
        """Extract important technical decisions.

        Args:
            content: Log file content

        Returns:
            List of key decisions
        """
        decisions = []

        # Look for decision markers
        patterns = [
            r"(?:Key Decision|Decision|결정)[:：]\s*(.+?)(?:\n\n|\n-|$)",
            r"(?:Decided to|Chose to)[:：]?\s*(.+?)(?:\n\n|\n-|$)",
            r"(?:Approach|방법)[:：]\s*(.+?)(?:\n\n|\n-|$)",
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, content, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                decision = match.group(1).strip()
                if decision and len(decision) > 10:
                    decisions.append(decision[:200])

        # Look for bullet lists of decisions
        decision_section = re.search(
            r"(?:Key.*?Decisions?|Technical.*?Decisions?)[:：]?\s*\n((?:\s*[-*]\s*.+\n?)+)",
            content,
            re.IGNORECASE | re.MULTILINE,
        )
        if decision_section:
            bullets = re.findall(r"[-*]\s*(.+)", decision_section.group(1))
            decisions.extend([b.strip()[:200] for b in bullets if len(b.strip()) > 10])

        return decisions[:10]  # Limit to 10 decisions

    def _extract_implementation_details(self, content: str) -> Dict[str, Any]:
        """Extract implementation specifics.

        Args:
            content: Log file content

        Returns:
            Dictionary with implementation details
        """
        details = {}

        # Extract approach name
        approach_match = re.search(
            r"(?:Approach|방법|Strategy)[:：]\s*(.+?)(?:\n|$)",
            content,
            re.IGNORECASE,
        )
        if approach_match:
            details["approach"] = approach_match.group(1).strip()

        # Extract architecture patterns
        arch_patterns = [
            "hexagonal",
            "mvc",
            "mvvm",
            "microservices",
            "monolith",
            "layered",
        ]
        found_patterns = []
        for pattern in arch_patterns:
            if re.search(rf"\b{pattern}\b", content, re.IGNORECASE):
                found_patterns.append(pattern.capitalize())
        if found_patterns:
            details["architecture"] = found_patterns

        return details

    def _extract_code_snippets(self, content: str) -> List[CodeSnippet]:
        """Extract relevant code examples.

        Args:
            content: Log file content

        Returns:
            List of CodeSnippet objects
        """
        snippets = []

        # Find markdown code blocks: ```language\ncode\n```
        pattern = r"```(\w+)?\n(.*?)```"
        matches = re.finditer(pattern, content, re.DOTALL)

        for match in matches:
            language = match.group(1) or "text"
            code = match.group(2).strip()

            # Skip very short or very long snippets
            if len(code) < 10 or len(code) > 5000:
                continue

            # Limit number of lines
            lines = code.split("\n")
            if len(lines) > 50:
                code = "\n".join(lines[:50]) + "\n... (truncated)"

            snippets.append(CodeSnippet(language=language, code=code, description=""))

        return snippets[:5]  # Limit to 5 snippets

    def _extract_files_modified(self, content: str) -> List[str]:
        """Extract list of modified files.

        Args:
            content: Log file content

        Returns:
            List of file paths
        """
        files = []

        # Look for file modification markers
        patterns = [
            r"(?:Modified|Updated|Changed)[:：]?\s*\n((?:\s*[-*]\s*`?.+?`?\n?)+)",
            r"(?:Files?\s+Modified)[:：]?\s*\n((?:\s*[-*]\s*`?.+?`?\n?)+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                file_list = re.findall(r"[-*]\s*`?([^\n`]+)`?", match.group(1))
                files.extend([f.strip() for f in file_list])

        return list(set(files))[:20]  # Deduplicate and limit

    def _extract_files_created(self, content: str) -> List[str]:
        """Extract list of created files.

        Args:
            content: Log file content

        Returns:
            List of file paths
        """
        files = []

        # Look for file creation markers
        patterns = [
            r"(?:Created|Added|New)[:：]?\s*\n((?:\s*[-*]\s*`?.+?`?\n?)+)",
            r"(?:Files?\s+Created)[:：]?\s*\n((?:\s*[-*]\s*`?.+?`?\n?)+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE | re.MULTILINE)
            if match:
                file_list = re.findall(r"[-*]\s*`?([^\n`]+)`?", match.group(1))
                files.extend([f.strip() for f in file_list])

        return list(set(files))[:20]  # Deduplicate and limit

    def _extract_status(self, content: str) -> str:
        """Extract task status.

        Args:
            content: Log file content

        Returns:
            Status string (completed, failed, in_progress, pending)
        """
        # Look for status indicators
        if re.search(
            r"\b(completed|done|finished|success)\b", content, re.IGNORECASE
        ):
            return "completed"
        elif re.search(r"\b(failed|error|failure)\b", content, re.IGNORECASE):
            return "failed"
        elif re.search(
            r"\b(in progress|working|ongoing)\b", content, re.IGNORECASE
        ):
            return "in_progress"
        else:
            return "unknown"

    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """Extract additional metadata.

        Args:
            content: Log file content

        Returns:
            Dictionary with metadata
        """
        metadata = {}

        # Extract word count
        metadata["word_count"] = len(content.split())

        # Extract line count
        metadata["line_count"] = len(content.split("\n"))

        return metadata
