# Repetitive Task Automator - 개발 분석 문서

> 작성일: 2026-03-18
> 상태: 미개발 (설계 단계)

---

## 1. 개요

### 목적
일일 작업 로그를 분석하여 **반복적으로 수행되는 패턴**을 감지하고, 이를 **쉘 스크립트** 또는 **CLAUDE.md 지시문**으로 자동화할 수 있도록 제안하는 시스템.

### 핵심 아이디어
```
여러 세션의 로그 축적
  → 반복 패턴 감지 (같은 명령어, 같은 파일 접근, 같은 유형의 요청)
  → 자동화 가능 여부 판단
  → 제안 생성:
    ├── Shell Script (.sh) — 반복 명령어 묶음
    ├── CLAUDE.md 지시문 — Claude가 자동으로 수행할 규칙
    └── Hook 확장 — save-conversation-log.sh에 추가할 추출 로직
```

### 실제 관측된 반복 예시 (현재 프로젝트 로그 기반)

| 반복 유형 | 실제 패턴 | 횟수 | 자동화 방식 |
|-----------|-----------|------|-------------|
| Bash 명령어 반복 | `python3 -m claude_log_organizer.cli timeline 2026-XX-XX` | 38~45회 | Shell alias/script |
| JSONL 파일 탐색 | `ls -tS *.jsonl \| head -1` | 54회 | Shell 함수 |
| 같은 파일 반복 읽기 | `Read → interactive.py` | 376회 | CLAUDE.md에 파일 구조 설명 추가 |
| 같은 파일 반복 편집 | `Edit → timeline_diagram.py` | 356회 | 모듈 분리 제안 |
| 테스트 패턴 | `python3 -c "..."` (인라인 테스트) | 290회 | 테스트 파일 자동 생성 |

---

## 2. 감지할 반복 패턴 유형

### 2.1 Bash 명령어 반복 (Command Repetition)

**감지 기준**: 동일 또는 유사한 Bash 명령어가 N일간 M회 이상 실행

**분석 대상**: `[TOOL] Bash → {command}` 태그

**유사도 판단**:
```python
# 날짜/ID 등 가변 부분을 플레이스홀더로 치환 후 비교
NORMALIZE_PATTERNS = [
    (r'\d{4}-\d{2}-\d{2}', '{DATE}'),           # 날짜
    (r'[a-f0-9-]{36}', '{UUID}'),                # UUID
    (r'[a-f0-9]{8}', '{SHORT_ID}'),              # 8자리 해시
    (r'/Users/\w+', '{HOME}'),                    # 홈 디렉토리
    (r'\d{6}', '{TIME}'),                         # HHMMSS
]

# 정규화 후 동일한 명령어 그룹화
"python3 -m claude_log_organizer.cli timeline 2026-02-13"
"python3 -m claude_log_organizer.cli timeline 2026-02-19"
"python3 -m claude_log_organizer.cli timeline 2026-02-20"
  → 정규화: "python3 -m claude_log_organizer.cli timeline {DATE}"
  → 3회 반복 감지
```

**자동화 제안**:
```bash
# 제안될 쉘 스크립트 예시
#!/bin/bash
# auto-generated: timeline 생성 (반복 감지됨 - 45회)
DATE=${1:-$(date '+%Y-%m-%d')}
python3 -m claude_log_organizer.cli timeline "$DATE"
```

### 2.2 파일 접근 패턴 (File Access Pattern)

**감지 기준**: 같은 파일이 세션마다 반복적으로 Read됨

**분석 대상**: `[TOOL] Read → {path}` 태그

**판단 로직**:
```
세션별 Read 파일 목록 추출
  → 파일별 접근 빈도 계산
  → 전체 세션의 70% 이상에서 접근되는 파일 = "핵심 참조 파일"
  → 해당 파일의 주요 구조/목적을 CLAUDE.md에 기술하면
     Claude가 매번 Read하지 않아도 됨
```

