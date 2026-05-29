# Claude Log Organizer - Project Guide

## Project Overview
Claude Code 세션의 JSONL 트랜스크립트를 자동으로 수집, 파싱, 분석하여 구조화된 마크다운 문서와 시각화 다이어그램을 생성하는 시스템.

## Architecture
```
JSONL Transcript → Hook (bash 또는 Python) → .log files
                                                  ↓
                              Watcher → EventDispatcher → Pipeline
                                                  ↓
   Pipeline 단계: validate → dedup → task-id → parse → output-path → generate → track
                                                  ↓
                              SessionParser → TaskData → MarkdownGenerator → task-*.md
                                                  ↓
                              TimelineDiagramGenerator → .drawio (timeline + detail pages)
                                                  ↓
                              TaskSuccessAnalyzer → success/failure report
```
> 모든 사용자 대면 출력은 `OutputWriter`(output.py)를 통해 흐르고, 시스템 로그는 `logging`을 사용한다.
> 시그널/분류 패턴은 `signals.yaml`로 외부화되어 `SignalRegistry`가 로드한다.

## Key Directories
- `claude_log_organizer/` — 메인 패키지
  - `parsers/` — 로그 파일 파서 (session_parser.py가 핵심) + `extraction.py` (공유 태그/추출 유틸)
  - `models/` — 데이터 모델 (TaskData, TimelineEntry, TaskInteraction 등)
  - `generators/` — 출력 생성: markdown_generator.py + `timeline/` 패키지(8 모듈: generator·data_extraction·entry_processing·phase_summarizer·drawio_builder·token_analyzer·markdown_builder·styles)
  - `analyzers/` — 분석 모듈 (task_success_analyzer, SignalRegistry 사용)
  - `interactive/` — Interactive CLI 패키지 (cli·handlers·analysis·file_discovery)
  - `pipeline/` — 처리 파이프라인 (base: Pipeline/PipelineStep/PipelineContext, steps: 7단계)
  - `hook/` — Stop 이벤트 훅 로직 (extractor·tag_formatter·state_manager, stdlib 전용·테스트 가능)
  - `watcher/` — 파일 감시 + 이벤트 디스패처(파이프라인 실행)
  - `storage/` — 처리 상태 추적
  - `output.py` — 사용자 대면 출력 단일 제어점 (OutputWriter, Rich 테이블/패널/마크다운)
  - `signals.py` / `signals.yaml` — 시그널/분류 패턴 레지스트리 + 외부 정의
  - `cli.py` — Typer 기반 CLI 엔트리포인트
- `prompt_optimizer/` — 프롬프트 최적화 도구 (별도 패키지)
- `tests/` — pytest 테스트 스위트 (200+ 테스트)
- `templates/` — Jinja2 마크다운 템플릿
- `.claude/hooks/` — Claude Code Stop event hook 스크립트 (bash + Python 버전)
- `.claude/logs/` — 생성된 .log 파일 및 .state/ (증분 처리 상태)
- `tasks/` — 생성된 task 마크다운 파일
- `summaries/` — 분석 결과 출력
- **`docs/` — 프로젝트 문서화 (기능 정리, 개발 분석, 아키텍처 설명)**

## docs/ Directory
프로젝트 구조 설명, 기존 기능 정리, 신규 개발 분석 문서를 관리하는 공간.
- `docs/existing-features.md` — 기존 구현 기능 정리 (버전별 개발 이력 포함)
- `docs/refactoring-directions.md` — 리팩토링 방향 문서 (8개 방향, 전부 완료)
- `docs/task-success-analyzer.md` — Task 성공/실패 분석기 개발 분석 문서
- `docs/repetitive-task-automator.md` — 반복 작업 자동화 제안 기능 개발 분석 문서

## Conventions
- 한국어 UI/문서, 영문 코드/변수명
- 분석 결과는 `summaries/` 디렉토리에 마크다운으로 출력
- **사용자 대면 출력은 `OutputWriter`(output.py)를 통해서만** — 직접 `print()` 금지. 시스템 로그는 `logging` 사용
- **새 시그널/분류 패턴은 코드가 아닌 `signals.yaml`에 추가** (사용자는 `~/.claude_log/signals.yaml`로 오버라이드 가능)
- 파서 태그 추출 로직은 `parsers/extraction.py`의 공유 유틸 재사용
- 처리 파이프라인에 단계를 추가하려면 `PipelineStep` 구현 후 `pipeline.add_step()`
- Hook 스크립트: 프로젝트 로컬(.claude/hooks/)과 글로벌(~/.claude/hooks/) 양쪽 동기화 필요. **글로벌 Stop 훅은 bash 버전 유지** (여러 프로젝트에서 로그 수집, jq만 의존). Python 버전(`save_conversation_log.py`)은 프로젝트 로컬 테스트 자산이며 출력은 bash와 byte-identical
- 로그 태그: [USER], [ASSISTANT], [TOOL], [THINKING], [TOOL_RESULT], [DOCUMENT], [SNAPSHOT], [COMPACT], [USAGE]

## Running
```bash
# Interactive CLI (무인자 실행 시 자동 진입)
python -m claude_log_organizer.cli

# Watch mode (파일 감시)
python -m claude_log_organizer.cli watch

# 단일/디렉토리 처리, 타임라인
python -m claude_log_organizer.cli process <file.log>
python -m claude_log_organizer.cli batch <dir> --force
python -m claude_log_organizer.cli timeline 2026-05-29

# 테스트
pytest                  # 200+ 테스트
pytest --cov            # 커버리지

# Prompt optimizer
python -m prompt_optimizer.cli optimize "입력"
```
