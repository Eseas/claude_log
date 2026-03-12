"""Data models for task information extracted from logs."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Union


@dataclass
class TokenUsage:
    """Token usage statistics for a conversation."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    total_tokens: int = 0
    request_count: int = 0

    def __post_init__(self):
        self.total_tokens = (
            self.input_tokens + self.output_tokens
            + self.cache_read_tokens + self.cache_write_tokens
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for template rendering."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
            "total_tokens": self.total_tokens,
            "request_count": self.request_count,
        }

    def add(self, other: 'TokenUsage') -> 'TokenUsage':
        """Merge another TokenUsage into this one (returns new instance)."""
        return TokenUsage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
            cache_read_tokens=self.cache_read_tokens + other.cache_read_tokens,
            cache_write_tokens=self.cache_write_tokens + other.cache_write_tokens,
            request_count=self.request_count + other.request_count,
        )


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

    # Token usage
    token_usage: Optional['TokenUsage'] = None

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
            "token_usage": self.token_usage.to_dict() if self.token_usage else None,
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
class TaskInteraction:
    """A single task interaction: user request → assistant work → user feedback."""

    request: str                          # User's original request
    assistant_work: List[str] = field(default_factory=list)   # Assistant responses
    tools_used: List[Dict[str, str]] = field(default_factory=list)  # Tools executed
    tool_results: List[str] = field(default_factory=list)     # Tool execution results
    feedback: Optional[str] = None        # Next user message (None if last interaction)

    # Analysis results
    heuristic_result: Optional[str] = None   # "success", "failure", "partial", "unknown"
    heuristic_confidence: float = 0.0        # 0.0 ~ 1.0
    heuristic_signals: List[str] = field(default_factory=list)  # Detected signal descriptions

    ai_result: Optional[str] = None          # "success", "failure", "partial", "unknown"
    ai_confidence: float = 0.0
    ai_reasoning: str = ""                   # AI's explanation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request": self.request,
            "assistant_work": self.assistant_work,
            "tools_used": self.tools_used,
            "tool_results": self.tool_results,
            "feedback": self.feedback,
            "heuristic_result": self.heuristic_result,
            "heuristic_confidence": self.heuristic_confidence,
            "heuristic_signals": self.heuristic_signals,
            "ai_result": self.ai_result,
            "ai_confidence": self.ai_confidence,
            "ai_reasoning": self.ai_reasoning,
        }


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
    token_usage: Optional['TokenUsage'] = None  # 토큰 사용량
    # Session metadata for analysis
    user_message_count: int = 0
    tool_use_count: int = 0
    assistant_response_count: int = 0
    thinking_count: int = 0
