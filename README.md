# Claude Log Organizer

Claude Code 대화 로그를 자동으로 수집하고, 구조화된 마크다운 요약 및 draw.io 타임라인 다이어그램을 생성하는 시스템.

## 동작 방식

```
Claude Code 대화 종료
       │
       ▼
┌─────────────────────┐     ┌────────────────────┐
│  JSONL Transcript    │────▶│  save-conversation  │
│  (.claude/projects/) │     │  -log.sh (Stop Hook)│
└─────────────────────┘     └────────┬───────────┘
                                     │ 증분 추출
                                     ▼
                            ┌────────────────────┐
                            │  .log 파일           │
                            │  (.claude/logs/)     │
                            └────────┬───────────┘
                                     │
                      ┌──────────────┼──────────────┐
                      ▼              ▼              ▼
              ┌──────────────┐ ┌──────────┐ ┌──────────────┐
              │ session_parser│ │ markdown │ │ timeline     │
              │              │ │ generator│ │ _diagram     │
              └──────┬───────┘ └────┬─────┘ └──────┬───────┘
                     ▼              ▼              ▼
              ┌──────────────┐ ┌──────────┐ ┌──────────────┐
              │ task-*.md    │ │ Jinja2   │ │ .drawio +    │
              │ (tasks/)     │ │ template │ │ companion .md│
              └──────────────┘ └──────────┘ │ (summaries/) │
                                            └──────────────┘
```

### 파이프라인 요약

1. **JSONL 수집** — Claude Code가 대화마다 자동 생성하는 JSONL 트랜스크립트
2. **Hook 변환** — `save-conversation-log.sh`(Stop Hook)가 JSONL에서 새 내용만 증분 추출하여 `.log` 파일로 변환
3. **파싱** — `session_parser.py`가 `.log`를 파싱하여 `TaskData` 모델로 변환
4. **출력 생성** — 마크다운 요약 (`task-*.md`) 및 타임라인 다이어그램 (`.drawio` + companion `.md`)

## 추출 태그

`.log` 파일에 기록되는 태그 목록:

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

## 타임라인 다이어그램

`timeline` 명령으로 일일 작업 타임라인을 생성합니다.

### 출력물

1. **`.drawio` 파일** (작업 수 + 1 페이지)
   - **Page 1: Timeline** — Gantt 차트 형태의 시간축 타임라인
   - **Page 2~N: 작업별 상세 페이지** — 각 작업(entry)마다 수직 플로우 다이어그램
     - 페이지 이름: 해당 작업의 초기 요청 내용
     - phase/step을 수직 화살표로 연결
     - Thinking 사고 과정 및 수정 파일 목록 포함

2. **Companion `.md` 파일** — 상세 작업 과정 마크다운

### 단계 유형 분류

각 작업 단계는 자동으로 5가지 유형으로 분류됩니다:

| 아이콘 | 유형 | 설명 | drawio 스타일 |
|--------|------|------|---------------|
| 🔍 | ANALYSIS | 코드 분석, 파일 탐색, 구조 파악 | 파란색 둥근 사각형 |
| ⚡ | DECISION | 의사결정, 문제 발견, 접근 방법 결정 | 노란색 육각형 |
| 🔧 | IMPLEMENTATION | 코드 작성, 수정, 파일 생성 | 초록색 둥근 사각형 |
| ✅ | VERIFICATION | 테스트, 검증, 빌드 확인 | 보라색 점선 사각형 |
| 📋 | SUMMARY | 결과 정리, 요약, 완료 보고 | 갈색 둥근 사각형 |

### Phase 요약 파이프라인

한 작업의 step이 8개를 초과하면 자동으로 phase 그룹화가 실행됩니다:

```
Step > 8개
   │
   ▼
Stage 1: 알고리즘 그룹화 (연속 동일 type 병합)
   │
   ├─ ≤ 8개 phase → 사용
   │
   ▼
Stage 2: AI 요약 (Claude CLI로 5~8개 phase로 그룹화)
   │
   ├─ 성공 → 캐시 저장 후 사용
   │
   ▼
Stage 3: 등분 청킹 (~6개 phase로 축소)
```

- **Stage 1**: 연속된 동일 type의 step을 하나의 phase로 병합
- **Stage 2**: Claude CLI(`claude --print`)로 AI 기반 의미 그룹화 (캐시: `summaries/.phase_cache.json`)
- **Stage 3**: AI 사용 불가 시 등분 분할로 ~6개 phase 생성

### Companion Markdown 예시

```markdown
## Detailed Work Process

### Session `777c4ad7`

#### 15:42 - 16:24 | 로직상 이상한 부분이 있는지 확인

**Work phases** (45 steps):

1. 🔍 **[ANALYSIS]** 프로젝트 구조 분석 (8 steps)
   *프로젝트 파일 구조와 관련 모듈을 분석하여 구현 방향을 파악*
   - cli.py, interactive.py 구조 확인
   - 기존 파서와 생성기 패턴 이해
2. ⚡ **[DECISION]** 구현 방식 결정 (5 steps)
   *draw.io XML 형식으로 타임라인 생성 방식 결정*
   - 추가 의존성 없이 xml.etree 사용
3. 🔧 **[IMPLEMENTATION]** 코드 구현 (28 steps)
   *TimelineEntry 모델과 다이어그램 생성기 구현*
   - timeline_diagram.py 신규 생성
   - CLI timeline 서브커맨드 추가
4. 📋 **[SUMMARY]** 결과 정리 (4 steps)
   *테스트 완료 후 결과 요약*
```

## 설치

```bash
cd claude_log
pip install -e .
```