**자동화 제안**:
```markdown
# CLAUDE.md에 추가될 내용 제안 예시

## Key Files (자주 참조되는 파일)
- `interactive.py`: Interactive CLI 메인 진입점.
  메뉴 구조: show_main_menu → handle_watch_menu / handle_ai_request_menu
  분석 타입: summary, efficiency, timeline, token_analysis, task_success
- `timeline_diagram.py`: draw.io XML 생성기.
  핵심 메서드: generate(), parse_task_files(), _build_gantt_page()
```

### 2.3 사용자 요청 패턴 (Request Pattern)

**감지 기준**: 유사한 사용자 요청이 여러 세션에서 반복

**분석 대상**: `[USER]` 태그

**유사도 판단**:
```python
# 요청 의도 분류
REQUEST_INTENT_PATTERNS = [
    (r'(?:확인|체크|검증|테스트).*(?:해|해줘|해봐)', 'verify'),
    (r'(?:추가|만들|생성|구현).*(?:해|해줘)', 'create'),
    (r'(?:수정|변경|바꿔|고쳐)', 'modify'),
    (r'(?:삭제|제거|지워)', 'delete'),
    (r'(?:설명|알려|뭐야|어떻게)', 'explain'),
    (r'(?:정리|요약|분석)', 'analyze'),
]

# 동일 의도 + 유사 대상 = 반복 패턴
# "토큰 저장되고 있는지 확인해" + "USAGE 태그 확인해" → verify + token 관련
```

**자동화 제안**:
- 자주 확인하는 항목 → Hook에 자동 검증 로직 추가
- 자주 요청하는 분석 → Interactive CLI에 바로가기 추가
- 자주 하는 설정 변경 → config.yaml 기본값 조정 제안

### 2.4 도구 시퀀스 패턴 (Tool Sequence Pattern)

**감지 기준**: 같은 순서로 실행되는 도구 조합이 반복

**분석 대상**: `[TOOL]` 태그의 순서

**예시**:
```
반복 시퀀스 감지:
  Read → file_a.py
  Edit → file_a.py
  Bash → python3 -c "..."  (테스트)
  Read → file_a.py          (결과 확인)

→ 제안: "파일 수정 후 자동 테스트 실행" 스크립트
```

**로직**:
```python
# N-gram 기반 시퀀스 추출
def extract_tool_sequences(interactions, n=3):
    """연속 N개 도구 호출 패턴 추출."""
    tools = [t['tool'] for i in interactions for t in i.tools_used]
    ngrams = [tuple(tools[i:i+n]) for i in range(len(tools) - n + 1)]
    # Counter로 빈도 계산, 상위 패턴 반환
```

### 2.5 인라인 테스트 패턴 (Inline Test Detection)

**감지 기준**: `python3 -c "..."` 형태의 인라인 테스트 코드가 반복

**분석 대상**: `[TOOL] Bash → python3 -c "..."` 태그

**자동화 제안**:
```python
# 제안: tests/ 디렉토리에 테스트 파일 생성
# "python3 -c 'from X import Y; print(Y())'" 패턴이 290회 감지됨
#
# 제안되는 테스트 파일:
# tests/test_imports.py
# tests/test_integration.py
```

---

## 3. 아키텍처

### 3.1 모듈 구조

```
analyzers/
  └── repetitive_task_analyzer.py    # 핵심 분석 엔진

models/
  └── task_data.py                   # RepetitivePattern, AutomationSuggestion 추가
```

### 3.2 데이터 모델

```python
@dataclass
class RepetitivePattern:
    """감지된 반복 패턴."""
    pattern_type: str          # "command", "file_access", "request", "tool_sequence", "inline_test"
    normalized_pattern: str    # 정규화된 패턴 문자열
    occurrences: int           # 발생 횟수
    sessions: List[str]        # 발생한 세션 ID 목록
    raw_examples: List[str]    # 원본 예시 (최대 5개)
    first_seen: datetime       # 최초 발생 시점
    last_seen: datetime        # 최근 발생 시점
    span_days: int             # 발생 기간 (일)

@dataclass
class AutomationSuggestion:
    """자동화 제안."""
    suggestion_type: str       # "shell_script", "claude_md", "hook_extension", "config_change", "test_file"
    title: str                 # 제안 제목
    description: str           # 제안 설명
    content: str               # 생성할 파일/추가할 내용
    target_path: str           # 적용 대상 경로
    impact: str                # "high", "medium", "low"
    pattern: RepetitivePattern # 근거가 된 반복 패턴
```

