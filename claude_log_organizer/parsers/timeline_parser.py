"""Parser for timeline logs with phase information."""

import re
from pathlib import Path
from datetime import datetime
from typing import List, Optional

from claude_log_organizer.parsers.base_parser import BaseLogParser
from claude_log_organizer.models.task_data import TaskData, PhaseInfo, CheckpointInfo


class TimelineLogParser(BaseLogParser):
    """Parser for timeline logs with phase information."""

    def can_parse(self, file_path: Path) -> bool:
        """Check if this parser can handle timeline logs."""
        return "timeline" in file_path.name.lower() and file_path.suffix == ".log"

    def parse(self, file_path: Path) -> TaskData:
        """Extract phase information and timing.

        Args:
            file_path: Path to timeline log file

        Returns:
            TaskData object with phase and checkpoint information
        """
        content = self._read_file(file_path)

        phases = self._parse_phases(content)
        checkpoints = self._parse_checkpoints(content)
        total_duration = self._calculate_duration(phases)
        status = self._determine_status(phases, checkpoints)

        return TaskData(
            task_id=self._extract_task_id(file_path),
            phases=phases,
            checkpoints=checkpoints,
            total_duration=total_duration,
            status=status,
        )

    def _extract_task_id(self, file_path: Path) -> str:
        """Extract task ID from filename.

        Args:
            file_path: Path to log file

        Returns:
            Task ID
        """
        # Try to extract from filename pattern
        match = re.search(r"task-(.+?)[-.]", file_path.name)
        if match:
            return match.group(1)
        return file_path.stem

    def _parse_phases(self, content: str) -> List[PhaseInfo]:
        """Parse phase markers like [PHASE] validation_start.

        Args:
            content: Log file content

        Returns:
            List of PhaseInfo objects
        """
        phases = []

        # Pattern: [timestamp] [PHASE] phase_name
        pattern = r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]\s+\[PHASE\]\s+(\w+)"

        for match in re.finditer(pattern, content):
            timestamp_str, phase_name = match.groups()

            try:
                # Parse timestamp
                timestamp = self._parse_timestamp(timestamp_str)

                # Calculate duration if we have a previous phase
                duration = None
                if phases:
                    prev_phase = phases[-1]
                    duration = (timestamp - prev_phase.timestamp).total_seconds()
                    prev_phase.duration = duration

                phases.append(PhaseInfo(name=phase_name, timestamp=timestamp))

            except Exception as e:
                # Skip invalid timestamps
                continue

        return phases

    def _parse_checkpoints(self, content: str) -> List[CheckpointInfo]:
        """Parse checkpoint markers.

        Args:
            content: Log file content

        Returns:
            List of CheckpointInfo objects
        """
        checkpoints = []

        # Pattern: [timestamp] [CHECKPOINT] checkpoint_name (status)
        pattern = r"\[(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?)\]\s+\[CHECKPOINT\]\s+(\w+)(?:\s+\((\w+)\))?"

        for match in re.finditer(pattern, content):
            timestamp_str, checkpoint_name, status = match.groups()

            try:
                timestamp = self._parse_timestamp(timestamp_str)
                checkpoints.append(
                    CheckpointInfo(
                        name=checkpoint_name,
                        timestamp=timestamp,
                        status=status or "unknown",
                    )
                )
            except Exception:
                continue

        return checkpoints

    def _parse_timestamp(self, timestamp_str: str) -> datetime:
        """Parse ISO format timestamp.

        Args:
            timestamp_str: Timestamp string

        Returns:
            Datetime object

        Raises:
            ValueError if timestamp cannot be parsed
        """
        return datetime.fromisoformat(timestamp_str)

    def _calculate_duration(self, phases: List[PhaseInfo]) -> Optional[float]:
        """Calculate total duration from phases.

        Args:
            phases: List of phase information

        Returns:
            Total duration in seconds or None
        """
        if len(phases) < 2:
            return None

        first_phase = phases[0]
        last_phase = phases[-1]

        return (last_phase.timestamp - first_phase.timestamp).total_seconds()

    def _determine_status(
        self, phases: List[PhaseInfo], checkpoints: List[CheckpointInfo]
    ) -> str:
        """Determine task status from phases and checkpoints.

        Args:
            phases: List of phases
            checkpoints: List of checkpoints

        Returns:
            Status string
        """
        # Check if there's a completion phase
        if phases:
            last_phase = phases[-1].name.lower()
            if "complete" in last_phase or "done" in last_phase:
                return "completed"
            elif "failed" in last_phase or "error" in last_phase:
                return "failed"

        # Check checkpoint status
        if checkpoints:
            last_checkpoint = checkpoints[-1]
            if last_checkpoint.status.lower() in ["approved", "completed"]:
                return "completed"
            elif last_checkpoint.status.lower() in ["rejected", "failed"]:
                return "failed"

        return "in_progress"
