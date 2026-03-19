# Claude Log Organizer - Project Guide

## Project Overview
Claude Code 세션의 JSONL 트랜스크립트를 자동으로 수집, 파싱, 분석하여 구조화된 마크다운 문서와 시각화 다이어그램을 생성하는 시스템.

## Architecture
```
JSONL Transcript → Hook (save-conversation-log.sh) → .log files
                                                        ↓
                                    SessionParser → TaskData → MarkdownGenerator → task-*.md
                                                        ↓
                                    TimelineDiagramGenerator → .drawio (timeline + detail pages)
                                                        ↓
                                    TaskSuccessAnalyzer → success/failure report
                                                        ↓
                                    RepetitiveTaskAnalyzer → automation suggestions
```

## Key Directories
- `claude_log_organizer/` — 메인 패키지
  - `parsers/` — 로그 파일 파서 (session_parser.py가 핵심)
  - `models/` — 데이터 모델 (TaskData, TimelineEntry, TaskInteraction 등)
  - `generators/` — 출력 생성 (markdown, timeline_diagram)
  - `analyzers/` — 분석 모듈 (task_success_analyzer)
  - `watcher/` — 파일 감시 + 이벤트 디스패처
  - `storage/` — 처리 상태 추적
- `prompt_optimizer/` — 프롬프트 최적화 도구 (별도 패키지)
- `templates/` — Jinja2 마크다운 템플릿
- `.claude/hooks/` — Claude Code Stop event hook 스크립트
- `.claude/logs/` — 생성된 .log 파일 및 .state/ (증분 처리 상태)
- `tasks/` — 생성된 task 마크다운 파일
- `summaries/` — 분석 결과 출력
- **`docs/` — 프로젝트 문서화 (기능 정리, 개발 분석, 아키텍처 설명)**

## docs/ Directory
프로젝트 구조 설명, 기존 기능 정리, 신규 개발 분석 문서를 관리하는 공간.
- `docs/existing-features.md` — 기존 구현 기능 정리 (버전별 개발 이력 포함)
- `docs/task-success-analyzer.md` — Task 성공/실패 분석기 개발 분석 문서
- `docs/repetitive-task-automator.md` — 반복 작업 자동화 제안 기능 개발 분석 문서

## Conventions
- 한국어 UI/문서, 영문 코드/변수명
- 분석 결과는 `summaries/` 디렉토리에 마크다운으로 출력
- Hook 스크립트: 프로젝트 로컬(.claude/hooks/)과 글로벌(~/.claude/hooks/) 양쪽 동기화 필요
- 로그 태그: [USER], [ASSISTANT], [TOOL], [THINKING], [TOOL_RESULT], [DOCUMENT], [SNAPSHOT], [COMPACT], [USAGE]

## Running
```bash
# Interactive CLI
python -m claude_log_organizer.interactive

# Watch mode (파일 감시)
python -m claude_log_organizer.cli watch

# Prompt optimizer
python -m prompt_optimizer.cli optimize "입력"
```