### 3.3 분석 엔진

```python
class RepetitiveTaskAnalyzer:
    """반복 작업 감지 및 자동화 제안 생성."""

    # 감지 임계값
    MIN_OCCURRENCES = 5         # 최소 반복 횟수
    MIN_SESSIONS = 2            # 최소 세션 수 (다른 날에도 반복해야 의미 있음)
    SIMILARITY_THRESHOLD = 0.7  # 명령어 유사도 임계값

    def analyze_log_files(self, file_paths: List[Path]) -> List[RepetitivePattern]:
        """여러 로그 파일에서 반복 패턴 감지."""

    def _detect_command_patterns(self, interactions) -> List[RepetitivePattern]:
        """Bash 명령어 반복 감지."""

    def _detect_file_access_patterns(self, interactions) -> List[RepetitivePattern]:
        """파일 접근 반복 감지."""

    def _detect_request_patterns(self, interactions) -> List[RepetitivePattern]:
        """사용자 요청 반복 감지."""

    def _detect_tool_sequence_patterns(self, interactions) -> List[RepetitivePattern]:
        """도구 시퀀스 반복 감지."""

    def _detect_inline_test_patterns(self, interactions) -> List[RepetitivePattern]:
        """인라인 테스트 반복 감지."""

    def generate_suggestions(self, patterns: List[RepetitivePattern]) -> List[AutomationSuggestion]:
        """감지된 패턴에서 자동화 제안 생성."""

    def _suggest_shell_script(self, pattern: RepetitivePattern) -> Optional[AutomationSuggestion]:
        """반복 명령어 → 쉘 스크립트 제안."""

    def _suggest_claude_md(self, pattern: RepetitivePattern) -> Optional[AutomationSuggestion]:
        """반복 파일 접근 → CLAUDE.md 지시문 제안."""

    def _suggest_hook_extension(self, pattern: RepetitivePattern) -> Optional[AutomationSuggestion]:
        """반복 검증 → Hook 확장 제안."""

    def _suggest_test_file(self, pattern: RepetitivePattern) -> Optional[AutomationSuggestion]:
        """인라인 테스트 → 테스트 파일 제안."""
```

---

## 4. 제안 생성 로직 상세

### 4.1 Shell Script 제안

**입력**: 명령어 반복 패턴 (command type)

**로직**:
```
1. 정규화된 명령어에서 가변 부분 추출
2. 가변 부분 → 스크립트 인자 ($1, $2, ...)
3. 기본값 설정 (날짜 → today, 경로 → CWD)
4. 스크립트 생성:
   - shebang
   - 인자 설명 주석
   - 반복 근거 주석 (N회 감지, 기간)
   - 실행 로직
```

**출력 예시**:
```bash
#!/bin/bash
# [자동 제안] timeline 생성
# 근거: 45회 반복 감지 (2026-02-13 ~ 2026-03-17, 5개 세션)
# 사용법: ./scripts/gen-timeline.sh [DATE]

DATE=${1:-$(date '+%Y-%m-%d')}
python3 -m claude_log_organizer.cli timeline "$DATE" 2>&1
echo "✓ Timeline generated for $DATE"
```

### 4.2 CLAUDE.md 지시문 제안

**입력**: 파일 접근 반복 패턴 (file_access type)

**로직**:
```
1. 자주 접근되는 파일 목록 추출
2. 각 파일의 핵심 구조 요약 (첫 50줄 + class/function 시그니처)
3. CLAUDE.md에 추가할 섹션 생성:
   - 파일별 역할 한 줄 설명
   - 핵심 클래스/함수 목록
   - "이 파일은 매번 Read하지 않아도 됩니다" 안내
```

**판단 기준: CLAUDE.md vs Shell Script**:

