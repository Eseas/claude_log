"""Shared pytest fixtures for the test suite."""

import pytest


SESSION_ID = "abc12345-6789-0000-1111-222233334444"


@pytest.fixture
def sample_session_log():
    """A representative Claude session .log with all tag types."""
    return f"""=== Claude Code Session Log ===
Session ID: {SESSION_ID}
Project-Root-Path: /Users/test/project
Saved at: 2026-05-27 14:30:00

[USER]
main.py 파일을 수정해줘

[ASSISTANT]
파일을 수정하겠습니다. 먼저 현재 상태를 확인합니다.

[TOOL] Read → /Users/test/project/main.py
[TOOL_RESULT] def main(): pass

[TOOL] Edit → /Users/test/project/main.py
[TOOL_RESULT] File edited successfully

[THINKING]
I should verify the change works correctly by reading the file again.

[ASSISTANT]
- 수정했습니다: main.py 함수 본문 구현 완료
- 변경했습니다: 반환 타입을 추가했습니다

[DOCUMENT] design-spec.md

[USAGE] input:1500 cache_read:500 cache_write:200 output:800
[USAGE] input:1200 cache_read:800 cache_write:100 output:600
"""


@pytest.fixture
def minimal_session_log():
    """A minimal session log with only a header and one user message."""
    return f"""=== Claude Code Session Log ===
Session ID: {SESSION_ID}

[USER]
간단한 질문 하나 할게요
"""


@pytest.fixture
def session_log_with_compact():
    """A session log containing context-compression boundaries."""
    return f"""=== Claude Code Session Log ===
Session ID: {SESSION_ID}

[USER]
긴 작업을 시작합니다

[COMPACT]

[ASSISTANT]
계속 진행합니다

[COMPACT]
"""


@pytest.fixture
def session_id():
    """The canonical session UUID used across fixtures."""
    return SESSION_ID


@pytest.fixture
def write_log(tmp_path):
    """Factory that writes log content to a temp file and returns its Path."""
    def _write(content, filename=f"2026-05-27_143000_{SESSION_ID}.log"):
        path = tmp_path / filename
        path.write_text(content, encoding="utf-8")
        return path
    return _write


@pytest.fixture
def sample_task_markdown():
    """A task-*.md file as produced by MarkdownGenerator, for timeline parsing."""
    return """# Task Report

**초기 요청**: main.py 파일 수정 작업 진행

**수행 작업**:
- Read 사용
- Edit 2회 사용

**응답 1**:
코드를 분석하고 있습니다. 현재 구조를 파악합니다.

**응답 2**:
파일을 수정합니다. main.py를 변경했습니다.

**응답 3**:
완료되었습니다. 결과를 정리합니다.

### Token Usage

| Type | Tokens |
|------|--------|
| Input | 2,700 |
| Output | 1,400 |
| Cache Read | 1,300 |
| Cache Write | 300 |
| **Total** | **5,700** |

**API Requests**: 2

### Session Stats

| Metric | Count |
|--------|-------|
| User Messages | 1 |
| Assistant Responses | 3 |
| Tool Uses | 3 |
| Thinking Blocks | 1 |
"""
