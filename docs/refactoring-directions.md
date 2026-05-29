# Claude Log Organizer - 리팩토링 방향 문서

> 작성일: 2026-05-27
> 현재 버전: v1.4
> 총 코드량: ~8,100줄 (Python + Bash)

> **✅ 상태 (2026-05-29): 8개 방향 전부 구현 완료.** 동작 보존하에 구조만 개선했으며 매 단계 테스트로 검증(200+ 테스트). 구현 결과 요약은 `docs/existing-features.md` §10 참조. 아래 본문은 작성 당시의 계획 원문이며 기록용으로 보존한다.
>
> | 방향 | 상태 | 산출물 |
> |------|------|--------|
> | 1 God Module 분해 | ✅ | `interactive/`, `generators/timeline/` 패키지 |
> | 2 테스트 인프라 | ✅ | `tests/` 200+ 테스트, `pyproject.toml` |
> | 3 파서 통합 | ✅ | `parsers/extraction.py` |
> | 4 Hook Python화 | ✅ | `hook/` 패키지 (글로벌 훅은 bash 유지) |
> | 5 로깅 정비 | ✅ | `output.py` OutputWriter |
> | 6 시그널 외부화 | ✅ | `signals.yaml` + `signals.py` |
> | 7 파이프라인 | ✅ | `pipeline/` |
> | 8 CLI/UI 현대화 | ✅ | Typer + Rich |
>
> 계획과 다르게 구현된 부분: 방향 8의 inquirer는 Rich로 대체하지 않고 유지(화살표 키 선택 미지원), 표시만 Rich 업그레이드. 방향 4의 글로벌 Stop 훅은 bash 유지(다중 프로젝트 로그 수집).

---

## 목차