| 패턴 | CLAUDE.md | Shell Script |
|------|-----------|-------------|
| 같은 파일을 매 세션 Read | O (구조 설명 추가) | X |
| 같은 Bash 명령어 반복 | X | O |
| "~~ 확인해" 류 반복 요청 | O (자동 확인 규칙 추가) | X |
| 파일 수정 후 테스트 패턴 | O (규칙) + Shell (스크립트) | O |

### 4.3 Hook 확장 제안

**입력**: 반복 검증 요청 패턴 (request type, verify 의도)

**로직**:
```
1. "확인해", "체크해" 요청에서 대상 추출
2. Hook에서 자동으로 검증 가능한 항목인지 판단:
   - 파일 존재 여부 → [[ -f path ]]
   - 태그 포함 여부 → grep pattern
   - 프로세스 상태 → pgrep / lsof
3. save-conversation-log.sh에 추가할 검증 블록 제안
```

### 4.4 AI 보강 제안 (선택적)

**입력**: 감지된 모든 패턴 + 현재 CLAUDE.md 내용

**로직**:
```
Claude CLI에 프롬프트:
  "다음은 반복 감지된 패턴입니다. 현재 CLAUDE.md를 고려하여,
   가장 효과적인 자동화 제안 3개를 구체적으로 작성해주세요.
   각 제안에는 실제 적용 가능한 코드/설정을 포함하세요."
```

---

## 5. 리포트 형식

```markdown
# Repetitive Task Analysis Report

## Summary
- 분석 기간: 2026-02-13 ~ 2026-03-17
- 분석 로그: 25개 파일, 12개 세션
- 감지된 반복 패턴: 8개
- 자동화 제안: 5개

## Detected Patterns

### 1. 🔄 Command: `python3 -m ... timeline {DATE}` (45회)
- 기간: 2026-02-13 ~ 2026-03-12 (5개 세션)
- 예시:
  - `python3 -m claude_log_organizer.cli timeline 2026-02-13`
  - `python3 -m claude_log_organizer.cli timeline 2026-02-19`
- **제안**: Shell Script → `scripts/gen-timeline.sh`

### 2. 📖 File Access: `interactive.py` (376회, 전체 세션의 90%)
- **제안**: CLAUDE.md에 파일 구조 설명 추가

### 3. 🧪 Inline Test: `python3 -c "..."` (290회)
- 자주 테스트하는 모듈: interactive, timeline_diagram, session_parser
- **제안**: `tests/test_smoke.py` 자동 생성

## Automation Suggestions

### Suggestion 1: `scripts/gen-timeline.sh` [HIGH impact]
> 근거: timeline 명령어 45회 반복

```bash
#!/bin/bash
DATE=${1:-$(date '+%Y-%m-%d')}
python3 -m claude_log_organizer.cli timeline "$DATE"
```

적용 방법: `chmod +x scripts/gen-timeline.sh`

### Suggestion 2: CLAUDE.md 업데이트 [HIGH impact]
> 근거: interactive.py 376회, timeline_diagram.py 331회 Read

추가할 내용:
```markdown
## Key Files
- interactive.py: CLI 메뉴 시스템 (1200줄). 핵심: _select_analysis_type(), handle_ai_request_menu()
- timeline_diagram.py: draw.io 생성기 (1300줄). 핵심: generate(), parse_task_files()
```

### Suggestion 3: `tests/test_smoke.py` [MEDIUM impact]
> 근거: python3 -c 인라인 테스트 290회
```

---

## 6. Interactive CLI 통합

### 메뉴 위치
```
분석 타입 선택
├── 일반 요약
├── 효율성 분석
├── 타임라인 다이어그램
├── 토큰 사용량 분석
├── 작업 성공/실패 분석
└── 반복 작업 자동화 제안 ← 신규
```

### 처리 흐름
```python
# interactive.py에 추가
if analysis_type == "repetitive_automation":
    self._generate_repetitive_analysis(selected_files, range_label)
    return

def _generate_repetitive_analysis(self, files, range_label):
    analyzer = RepetitiveTaskAnalyzer()
    patterns = analyzer.analyze_log_files(files)
    suggestions = analyzer.generate_suggestions(patterns)
    report = analyzer.generate_report(patterns, suggestions)
    # 파일 저장 + 콘솔 출력
```

