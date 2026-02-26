# Claude Log Organizer 사용 가이드

## 목차

- [설치](#설치)
- [실행](#실행)
- [Interactive 모드](#interactive-모드)
- [CLI 명령어](#cli-명령어)
- [Hook 설정](#hook-설정)
- [설정 파일](#설정-파일-configyaml)
- [출력물](#출력물)
- [문제 해결](#문제-해결)

---

## 설치

```bash
cd claude_log
pip install -e .
```

의존성 패키지:
- `pyyaml>=6.0`
- `watchdog>=3.0.0`
- `jinja2>=3.1.0`
- `python-dateutil>=2.8.0`
- `inquirer>=3.1.0`
- `anthropic>=0.18.0` (AI 요약 기능 사용 시)

---

## 실행

### 기본 실행 (Interactive 모드)

```bash
claude-log-organizer
```

명령어 없이 실행하면 대화형 메뉴가 시작됩니다.

### CLI 명령어로 직접 실행

```bash
claude-log-organizer <command> [options]
```

사용 가능한 명령어: `init`, `watch`, `process`, `batch`, `clear`, `timeline`

---

## Interactive 모드

```
============================================================
Claude Log Organizer - Interactive Mode
============================================================

? 작업을 선택하세요
  1. Watch - 디렉토리 모니터링 시작
  2. Request AI - AI 요약 요청
  3. Exit - 종료
```

### 1. Watch — 디렉토리 모니터링

```
? 디렉토리 선택 방법
  1. Config - 설정 파일의 디렉토리 사용
  2. Manual - 직접 입력
  3. Back - 메인 메뉴로 돌아가기
```

- **Config**: `config.yaml`에 설정된 디렉토리를 감시
- **Manual**: 경로를 직접 입력하여 감시 (존재하지 않으면 생성 가능)

### 2. Request AI — AI 요약 요청

#### Step 1: 그룹화 방식 선택

```
? 그룹화 방식을 선택하세요
  1. Session - 세션 ID별 그룹화
  2. Date - 날짜 기반 그룹화
```

**Session 기반**: 동일 세션 ID로 그룹화된 task 파일들을 선택
**Date 기반**: 날짜 단위로 그룹화

#### Step 2: 날짜 그룹화 (Date 선택 시)

```
? 날짜 그룹화 방식을 선택하세요
  1. Daily - 특정 날짜의 모든 작업 요약
  2. Weekly - 주간 단위 요약
  3. Custom - 날짜 범위 직접 지정
```

- **Daily**: 특정 날짜 하나를 선택
- **Weekly**: 주간 범위 선택 (시작 요일은 `config.yaml`의 `summarization.weekly_start`로 설정)
- **Custom**: 시작/종료 날짜를 직접 입력

#### Step 3: 분석 타입 선택

```
? 분석 타입을 선택하세요
  1. 일반 요약 - 세션 작업 내용 요약
  2. 효율성 분석 - 프롬프트 효율성 + 개선 제안
  3. 타임라인 다이어그램 - 시간대별 작업 시각화 (.drawio)
```

| 분석 타입 | 설명 | 출력 |
|-----------|------|------|
| 일반 요약 | 세션/기간 작업 종합 요약 | `summaries/*_summary.md` |
| 효율성 분석 | 프롬프트 효율성 평가 + 개선 제안 | `summaries/*_efficiency.md` |
| 타임라인 다이어그램 | Gantt 차트 + 작업 흐름도 | `summaries/*_timeline.drawio` + `.md` |

#### Step 4: AI 방식 선택 (일반 요약/효율성 분석만 해당)

```
? AI 요약 방식을 선택하세요
  1. Claude Code CLI 사용 (추천)
  2. API 키 사용
```

- **Claude Code CLI**: `claude --print` 명령으로 실행 (별도 API 키 불필요)
- **API 키**: Anthropic API 키를 직접 입력 (config.yaml에 저장 가능)

---

## CLI 명령어

### `init` — 설정 파일 생성

```bash
claude-log-organizer init
claude-log-organizer init -o custom_config.yaml
```

### `watch` — 디렉토리 감시

```bash
claude-log-organizer watch
claude-log-organizer watch -c custom_config.yaml
```

`config.yaml`에 설정된 디렉토리를 실시간으로 감시하고, 새 `.log` 파일이 감지되면 자동으로 파싱하여 `task-*.md`를 생성합니다.

### `process` — 단일 파일 처리

```bash
claude-log-organizer process .claude/logs/2026-02-19_170012_abc123.log
```

### `batch` — 디렉토리 일괄 처리

```bash
claude-log-organizer batch .claude/logs/
claude-log-organizer batch .claude/logs/ --force   # 이미 처리된 파일도 재처리
```

### `clear` — 처리 이력 초기화

```bash
claude-log-organizer clear
```

`.processed.json`에 저장된 처리 이력을 삭제합니다.

### `timeline` — 타임라인 다이어그램 생성

```bash
claude-log-organizer timeline 2026-02-19
# -> summaries/daily-2026-02-19_timeline.drawio
# -> summaries/daily-2026-02-19_timeline.md
```

해당 날짜의 `task-*.md` 파일들을 읽어 `.drawio` 타임라인 다이어그램과 companion `.md` 파일을 생성합니다.

---

## Hook 설정

Claude Code의 Stop Hook으로 대화 종료 시 자동으로 JSONL 트랜스크립트를 `.log` 파일로 변환합니다.

### 1. 글로벌 Hook 등록

`~/.claude/settings.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "/path/to/save-conversation-log.sh"
          }
        ]
      }
    ]
  }
}
```

### 2. 프로젝트별 Hook 등록

`.claude/settings.local.json`:

```json
{
  "hooks": {
    "Stop": [
      {
        "hooks": [
          {
            "type": "command",
            "command": ".claude/hooks/save-conversation-log.sh"
          }
        ]
      }
    ]
  }
}
```

### 추출 태그

Hook 스크립트가 JSONL에서 추출하는 태그:

| 태그 | 출처 | 설명 |
|------|------|------|
| `[USER]` | user message | 사용자 입력 텍스트 |
| `[ASSISTANT]` | assistant message | 어시스턴트 응답 텍스트 |
| `[TOOL]` | assistant message | 도구 호출 (이름 + 주요 파라미터) |
| `[THINKING]` | assistant message | 사고 과정 (thinking block) |
| `[TOOL_RESULT]` | user message | 도구 실행 결과 (300자 제한) |
| `[DOCUMENT]` | user message | 첨부 문서 제목 |
| `[SNAPSHOT]` | file-history-snapshot | 파일 수정 스냅샷 (추적 파일 수) |
| `[COMPACT]` | system (compact_boundary) | 컨텍스트 압축 발생 지점 |

### 자동 처리 파이프라인

```
Claude Code 대화 종료
  → Stop Hook이 JSONL → .log 변환
  → watch 모드가 .log 감지
  → parser가 .log 파싱 → TaskData 생성
  → Jinja2 템플릿으로 task-*.md 생성
```

---

## 설정 파일 (config.yaml)

```yaml
watch:
  # 감시할 디렉토리 (절대 경로 또는 ~ 사용)
  directories:
    - ~/Desktop/workspace/project-a/.claude/logs
    - ~/Desktop/workspace/project-b/.claude/logs
  patterns:
    - '*.log'
  poll_interval: 1.0       # 폴링 주기 (초)
  recursive: false          # 하위 디렉토리 포함 여부
  debounce_delay: 3.0       # 파일 변경 후 대기 시간 (초)

output:
  directory: ./tasks                    # task 마크다운 출력 디렉토리
  summaries_directory: ./summaries      # AI 요약 및 타임라인 출력 디렉토리
  filename_pattern: task-{task_id}.md
  overwrite: false

parsing:
  extract_code_snippets: true
  max_snippet_lines: 50
  extract_phases: true
  extract_decisions: true
  extract_file_changes: true

templates:
  directory: ./templates
  default_template: default.md.jinja2

storage:
  processed_log: .processed.json    # 중복 처리 방지용 이력 파일
  enable_cache: true

logging:
  level: INFO                       # DEBUG, INFO, WARNING, ERROR
  file: organizer.log

summarization:
  weekly_start: monday              # 주간 요약 시작 요일 (monday 또는 sunday)
```

---

## 출력물

### 1. Task 마크다운 (`tasks/task-*.md`)

각 `.log` 파일당 하나씩 생성되는 구조화된 작업 요약:

```markdown
# Task Summary: 2026-02-19_170012_abc123

**Status**: Completed
**Timestamp**: 2026-02-19 17:00:12
**Duration**: 42분

---

## Summary
MeetingController 비교 분석 후 7개 버그 수정

## Implementation Details

### Files Modified
- `src/controller/MeetingController.java`
- `src/service/MeetingService.java`

### Key Technical Decisions
- 보고서 조회 방식을 단일 쿼리로 통합
- corpIdxWriter 기준으로 변경

### Thinking Process
- B2B와 PSA 컨트롤러 비교 분석 결정
- 서비스 레이어까지 추적 확인 필요

### Referenced Documents
- `API_SPEC.md`

**Context Compressions**: 2회
```

### 2. 타임라인 다이어그램 (`summaries/*_timeline.drawio`)

2페이지 구성의 draw.io 파일:

**Page 1: Timeline** — Gantt 차트 형태의 시간축 타임라인
- 각 세션을 시간 바로 표시
- 바 위에 작업 요약 표시

**Page 2: Process Flow** — 세션별 작업 흐름도
- 각 작업 단계가 유형별 색상/모양으로 구분

#### 단계 유형 (ProcessStep)

| 아이콘 | 유형 | 설명 | 스타일 |
|--------|------|------|--------|
| 🔍 | ANALYSIS | 코드 분석, 파일 탐색 | 파란색 둥근 사각형 |
| ⚡ | DECISION | 의사결정, 접근 방법 결정 | 노란색 육각형 |
| 🔧 | IMPLEMENTATION | 코드 작성, 수정 | 초록색 둥근 사각형 |
| ✅ | VERIFICATION | 테스트, 검증, 빌드 확인 | 보라색 점선 사각형 |
| 📋 | SUMMARY | 결과 정리, 요약 | 갈색 둥근 사각형 |

### 3. Companion 마크다운 (`summaries/*_timeline.md`)

타임라인 다이어그램의 상세 작업 과정:

```markdown
## Detailed Work Process

### Session `777c4ad7`

#### 15:42 - 16:24 | 로직상 이상한 부분이 있는지 확인

**Work process**:

1. ⚡ **[DECISION]** 두 컨트롤러를 비교 분석한 결과, 주요 이슈를 발견
2. ✅ **[VERIFICATION]** 서비스 레이어까지 추적해서 확인
3. 🔧 **[IMPLEMENTATION]** 7개 버그를 수정
   - B2B rejectMeeting 히스토리 enum 수정
   - PSA reRequestMeeting 권한 체크 수정
4. 📋 **[SUMMARY]** 수정 완료 요약
```

### 4. AI 요약 (`summaries/*_summary.md`)

AI가 생성한 세션/기간 종합 요약.

### 5. 효율성 분석 (`summaries/*_efficiency.md`)

프롬프트 효율성 평가 + 개선 제안.

---

## 중복 처리 방지

`.processed.json`에 파일별 SHA256 해시를 저장하여 동일 파일의 중복 처리를 방지합니다.

- 해시가 같으면 건너뜀
- 파일 내용이 변경되면 자동으로 다시 처리
- `--force` 옵션 또는 `clear` 명령으로 우회 가능

---

## 문제 해결

### 파일이 처리되지 않음

1. **파일 패턴 확인**: `config.yaml`의 `watch.patterns`이 대상 파일과 맞는지 확인
2. **이미 처리된 파일**: `claude-log-organizer clear` 또는 `--force` 사용
3. **로그 확인**: `tail -f organizer.log`

### Watch 모드가 감지하지 못함

1. **절대 경로 사용**: `config.yaml`의 `watch.directories`에 절대 경로 또는 `~` 사용
2. **디렉토리 존재 여부**: 감시 대상 디렉토리가 실제로 존재하는지 확인
3. **debounce 대기**: 파일 변경 후 `debounce_delay` (기본 3초) 만큼 대기

### 출력 파일이 생성되지 않음

1. **출력 디렉토리 확인**: `tasks/`, `summaries/` 디렉토리 존재 여부
2. **템플릿 확인**: `templates/default.md.jinja2` 존재 여부
3. **overwrite 설정**: 동일 파일이 있고 `output.overwrite: false`이면 건너뜀

### 로그 레벨 변경

```yaml
logging:
  level: DEBUG    # 상세 로그 출력
```

---

## 빠른 참조

| 작업 | 명령어 |
|------|--------|
| Interactive 모드 | `claude-log-organizer` |
| 설정 파일 생성 | `claude-log-organizer init` |
| 디렉토리 감시 | `claude-log-organizer watch` |
| 단일 파일 처리 | `claude-log-organizer process <file>` |
| 일괄 처리 | `claude-log-organizer batch <dir>` |
| 전체 재처리 | `claude-log-organizer batch <dir> --force` |
| 타임라인 생성 | `claude-log-organizer timeline 2026-02-19` |
| 처리 이력 초기화 | `claude-log-organizer clear` |