1. [현재 상태 진단](#1-현재-상태-진단)
2. [리팩토링 방향 총괄](#2-리팩토링-방향-총괄)
3. [방향 1: God Module 분해](#3-방향-1-god-module-분해)
4. [방향 2: 테스트 인프라 구축](#4-방향-2-테스트-인프라-구축)
5. [방향 3: 파서 공통 로직 통합](#5-방향-3-파서-공통-로직-통합)
6. [방향 4: Hook 스크립트 Python 전환](#6-방향-4-hook-스크립트-python-전환)
7. [방향 5: 로깅 체계 정비](#7-방향-5-로깅-체계-정비)
8. [방향 6: 시그널/패턴 외부화](#8-방향-6-시그널패턴-외부화)
9. [방향 7: 파이프라인 아키텍처 도입](#9-방향-7-파이프라인-아키텍처-도입)
10. [방향 8: CLI/UI 현대화](#10-방향-8-cliui-현대화)
11. [실행 로드맵](#11-실행-로드맵)

---

## 1. 현재 상태 진단

### 1.1 강점 (유지할 것)

| 영역 | 상태 | 근거 |
|------|------|------|
| 레이어 아키텍처 | 우수 | Hook → Parser → Model → Generator 단방향 의존 |
| 설정 시스템 | 우수 | YAML + dot notation + deep merge |
| 파서 팩토리 | 우수 | 확장 가능한 플러그인 구조 |
| 처리 상태 추적 | 우수 | SHA256 해시 기반 중복 방지 |
| 타입 힌트 | 우수 | 공개 API 95%+ 적용 |
| 디바운싱 | 우수 | 불완전 파일 처리 방지 |
| 의존성 주입 | 양호 | EventDispatcher, Generator 등 컴포넌트 주입 |

### 1.2 문제점 (개선 대상)

| 영역 | 심각도 | 상세 |
|------|--------|------|
| 테스트 부재 | 치명적 | 7,377줄 Python에 단위 테스트 0개 |
| God Module | 높음 | interactive.py(1,627줄), timeline_diagram.py(1,522줄) |
| 로깅 비일관 | 높음 | print() 127개소 vs logging 모듈 혼용 |
| 코드 중복 | 중간 | 파서 간 추출 로직, 파일 검색 로직 반복 |
| Bash Hook | 중간 | 211줄 Bash — 테스트/디버그/확장 어려움 |
| 하드코딩 패턴 | 중간 | 분석기 시그널 38개가 코드 내 고정 |
| 절차적 파이프라인 | 낮음 | 확장 시 기존 코드 수정 필요 |

### 1.3 모듈 크기 분포

```
interactive.py          ██████████████████████████████████ 1,627줄  ← 분해 필요
timeline_diagram.py     ██████████████████████████████     1,522줄  ← 분해 필요
task_success_analyzer.py ██████████                          482줄
session_parser.py       █████████                           422줄
generator.py (optimizer) ███████                             333줄
conversation_parser.py  ██████                              317줄
cli.py                  ██████                              315줄
models/task_data.py     █████                               270줄
event_dispatcher.py     █████                               262줄
context.py              ████                                225줄
save-conversation-log.sh ████                               211줄  ← Python 전환 대상
file_watcher.py         ████                                186줄
markdown_generator.py   ███                                 176줄
pattern_db.py           ███                                 172줄
main.py                 ███                                 171줄
timeline_parser.py      ███                                 184줄
config.py               ███                                 146줄
processed_tracker.py    ███                                 146줄
session_analyzer.py     ██                                  123줄
cli.py (optimizer)      ██                                  116줄
base_parser.py          █                                    59줄
parser_factory.py       █                                    55줄
```

---

## 2. 리팩토링 방향 총괄

### 우선순위 매트릭스

```
영향도 ↑
  │
  │  ★ 테스트 인프라       ★ God Module 분해
  │     (방향 2)              (방향 1)
  │
  │  ★ 파서 통합           ★ 로깅 정비
  │     (방향 3)              (방향 5)
  │
  │  ★ Hook Python화       ★ 패턴 외부화
  │     (방향 4)              (방향 6)
  │
  │  ★ CLI 현대화          ★ 파이프라인 아키텍처
  │     (방향 8)              (방향 7)
  │
  └──────────────────────────────── 난이도 →
       낮음                         높음
```

### 의존 관계

```
방향 1 (God Module 분해) ─┐
                          ├→ 방향 2 (테스트 인프라) ← 분해 후 테스트가 쉬워짐
방향 3 (파서 통합) ───────┘
                          
방향 5 (로깅 정비) ─→ 방향 8 (CLI 현대화)  ← 로깅 정리 후 UI 교체

방향 4 (Hook Python화) ─→ 방향 7 (파이프라인)  ← Hook이 Python이면 파이프라인 통합 가능

방향 6 (패턴 외부화) — 독립 실행 가능
```

---

## 3. 방향 1: God Module 분해

### 3.1 interactive.py 분해 (1,627줄 → 4개 모듈)

**문제**: UI 렌더링, 비즈니스 로직, 상태 관리, 파일 탐색이 단일 파일에 혼재

**목표 구조**:

```
claude_log_organizer/
  interactive/
    __init__.py            # InteractiveCLI 재수출
    cli.py                 # 메인 메뉴 루프 + 메뉴 정의 (~200줄)
    handlers.py            # 각 메뉴 액션 핸들러 (~400줄)
    analysis_workflow.py   # 분석 요청 워크플로우 (~400줄)
    display.py             # 출력 포맷팅 + 테이블 렌더링 (~300줄)
    file_discovery.py      # 태스크/로그 파일 탐색 (~200줄)
```

**분해 원칙**:
- `cli.py`: 메뉴 구조만 정의, 실제 로직은 handlers로 위임
- `handlers.py`: watch/analyze/export 등 각 메뉴 항목의 실행 로직
- `analysis_workflow.py`: 날짜 선택 → 세션 선택 → 분석 타입 → 실행 → 출력 흐름
- `display.py`: 테이블/차트/요약 포맷팅 유틸리티
- `file_discovery.py`: `_discover_project_task_files()`, 날짜 필터링 등 파일 탐색

**마이그레이션 전략**:
```
1단계: interactive/ 패키지 생성, __init__.py에서 기존 InteractiveCLI 임포트
2단계: display 유틸리티 추출 (가장 독립적)
3단계: file_discovery 추출
4단계: handlers 추출
5단계: analysis_workflow 추출
6단계: 원본 interactive.py 삭제, __init__.py에서 새 모듈 재수출
```

### 3.2 timeline_diagram.py 분해 (1,522줄 → 4개 모듈)

**문제**: XML 생성, 레이아웃 계산, 데이터 변환, AI 요약이 단일 클래스에 혼재

**목표 구조**:

```
claude_log_organizer/
  generators/
    timeline/
      __init__.py               # TimelineDiagramGenerator 재수출
      generator.py              # 메인 오케스트레이터 (~200줄)
      task_file_parser.py       # task-*.md → TimelineEntry 변환 (~250줄)
      drawio_builder.py         # draw.io XML 생성 엔진 (~400줄)
      gantt_page.py             # Gantt 차트 페이지 레이아웃 (~300줄)
      detail_page.py            # 세션 상세 페이지 레이아웃 (~250줄)
      phase_summarizer.py       # AI 페이즈 요약 + 캐시 (~200줄)
      token_analyzer.py         # 토큰 사용량 분석 (~150줄)
      styles.py                 # 색상, 크기, 레이아웃 상수 (~50줄)
```

**분해 원칙**:
- `generator.py`: 전체 흐름 오케스트레이션만
- `drawio_builder.py`: XML ElementTree 조작, 셀/커넥터 생성 유틸리티
- `gantt_page.py` / `detail_page.py`: 각각 하나의 페이지 유형만 담당
- `styles.py`: `TITLE_Y`, `ROW_HEIGHT`, `PX_PER_MINUTE`, 색상 맵 등 상수 집중

### 3.3 기대 효과

| 지표 | Before | After |
|------|--------|-------|
| 최대 모듈 크기 | 1,627줄 | ~400줄 |
| 단일 모듈 책임 수 | 4~5개 | 1개 |
| 테스트 가능성 | 낮음 (통합만 가능) | 높음 (단위 테스트 가능) |
| 코드 탐색 | 어려움 | 파일명으로 기능 식별 |

---

## 4. 방향 2: 테스트 인프라 구축

### 4.1 현재 상태

- 자동화된 Python 테스트: **0개**
- `test_hook_context.sh` (셸 스크립트): 유일한 테스트
- `requirements.txt`에 pytest 등 dev 의존성 주석 처리 상태

### 4.2 테스트 전략

**계층별 접근** — 투자 대비 효과가 큰 순서로:

```
                     ┌─────────────────┐
                     │  E2E Tests      │  ← 나중에 (비용 높음)
                     │  (JSONL → .md)  │
                     ├─────────────────┤
                     │  Integration    │  ← Phase 2
                     │  (Parser→Gen)   │
                     ├─────────────────┤
                     │  Unit Tests     │  ← Phase 1 (먼저)
                     │  (각 모듈)       │
                     └─────────────────┘
```

### 4.3 Phase 1: 핵심 단위 테스트 (~40개)

**우선 대상**: 파싱 로직 (버그 발생 시 모든 출력에 영향)

```
tests/
  __init__.py
  conftest.py                    # 공통 fixture (샘플 .log, config)
  fixtures/
    sample_session.log           # 정상 세션 로그
    sample_minimal.log           # 최소한의 태그만 있는 로그
    sample_malformed.log         # 비정상 형식
    sample_config.yaml           # 테스트용 설정
  
  test_models/
    test_task_data.py            # TaskData, TokenUsage 생성/직렬화
    test_token_usage.py          # TokenUsage.add(), to_dict()
  
  test_parsers/
    test_session_parser.py       # 태그 추출, work_summary, key_decisions
    test_conversation_parser.py  # 대화 형식 파싱
    test_timeline_parser.py      # 타임라인 형식 파싱
    test_parser_factory.py       # 올바른 파서 선택
  
  test_generators/
    test_markdown_generator.py   # 템플릿 렌더링, 커스텀 필터
  
  test_analyzers/
    test_success_analyzer.py     # 시그널 매칭, 점수 계산
  
  test_storage/
    test_processed_tracker.py    # 해시 계산, 중복 감지
  
  test_config.py                 # 설정 로드, deep merge, dot notation
```

**핵심 테스트 케이스 예시**:

```python
# test_parsers/test_session_parser.py

class TestSessionParser:
    """세션 파서 핵심 로직 테스트."""
    
    def test_extract_user_messages(self, sample_log):
        """[USER] 태그 정확히 추출."""
        
    def test_extract_tool_uses(self, sample_log):
        """[TOOL] 태그에서 도구명+액션 추출."""
        
    def test_extract_token_usage(self, sample_log_with_usage):
        """[USAGE] 태그에서 토큰 집계."""
        
    def test_generate_work_summary_truncation(self):
        """work_summary 500자 제한 적용."""
        
    def test_empty_log_returns_minimal_taskdata(self):
        """빈 로그 → 기본값 TaskData (에러 아님)."""
        
    def test_encoding_fallback(self, latin1_log):
        """UTF-8 실패 시 Latin-1 폴백."""
```

### 4.4 Phase 2: 통합 테스트 (~15개)

```python
# tests/test_integration/test_pipeline.py

class TestPipeline:
    """JSONL → .log → TaskData → .md 전체 흐름."""
    
    def test_session_log_to_markdown(self, tmp_path):
        """세션 로그 → 마크다운 생성 성공."""
        
    def test_event_dispatcher_debounce(self):
        """빠른 연속 이벤트 → 디바운싱 → 1회만 처리."""
        
    def test_processed_tracker_prevents_reprocessing(self):
        """동일 해시 파일 재처리 방지."""
        
    def test_modified_file_reprocessed(self):
        """내용 변경 시 재처리."""
```

### 4.5 테스트 설정

```toml
# pyproject.toml 추가
[tool.pytest.ini_options]
testpaths = ["tests"]
python_files = ["test_*.py"]
python_classes = ["Test*"]
python_functions = ["test_*"]
addopts = "-v --tb=short"

[tool.coverage.run]
source = ["claude_log_organizer"]
omit = ["*/tests/*", "*/interactive/*"]
```

### 4.6 기대 효과

| 지표 | Before | After (Phase 1) | After (Phase 2) |
|------|--------|-----------------|-----------------|
| 테스트 수 | 0 | ~40 | ~55 |
| 커버리지 | 0% | ~45% | ~65% |
| 파서 버그 감지 | 수동 확인 | 자동 | 자동 |
| 리팩토링 안전성 | 없음 | 부분적 | 충분 |

---

## 5. 방향 3: 파서 공통 로직 통합

### 5.1 현재 중복 현황

| 중복 로직 | 위치 | 예상 중복률 |
|-----------|------|-------------|
| 파일 변경 추출 (`_extract_files_modified/created`) | session_parser, conversation_parser | 90% |
| 타임스탬프 추출 | session_parser, conversation_parser | 70% |
| Task ID 추출 | event_dispatcher, conversation_parser, session_parser | 80% |
| 정규식 패턴 (태그 매칭) | 각 파서에 산재 | 60% |
| 날짜/시간 포맷팅 | markdown_generator, timeline_diagram, interactive | 50% |

### 5.2 해결 방안

**A. 공통 추출 유틸리티 (`parsers/extraction.py`)**:

```python
"""파서 간 공유되는 추출 로직."""

# 정규식 패턴 상수
TAG_PATTERNS = {
    "user": re.compile(r"\[USER\]\s*(.*?)(?=\[(?:USER|ASSISTANT|TOOL|THINKING|TOOL_RESULT|DOCUMENT|SNAPSHOT|COMPACT|USAGE)\]|\Z)", re.DOTALL),
    "assistant": re.compile(r"\[ASSISTANT\]\s*(.*?)(?=\[(?:USER|ASSISTANT|TOOL|...)\]|\Z)", re.DOTALL),
    # ... 나머지 태그
}

# 공통 추출 함수
def extract_by_tag(content: str, tag: str) -> List[str]: ...
def extract_files_modified(content: str) -> List[str]: ...
def extract_files_created(content: str) -> List[str]: ...
def extract_timestamp(content: str) -> Optional[datetime]: ...
def extract_task_id(file_path: str, content: str) -> str: ...
```

**B. BaseLogParser 강화**:

```python
class BaseLogParser(ABC):
    """기본 파서에 공통 추출 메서드 포함."""
    
    def _read_file(self, file_path): ...          # 기존
    def _extract_by_tag(self, content, tag): ...   # 신규: 태그 추출
    def _extract_files(self, content): ...         # 신규: 파일 변경 추출
    def _extract_timestamp(self, content): ...     # 신규: 타임스탬프 추출
    
    @abstractmethod
    def can_parse(self, file_path) -> bool: ...
    
    @abstractmethod
    def parse(self, file_path) -> TaskData: ...
```

### 5.3 기대 효과

| 지표 | Before | After |
|------|--------|-------|
| 중복 코드 | ~200줄 | ~50줄 (extraction.py) |
| 패턴 수정 시 변경점 | 3개 파서 각각 | extraction.py 1곳 |
| 새 파서 추가 작업량 | 높음 | 낮음 (공통 메서드 재사용) |

---

## 6. 방향 4: Hook 스크립트 Python 전환

### 6.1 현재 문제

`save-conversation-log.sh` (211줄 Bash):
- **테스트 불가**: 단위 테스트 작성 어려움
- **디버그 어려움**: `jq` 파이프라인 디버깅이 복잡
- **에러 처리 한계**: Bash의 에러 핸들링은 원시적
- **의존성**: `jq` 별도 설치 필요
- **확장 어려움**: 새 태그 타입 추가 시 Bash 파싱 로직 수정

### 6.2 전환 계획

```
.claude/hooks/
  save-conversation-log.sh  →  save_conversation_log.py (런처)
                                claude_log_organizer/
                                  hook/
                                    __init__.py
                                    conversation_extractor.py   # 핵심 추출 로직
                                    tag_formatter.py            # 태그 포맷팅
                                    state_manager.py            # .state 파일 관리
```

**핵심 전환 포인트**:

| Bash 로직 | Python 대체 |
|-----------|-------------|
| `jq` 파싱 | `json.loads()` |
| `tail -n +N` | `itertools.islice()` + 파일 오프셋 |
| `date +%Y-%m-%d` | `datetime.now().strftime()` |
| `.state/{id}.lines` 파일 | `StateManager` 클래스 |
| 환경변수 체크 | `argparse` 또는 stdin JSON 파싱 |

**Hook 진입점 (`save_conversation_log.py`)**:

```python
#!/usr/bin/env python3
"""Claude Code Stop 이벤트 훅 — JSONL → .log 변환."""

import sys
import json
from claude_log_organizer.hook import ConversationExtractor

def main():
    context = json.load(sys.stdin)
    extractor = ConversationExtractor(
        transcript_path=context["transcript_path"],
        session_id=context["session_id"],
        cwd=context.get("cwd", ""),
    )
    extractor.extract()

if __name__ == "__main__":
    main()
```

### 6.3 장점

| 항목 | Bash | Python |
|------|------|--------|
| 테스트 | 수동 | pytest로 자동화 |
| 에러 처리 | `set -e` + 조건문 | try-except + 로깅 |
| 의존성 | jq 필수 | 표준 라이브러리만 |
| 디버그 | echo 디버깅 | pdb, 로그 레벨 |
| 확장성 | 어려움 | 클래스 확장/상속 |
| 파서와 통합 | 분리 (별도 언어) | 공유 가능 (TAG_PATTERNS 등) |

### 6.4 호환성

- Hook 스크립트 경로는 `.claude/hooks/stop`에 등록되므로 Python 스크립트로 교체만 하면 됨
- `.state/` 파일 형식 유지 — 기존 상태와 호환
- 출력 `.log` 형식 완전 동일 — 하위 파서에 영향 없음

---

## 7. 방향 5: 로깅 체계 정비

### 7.1 현재 문제

```
print() 사용: 127개소 (interactive.py 대부분)
logging 사용: main.py, event_dispatcher.py, file_watcher.py 등
→ 동일 프로그램 내에서 두 가지 출력 방식 혼용
→ 로그 레벨 제어 불가 (print는 항상 출력)
→ 파일 로깅 시 print 출력 누락
```

### 7.2 해결 방안

**A. print → logging 전환 기준**:

| 현재 용도 | 전환 대상 | 로그 레벨 |
|-----------|-----------|-----------|
| 사용자 안내 메시지 | `logger.info()` 또는 별도 UI 레이어 | INFO |
| 에러 메시지 | `logger.error()` | ERROR |
| 디버그 정보 | `logger.debug()` | DEBUG |
| 진행 상태 표시 | 진행률 콜백 또는 `logger.info()` | INFO |
| 분석 결과 출력 | 별도 출력 함수 (stdout 전용) | — |

**B. 출력 레이어 분리**:

```python
# claude_log_organizer/output.py

class OutputWriter:
    """사용자 대면 출력 전담."""
    
    def __init__(self, file=sys.stdout):
        self.file = file
    
    def info(self, msg: str): ...
    def success(self, msg: str): ...
    def error(self, msg: str): ...
    def table(self, headers: List[str], rows: List[List[str]]): ...
    def section(self, title: str, content: str): ...
```

- `logging`: 시스템 로그 (파일, 디버그)
- `OutputWriter`: 사용자 대면 출력 (터미널)

### 7.3 마이그레이션 단계

```
1단계: OutputWriter 클래스 생성
2단계: interactive.py의 print() → OutputWriter 교체 (가장 많음)
3단계: cli.py의 print() → OutputWriter 교체
4단계: 나머지 모듈의 산발적 print() 정리
5단계: logging.basicConfig → 구조화된 로깅 설정
```

---

## 8. 방향 6: 시그널/패턴 외부화

### 8.1 현재 문제

`task_success_analyzer.py`에 38개 시그널 패턴이 Python 코드로 하드코딩:

```python
# 현재: 코드에 직접 정의
FAILURE_SIGNALS = [
    (re.compile(r"아니[요]?|아닌데|아니야"), "negation", 0.7),
    (re.compile(r"그게 아니라|그거 말고"), "correction", 0.8),
    # ... 13개 패턴
]
```

**문제점**:
- 패턴 추가/수정 시 코드 변경 필요
- 사용자가 자신만의 패턴을 추가할 수 없음
- 다국어 지원 시 코드 수정 범위가 넓음

### 8.2 해결 방안

**시그널 정의 파일 (`signals.yaml`)**:

```yaml
# config/signals.yaml
version: 1

failure_signals:
  - pattern: "아니[요]?|아닌데|아니야"
    category: negation
    weight: 0.7
    description: "부정 표현"
    
  - pattern: "그게 아니라|그거 말고"
    category: correction
    weight: 0.8
    description: "수정 요청"
    
  # ...

success_signals:
  - pattern: "좋아|좋네|잘 됐"
    category: confirmation
    weight: 0.8
    description: "긍정 확인"
    
  # ...

tool_error_signals:
  - pattern: "Error|Exception|Traceback"
    weight: 0.7
    dampening: 0.5
    description: "도구 실행 에러"

step_classification:
  analysis:
    keywords: ["분석", "파악", "조사", "읽", "탐색"]
    color: "#e1f5fe"
    icon: "🔍"
  decision:
    keywords: ["결정", "선택", "판단", "발견"]
    color: "#fff8e1"
    icon: "⚡"
  # ...
```

**로더 클래스**:

```python
class SignalRegistry:
    """외부 YAML에서 시그널 패턴 로드."""
    
    def __init__(self, config_path: str = "config/signals.yaml"):
        self._signals = self._load(config_path)
    
    @property
    def failure_signals(self) -> List[Signal]: ...
    
    @property
    def success_signals(self) -> List[Signal]: ...
    
    def add_custom_signal(self, signal: Signal): ...
```

### 8.3 기대 효과

- 패턴 추가 시 YAML만 편집 (코드 무수정)
- 사용자 커스텀 패턴 지원 (`~/.claude_log/signals.yaml` 오버라이드)
- 언어별 시그널 파일 분리 가능 (`signals_ko.yaml`, `signals_en.yaml`)
- timeline_diagram.py의 분류 키워드도 동일 파일로 통합 관리

---

## 9. 방향 7: 파이프라인 아키텍처 도입

### 9.1 현재 구조

```python
# 현재: 절차적 파이프라인 (main.py)
def process_file(self, file_path):
    parser = self.parser_factory.get_parser(file_path)
    task_data = parser.parse(file_path)
    self.generator.generate(task_data, output_path)
    self.tracker.mark_processed(file_path)
```

**제한**: 중간에 분석기 추가, 필터링, 변환 등을 끼워넣으려면 기존 코드 수정 필요

### 9.2 파이프라인 패턴

```python
class Pipeline:
    """확장 가능한 처리 파이프라인."""
    
    def __init__(self):
        self._steps: List[PipelineStep] = []
    
    def add_step(self, step: PipelineStep) -> "Pipeline":
        self._steps.append(step)
        return self
    
    def execute(self, context: PipelineContext) -> PipelineContext:
        for step in self._steps:
            if step.should_run(context):
                context = step.execute(context)
        return context

class PipelineStep(ABC):
    @abstractmethod
    def should_run(self, context: PipelineContext) -> bool: ...
    
    @abstractmethod
    def execute(self, context: PipelineContext) -> PipelineContext: ...
```

**기본 파이프라인 구성**:

```python
pipeline = Pipeline()
pipeline.add_step(FileValidationStep())      # 파일 유효성
pipeline.add_step(DeduplicationStep())        # 중복 검사
pipeline.add_step(ParsingStep())              # 파싱
pipeline.add_step(SuccessAnalysisStep())      # 성공/실패 분석 (선택적)
pipeline.add_step(MarkdownGenerationStep())   # 마크다운 생성
pipeline.add_step(TrackingStep())             # 처리 완료 마킹
```

**확장 예시**:
```python
# 사용자가 커스텀 분석 단계를 플러그인으로 추가
pipeline.add_step(CustomMetricsStep())
pipeline.add_step(SlackNotificationStep())
```

### 9.3 적용 범위

| 현재 모듈 | 파이프라인 단계로 전환 |
|-----------|----------------------|
| `_validate_file()` | `FileValidationStep` |
| `ProcessedTracker.is_processed()` | `DeduplicationStep` |
| `ParserFactory.get_parser() + parse()` | `ParsingStep` |
| `MarkdownGenerator.generate()` | `MarkdownGenerationStep` |
| `ProcessedTracker.mark_processed()` | `TrackingStep` |
| `TaskSuccessAnalyzer` | `SuccessAnalysisStep` (선택적) |
| 타임라인 생성 | `TimelineGenerationStep` (선택적) |

### 9.4 점진적 도입

이 리팩토링은 가장 큰 구조 변경이므로 점진적으로:

```
Phase A: PipelineContext, PipelineStep 인터페이스만 정의
Phase B: 기존 process_file()을 파이프라인으로 래핑 (동작 변경 없음)
Phase C: 각 단계를 독립 클래스로 추출
Phase D: 플러그인 등록 메커니즘 추가
```

---

## 10. 방향 8: CLI/UI 현대화

### 10.1 현재 한계

| 구성 요소 | 현재 | 한계 |
|-----------|------|------|
| CLI 파서 | `argparse` | 서브커맨드 많아질수록 코드 비대 |
| 대화형 UI | `inquirer` | 스타일링 제한, 프로젝트 유지보수 불안정 |
| 출력 포맷 | `print()` 직접 | 색상/테이블/진행률 표현 어려움 |

### 10.2 권장 스택

**Option A: Rich + Typer (권장)**

```python
# Typer: 타입 힌트 기반 CLI 자동 생성
import typer
from rich.console import Console
from rich.table import Table
from rich.progress import track

app = typer.Typer(help="Claude Log Organizer")
console = Console()

@app.command()
def watch(
    directory: str = typer.Argument(..., help="감시할 디렉토리"),
    pattern: str = typer.Option("*.log", help="파일 패턴"),
):
    """디렉토리 감시 모드 시작."""
    console.print(f"[bold green]감시 시작:[/] {directory}")
    ...

@app.command()
def analyze(
    date: str = typer.Argument("today", help="분석 대상 날짜"),
    type: str = typer.Option("summary", help="분석 타입"),
):
    """세션 분석 실행."""
    ...
```

**Rich 활용 예시**:

```python
# 분석 결과 테이블
table = Table(title="세션 분석 결과")
table.add_column("세션", style="cyan")
table.add_column("상태", justify="center")
table.add_column("토큰", justify="right", style="green")
table.add_row("abc123", "✅ 성공", "15,234")
console.print(table)

# 진행률 표시
for file in track(log_files, description="파싱 중..."):
    process(file)
```

### 10.3 마이그레이션 경로

```
1단계: rich 의존성 추가, OutputWriter를 Rich Console 기반으로 구현
2단계: cli.py의 argparse → typer 전환
3단계: interactive.py의 inquirer → rich.prompt + rich.panel 전환
4단계: 분석 결과 출력에 Rich 테이블/패널 적용
```

---

## 11. 실행 로드맵

### Phase 1: 기반 정비 (v1.5)

**목표**: 리팩토링의 안전망 확보 + 가장 급한 문제 해결

| 순서 | 작업 | 예상 공수 | 근거 |
|------|------|-----------|------|
| 1-1 | 테스트 인프라 + 핵심 단위 테스트 40개 | 2~3일 | 이후 모든 리팩토링의 안전망 |
| 1-2 | 로깅 체계 정비 (print → logging/OutputWriter) | 1~2일 | 즉시 효과, 독립 작업 |
| 1-3 | 파서 공통 로직 추출 (extraction.py) | 1일 | 테스트 작성 과정에서 자연스럽게 |

**결과물**: pytest 통과하는 테스트 스위트, 일관된 로깅

### Phase 2: 구조 개선 (v1.6)

**목표**: God Module 분해 + Hook 현대화

| 순서 | 작업 | 예상 공수 | 근거 |
|------|------|-----------|------|
| 2-1 | interactive.py → interactive/ 패키지 분해 | 2~3일 | 최대 모듈, 테스트로 검증 |
| 2-2 | timeline_diagram.py → timeline/ 패키지 분해 | 2일 | 두 번째 큰 모듈 |
| 2-3 | Hook 스크립트 Python 전환 | 1~2일 | 파서와 코드 공유 가능 |

**결과물**: 400줄 이하의 모듈들, Python Hook

### Phase 3: 아키텍처 고도화 (v2.0)

**목표**: 확장성 확보 + 사용자 경험 개선

| 순서 | 작업 | 예상 공수 | 근거 |
|------|------|-----------|------|
| 3-1 | 시그널/패턴 외부화 (signals.yaml) | 1~2일 | 독립 작업, 즉시 효과 |
| 3-2 | CLI/UI 현대화 (Rich + Typer) | 2~3일 | 방향 1 분해 후 적용이 쉬움 |
| 3-3 | 파이프라인 아키텍처 도입 | 3~4일 | 모든 분해/정리 완료 후 |

**결과물**: 플러그인 가능한 파이프라인, 현대적 CLI

### 전체 타임라인

```
v1.5 (Phase 1)          v1.6 (Phase 2)         v2.0 (Phase 3)
기반 정비                구조 개선               아키텍처 고도화
──────────────────── ──────────────────── ────────────────────
 테스트 인프라          interactive 분해       시그널 외부화
 로깅 정비              timeline 분해          CLI 현대화
 파서 통합              Hook Python화          파이프라인 도입
                                              
 ~4~6일                 ~5~7일                 ~6~9일
```

### 리스크 관리

| 리스크 | 대응 |
|--------|------|
| 리팩토링 중 기존 기능 깨짐 | Phase 1에서 테스트 먼저 → 안전망 확보 |
| Hook 전환 시 기존 .log 호환 | 출력 형식 동일하게 유지, 전환 후 diff 비교 |
| interactive 분해 시 import 경로 변경 | `__init__.py`에서 기존 경로 재수출 (deprecation 경고) |
| 파이프라인 도입이 과도한 추상화 | Phase A에서 인터페이스만 정의, 기존 코드 래핑으로 시작 |

---

## 부록: 의존성 업데이트 권장

| 현재 | 권장 추가 | 용도 |
|------|-----------|------|
| pyyaml | — | 유지 |
| watchdog | — | 유지 |
| jinja2 | — | 유지 |
| inquirer | → `rich` (대체) | UI/출력 |
| argparse (stdlib) | → `typer` (대체) | CLI |
| — | `pytest` + `pytest-cov` | 테스트 |
| — | `ruff` | 린팅 (black+flake8 대체) |

```toml
# pyproject.toml 권장 의존성
[project]
dependencies = [
    "pyyaml>=6.0",
    "watchdog>=3.0",
    "jinja2>=3.1",
    "python-dateutil>=2.8",
    "rich>=13.0",
    "typer>=0.9",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=5.0",
    "ruff>=0.4",
]
```
