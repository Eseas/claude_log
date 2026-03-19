# 기존 기능 정리

> 최종 업데이트: 2026-03-17

---

## 버전 이력

| 버전 | 날짜 | 핵심 변경 |
|------|------|-----------|
| v0.0 | 2026-02-26 | 초기 프로젝트 구조, 기본 파서/생성기/감시자 |
| v0.1 | 2026-02-26 | 설정 시스템, 파서 팩토리, 이벤트 디스패처 |
| v0.2 | 2026-02-26 | 디바운싱, 처리 상태 추적, 템플릿 시스템 |
| v1.0 | 2026-02-26 | Interactive CLI, 세션 기반 분석, AI 요약 |
| v1.1 | 2026-02-27 | 타임라인 다이어그램(.drawio), 프로세스 단계 분류, AI 페이즈 요약 |
| v1.2 | 2026-03-12 | 토큰 사용량 추적/분석, Interactive 메뉴 확장, 작업 성공/실패 분석기 |

---

## 1. 데이터 수집 파이프라인

### 1.1 Hook 스크립트 (`save-conversation-log.sh`)

**개발 시기**: v0.0 ~ v1.2 (지속적 확장)

**역할**: Claude Code Stop 이벤트 시 JSONL 트랜스크립트에서 구조화된 .log 파일 생성

**로직**:
```
1. stdin에서 JSON 컨텍스트 수신 (transcript_path, session_id, cwd)
2. .state/{session_id}.lines에서 이전 처리 위치 확인
3. tail -n +N으로 새 라인만 추출
4. 각 JSONL 라인을 jq로 파싱:
   - type=user → [USER], [DOCUMENT], [TOOL_RESULT] 태그 추출
   - type=assistant → [THINKING], [ASSISTANT], [TOOL], [USAGE] 태그 추출
   - type=file-history-snapshot → [SNAPSHOT] 태그
   - type=system (subtype=compact_boundary) → [COMPACT] 태그
5. {DATE}_{SESSION_ID}.log 파일에 기록
6. .state 파일 업데이트
```

**핵심 설계 결정**:
- 증분 처리: `.lines` 상태 파일로 매번 전체 JSONL을 재처리하지 않음
- 매 Stop 이벤트마다 새 .log 파일 생성 (하나의 세션이 여러 .log를 가질 수 있음)
- TOOL_RESULT는 300자 제한으로 잘라서 저장

### 1.2 추출 태그 체계

| 태그 | 소스 | 설명 |
|------|------|------|
| `[USER]` | user.message.content[text] | 사용자 메시지 |
| `[ASSISTANT]` | assistant.message.content[text] | 어시스턴트 응답 |
| `[TOOL]` | assistant.message.content[tool_use] | 도구 호출 (이름 + 액션) |
| `[THINKING]` | assistant.message.content[thinking] | 사고 과정 |
| `[TOOL_RESULT]` | user.message.content[tool_result] | 도구 실행 결과 (300자) |
| `[DOCUMENT]` | user.message.content[document] | 첨부 문서 제목 |
| `[SNAPSHOT]` | file-history-snapshot | 추적 파일 수 |
| `[COMPACT]` | system.compact_boundary | 컨텍스트 압축 경계 |
| `[USAGE]` | assistant.message.usage | 토큰 사용량 (v1.2) |

---

## 2. 파싱 시스템

### 2.1 SessionParser (`parsers/session_parser.py`)

**개발 시기**: v0.0 (기본) → v1.1 (thinking/tool_result/document/compact 확장) → v1.2 (token_usage 추가)

**역할**: .log 파일을 파싱하여 TaskData 객체 생성

**추출 항목**:
- 헤더: session_id, project_path, timestamp
- 대화: user_messages, assistant_responses, tool_uses
- 메타: thinking_blocks, tool_results, documents, compact_count, token_usage
- 파생: work_summary (초기 요청 + 도구 요약 + 응답 내용), key_decisions

**로직 흐름**:
```
.log content
  → regex 기반 태그별 추출
  → _generate_work_summary() — 초기 요청 + 도구 카운트 + 응답 미리보기
  → _extract_key_points() — 불릿포인트 + 한국어 작업 패턴 추출
  → TaskData 객체 반환
```

