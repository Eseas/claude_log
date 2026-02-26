"""Data models for task information extracted from logs."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Union


@dataclass
class CodeSnippet:
    """Represents a code snippet extracted from logs."""

    language: str
    code: str
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            "language": self.language,
            "code": self.code,
            "description": self.description,
        }


@dataclass
class PhaseInfo:
    """Phase timing information."""

    name: str
    timestamp: datetime
    duration: Optional[float] = None  # seconds

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "duration": self.duration,
        }


@dataclass
class CheckpointInfo:
    """Checkpoint information."""

    name: str
    timestamp: datetime
    status: str  # approved, waiting, rejected

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            "name": self.name,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "status": self.status,
        }


@dataclass
class TaskData:
    """Complete task information extracted from logs."""

    task_id: str
    timestamp: Optional[datetime] = None

    # Summary information
    work_summary: str = ""
    status: str = "unknown"  # completed, failed, in_progress, pending

    # Implementation details
    approach_name: str = ""
    implementation_details: Dict[str, Any] = field(default_factory=dict)
    files_modified: List[str] = field(default_factory=list)
    files_created: List[str] = field(default_factory=list)

    # Technical information
    key_decisions: List[str] = field(default_factory=list)
    libraries_used: List[str] = field(default_factory=list)
    architecture_patterns: List[str] = field(default_factory=list)

    # Code snippets
    code_snippets: List[CodeSnippet] = field(default_factory=list)

    # Phase information
    phases: List[PhaseInfo] = field(default_factory=list)
    checkpoints: List[CheckpointInfo] = field(default_factory=list)
    total_duration: Optional[float] = None  # seconds

    # Testing/Review
    review_passed: Optional[bool] = None
    test_passed: Optional[bool] = None

    # Thinking / Reasoning
    thinking_summary: List[str] = field(default_factory=list)

    # Tool execution results
    tool_results_summary: List[str] = field(default_factory=list)

    # Reference documents
    referenced_documents: List[str] = field(default_factory=list)

    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            "task_id": self.task_id,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "work_summary": self.work_summary,
            "status": self.status,
            "approach_name": self.approach_name,
            "implementation_details": self.implementation_details,
            "files_modified": self.files_modified,
            "files_created": self.files_created,
            "key_decisions": self.key_decisions,
            "libraries_used": self.libraries_used,
            "architecture_patterns": self.architecture_patterns,
            "code_snippets": [cs.to_dict() for cs in self.code_snippets],
            "phases": [p.to_dict() for p in self.phases],
            "checkpoints": [c.to_dict() for c in self.checkpoints],
            "total_duration": self.format_duration(),
            "thinking_summary": self.thinking_summary,
            "tool_results_summary": self.tool_results_summary,
            "referenced_documents": self.referenced_documents,
            "review_passed": self.review_passed,
            "test_passed": self.test_passed,
            "metadata": self.metadata,
        }

    def format_duration(self) -> str:
        """Format duration as human-readable string."""
        if not self.total_duration:
            return "N/A"

        total_seconds = int(self.total_duration)
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"


@dataclass
class ProcessPhase:
    """여러 ProcessStep을 그룹화한 작업 페이즈."""

    phase_name: str        # "코드 분석 및 파일 탐색"
    primary_type: str      # analysis/decision/implementation/verification/summary
    step_count: int        # 원본 step 수
    summary: str           # 이 페이즈에서 한 일 요약
    key_details: List[str] = field(default_factory=list)  # 핵심 세부사항

    def to_dict(self) -> dict:
        return {
            "phase_name": self.phase_name,
            "primary_type": self.primary_type,
            "step_count": self.step_count,
            "summary": self.summary,
            "key_details": self.key_details,
        }


@dataclass
class TimelineEntry:
    """일일 타임라인의 단일 항목."""

    session_id: str          # Full UUID
    session_short: str       # 앞 8자리
    start_time: datetime
    end_time: datetime       # 추론됨
    label: str               # 작업 요약 (초기 요청에서 추출)
    task_file: str           # 파일명 참조
    status: str = "completed"
    process_steps: List[Any] = field(default_factory=list)  # ProcessStep objects or strings
    process_phases: List[Any] = field(default_factory=list)  # ProcessPhase objects (AI 요약)
    tools_used: str = ""     # 수행 작업 요약
    files_modified: List[str] = field(default_factory=list)
    thinking_summary: List[str] = field(default_factory=list)  # 사고 과정 요약
    compact_count: int = 0   # 컨텍스트 압축 횟수
    referenced_documents: List[str] = field(default_factory=list)  # 참조 문서