### 제안 적용 프롬프트
```
제안이 생성된 후, 사용자에게 적용 여부를 물음:

  발견된 자동화 제안 3개:
  [1] scripts/gen-timeline.sh 생성 (HIGH)
  [2] CLAUDE.md 업데이트 (HIGH)
  [3] tests/test_smoke.py 생성 (MEDIUM)

  적용할 제안을 선택하세요 (복수 선택 가능):
  > [1, 2] 선택 시 → 파일 자동 생성/수정
```

---

## 7. 개발 계획

### Phase 1: 명령어 + 파일 접근 패턴 감지 + 리포트
- `RepetitiveTaskAnalyzer` 기본 구조
- `_detect_command_patterns()` — 정규화 + 빈도 계산
- `_detect_file_access_patterns()` — 세션별 파일 접근 빈도
- `generate_report()` — 마크다운 리포트 생성
- **수정 파일**: `task_data.py` (모델 추가), `analyzers/repetitive_task_analyzer.py` (신규)
- **예상 작업량**: ~200줄

### Phase 2: 제안 생성 + Interactive 통합
- `generate_suggestions()` — 패턴 → 제안 변환
- `_suggest_shell_script()`, `_suggest_claude_md()`
- Interactive CLI 메뉴 추가 + 제안 적용 프롬프트
- **수정 파일**: `repetitive_task_analyzer.py` (확장), `interactive.py` (메뉴 추가)
- **예상 작업량**: ~150줄

### Phase 3: 요청 패턴 + 도구 시퀀스 + 인라인 테스트 감지
- `_detect_request_patterns()` — 의도 분류 + 유사도
- `_detect_tool_sequence_patterns()` — N-gram 분석
- `_detect_inline_test_patterns()` — 테스트 코드 추출
- `_suggest_hook_extension()`, `_suggest_test_file()`
- **수정 파일**: `repetitive_task_analyzer.py` (확장)
- **예상 작업량**: ~180줄

### Phase 4: AI 보강 제안
- Claude CLI로 패턴 + CLAUDE.md 분석 → 맞춤 제안
- 제안의 자동 적용 (파일 생성/수정)
- **예상 작업량**: ~100줄

```
Phase 1            Phase 2            Phase 3            Phase 4
──────────────────┬──────────────────┬──────────────────┬──────────────────
명령어/파일 감지   │ 제안 생성 +       │ 요청/시퀀스/      │ AI 보강 제안
+ 리포트           │ Interactive 통합   │ 인라인 테스트     │ + 자동 적용
                   │                   │                   │
~200줄             │ ~150줄            │ ~180줄            │ ~100줄
```

---

## 8. 기존 모듈과의 관계

```
repetitive_task_analyzer.py
  ├── 입력: .log 파일 (TaskSuccessAnalyzer와 동일 소스)
  │   └── extract_interactions() 재사용 또는 독립 파싱
  ├── 패턴 감지: 자체 로직 (정규화, N-gram, 의도 분류)
  ├── 제안 생성: 자체 로직 + AI (선택적)
  └── 출력:
      ├── generate_report() → markdown (timeline_diagram.py와 동일 패턴)
      ├── Shell Script → scripts/ 디렉토리
      ├── CLAUDE.md 수정안
      └── Hook 확장안
```

### TaskSuccessAnalyzer와의 차이

| 항목 | TaskSuccessAnalyzer | RepetitiveTaskAnalyzer |
|------|--------------------|-----------------------|
| 분석 단위 | 단일 상호작용 (요청-응답 쌍) | 여러 세션에 걸친 패턴 |
| 시간 범위 | 세션 내 | 세션 간 (일/주 단위) |
| 출력 | 성공/실패 판정 | 자동화 제안 (실행 가능한 코드) |
| AI 역할 | 판정 (success/failure) | 제안 보강 (더 나은 자동화 방법) |