### 2.2 파서 팩토리 (`parsers/parser_factory.py`)

**개발 시기**: v0.1

**역할**: 파일 형식에 따라 적절한 파서 자동 선택
- `ClaudeSessionLogParser` — 세션 로그 (주 파서)
- `ConversationParser` — 대화 형식
- `TimelineParser` — 타임라인 형식

---

## 3. 데이터 모델 (`models/task_data.py`)

**개발 시기**: v0.0 (기본) → v1.1 (TimelineEntry, ProcessPhase) → v1.2 (TokenUsage, TaskInteraction)

### 핵심 모델

| 모델 | 용도 | 주요 필드 |
|------|------|-----------|
| `TaskData` | 파싱된 태스크 전체 정보 | task_id, work_summary, status, files_modified, key_decisions, token_usage, metadata |
| `TokenUsage` | 토큰 사용량 통계 | input_tokens, output_tokens, cache_read/write_tokens, request_count, total_tokens (자동 계산) |
| `TimelineEntry` | 타임라인 항목 | session_id, start/end_time, label, process_steps/phases, token_usage, user_message_count 등 |
| `ProcessPhase` | 작업 페이즈 그룹 | phase_name, primary_type, step_count, summary, key_details |
| `TaskInteraction` | 사용자-어시스턴트 상호작용 쌍 | request, assistant_work, tools_used, tool_results, feedback, heuristic/ai_result |
| `CodeSnippet` | 코드 조각 | language, code, description |

---

## 4. 출력 생성

### 4.1 Markdown Generator (`generators/markdown_generator.py`)

**개발 시기**: v0.0 (기본) → v1.1 (토큰 사용량 섹션 추가)

**역할**: TaskData → Jinja2 템플릿 → task-*.md 파일

**로직**: `templates/default.md.jinja2` 기반 렌더링, Config에서 템플릿 경로/이름 설정

### 4.2 Timeline Diagram Generator (`generators/timeline_diagram.py`)

**개발 시기**: v1.1 (핵심) → v1.2 (토큰 분석 추가)

**역할**: task-*.md 파일들 → draw.io XML (.drawio) 다이어그램

**핵심 로직**:

#### A. 타임라인 생성
```
1. parse_task_files() — task markdown → TimelineEntry 리스트
2. _infer_end_times() — 세션 간 간격으로 종료 시간 추정
3. _merge_entries() — 같은 라벨의 연속 항목 병합
4. _build_gantt_page() — 가로 Gantt 차트 XML 생성
5. _build_entry_detail_page() — 세션별 세로 플로우 다이어그램
```

#### B. 프로세스 단계 분류 (`_classify_step`)
Assistant 응답을 5가지 유형으로 자동 분류:

| 유형 | 키워드 | 시각 |
|------|--------|------|
| analysis | 분석, 파악, 조사, 읽, 탐색 | 🔍 파란색 |
| decision | 결정, 선택, 판단, 발견, 이슈 | ⚡ 노란색 |
| implementation | 수정, 변경, 추가, 생성, 삭제 | 🔧 초록색 |
| verification | 확인, 검증, 테스트, 빌드 | ✅ 보라색 |
| summary | 완료, 정리, 요약, 결과 | 📋 갈색 |

#### C. 페이즈 요약 (3단계 파이프라인)
```
Stage 1: _group_consecutive_steps() — 같은 타입 연속 단계 그룹화
Stage 2: _ai_summarize_phases() — Claude CLI로 의미 단위 그룹화 (캐시: .phase_cache.json)
Stage 3: _condense_phases() — AI 불가 시 균등 분할 폴백
```

#### D. 토큰 사용량 분석 (`_analyze_token_usage`)
```
1. token_usage가 있는 항목 필터링
2. 평균 × 1.5 = 고사용 기준 계산
3. _identify_factors() — 원인 식별 (compact, 도구 과다, thinking 과다 등)
4. 캐시 효율, 출력 비율 계산
5. _suggest_strategies() — 감량 전략 6가지 패턴
```

---