> `pip install -e .` 실행 후 `command not found` 오류가 발생하면, 설치 시 출력된 경로 (예: `~/Library/Python/3.9/bin`)를 `~/.zshrc`에 추가하세요:
> ```bash
> export PATH="$HOME/Library/Python/3.9/bin:$PATH"
> ```

### 요구사항

- Python 3.8+
- pyyaml >= 6.0
- watchdog >= 3.0.0
- jinja2 >= 3.1.0
- python-dateutil >= 2.8.0
- inquirer >= 3.1.0
- anthropic >= 0.18.0 (AI 요약 기능 사용 시)

## 사용법

### 기본 실행 (Interactive 모드)

명령어 없이 실행하면 대화형 메뉴가 시작됩니다:

```bash
claude-log-organizer
```

```
============================================================
Claude Log Organizer - Interactive Mode
============================================================

? 작업을 선택하세요
  1. Watch - 디렉토리 모니터링 시작
  2. Request AI - AI 요약 요청
  3. Exit - 종료
```

Interactive 모드에서 Watch, AI 요약(세션별/날짜별), 효율성 분석, 타임라인 다이어그램 생성을 메뉴로 선택할 수 있습니다.

### CLI 명령어

```bash
claude-log-organizer init                          # 설정 파일 생성
claude-log-organizer watch                         # 디렉토리 감시 (실시간)
claude-log-organizer process <file>                # 단일 파일 처리
claude-log-organizer batch <dir>                   # 디렉토리 일괄 처리
claude-log-organizer batch <dir> --force           # 전체 재처리
claude-log-organizer timeline 2026-02-19           # 타임라인 다이어그램 생성
claude-log-organizer clear                         # 처리 이력 초기화
```

## Hook 설정

### Stop Hook (로그 저장 — 증분 방식)

`.claude/hooks/save-conversation-log.sh`가 대화 종료 시 JSONL에서 **새로운 내용만** 추출하여 `.log`로 변환합니다.

```
Stop 1회차 → 2026-02-26_150000_abc.log (JSONL 라인 1~50)
Stop 2회차 → 2026-02-26_153000_abc.log (JSONL 라인 51~80, 새 내용만)
Stop 3회차 → 새 라인 없으면 파일 미생성
```

세션별 처리 상태는 `.claude/logs/.state/SESSION_ID.lines`에 저장됩니다.

글로벌 설정 (`~/.claude/settings.json`):

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

### UserPromptSubmit Hook (컨텍스트 주입)

`.claude/hooks/start`가 매 프롬프트 제출 시 git 브랜치/상태 정보를 주입합니다.

## 프로젝트 구조

```
claude_log/
├── claude_log_organizer/
│   ├── cli.py                      # CLI 엔트리포인트 (기본: Interactive 모드)
│   ├── interactive.py              # Interactive CLI (메뉴 기반)
│   ├── config.py                   # 설정 관리
│   ├── main.py                     # 앱 오케스트레이터
│   ├── generators/
│   │   ├── markdown_generator.py   # Jinja2 마크다운 생성기
│   │   └── timeline_diagram.py     # draw.io 타임라인 + phase 요약 + companion md
│   ├── models/
│   │   └── task_data.py            # TaskData, TimelineEntry, ProcessPhase, ProcessStep
│   ├── parsers/
│   │   ├── base_parser.py          # 파서 베이스 클래스
│   │   ├── conversation_parser.py  # conversation-task-*.log 파서
│   │   ├── session_parser.py       # 세션 .log 파서 (태그 기반)
│   │   ├── parser_factory.py       # 파서 팩토리
│   │   └── timeline_parser.py      # 타임라인 로그 파서
│   ├── storage/
│   │   └── processed_tracker.py    # 처리 이력 추적
│   └── watcher/
│       ├── file_watcher.py         # 파일 감시
│       └── event_dispatcher.py     # 이벤트 디스패처
├── prompt_optimizer/               # 프롬프트 효율성 분석
├── templates/
│   └── default.md.jinja2           # task 마크다운 템플릿
├── .claude/
│   ├── hooks/
│   │   ├── save-conversation-log.sh  # Stop Hook (JSONL → .log)
│   │   ├── start                     # UserPromptSubmit Hook
│   │   └── stop                      # Project stop hook
│   └── settings.local.json           # 프로젝트 Hook 설정
├── tasks/                          # 생성된 task 마크다운
├── summaries/                      # 생성된 타임라인/요약 (.drawio + .md)
├── config.yaml                     # 실행 설정
├── setup.py
└── requirements.txt
```

## 설정 (config.yaml)

```yaml
watch:
  # 감시할 디렉토리 (절대 경로 또는 ~ 사용)
  directories:
    - ~/Desktop/workspace/project-a/.claude/logs
    - ~/Desktop/workspace/project-b/.claude/logs
  patterns:
    - '*.log'
  poll_interval: 1.0
  recursive: false

output:
  directory: ./tasks
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
  processed_log: .processed.json
  enable_cache: true

logging:
  level: INFO
  file: organizer.log

summarization:
  weekly_start: monday    # monday 또는 sunday
```

## 커스터마이징

### 템플릿 수정

`templates/default.md.jinja2`를 수정하여 task 마크다운 출력 형식을 변경할 수 있습니다.

사용 가능한 변수:
- `task.work_summary` — 작업 요약
- `task.files_modified` / `task.files_created` — 파일 변경 목록
- `task.key_decisions` — 주요 기술 결정
- `task.thinking_summary` — 사고 과정 요약
- `task.referenced_documents` — 참조 문서
- `task.metadata.compact_count` — 컨텍스트 압축 횟수

## License

MIT License