## 5. 파일 감시 시스템

### 5.1 FileWatcher (`watcher/file_watcher.py`)

**개발 시기**: v0.0 (기본) → v0.2 (다중 디렉토리)

**역할**: watchdog 기반 디렉토리 감시, 파일 생성/수정 이벤트 감지

### 5.2 EventDispatcher (`watcher/event_dispatcher.py`)

**개발 시기**: v0.1 (기본) → v0.2 (디바운싱 추가)

**역할**: 파일 이벤트 → 파싱 → 마크다운 생성 파이프라인 오케스트레이션

**로직**:
```
1. dispatch_file_event() — 이벤트 수신
2. _process_with_debounce() — N초 대기 후 파일 안정화 확인
3. _validate_file() — 크기/형식 검증
4. _process_new_file() — 파서 선택 → 파싱 → 마크다운 생성 → 처리 완료 마킹
```

---

## 6. Interactive CLI (`interactive.py`)

**개발 시기**: v1.0 (기본) → v1.2 (토큰 분석, 작업 성공/실패 분석 메뉴 추가)

**메뉴 구조**:
```
메인 메뉴
├── 1. Watch - 디렉토리 감시 모드
│   ├── Config 기반 (config.yaml 디렉토리)
│   └── 수동 입력
├── 2. Request AI - 분석 요청
│   ├── 세션 기반 선택
│   │   ├── 세션 목록 표시 (ID + 날짜 + 파일 수)
│   │   └── 분석 타입 선택
│   └── 날짜 기반 선택
│       ├── 날짜 범위 선택 (today/yesterday/week/custom)
│       └── 분석 타입 선택
└── 3. Exit
```

**분석 타입**:
| 타입 | 키 | AI 필요 | 설명 |
|------|-----|---------|------|
| 일반 요약 | `summary` | O | 세션 작업 내용 요약 |
| 효율성 분석 | `efficiency` | O | 프롬프트 효율성 + 개선 제안 |
| 타임라인 다이어그램 | `timeline` | X (페이즈 요약 시 선택적) | .drawio 시각화 |
| 토큰 사용량 분석 | `token_analysis` | X | 고사용 세션 식별 + 감량 전략 |
| 작업 성공/실패 분석 | `task_success` | O (선택적) | 시그널 + AI 판정 |

---

## 7. Prompt Optimizer (`prompt_optimizer/`)

**개발 시기**: v1.0

**역할**: 사용자 입력을 분석하여 더 효과적인 프롬프트로 보강

**구성**:
- `analyzers/session_analyzer.py` — 세션 컨텍스트 분석
- `patterns/pattern_db.py` — 프롬프트 패턴 데이터베이스
- `generator.py` — 보강 프롬프트 생성
- `context.py` — 프로젝트 컨텍스트 수집
- `cli.py` — CLI 인터페이스

---

## 8. 설정 시스템 (`config.py`)

**개발 시기**: v0.1

**구조**: YAML 기반, dot notation 접근 (`config.get("watch.directories")`)

**주요 설정 항목**:
```yaml
watch:
  directories: []           # 감시 디렉토리 목록
  patterns: ["*.log"]       # 파일 패턴
  poll_interval: 1.0        # 감시 주기 (초)
  debounce_delay: 3.0       # 디바운스 대기 (초)
output:
  directory: "./tasks"      # 출력 디렉토리
  summaries_directory: "./summaries"  # 분석 결과
templates:
  directory: "./templates"
  default_template: "default.md.jinja2"
```

---

## 9. 모듈 의존 관계

```
interactive.py
  ├── main.py (LogOrganizerApp)
  │   ├── config.py (Config)
  │   ├── parsers/parser_factory.py → session_parser.py
  │   ├── generators/markdown_generator.py
  │   ├── watcher/file_watcher.py
  │   ├── watcher/event_dispatcher.py
  │   └── storage/processed_tracker.py
  ├── generators/timeline_diagram.py
  │   └── models/task_data.py (TimelineEntry, ProcessPhase, TokenUsage)
  └── analyzers/task_success_analyzer.py
      └── models/task_data.py (TaskInteraction)
```
